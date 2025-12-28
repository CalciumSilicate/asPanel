# backend/services/mcdr_manager.py

import asyncio
import socketio
import re
import os
import gzip
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, TextIO, TYPE_CHECKING, Tuple

from backend.core.database import SessionLocal
from backend.core.constants import LOG_EMIT_INTERVAL_MS
from backend.core import crud, models, schemas
from backend.core.logger import logger

if TYPE_CHECKING:
    from backend.services.server_service import ServerService


class MCDRManager:
    _ansi_escape_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __init__(self, sio: socketio.AsyncServer = None):
        """MCDR 管理器

        日志系统增强：
        - 活动日志写入 `asp_logs/latest.log`
        - 当活动日志超过阈值自动轮转到 `asp_logs/archive/yyyymmdd-HHMMSS.log.gz`
        - 保留一定数量与天数的归档，自动清理过期归档
        - `get_historical_logs` 在不足行数时，自动补齐最近归档的末尾内容
        """
        self.processes: dict[int, asyncio.subprocess.Process] = {}
        self.return_code: dict[int, int] = {}
        self.java_pid: dict[int, int] = {}
        self.log_tasks: dict[int, asyncio.Task] = {}
        self.log_file_handles: dict[int, TextIO] = {}

        self.sio = sio
        self.save_all_method = None
        self.server_service: 'Optional[ServerService]' = None
        self.log_buffers: dict[int, List[str]] = {}
        self.log_emitter_tasks: dict[int, asyncio.Task] = {}
        self.LOG_EMIT_INTERVAL = LOG_EMIT_INTERVAL_MS / 1000

        # 日志轮转与归档策略（可调整）
        self.LOG_DIRNAME = 'asp_logs'
        self.ARCHIVE_DIRNAME = 'archive'
        self.ACTIVE_LOG_NAME = 'latest.log'
        # 单文件最大大小（字节），超过即轮转（默认 10MB）
        self.LOG_MAX_BYTES = 1024 * 1024
        # 归档最大保留数量（超过数量将按时间先后清理）
        self.LOG_RETENTION_COUNT = 20
        # 归档最大保留天数（超过天数将被清理），0 表示不按天数清理
        self.LOG_RETENTION_DAYS = 30

        # 外部状态覆盖（来自 aspanel_ws_reporter 插件）：pending / running 等
        # 键：server_id，值：状态字符串
        self.external_status: dict[int, str] = {}

    def set_external_status(self, server_id: int, status: str, return_code: Optional[int] = None) -> None:
        """设置来自插件事件的外部状态，并可选更新 return_code。"""
        if status:
            self.external_status[server_id] = status
        if return_code is not None:
            self.return_code[server_id] = int(return_code)

    def clear_external_status(self, server_id: int) -> None:
        self.external_status.pop(server_id, None)

    def set_server_service(self, service: 'ServerService'):
        self.server_service = service

    async def _notify_server_update(self, server_id: int):
        if not self.sio or not self.server_service:
            logger.warning("SIO 或 ServerService 未就绪，跳过状态通知")
            return

        try:
            with SessionLocal() as db:
                server_details = await self.server_service.get_server_details_by_id(server_id, db)
                await self.sio.emit(
                    'server_status_update',
                    server_details.model_dump(mode='json')
                )
                await self.sio.emit(
                    'status_update',
                    {'status': server_details.status},
                    room=f'server_console_{server_id}'
                )
        except Exception as e:
            logger.error(f"通知服务器 {server_id} 状态更新时出错：{e}")

    # [新增] 定时批量发送日志的后台任务
    async def _emit_log_batch_periodically(self, server_id: int):
        """
        每隔 LOG_EMIT_INTERVAL 秒检查一次缓冲区，并批量发送日志。
        """
        while True:
            await asyncio.sleep(self.LOG_EMIT_INTERVAL)

            # 从缓冲区获取日志，并立即清空，准备下一次收集
            buffer = self.log_buffers.get(server_id)
            if buffer and len(buffer) > 0:
                # 制作副本以发送，并清空原始缓冲区
                batch_to_send = list(buffer)
                buffer.clear()

                if self.sio:
                    await self.sio.emit(
                        'console_log_batch',  # 使用新的事件名
                        {'logs': batch_to_send},
                        room=f'server_console_{server_id}'
                    )

    async def _monitor_and_notify_on_exit(self, server_id: int, process: asyncio.subprocess.Process):
        await process.wait()
        logger.info(f"[MCDR] 服务器 {server_id} (PID: {process.pid}) 已退出 (code={process.returncode})")

        # [修改] 停止并清理日志发送器任务，并进行最后一次日志刷新
        if server_id in self.log_emitter_tasks:
            self.log_emitter_tasks.pop(server_id).cancel()

        # 刷新缓冲区中剩余的任何日志
        if buffer := self.log_buffers.pop(server_id, None):
            if buffer and self.sio:
                await self.sio.emit('console_log_batch', {'logs': buffer}, room=f'server_console_{server_id}')

        # 清理其他资源
        self.processes.pop(server_id, None)
        self.java_pid.pop(server_id, None)
        if server_id in self.log_tasks:
            self.log_tasks.pop(server_id).cancel()
        if log_file := self.log_file_handles.pop(server_id, None):
            log_file.close()

        # 清理外部状态覆盖，回退到常规判定逻辑
        self.external_status.pop(server_id, None)

        await self._notify_server_update(server_id)

    async def notify_server_list_update(
            self, server: models.Server = None, server_details: schemas.ServerDetail = None,
            is_adding: bool = True
    ):
        if not self.sio or not self.server_service:
            logger.warning("SIO 或 ServerService 未就绪，跳过服务器列表通知")
            return

        logger.info("广播服务器列表更新通知")
        try:
            with SessionLocal() as db:
                if server_details is None and server.id is not None:
                    server_details = await self.server_service.get_server_details_by_id(server.id, db)
                else:
                    server_details = None
                await self.sio.emit(
                    'server_create' if is_adding else 'server_delete',
                    server_details.model_dump(mode='json') if server_details is not None else None
                )
        except Exception as e:
            logger.error(f"服务器 {server.id} 列表更新通知失败：{e}")

    def _clean_log_line(self, line: str) -> Optional[str]:
        # ... (此方法无变化)
        cleaned_line = self._ansi_escape_pattern.sub('', line)
        stripped_line = cleaned_line.strip()
        if stripped_line == '>':
            return None
        return stripped_line if stripped_line else None

    async def _read_logs(self, server: models.Server, process: asyncio.subprocess.Process):
        streams = [process.stdout, process.stderr]
        while process.returncode is None:
            tasks = [asyncio.create_task(s.readline()) for s in streams]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for future in done:
                try:
                    line_bytes = future.result()
                    if not line_bytes:
                        continue
                    raw_line = line_bytes.decode('utf-8', errors='ignore')
                    cleaned_line = self._clean_log_line(raw_line)
                    if cleaned_line:
                        # 每次写入前动态获取最新的文件句柄，避免轮转后句柄失效
                        log_file = self.log_file_handles.get(server.id)
                        if log_file:
                            try:
                                log_file.write(cleaned_line + "\n")
                                log_file.flush()
                                # 每次写入后检查是否需要轮转
                                self._rotate_log_if_needed(server)
                            except Exception as e:
                                logger.error(f"写入 SERVER {server.id} 日志文件失败：{e}")

                        if server.id not in self.java_pid and "Server is running at PID" in cleaned_line:
                            self.return_code.pop(server.id, None)
                            self.java_pid[server.id] = int(cleaned_line.split()[-1])

                        if server.id not in self.java_pid and "服务端正在以 PID" in cleaned_line:
                            self.return_code.pop(server.id, None)
                            self.java_pid[server.id] = int(cleaned_line.split()[-2])

                        if server.id in self.processes and "Server process stopped with code" in cleaned_line:
                            self.return_code[server.id] = int(cleaned_line.split()[-1])

                        # [修改] 不再直接发送，而是添加到缓冲区
                        if server.id in self.log_buffers:
                            self.log_buffers[server.id].append(cleaned_line)

                except Exception as e:
                    logger.error(f"读取 SERVER {server.id} 日志时出错：{e}")
                    break

            for future in pending: future.cancel()
            if process.returncode is not None: break

        logger.info(f"SERVER {server.id} 日志读取结束")
        if self.sio:
            await self.sio.emit('status_update', {'status': 'stopped'}, room=f'server_console_{server.id}')

    @staticmethod
    async def initialize_server_files(server: models.Server) -> tuple[bool, str]:
        # ... (此方法无变化)
        try:
            server_path: Path = Path(server.path)
            if not server_path.is_dir():
                return False, f"Server path {server_path} does not exist."

            # 解析系统设置中的 venv，推导 python 可执行路径
            py_exec = MCDRManager._resolve_python_executable(server_path)

            logger.info(f"在 {server_path} 执行初始化命令：{py_exec} -m mcdreforged init")
            process = await asyncio.create_subprocess_exec(
                py_exec, '-m', 'mcdreforged', 'init',
                cwd=str(server_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output_log = stdout.decode('utf-8', 'ignore').strip()
            error_log = stderr.decode('utf-8', 'ignore').strip()
            full_log = (output_log + "\n" + error_log).strip()

            if process.returncode == 0:
                logger.info(f"服务器 {server_path} 初始化成功")
                eula_path = server_path / 'server' / 'eula.txt'
                eula_path.parent.mkdir(exist_ok=True)
                with open(eula_path, 'w', encoding='utf-8') as f:
                    f.write("eula=true")
                return True, f"Successful initialization.\n{full_log}"
            else:
                logger.error(f"服务器 {server_path} 初始化失败，返回码：{process.returncode}")
                return False, f"Fail initialization, return code: {process.returncode}\n{full_log}"

        except Exception as e:
            return False, f"An unexpected error occurred during initialization: {e}"

    @staticmethod
    def _resolve_python_executable(server_path: Path) -> str:
        """
        根据系统设置推导 python 可执行路径：
        - 若设置了 python_executable：
          - 绝对路径：直接使用
          - 相对路径：相对于 server_path 解析
        - 若未设置或不可用：尝试 server_path/.venv/bin/python
        - 最后回退 'python'
        """
        try:
            with SessionLocal() as db:
                settings = crud.get_system_settings_data(db)
        except Exception:
            settings = {}
        try:
            py_cfg = (settings or {}).get('python_executable')
            if py_cfg:
                p = Path(py_cfg)
                if not p.is_absolute():
                    p = (server_path / p).resolve()
                if p.exists():
                    return str(p)
            guess = (server_path / '.venv' / 'bin' / 'python')
            if guess.exists():
                return str(guess)
        except Exception:
            pass
        return 'python'

    async def start(self, server: models.Server) -> tuple[bool, str]:
        server_path = Path(server.path)
        if server.id in self.processes and self.processes[server.id].returncode is None:
            return False, "server is already running"

        try:
            log_dir = Path(server_path) / self.LOG_DIRNAME
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file_path = log_dir / self.ACTIVE_LOG_NAME
            # 如果启动前 active log 已超过阈值，先归档再创建
            if log_file_path.exists() and log_file_path.stat().st_size >= self.LOG_MAX_BYTES:
                try:
                    # 先临时打开以确保存在，再做轮转
                    self.log_file_handles[server.id] = open(log_file_path, 'a', encoding='utf-8')
                    self._archive_and_reopen(server)
                except Exception as e:
                    logger.warning(f"SERVER {server.id} 预启动日志轮转失败：{e}")
                    # 回退：若轮转失败，仍尝试继续
                    self.log_file_handles[server.id] = open(log_file_path, 'a', encoding='utf-8')
            else:
                self.log_file_handles[server.id] = open(log_file_path, 'a', encoding='utf-8')
        except OSError as e:
            return False, f"Failed to open log file: {e}"

        # 解析 python 可执行文件（遵循系统设置 venv）
        py_exec = MCDRManager._resolve_python_executable(server_path)

        process = await asyncio.create_subprocess_exec(
            py_exec, '-m', 'mcdreforged',
            cwd=server_path, stdout=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        self.return_code.pop(server.id, None)
        self.processes[server.id] = process
        self.log_tasks[server.id] = asyncio.create_task(self._read_logs(server, process))
        logger.info(f"SERVER {server.id} 的 MCDR 进程已启动，PID={process.pid}")

        # [修改] 初始化日志缓冲区并启动定时发送任务
        self.log_buffers[server.id] = []
        self.log_emitter_tasks[server.id] = asyncio.create_task(self._emit_log_batch_periodically(server.id))

        # [新增] 立即设置外部状态为启动中，并广播一次，保证前端第一时间看到“启动中”
        try:
            self.set_external_status(server.id, 'pending')
            asyncio.create_task(self._notify_server_update(server.id))
        except Exception as e:
            logger.warning(f"设置 SERVER {server.id} 的 pending 状态失败：{e}")

        asyncio.create_task(self._notify_server_update(server.id))
        asyncio.create_task(self._monitor_and_notify_on_exit(server.id, process))

        return True, str(process.pid)

    async def get_status(self, server_id: int, server_path: str) -> Tuple[schemas.ServerStatus, int]:
        is_new_setup = False
        server_dir_path = Path(server_path) / 'server'
        if not server_dir_path.exists():
            is_new_setup = True
        else:
            try:
                contents = [item.name for item in server_dir_path.iterdir()]
                if len(contents) <= 1 and 'eula.txt' in contents:
                    is_new_setup = True
                elif len(contents) <= 1 and 'mods' in contents:
                    is_new_setup = True
                elif len(contents) == 2 and contents == ['mods', 'eula.txt']:
                    is_new_setup = True
            
            except OSError as e:
                logger.error(f"无法读取目录 {server_path}：{e}")
                is_new_setup = False

        if is_new_setup:
            return schemas.ServerStatus.NEW_SETUP, 0

        # 优先使用外部状态覆盖（来自插件）
        ext = self.external_status.get(server_id)
        if ext == 'pending':
            return schemas.ServerStatus.PENDING, 0
        if ext == 'running':
            return schemas.ServerStatus.RUNNING, 0

        return_code = self.return_code.get(server_id, None)
        if server_id in self.processes:
            if return_code is None:
                return schemas.ServerStatus.RUNNING, 0
        if server_id not in self.processes and return_code not in [None, 0]:
            return schemas.ServerStatus.ERROR, return_code

        return schemas.ServerStatus.STOPPED, 0

    # ... stop, restart, send_command, get_historical_logs, force_kill 方法无变化 ...
    async def stop(self, server: models.Server) -> tuple[bool, str]:
        process = self.processes.get(server.id)
        if not process or process.returncode is not None:
            asyncio.create_task(self._notify_server_update(server.id))
            return True, "Server was already stopped."
        try:
            process.stdin.write(b'stop\n')
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            logger.warning(f"SERVER {server.id} 的标准输入管道已关闭")
        return True, "Stop command sent."

    async def restart(self, server: models.Server, server_path: str) -> tuple[bool, str]:
        logger.info(f"正在重启 SERVER {server.id} ...")
        await self.stop(server)
        await asyncio.sleep(2)

        process = self.processes.get(server.id)
        if process and process.returncode is None:
            await process.wait()

        logger.info(f"SERVER {server.id} 开始启动阶段 ...")
        return await self.start(server)

    async def send_command(self, server: models.Server, command: str):
        process = self.processes.get(server.id)
        if process and process.returncode is None:
            process.stdin.write((command + '\n').encode('utf-8'))
            await process.stdin.drain()

    async def save_all(self, server: models.Server):
        await self.save_all_method(server.name)

    async def start_for_a_while(self, server: models.Server, delay: int = 3):
        await self.start(server)
        await asyncio.sleep(delay)
        await self.force_kill(server)

    def get_historical_logs(self, server: models.Server, line_limit: int = 200) -> List[str]:
        server_path = Path(server.path)
        log_file_path = server_path / self.LOG_DIRNAME / self.ACTIVE_LOG_NAME

        if not log_file_path.is_file():
            return []
        try:
            # 读取活动日志的末尾
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
            last_lines = all_lines[-line_limit:]
            cleaned_logs: List[str] = []
            for line in last_lines:
                cleaned_line = self._clean_log_line(line.strip())
                if cleaned_line:
                    cleaned_logs.append(cleaned_line)

            # 若不足 line_limit，则尝试从最近归档补齐
            if len(cleaned_logs) < line_limit:
                need = line_limit - len(cleaned_logs)
                archive_dir = (server_path / self.LOG_DIRNAME / self.ARCHIVE_DIRNAME)
                if archive_dir.is_dir():
                    # 按修改时间逆序取最近的一个归档文件
                    cand = sorted(
                        [p for p in archive_dir.iterdir() if p.is_file() and (p.suffix in ['.gz', '.log'])],
                        key=lambda p: p.stat().st_mtime,
                        reverse=True
                    )
                    if cand:
                        latest_archive = cand[0]
                        try:
                            if latest_archive.suffix == '.gz':
                                with gzip.open(latest_archive, 'rt', encoding='utf-8', errors='ignore') as af:
                                    a_lines = af.readlines()
                            else:
                                with open(latest_archive, 'r', encoding='utf-8', errors='ignore') as af:
                                    a_lines = af.readlines()
                            a_tail = a_lines[-need:]
                            a_cleaned: List[str] = []
                            for line in a_tail:
                                cl = self._clean_log_line(line.strip())
                                if cl:
                                    a_cleaned.append(cl)
                            cleaned_logs = a_cleaned + cleaned_logs
                        except Exception as e:
                            logger.error(f"读取归档日志失败（路径：{server_path}）：{e}")

            return cleaned_logs
        except Exception as e:
            logger.error(f"读取历史日志失败（路径：{server_path}）：{e}")
            return []

    async def force_kill(self, server: models.Server) -> tuple[bool, str]:
        java_pid = self.java_pid.get(server.id)
        mcdr_process = self.processes.get(server.id)
        message = ""
        try:
            if java_pid and psutil.pid_exists(java_pid):
                psutil.Process(java_pid).kill()
                message += f"Killed java process {java_pid}. "
            if mcdr_process and mcdr_process.returncode is None:
                mcdr_process.kill()
                message += f"Killed MCDR process {mcdr_process.pid}."
            success = True
        except psutil.NoSuchProcess:
            message = "Process already gone."
            success = True
        except psutil.AccessDenied:
            message = "Access denied to kill process."
            success = False
        except Exception as e:
            message = f"Error during force-kill: {e}"
            success = False
        return success, message

    # ========== 以下为日志轮转与归档的内部实现 ==========
    def _rotate_log_if_needed(self, server: models.Server):
        """检查活动日志大小，超过阈值时触发归档轮转。

        - 关闭当前 `latest.log`
        - 移动为 `archive/<timestamp>.log.gz`
        - 重新打开新的 `latest.log`
        - 执行归档清理策略
        """
        handle = self.log_file_handles.get(server.id)
        if not handle:
            return
        try:
            handle.flush()
            path = Path(server.path) / self.LOG_DIRNAME / self.ACTIVE_LOG_NAME
            # 若文件不存在（例如被外部移动），直接重开
            if not path.exists():
                try:
                    self.log_file_handles[server.id] = open(path, 'a', encoding='utf-8')
                except Exception as e:
                    logger.error(f"重新打开活动日志失败（SERVER {server.id}）：{e}")
                return
            size = path.stat().st_size
            if size >= self.LOG_MAX_BYTES:
                self._archive_and_reopen(server)
        except Exception as e:
            logger.error(f"日志轮转检查出错（SERVER {server.id}）：{e}")

    def _archive_and_reopen(self, server: models.Server):
        """将当前活动日志归档并压缩，并重新打开新的活动日志。"""
        try:
            base_dir = Path(server.path) / self.LOG_DIRNAME
            active_path = base_dir / self.ACTIVE_LOG_NAME
            archive_dir = base_dir / self.ARCHIVE_DIRNAME
            archive_dir.mkdir(parents=True, exist_ok=True)

            # 关闭当前句柄
            handle = self.log_file_handles.get(server.id)
            if handle and not handle.closed:
                try:
                    handle.flush()
                except Exception:
                    pass
                handle.close()

            # 归档文件名：yyyymmdd-HHMMSS.log.gz
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            dst_plain = archive_dir / f"{ts}.log"
            dst_gz = archive_dir / f"{ts}.log.gz"

            # 移动并压缩
            if active_path.exists():
                try:
                    os.replace(active_path, dst_plain)
                except Exception as e:
                    logger.error(f"移动活动日志到归档失败（SERVER {server.id}）：{e}")
                    # 若移动失败，尝试复制退而求其次
                    try:
                        with open(active_path, 'rb') as src, open(dst_plain, 'wb') as dst:
                            dst.write(src.read())
                        # 清空原文件
                        open(active_path, 'w').close()
                    except Exception as e2:
                        logger.error(f"复制活动日志以归档失败（SERVER {server.id}）：{e2}")

            try:
                if dst_plain.exists():
                    with open(dst_plain, 'rb') as f_in, gzip.open(dst_gz, 'wb') as f_out:
                        while True:
                            chunk = f_in.read(1024 * 1024)
                            if not chunk:
                                break
                            f_out.write(chunk)
                    # 压缩完成后删除未压缩归档
                    try:
                        dst_plain.unlink(missing_ok=True)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"压缩归档日志失败（SERVER {server.id}）：{e}")

            # 重新打开新的活动日志
            try:
                self.log_file_handles[server.id] = open(active_path, 'a', encoding='utf-8')
            except Exception as e:
                logger.error(f"重新打开活动日志失败（SERVER {server.id}）：{e}")

            # 清理归档
            self._prune_archives(archive_dir)
        except Exception as e:
            logger.error(f"归档与重开日志过程出现异常（SERVER {server.id}）：{e}")

    def _prune_archives(self, archive_dir: Path):
        """按照数量与天数清理归档文件。"""
        try:
            if not archive_dir.is_dir():
                return
            files = [p for p in archive_dir.iterdir() if p.is_file()]
            # 先按时间排序（新->旧）
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # 数量控制
            if self.LOG_RETENTION_COUNT and len(files) > self.LOG_RETENTION_COUNT:
                for p in files[self.LOG_RETENTION_COUNT:]:
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        pass

            # 天数控制
            if self.LOG_RETENTION_DAYS and self.LOG_RETENTION_DAYS > 0:
                expire_before = datetime.now() - timedelta(days=self.LOG_RETENTION_DAYS)
                for p in archive_dir.iterdir():
                    try:
                        if datetime.fromtimestamp(p.stat().st_mtime) < expire_before:
                            p.unlink(missing_ok=True)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"清理归档失败（目录：{archive_dir}）：{e}")
