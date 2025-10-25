# backend/core/utils.py

import json
import os
import re
import time
import shutil
import asyncio
import hashlib
import zipfile
import subprocess
from pathlib import Path
from threading import RLock
from typing import Tuple, Optional, Dict, Union, List
from zoneinfo import ZoneInfo
from datetime import timezone, timedelta
from cachetools import TTLCache, cached

from backend.core.constants import TIMEZONE
from backend.core.logger import logger

_size_cache = TTLCache(ttl=60, maxsize=1024)
_size_cache_lock = RLock()
_hash_cache = TTLCache(ttl=60, maxsize=1024)
_hash_cache_lock = RLock()

_MC_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")


def _hash_cache_key(data: Path | bytes, hash_tool):
    if isinstance(data, Path):
        if not data.is_file():
            return None
        mtime = data.stat().st_mtime
        return str(data), mtime, hash_tool.name
    elif isinstance(data, bytes):
        return hash(data), hash_tool.name
    else:
        raise TypeError(f"不支持的类型: {type(data)}，请输入 Path 或 bytes。")


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


@cached(_size_cache, key=lambda path, _r=None: (path,), lock=_size_cache_lock)
def get_size_mb(path: str | Path, _r=None) -> float:
    if _r is not None:
        _size_cache.pop((path,), None)
    return round(get_size_bytes(path) / (1024 ** 2), 3)


@cached(_hash_cache, key=_hash_cache_key, lock=_hash_cache_lock)
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


def get_str_md5(text: str) -> str:
    md5_obj = hashlib.md5()
    md5_obj.update(text.encode('utf-8'))
    return md5_obj.hexdigest()


def is_valid_mc_name(name: str) -> bool:
    return bool(_MC_NAME_RE.match(name))


def _read_files_in_zipfile(zip_file_path: Path, *files_name: str) -> List[Optional[bytes]]:
    if not os.path.exists(zip_file_path):
        return None
    try:
        file_bytes = []
        with zipfile.ZipFile(zip_file_path, 'r') as jar_file:
            for file_name in files_name:
                if file_name in jar_file.namelist():
                    file_bytes.append(jar_file.read(file_name))
                else:
                    file_bytes.append(jar_file.read(file_name))
    except zipfile.BadZipFile:
        return None
    except Exception as e:
        return None
    return file_bytes


def _get_version_json_from_vanilla_jar(jar_path: Path) -> Dict | None:
    _ = _read_files_in_zipfile(jar_path, 'version.json')[0]
    return json.loads(_.decode('utf-8')) if _ else None


def get_vanilla_jar_version(jar_path: Path) -> Optional[str]:
    js = _get_version_json_from_vanilla_jar(jar_path)
    if js is None:
        return None
    version_id: Optional[str] = js.get("id", None)
    if version_id is None:
        return None
    if '/' in version_id:
        version_id = version_id.split("/")[0].strip()
    return version_id


def _get_manifest_mf_from_velocity_jar(jar_path: Path) -> str | None:
    _ = _read_files_in_zipfile(jar_path, 'META-INF/MANIFEST.MF')[0]
    return _.decode('utf-8') if _ else None


def get_velocity_jar_version(jar_path: Path) -> Optional[str]:
    manifest_mf = _get_manifest_mf_from_velocity_jar(jar_path)
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
    _ = _read_files_in_zipfile(jar_path, 'META-INF/MANIFEST.MF')[0]
    manifest_lines = _.decode().splitlines()

    vanilla_version = None
    fabric_loader_version = None
    class_string = ""
    for line in manifest_lines[2:]:
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


