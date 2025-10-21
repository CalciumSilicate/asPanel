# tasks/background.py
import asyncio
import textwrap
import time
import uuid
import zipfile
import subprocess
from http.client import HTTPException

import requests
import shutil
import os

from sqlalchemy.orm import Session
from typing import Dict, Optional
from pathlib import Path

from backend import crud, server_parser, models
from backend.core.api import get_velocity_version_detail, get_fabric_version_meta
from backend.core.config import FABRIC_REPO_URL, TEMP_PATH
from backend.core.utils import get_file_sha1, get_file_sha256
from backend.database import get_db_context
from backend.schemas import TaskStatus, ArchiveCreate, ArchiveType, PaperBuild, Task, PaperBuildDownload, Server
from backend.dependencies import task_manager, archive_manager, mcdr_manager


def download_file(dest_path: Path, download_url: str, task: Task = None, start: float = 0, end: float = 100):
    with get_db_context() as db:
        if db is not None:
            if (file := crud.get_download_file_by_url(db, download_url)) is not None:
                file: models.Download
                if Path(file.path).exists():
                    os.makedirs(dest_path.parent, exist_ok=True)
                    shutil.copy2(file.path, dest_path)
                    task.progress = round(end, 2)
                    return
                else:
                    crud.delete_download_file(db, file.id)
    with get_db_context() as db:
        os.makedirs(dest_path.parent, exist_ok=True)
        with requests.get(download_url, stream=True, timeout=300) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            downloaded_size = 0
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    if task is not None and total_size > 0:
                        task.progress = round(start + (downloaded_size / total_size) * (end - start), 2)
            if db is not None:
                file_name = dest_path.stem + '_' + uuid.uuid4().hex + dest_path.suffix
                file_path = TEMP_PATH / file_name
                os.makedirs(file_path.parent, exist_ok=True)
                shutil.copy2(dest_path, file_path)
                crud.create_download_file(db, download_url, str(file_path), dest_path.name)


def background_download_jar(url: str, dest_path: Path, task: Task, sha1: str = None,
                            sha256: str = None):
    task.status = TaskStatus.RUNNING
    try:
        download_file(dest_path, url, task)
        if sha1 and get_file_sha1(dest_path) != sha1:
            raise ValueError(f"SHA1 mismatch! Expected {sha1}")
        if sha256 and get_file_sha256(dest_path) != sha256:
            raise ValueError(f"SHA256 mismatch! Expected {sha256}")
        task.status = TaskStatus.SUCCESS
        task.progress = 100.0
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        if dest_path.exists():
            os.remove(dest_path)


def background_install_fabric(loader_meta: Dict, server_path: Path, vanilla_core_version: str,
                              fabric_loader_version: str,
                                    task: Task):
    task.status = TaskStatus.RUNNING
    libraries_path = server_path / 'libraries'
    launcher_jar_path = server_path / 'fabric-server-launch.jar'
    try:
        libraries_to_download = (loader_meta['launcherMeta']['libraries']['common'] +
                                 loader_meta['launcherMeta']['libraries']['server'])
        libraries_to_download.append(loader_meta['intermediary'])
        libraries_to_download.append(loader_meta['loader'])
        os.makedirs(libraries_path, exist_ok=True)
        total_libs = len(libraries_to_download)
        classpath_entries = []
        for i, lib in enumerate(libraries_to_download):
            lib_name = lib.get('name', lib.get('maven', None))
            if lib_name is None:
                continue
            group, artifact, version = lib_name.split(':')
            group_path = group.replace('.', '/')
            file_name = f"{artifact}-{version}.jar"
            file_path = libraries_path / group_path / artifact / version / file_name
            relative_path = Path('libraries') / group_path / artifact / version / file_name
            download_url = f"{FABRIC_REPO_URL}{group_path}/{artifact}/{version}/{file_name}"
            download_file(file_path, download_url, task, i / total_libs * 100, (i + 1) / total_libs * 100)
            classpath_entries.append(str(relative_path))

        server_main_class = (loader_meta.get('launcherMeta', {}).get('mainClass', {}).
                             get('server', 'net.fabricmc.loader.launch.knot.KnotServer'))
        _create_fabric_launcher_jar(server_path, server_main_class, classpath_entries)
        task.status = TaskStatus.SUCCESS
        task.progress = 100.0

    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        if libraries_path.exists():
            shutil.rmtree(libraries_path)
        if launcher_jar_path.exists():
            os.remove(launcher_jar_path)
        raise e


