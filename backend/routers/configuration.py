# backend/routers/configuration.py

import json
import yaml
import tomli
import tomli_w
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.database import get_db
from backend.core import crud
from backend.core.logger import logger
from backend.core.auth import require_role
from backend.core.schemas import Role

router = APIRouter(prefix="/api/configs", tags=["Configurations"])


@dataclass
class PluginSpec:
    key: str
    fmt: str  # json|yaml|toml
    default_repo_path: Path
    # relative to server.path
    target_rel_path: Path
    # editable paths list. '*' means all, 'x.*' means subtree
    editable: List[str]
    # optional field schema for UI (basic)
    ui_fields: List[Dict[str, Any]]


REPO_ROOT = Path(__file__).resolve().parents[2]


def _p(rel: str) -> Path:
    return (REPO_ROOT / rel).resolve()


PLUGIN_SPECS: Dict[str, PluginSpec] = {
    # 1. ViaVersion (Velocity only)
    "viaversion": PluginSpec(
        key="viaversion",
        fmt="yaml",
        default_repo_path=_p("storages/mcdr-servers/testV/server/plugins/viaversion/config.yml"),
        target_rel_path=Path("server/plugins/viaversion/config.yml"),
        editable=[
            "packet-limiter.max-per-second",
            "packet-limiter.sustained-max-per-second",
        ],
        ui_fields=[
            {"path": "packet-limiter.max-per-second", "type": "int", "label": "每秒最大包数", "min": -1},
            {"path": "packet-limiter.sustained-max-per-second", "type": "int", "label": "持续期最大包数", "min": -1},
        ],
    ),
    # 2. Velocity Proxy (Fabric only)
    "velocity_proxy": PluginSpec(
        key="velocity_proxy",
        fmt="toml",
        default_repo_path=_p("storages/mcdr-servers/test1/server/config/FabricProxy-Lite.toml"),
        target_rel_path=Path("server/config/FabricProxy-Lite.toml"),
        editable=["*"],
        ui_fields=[
            {"path": "hackOnlineMode", "type": "bool", "label": "Hack Online Mode"},
            {"path": "hackEarlySend", "type": "bool", "label": "Hack Early Send"},
            {"path": "hackMessageChain", "type": "bool", "label": "Hack Message Chain"},
            {"path": "disconnectMessage", "type": "string", "label": "断开消息"},
            {"path": "secret", "type": "string", "label": "密钥"},
        ],
    ),
    # 3. Prime Backup (no velocity)
    "prime_backup": PluginSpec(
        key="prime_backup",
        fmt="json",
        default_repo_path=_p("storages/mcdr-servers/test1/config/prime_backup/config.json"),
        target_rel_path=Path("config/prime_backup/config.json"),
        editable=[
            "enabled",
            "command.permission.back",
            "command.permission.confirm",
            "scheduled_backup.enabled",
            "scheduled_backup.interval",
            "scheduled_backup.crontab",
            "scheduled_backup.require_online_players",
            "scheduled_backup.require_online_players_blacklist",
            "prune.*",
        ],
        ui_fields=[
            {"path": "enabled", "type": "bool", "label": "启用插件"},
            {"path": "command.permission.back", "type": "role_level", "label": "Back 权限"},
            {"path": "command.permission.confirm", "type": "role_level", "label": "Confirm 权限"},
            {"path": "scheduled_backup.enabled", "type": "bool", "label": "定时备份启用"},
            {"path": "scheduled_backup.interval", "type": "string", "label": "定时间隔 (如12h)"},
            {"path": "scheduled_backup.crontab", "type": "crontab", "label": "Crontab 表达式"},
            {"path": "scheduled_backup.require_online_players", "type": "bool", "label": "需要在线玩家"},
            {"path": "scheduled_backup.require_online_players_blacklist", "type": "string_array", "label": "在线玩家黑名单"},
            {"path": "prune.enabled", "type": "bool", "label": "清理启用"},
        ],
    ),
    # 4. Auto Plugin Reloader (all)
    "auto_plugin_reloader": PluginSpec(
        key="auto_plugin_reloader",
        fmt="json",
        default_repo_path=_p("storages/mcdr-servers/importC/config/auto_plugin_reloader/config.json"),
        target_rel_path=Path("config/auto_plugin_reloader/config.json"),
        editable=["enabled"],
        ui_fields=[
            {"path": "enabled", "type": "bool", "label": "启用插件"},
        ],
    ),
    # 5. Bili Live Helper (no velocity) - note: key is 'enable' in default
    "bili_live_helper": PluginSpec(
        key="bili_live_helper",
        fmt="json",
        default_repo_path=_p("storages/mcdr-servers/test1/config/bili_live_helper/config.json"),
        target_rel_path=Path("config/bili_live_helper/config.json"),
        editable=["enable", "account.*"],
        ui_fields=[
            {"path": "enable", "type": "bool", "label": "启用插件"},
            {"path": "account.uid", "type": "int", "label": "UID"},
            {"path": "account.sessdata", "type": "string", "label": "SESSDATA"},
            {"path": "account.bili_jct", "type": "string", "label": "bili_jct"},
            {"path": "account.buvid3", "type": "string", "label": "buvid3"},
            {"path": "account.ac_time_value", "type": "string", "label": "ac_time_value"},
        ],
    ),
    # 6. Where Is (no velocity)
    "where_is": PluginSpec(
        key="where_is",
        fmt="json",
        default_repo_path=_p("storages/mcdr-servers/test1/config/where_is/config.json"),
        target_rel_path=Path("config/where_is/config.json"),
        editable=[
            "command_prefix.where_is",
            "command_prefix.here",
            "permission_requirements.where_is",
            "permission_requirements.here",
        ],
        ui_fields=[
            {"path": "command_prefix.where_is", "type": "string_array", "label": "where_is 前缀"},
            {"path": "command_prefix.here", "type": "string_array", "label": "here 前缀"},
            {"path": "permission_requirements.where_is", "type": "role_level", "label": "where_is 权限"},
            {"path": "permission_requirements.here", "type": "role_level", "label": "here 权限"},
        ],
    ),
    # 7. Crash Restart (all)
    "crash_restart": PluginSpec(
        key="crash_restart",
        fmt="json",
        default_repo_path=_p("storages/mcdr-servers/importC2/config/CrashRestart.json"),
        target_rel_path=Path("config/CrashRestart.json"),
        editable=["*"],
        ui_fields=[
            {"path": "MAX_COUNT", "type": "int", "label": "最大重启次数", "min": 0},
            {"path": "COUNTING_TIME", "type": "int", "label": "计时窗口(秒)", "min": 0},
        ],
    ),
    # 8. joinMOTD (no velocity)
    "join_motd": PluginSpec(
        key="join_motd",
        fmt="json",
        default_repo_path=_p("storages/mcdr-servers/test1/config/joinMOTD.json"),
        target_rel_path=Path("config/joinMOTD.json"),
        editable=["serverName", "mainServerName", "serverList", "start_day"],
        ui_fields=[
            {"path": "serverName", "type": "string", "label": "服务器名"},
            {"path": "mainServerName", "type": "string", "label": "主服务器名"},
            {"path": "serverList", "type": "string_array", "label": "服务器列表"},
            {"path": "start_day", "type": "date", "label": "起始日期(YYYY-MM-DD)"},
        ],
    ),
    # 9. Quick Backup Multi (no velocity)
    "quick_backup_multi": PluginSpec(
        key="quick_backup_multi",
        fmt="json",
        default_repo_path=_p("storages/mcdr-servers/importC2/config/QuickBackupM.json"),
        target_rel_path=Path("config/QuickBackupM.json"),
        editable=["minimum_permission_level.back", "minimum_permission_level.confirm"],
        ui_fields=[
            {"path": "minimum_permission_level.back", "type": "role_level", "label": "Back 权限"},
            {"path": "minimum_permission_level.confirm", "type": "role_level", "label": "Confirm 权限"},
        ],
    ),
}


