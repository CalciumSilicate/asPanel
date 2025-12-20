# backend/tasks/background.py

import uuid
import zipfile
import subprocess
import requests
import shutil
import os
from sqlalchemy.orm import Session
from typing import Dict, Optional
from pathlib import Path

from backend.tools import server_parser
from backend.core import crud, models
from backend.core.api import get_velocity_version_detail
from backend.core.constants import FABRIC_REPO_URL, TEMP_PATH
from backend.core.utils import get_file_sha1, get_file_sha256
from backend.core.database import get_db_context
from backend.core.schemas import TaskStatus, ArchiveCreate, ArchiveType, PaperBuild, Task, PaperBuildDownload, Server
from backend.core.dependencies import task_manager, archive_manager, mcdr_manager


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
