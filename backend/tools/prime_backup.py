from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path
import os
import shutil
from typing import List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend import crud, schemas
from backend.core.config import PYTHON_EXECUTABLE, TEMP_PATH
from backend.core.utils import get_size_bytes
from backend.dependencies import plugin_manager, server_service


PB_PLUGIN_ID = "prime_backup"


def _get_server(db: Session, server_id: int):
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


def _get_pb_env_paths(server_path: Path) -> Tuple[Path, Path]:
    pb_dir = server_path / "pb_files"
    db_path = pb_dir / "prime_backup.db"
    return pb_dir, db_path


def _resolve_pb_cli_path(server_path: Path) -> Path:
    plugins_dir = server_path / 'plugins'
    info = plugin_manager.get_plugins_info(plugins_dir)
    for p in info.data:
        if (p.meta or {}).get('id') == PB_PLUGIN_ID:
            # 直接使用其物理路径，即使被禁用也可作为 CLI 执行
            return Path(p.path)
    raise HTTPException(status_code=404, detail="Prime Backup plugin not installed on this server")


async def _run_pb(cli_path: Path, db_ref: Path, args: List[str]) -> Tuple[int, str, str]:
    """运行 PB 命令并返回 (returncode, stdout, stderr)。使用 asyncio 子进程，参考 mcdr_manager 的模式。"""
    # -d 可接收 db 文件或其所在目录，这里统一传目录路径更稳妥
    db_arg = str(db_ref if db_ref.is_file() else db_ref)
    if not cli_path.exists():
        raise HTTPException(status_code=404, detail=f"PB CLI not found at {cli_path}")
    proc = await asyncio.create_subprocess_exec(
        PYTHON_EXECUTABLE, str(cli_path), '-d', db_arg, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cli_path.parent)
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout.decode('utf-8', 'ignore'), stderr.decode('utf-8', 'ignore')


def _parse_overview(text: str) -> schemas.PBOverview:
    # 支持不同实现略有差异的文案，尽量宽松匹配
    storage_root = None
    db_version = None
    backup_amount = None
    db_path = None
    db_file_size = None
    blob_stored_size = None
    blob_raw_size = None

    for line in text.splitlines():
        if 'Storage root set to' in line:
            m = re.search(r"Storage root set to '([^']+)'", line)
            if m: storage_root = m.group(1)
        elif 'DB version' in line:
            m = re.search(r"DB version: (\d+)", line)
            if m: db_version = m.group(1)
        elif 'Backup count' in line or 'Backup amount' in line:
            m = re.search(r"Backup (?:count|amount): (\d+)", line)
            if m: backup_amount = int(m.group(1))
        elif 'DB path:' in line:
            m = re.search(r"DB path: (.+)$", line)
            if m: db_path = m.group(1).strip()
        elif 'DB file size:' in line:
            m = re.search(r"DB file size: (\d+)", line)
            if m: db_file_size = int(m.group(1))
        elif 'Blob stored size sum:' in line:
            m = re.search(r"Blob stored size sum: (\d+)", line)
            if m: blob_stored_size = int(m.group(1))
        elif 'Blob raw size sum:' in line:
            m = re.search(r"Blob raw size sum: (\d+)", line)
            if m: blob_raw_size = int(m.group(1))

    return schemas.PBOverview(
        storage_root=storage_root,
        db_version=db_version,
        backup_amount=backup_amount,
        db_path=db_path,
        db_file_size=db_file_size,
        blob_stored_size=blob_stored_size,
        blob_raw_size=blob_raw_size,
    )


def _parse_list(text: str) -> List[schemas.PBBackupItem]:
    items: List[schemas.PBBackupItem] = []
    for line in text.splitlines():
        # id=7 date='2025-09-30 13:34:57' stored_size=... raw_size=... creator='...' comment=''
        if 'id=' in line and "date='" in line and 'stored_size=' in line:
            m = re.search(
                r"id=(\d+)\s+date='([^']+)'\s+stored_size=(\d+)\s+raw_size=(\d+)\s+creator='([^']*)'\s+comment='([^']*)'",
                line
            )
            if m:
                items.append(schemas.PBBackupItem(
                    id=int(m.group(1)),
                    date=m.group(2),
                    stored_size=int(m.group(3)),
                    raw_size=int(m.group(4)),
                    creator=m.group(5),
                    comment=m.group(6),
                ))
    return items