def deep_get(d: Dict[str, Any], path: str) -> Any:
    cur: Any = d
    for part in path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def deep_set(d: Dict[str, Any], path: str, value: Any):
    cur = d
    parts = path.split('.')
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    # merge dict b onto a (a as base), return new dict
    out: Dict[str, Any] = json.loads(json.dumps(a))  # deep copy
    def _merge(tgt, src):
        for k, v in (src or {}).items():
            if isinstance(v, dict) and isinstance(tgt.get(k), dict):
                _merge(tgt[k], v)
            else:
                tgt[k] = v
    _merge(out, b or {})
    return out


def _spec_or_404(plugin: str) -> PluginSpec:
    if plugin not in PLUGIN_SPECS:
        raise HTTPException(status_code=404, detail="未知的插件标识")
    return PLUGIN_SPECS[plugin]


def _read_default(spec: PluginSpec) -> Dict[str, Any]:
    try:
        raw = spec.default_repo_path.read_text(encoding='utf-8')
        if spec.fmt == 'json':
            return json.loads(raw)
        if spec.fmt == 'yaml':
            return yaml.safe_load(raw) or {}
        if spec.fmt == 'toml':
            return tomli.loads(raw)
        return {}
    except Exception as e:
        logger.warning(f"读取默认配置失败 {spec.key}: {e}")
        return {}


def _read_current(path: Path, spec: PluginSpec) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding='utf-8')
        if spec.fmt == 'json':
            return json.loads(raw)
        if spec.fmt == 'yaml':
            return yaml.safe_load(raw) or {}
        if spec.fmt == 'toml':
            return tomli.loads(raw)
        return None
    except Exception as e:
        logger.warning(f"读取现有配置失败 {spec.key}: {e}")
        return None


