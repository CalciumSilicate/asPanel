# core/utils.py
import asyncio
import json
import os
import re
import shutil
from pathlib import Path
from typing import Tuple, Optional, Dict, Union
import time
from backend.logger import logger

import hashlib
import zipfile
import subprocess


def get_size_bytes(path: Union[str, Path], *, prefer_du: bool = True, timeout: float = 3.0) -> int:
    p = Path(path)
    if not p.exists():
        return 0

    if prefer_du and os.name != "nt":
        du_path = shutil.which("du")
        if du_path:
            try:
                result = subprocess.run(
                    [du_path, "-sb", "--", str(p)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=timeout,
                )
                first_token = result.stdout.strip().split()[0]
                return int(first_token)
            except Exception:
                pass

    def _dir_size(dir_path: Path) -> int:
        total = 0
        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            total += _dir_size(Path(entry.path))
                    except OSError:
                        continue
        except OSError:
            return 0
        return total

    if p.is_file():
        try:
            return p.stat().st_size
        except OSError:
            return 0

    return _dir_size(p)


def get_size_mb(path: str | Path) -> float:
    return round(get_size_bytes(path) / (1024 ** 2), 3)


def get_file_hash(data: Path | bytes, hash_tool) -> str | None:
    if isinstance(data, Path):
        if not data.is_file():
            return None
        with open(data, 'rb') as f:
            while chunk := f.read(8192):
                hash_tool.update(chunk)
    elif isinstance(data, bytes):
        hash_tool.update(data)
    else:
        raise TypeError(f"不支持的类型: {type(data)}，请输入 Path 或 bytes。")
    return hash_tool.hexdigest()


def get_file_sha1(data: Path | bytes) -> str | None:
    return get_file_hash(data, hashlib.sha1())


def get_file_sha256(data: Path | bytes) -> str | None:
    return get_file_hash(data, hashlib.sha256())


def get_file_md5(data: Path | bytes) -> str | None:
    return get_file_hash(data, hashlib.md5())


def get_version_json_from_vanilla_jar(jar_path: Path) -> Dict | None:
    if not os.path.exists(jar_path):
        return None
    try:
        with zipfile.ZipFile(jar_path, 'r') as jar_file:
            if 'version.json' in jar_file.namelist():
                version_json_bytes = jar_file.read('version.json')
                return json.loads(version_json_bytes.decode('utf-8'))
            else:
                return None
    except zipfile.BadZipFile:
        return None
    except Exception as e:
        return None


def get_vanilla_jar_version(jar_path: Path) -> Optional[str]:
    js = get_version_json_from_vanilla_jar(jar_path)
    if js is None:
        return None
    version_id: Optional[str] = js.get("id", None)
    if version_id is None:
        return None
    if '/' in version_id:
        version_id = version_id.split("/")[0].strip()
    return version_id


def get_manifest_mf_from_velocity_jar(jar_path: Path) -> str | None:
    if not os.path.exists(jar_path):
        return None
    try:
        with zipfile.ZipFile(jar_path, 'r') as jar_file:
            if 'META-INF/MANIFEST.MF' in jar_file.namelist():
                manifest_mf_bytes = jar_file.read('META-INF/MANIFEST.MF')
                return manifest_mf_bytes.decode('utf-8')
            else:
                return None
    except zipfile.BadZipFile:
        return None
    except Exception as e:
        return None


def get_velocity_jar_version(jar_path: Path) -> Optional[str]:
    manifest_mf = get_manifest_mf_from_velocity_jar(jar_path)
    if manifest_mf is None:
        return None
    pattern = r"Implementation-Version:\s+(.+?)\s+\(git-[a-f0-9]+-b(\w+)\)"
    match = re.search(pattern, manifest_mf)
    if match:
        version = match.group(1)
        build_number = match.group(2)
        formatted_output = f"{version}#{build_number}"
        return formatted_output
    else:
        return None


def get_fabric_jar_version(jar_path: Path) -> Tuple[Optional[str], Optional[str]]:
    if not os.path.exists(jar_path):
        return None, None
    try:
        vanilla_version = None
        fabric_loader_version = None
        with zipfile.ZipFile(jar_path, 'r') as jar_file:
            if 'META-INF/MANIFEST.MF' in jar_file.namelist():
                manifest = jar_file.read('META-INF/MANIFEST.MF')
                lines = manifest.decode().splitlines()
                class_string = ""
                for line in lines[2:]:
                    class_string += line.replace("Class-Path:", "")[1:]
                class_entries = class_string.split()
                for cls in class_entries:
                    split_cls = cls.split("/")
                    if "intermediary" in cls:
                        vanilla_version = split_cls[-2]
                    if "fabric-loader" in cls:
                        fabric_loader_version = split_cls[-2]
                    if vanilla_version and fabric_loader_version:
                        return vanilla_version, fabric_loader_version
        return vanilla_version, fabric_loader_version
    except zipfile.BadZipFile:
        return None, None
    except Exception as e:
        return None, None


async def poll_copy_progress(source_path: Path, target_path: Path, task, interval: float = 2.0):
    try:
        total_size: int = max(1, get_size_bytes(source_path))
    except Exception:
        return
    while True:
        try:
            if target_path.exists():
                copied: int = get_size_bytes(target_path)
            else:
                copied = 0
            progress = round((copied / total_size) * 100, 2)
            task.progress = progress
        except Exception:
            # 目标目录尚在创建或扫描失败时忽略，继续下一轮
            pass
        await asyncio.sleep(interval)


class Timer:
    def __init__(self, name: str = "Timer"):
        self.name = name
        self._start_time = None

    def __enter__(self):
        self._start_time = time.perf_counter()
        logger.info(f"[{self.name}] 计时开始")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start_time is None:
            logger.warning(f"[{self.name}] 计时尚未开始")
            return
        elapsed = time.perf_counter() - self._start_time
        logger.info(f"[{self.name}] 计时结束，用时 {elapsed:.4f} 秒")
        self._start_time = None

    def print(self, point: int = None):
        """手动打印当前耗时（不中断计时）"""
        if self._start_time is None:
            logger.warning(f"[{self.name}] 计时尚未开始")
            return
        elapsed = time.perf_counter() - self._start_time
        if point is None:
            logger.info(f"[{self.name}] 当前已用时 {elapsed:.4f} 秒")
        else:
            logger.info(f"[{self.name}.{point}] 当前已用时 {elapsed:.4f} 秒")