def background_install_forge(installer_meta: Dict, server_path: Path, java_command: str, task: Task):
    task.status = TaskStatus.RUNNING
    installer_url: Optional[str] = installer_meta.get("installer_url")
    if not installer_url:
        task.status = TaskStatus.FAILED
        task.error = "缺少 Forge 安装器下载地址"
        raise ValueError("Missing installer_url in Forge metadata")
    installer_name = installer_meta.get("installer_name") or os.path.basename(installer_url)
    installer_path = server_path / installer_name
    try:
        download_file(installer_path, installer_url, task, 0, 70)
        expected_sha1 = installer_meta.get("installer_sha1")
        if expected_sha1 and get_file_sha1(installer_path) != expected_sha1:
            raise ValueError("Forge installer SHA1 mismatch")
        task.progress = 80.0
        cmd = [java_command or 'java', '-jar', installer_name, '--installServer']
        proc = subprocess.run(cmd, cwd=server_path, capture_output=True, text=True)
        if proc.returncode != 0:
            stderr = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"Forge installer exited with code {proc.returncode}: {stderr}")
        try:
            installer_path.unlink(missing_ok=True)
        except AttributeError:
            # Python <3.8 fallback
            try:
                if installer_path.exists():
                    os.remove(installer_path)
            except Exception:
                pass
        task.progress = 100.0
        task.status = TaskStatus.SUCCESS
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        raise e


def _create_fabric_launcher_jar(server_path, server_main_class, classpath_entries):
    launcher_jar_path = os.path.join(server_path, 'fabric-server-launch.jar')
    properties_content = f"launch.mainClass={server_main_class}\n"
    manifest_lines = [
        "Manifest-Version: 1.0",
        "Main-Class: net.fabricmc.loader.impl.launch.server.FabricServerLauncher"
    ]

    # Class-Path 应该包含原版核心和所有库
    classpath_string = " ".join(classpath_entries)
    _ = ""
    for i, ch in enumerate(classpath_string):
        if i == 0:
            _ += "Class-Path: "
        elif len(_) == 0:
            _ += " "
        _ += ch
        if len(_) >= 72:
            manifest_lines.append(_)
            _ = ""
        if i == len(classpath_string) - 1:
            manifest_lines.append(_)
            break

    manifest_content = "\n".join(manifest_lines) + "\n\n"

    with zipfile.ZipFile(launcher_jar_path, 'w') as zf:
        zf.writestr('fabric-server-launch.properties', properties_content.encode('utf-8'))
        zf.writestr('META-INF/MANIFEST.MF', manifest_content.encode('utf-8'))


def background_create_archive(db: Session, server_id: int, task: Task):
    try:
        db_server = crud.get_server_by_id(db, server_id)
        server = Server.model_validate(db_server)
        if not db_server:
            raise FileNotFoundError("源服务器不存在")

        server_path = Path(db_server.path)
        if server.core_config.server_type in ['velocity', 'bungeecord']:
            raise TypeError("该服务器类型不支持此操作")

        properties_path = server_path / "server" / "server.properties"

        if not properties_path.is_file():
            raise FileNotFoundError(f"服务器 '{db_server.name}' 尚未配置或启动，找不到 server.properties 文件。")

        properties_dict = server_parser.parse_properties(str(properties_path))
        world_name = properties_dict.get('level-name', 'world')
        source_world_path = server_path / "server" / world_name
        if not source_world_path.is_dir():
            raise FileNotFoundError(
                f"服务器 '{db_server.name}' 的世界文件夹 '{source_world_path.name}' 不存在。请先启动一次服务器以生成世界。")
        archive_name = f"{db_server.name}_{world_name}"
        task.status = TaskStatus.RUNNING
        task.progress = 50
        task.message = f"正在打包服务器 '{db_server.name}' 的世界 '{world_name}'..."
        tar_path = archive_manager.create_tar_from_server_world(db_server.path, world_name, task.id)  # 假设它不接收task_id
        task.progress = 90
        task.message = "正在写入数据库..."

        archive_schema = ArchiveCreate(
            name=archive_name,
            type=ArchiveType.SERVER,
            source_server_id=server_id,
            filename=tar_path.name,
            path=str(tar_path)
        )
        crud.create_archive(db, archive_schema)
        task.status = TaskStatus.SUCCESS
        task.progress = 100
        task.message = f"服务器 '{db_server.name}' 的世界 '{world_name}' 存档创建成功！"
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        raise e
    finally:
        task_manager.clear_finished_task(task.id)


def background_process_upload(db: Session, file_path: Path, archive_name: str, mc_version: str, task: Task):
    task.status = TaskStatus.RUNNING
    try:
        final_path = archive_manager.process_uploaded_archive(file_path, archive_name)
        archive_schema = ArchiveCreate(
            name=archive_name,
            type=ArchiveType.UPLOADED,
            mc_version=mc_version,
            filename=final_path.name,
            path=str(final_path)
        )
        crud.create_archive(db, archive_schema)
        task.status = TaskStatus.SUCCESS
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
    finally:
        task_manager.clear_finished_task(task.id)