async def pb_overview(db: Session, server_id: int) -> schemas.PBOverview:
    server = _get_server(db, server_id)
    pb_dir, db_path = _get_pb_env_paths(Path(server.path))
    if not pb_dir.exists() or not db_path.exists():
        # 返回最小概览（不依赖插件是否安装）
        return schemas.PBOverview(storage_root=str(pb_dir), backup_amount=0, db_path=str(db_path))
    cli = _resolve_pb_cli_path(Path(server.path))
    rc, out, err = await _run_pb(cli, pb_dir, ['overview'])
    if rc != 0:
        # 尝试返回保底信息
        return schemas.PBOverview(storage_root=str(pb_dir), backup_amount=0, db_path=str(db_path))
    return _parse_overview(out + "\n" + err)


async def pb_list(db: Session, server_id: int) -> List[schemas.PBBackupItem]:
    server = _get_server(db, server_id)
    pb_dir, db_path = _get_pb_env_paths(Path(server.path))
    if not pb_dir.exists() or not db_path.exists():
        return []
    cli = _resolve_pb_cli_path(Path(server.path))
    rc, out, err = await _run_pb(cli, pb_dir, ['list'])
    if rc != 0:
        return []
    return _parse_list(out + "\n" + err)


async def pb_show(db: Session, server_id: int, backup_id: int) -> str:
    server = _get_server(db, server_id)
    cli = _resolve_pb_cli_path(Path(server.path))
    pb_dir, db_path = _get_pb_env_paths(Path(server.path))
    if not pb_dir.exists() or not db_path.exists():
        raise HTTPException(status_code=404, detail="PB database not found")
    rc, out, err = await _run_pb(cli, pb_dir, ['show', str(backup_id)])
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"show failed: {err or out}")
    return out or err or ''


def _safe_unlink(p: Path):
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


async def pb_export(db: Session, server_id: int, backup_id: int, background_tasks: BackgroundTasks) -> FileResponse:
    server = _get_server(db, server_id)
    cli = _resolve_pb_cli_path(Path(server.path))
    pb_dir, db_path = _get_pb_env_paths(Path(server.path))
    if not pb_dir.exists() or not db_path.exists():
        raise HTTPException(status_code=404, detail="PB database not found")

    # 输出文件放在 TEMP_PATH，默认 tar 格式
    out_name = f"pb_{server_id}_{backup_id}_{uuid.uuid4().hex}.tar"
    out_path = TEMP_PATH / out_name

    rc, out, err = await _run_pb(cli, pb_dir, ['export', str(backup_id), str(out_path)])
    if rc != 0 or not out_path.exists():
        raise HTTPException(status_code=500, detail=f"export failed: {err or out}")

    # 模仿 archives.py，下载后删除临时文件
    background_tasks.add_task(_safe_unlink, out_path)
    return FileResponse(path=str(out_path), filename=f"pb_{server_id}_{backup_id}.tar", media_type='application/x-tar')


async def pb_extract(db: Session, server_id: int, payload: schemas.PBExtractPayload):
    server = _get_server(db, server_id)
    cli = _resolve_pb_cli_path(Path(server.path))
    pb_dir, db_path = _get_pb_env_paths(Path(server.path))
    if not pb_dir.exists() or not db_path.exists():
        raise HTTPException(status_code=404, detail="PB database not found")
    # 目标路径：允许绝对路径，或相对服务器根目录
    dest = Path(payload.dest_path)
    if not dest.is_absolute():
        dest = Path(server.path) / payload.dest_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = await _run_pb(cli, pb_dir, ['extract', str(payload.id), payload.src_path, '-o', str(dest)])
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"extract failed: {err or out}")
    return {"message": "extract started"}