def _write_config(path: Path, spec: PluginSpec, data: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if spec.fmt == 'json':
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    elif spec.fmt == 'yaml':
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding='utf-8')
    elif spec.fmt == 'toml':
        path.write_text(tomli_w.dumps(data), encoding='utf-8')


def _server_target_path(server_path: str, spec: PluginSpec) -> Path:
    return (Path(server_path) / spec.target_rel_path).resolve()


def _allowed(spec: PluginSpec, path: str) -> bool:
    if '*' in spec.editable:
        return True
    for pat in spec.editable:
        if pat.endswith('.*'):
            if path == pat[:-2] or path.startswith(pat[:-2] + '.'):
                return True
        if path == pat:
            return True
    return False


class ConfigResponse(BaseModel):
    plugin: str
    file_path: str
    format: str
    config: Dict[str, Any]
    editable_paths: List[str]
    ui_fields: List[Dict[str, Any]]


class ConfigUpdatePayload(BaseModel):
    updates: Dict[str, Any]


@router.get("/{plugin}/{server_id}", response_model=ConfigResponse)
async def get_config(plugin: str, server_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.HELPER))):
    spec = _spec_or_404(plugin)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='服务器不存在')

    target = _server_target_path(server.path, spec)
    default_cfg = _read_default(spec)
    current_cfg = _read_current(target, spec) or {}
    merged = deep_merge(default_cfg, current_cfg)

    # 特例：joinMOTD serverName 若为默认值，则按服务器名称显示
    if plugin == 'join_motd':
        try:
            if merged.get('serverName') == 'Survival Server':
                merged['serverName'] = server.name
        except Exception:
            pass

    return ConfigResponse(
        plugin=plugin,
        file_path=str(target),
        format=spec.fmt,
        config=merged,
        editable_paths=spec.editable,
        ui_fields=spec.ui_fields,
    )


@router.patch("/{plugin}/{server_id}")
async def update_config(plugin: str, server_id: int, payload: ConfigUpdatePayload, db: Session = Depends(get_db), _user=Depends(require_role(Role.HELPER))):
    spec = _spec_or_404(plugin)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='服务器不存在')

    target = _server_target_path(server.path, spec)
    default_cfg = _read_default(spec)
    current_cfg = _read_current(target, spec) or {}
    base = deep_merge(default_cfg, current_cfg)

    # 将 payload.updates 展平为路径，以限制可编辑范围
    def _flatten(prefix: str, obj: Any, out: Dict[str, Any]):
        if isinstance(obj, dict):
            for k, v in obj.items():
                p2 = f"{prefix}.{k}" if prefix else k
                _flatten(p2, v, out)
        else:
            out[prefix] = obj

    flat: Dict[str, Any] = {}
    _flatten('', payload.updates or {}, flat)

    for path, value in flat.items():
        if not _allowed(spec, path):
            logger.debug(f"跳过不可编辑字段 {plugin}.{path}")
            continue
        deep_set(base, path, value)

    try:
        _write_config(target, spec, base)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存配置失败: {e}")
    return {"message": "ok", "file_path": str(target)}


class RawPayload(BaseModel):
    content: str


@router.get("/{plugin}/{server_id}/raw", response_class=Response)
async def get_raw(plugin: str, server_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.HELPER))):
    spec = _spec_or_404(plugin)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='服务器不存在')
    target = _server_target_path(server.path, spec)
    text: str
    if not target.exists():
        # 无文件时返回默认模板文本
        default = _read_default(spec)
        if spec.fmt == 'json':
            text = json.dumps(default, ensure_ascii=False, indent=2)
        elif spec.fmt == 'yaml':
            text = yaml.safe_dump(default, sort_keys=False, allow_unicode=True)
        elif spec.fmt == 'toml':
            text = tomli_w.dumps(default)
        else:
            text = ""
        return Response(content=text, media_type="text/plain")
    try:
        text = target.read_text(encoding='utf-8')
        return Response(content=text, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取失败: {e}")


@router.post("/{plugin}/{server_id}/raw")
async def save_raw(plugin: str, server_id: int, payload: RawPayload, db: Session = Depends(get_db), _user=Depends(require_role(Role.HELPER))):
    spec = _spec_or_404(plugin)
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail='服务器不存在')
    target = _server_target_path(server.path, spec)

    # 先尝试解析，避免写入非法格式
    try:
        if spec.fmt == 'json':
            _ = json.loads(payload.content)
        elif spec.fmt == 'yaml':
            _ = yaml.safe_load(payload.content)
        elif spec.fmt == 'toml':
            _ = tomli.loads(payload.content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"内容解析失败: {e}")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload.content, encoding='utf-8')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")
    return {"message": "saved", "file_path": str(target)}