async def background_restore_archive(db: Session, archive_id: int, target_server_id: int, task: Task):
    temp_unpack_dir = None
    try:
        db_archive = crud.get_archive_by_id(db, archive_id)
        db_server = crud.get_server_by_id(db, target_server_id)
        if (await mcdr_manager.get_status(server_id=db_server.id, server_path=db_server.path))[0] == "running":
            await mcdr_manager.stop(server_id=target_server_id)
        if not db_archive or not db_server:
            raise FileNotFoundError("源存档或目标服务器未找到。")
        task.status = TaskStatus.RUNNING
        task.progress = 10
        task.message = f"准备恢复存档 '{db_archive.name}' 到服务器 '{db_server.name}'..."
        target_server_path = Path(db_server.path)
        target_mc_server_dir = target_server_path / "server"
        target_mc_server_dir.mkdir(exist_ok=True)

        # 步骤 1: 解析目标服务器的 server.properties 以找到世界名称
        properties_path = target_mc_server_dir / "server.properties"
        world_name = "world"  # 默认世界名
        if properties_path.exists():
            properties = server_parser.parse_properties(str(properties_path))
            world_name = properties.get('level-name', 'world')
        target_world_path = target_mc_server_dir / world_name
        # --- [修改] 步骤 2: 使用滚动备份策略 ---
        task.progress = 30
        task.message = f"正在备份当前世界 '{world_name}'..."
        if target_world_path.exists() and target_world_path.is_dir():
            # 定义固定的备份名称，例如 "world_backup_last"
            backup_name = f"{world_name}_backup_last"
            backup_path = target_world_path.with_name(backup_name)
            # 如果上一次的备份已经存在，则先删除它
            if backup_path.exists():
                task.message = f"正在删除旧的备份 '{backup_name}'..."
                shutil.rmtree(backup_path)  # rmtree 可以删除整个目录树
            # 将当前世界文件夹重命名为备份文件夹
            task.message = f"正在将当前世界备份为 '{backup_name}'..."
            shutil.move(str(target_world_path), str(backup_path))
            task.message = f"当前世界已成功备份为 '{backup_name}'。"
        else:
            # 如果路径存在但不是目录，也删除它
            if target_world_path.exists():
                target_world_path.unlink()
            task.message = "当前世界不存在或无效，跳过备份。"
        # 步骤 3: 恢复存档
        task.progress = 60
        source_archive_path = Path(db_archive.path)
        if db_archive.type.value == ArchiveType.UPLOADED.value:
            task.message = f"正在复制上传的存档到 '{world_name}'..."
            shutil.copytree(str(source_archive_path), str(target_world_path))
        elif db_archive.type.value == ArchiveType.SERVER.value:
            task.message = "正在解压服务器存档..."
            temp_unpack_dir = target_mc_server_dir / f"temp_unpack_{task.id}"
            temp_unpack_dir.mkdir()
            shutil.unpack_archive(str(source_archive_path), str(temp_unpack_dir))

            task.message = "正在查找世界数据..."
            unpacked_world_path = None
            for item in temp_unpack_dir.iterdir():
                if item.is_dir() and (item / 'level.dat').is_file():
                    unpacked_world_path = item
                    break
            if not unpacked_world_path:
                raise FileNotFoundError("在解压的存档中未能找到有效的世界文件夹 (缺少 level.dat)。")

            task.message = f"正在恢复世界到 '{world_name}'..."
            shutil.move(str(unpacked_world_path), str(target_world_path))

        task.progress = 100
        task.status = TaskStatus.SUCCESS
        task.message = f"存档 '{db_archive.name}' 已成功恢复到服务器 '{db_server.name}'！"
        # 根据服务器原始状态决定是启动还是重启
        # 注意: 之前的状态检查应该保存下来，但为了简化，这里重新检查
        # 更好的做法是在函数开头保存 status = (await mcdr_manager.get_status(...))[1]
        # 但考虑到停止服务器后状态必然是 'stopped'，所以直接启动即可。
        task.message = "正在启动服务器..."
        await mcdr_manager.start(db_server)
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        # 可以在这里添加逻辑，如果恢复失败，尝试恢复刚才的备份
    finally:
        # 确保清理临时解压目录
        if temp_unpack_dir and temp_unpack_dir.exists():
            shutil.rmtree(temp_unpack_dir)
        # 清理任务字典
        task_manager.clear_finished_task(task.id)


async def background_download_velocity(version: str, build: str, permanent_path: Path, final_dest_path: Path,
                                       task: Task):
    """后台下载并安装 Velocity 核心的专用函数。"""
    task.status = TaskStatus.RUNNING
    try:
        # 1. 获取最新 build
        build = await get_velocity_version_detail(version, build)
        build_info = PaperBuild.model_validate(build)
        download_info = PaperBuildDownload.model_validate(list(build_info.downloads.items())[0])

        expected_sha256 = download_info.checksums.sha256
        download_url = download_info.url

        # 3. 执行下载 (类似 _background_download_and_install)

        download_file(permanent_path, download_url, task)
        # [修改] 使用 sha256 校验
        if get_file_sha256(permanent_path) != expected_sha256:
            raise ValueError(f"SHA256 mismatch! Expected {expected_sha256}")
        final_dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(permanent_path, final_dest_path)
        task.status = TaskStatus.SUCCESS
        task.progress = 100.0
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        if permanent_path.exists():
            os.remove(permanent_path)