def get_forge_jar_version(jar_path: Path) -> Tuple[Optional[str], Optional[str]]:
    if not os.path.exists(jar_path):
        return None, None
    jar_name = os.path.basename(jar_path)
    patterns = [
        r"forge-(?P<mc>[0-9.]+)-(?P<forge>[0-9.]+)(?:-[\w.]+)?\.jar$",
        r"forge-(?P<mc>[0-9.]+)-(?P<forge>[0-9.]+)(?:-[\w.]+)?-server\.jar$",
    ]
    for pattern in patterns:
        match = re.match(pattern, jar_name)
        if match:
            return match.group("mc"), match.group("forge")
    _ = _read_files_in_zipfile(jar_path, "version.json", "META-INF/version.json")
    for candidate in _:
        if candidate:
            try:
                version_info = json.loads(candidate.decode())
            except Exception:
                continue
            version_id = version_info.get("id") or version_info.get("version")
            if isinstance(version_id, str) and version_id.startswith("forge-"):
                parts = version_id.split("-")
                if len(parts) >= 3:
                    return parts[1], parts[2]
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
        if self._start_time is None:
            logger.warning(f"[{self.name}] 计时尚未开始")
            return
        elapsed = time.perf_counter() - self._start_time
        if point is None:
            logger.info(f"[{self.name}] 当前已用时 {elapsed:.4f} 秒")
        else:
            logger.info(f"[{self.name}.{point}] 当前已用时 {elapsed:.4f} 秒")


def _bw_sleep(start_ts: float, bytes_written: int, limit_bps: float):
    if limit_bps <= 0:
        return
    elapsed = time.perf_counter() - start_ts
    expected = bytes_written / limit_bps
    if expected > elapsed:
        time.sleep(expected - elapsed)


def _copy_file_resumable_throttled(src: Path, dst: Path, *, max_mbps: float = 1024.0, preserve_stat: bool = True):
    if not src.is_file():
        return

    src_size = src.stat().st_size
    dst_parent = dst.parent
    dst_parent.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    limit_bps = max(0.0, float(os.getenv('ASP_IMPORT_BWLIMIT_MBPS', max_mbps)) * 1024 * 1024)

    existing = 0
    if dst.exists():
        try:
            existing = dst.stat().st_size
        except OSError:
            existing = 0
        if existing > src_size:
            existing = 0

    mode = 'ab' if existing > 0 else 'wb'

    with open(src, 'rb') as s, open(dst, mode) as d:
        if existing > 0:
            s.seek(existing)
        written = existing
        chunk = 1024 * 1024
        while True:
            buf = s.read(chunk)
            if not buf:
                break
            d.write(buf)
            written += len(buf)
            _bw_sleep(start, written - existing, limit_bps)

    if preserve_stat:
        try:
            shutil.copystat(src, dst, follow_symlinks=False)
        except OSError:
            pass


def copytree_resumable_throttled(src: Path, dst: Path, *, max_mbps: float = 1024.0):
    src = Path(src)
    dst = Path(dst)
    if not src.exists():
        raise FileNotFoundError(f"源目录不存在: {src}")

    for root, dirs, files in os.walk(src):
        root_p = Path(root)
        rel = root_p.relative_to(src)
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for name in files:
            sp = root_p / name
            if sp.is_symlink():
                continue
            dp = (dst / rel / name)
            try:
                _copy_file_resumable_throttled(sp, dp, max_mbps=max_mbps)
            except Exception as e:
                logger.error(f"复制文件失败: {sp} -> {dp}：{e}")


def get_tz_info():
    if ZoneInfo:
        try:
            return ZoneInfo(TIMEZONE)
        except Exception:
            pass
    try:
        if TIMEZONE.upper().startswith("UTC"):
            s = TIMEZONE[3:].strip()
            sign = 1
            if s.startswith("+"):
                s = s[1:]
            elif s.startswith("-"):
                s = s[1:]
                sign = -1
            if ":" in s:
                hh, mm = s.split(":", 1)
                hours, minutes = int(hh), int(mm)
            else:
                hours, minutes = int(s), 0
            return timezone(sign * timedelta(hours=hours, minutes=minutes))
    except Exception:
        pass
    return timezone(timedelta(hours=8))


def to_local_dt(dt):
    if dt is None:
        return None
    tz = get_tz_info()
    try:
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz)
    except Exception:
        return dt


def to_local_iso(dt):
    x = to_local_dt(dt)
    return x.isoformat() if x else None