async def pb_import(db: Session, server_id: int, file: UploadFile, auto_meta: bool = False):
    server = _get_server(db, server_id)
    cli = _resolve_pb_cli_path(Path(server.path))
    pb_dir, db_path = _get_pb_env_paths(Path(server.path))
    pb_dir.mkdir(parents=True, exist_ok=True)

    # 保存到临时文件
    tmp = TEMP_PATH / f"upload_{uuid.uuid4().hex}_{file.filename}"
    content = await file.read()
    tmp.write_bytes(content)
    try:
        args = ['import', str(tmp)]
        if auto_meta:
            args.append('--auto-meta')
        rc, out, err = await _run_pb(cli, pb_dir, args)
        if rc != 0:
            raise HTTPException(status_code=500, detail=f"import failed: {err or out}")
        return {"message": "import started"}
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


async def pb_migrate(db: Session, server_id: int):
    server = _get_server(db, server_id)
    cli = _resolve_pb_cli_path(Path(server.path))
    pb_dir, db_path = _get_pb_env_paths(Path(server.path))
    if not pb_dir.exists() or not db_path.exists():
        raise HTTPException(status_code=404, detail="PB database not found")
    rc, out, err = await _run_pb(cli, pb_dir, ['migrate_db'])
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"migrate_db failed: {err or out}")
    return {"message": "migrate started"}


async def pb_usage(db: Session, server_id: int) -> schemas.PBUsage:
    server = _get_server(db, server_id)
    pb_dir, _ = _get_pb_env_paths(Path(server.path))
    size = get_size_bytes(pb_dir) if pb_dir.exists() else 0
    return schemas.PBUsage(bytes=size)


async def pb_usage_total(db: Session) -> schemas.PBUsage:
    total = 0
    for s in crud.get_all_servers(db):
        pb_dir, _ = _get_pb_env_paths(Path(s.path))
        total += get_size_bytes(pb_dir) if pb_dir.exists() else 0
    return schemas.PBUsage(bytes=total)


async def pb_restore(db: Session, source_server_id: int, backup_id: int, target_server_id: int):
    # 运行中的服务器不允许
    target = crud.get_server_by_id(db, target_server_id)
    if not target:
        print(1)
        raise HTTPException(status_code=404, detail="Target server not found")
    st, _ = await server_service.get_status(target)
    if str(st) == schemas.ServerStatus.RUNNING or st == schemas.ServerStatus.RUNNING:
        raise HTTPException(status_code=409, detail="目标服务器正在运行，无法恢复")

    # 提取整个备份到临时目录
    source = _get_server(db, source_server_id)
    cli = _resolve_pb_cli_path(Path(source.path))
    pb_dir, db_path = _get_pb_env_paths(Path(source.path))
    if not pb_dir.exists() or not db_path.exists():
        print(2)
        raise HTTPException(status_code=404, detail="PB database not found on source server")

    temp_out = TEMP_PATH / f"pb_extract_{uuid.uuid4().hex}"
    temp_out.mkdir(parents=True, exist_ok=True)
    try:
        rc, out, err = await _run_pb(cli, pb_dir, ['extract', str(backup_id), '.', '-o', str(temp_out), '-r'])
        if rc != 0:
            raise HTTPException(status_code=500, detail=f"extract failed: {err or out}")

        # 搜索 level.dat，定位世界根目录
        world_dir: Optional[Path] = None
        for dirpath, dirnames, filenames in os.walk(temp_out):
            if 'level.dat' in filenames:
                world_dir = Path(dirpath)
                break
        if world_dir is None:
            print(3)
            raise HTTPException(status_code=404, detail="在备份中未找到 level.dat")

        target_server_path = Path(target.path)
        server_folder = target_server_path / 'server'
        server_folder.mkdir(parents=True, exist_ok=True)
        target_world_dir = server_folder / 'world'

        # 备份旧 world
        if target_world_dir.exists():
            backup_dir = server_folder / f"world_backup_{uuid.uuid4().hex}"
            shutil.move(str(target_world_dir), str(backup_dir))

        # 将 world_dir 移动为 world
        if target_world_dir.exists():
            shutil.rmtree(target_world_dir, ignore_errors=True)
        shutil.move(str(world_dir), str(target_world_dir))

        return {"message": "restore completed", "world_path": str(target_world_dir)}
    finally:
        shutil.rmtree(temp_out, ignore_errors=True)
