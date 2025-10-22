from mcdreforged.api.all import *
import threading
import time
from typing import Dict, List

PLUGIN_METADATA = {
    "id": "force_load_pearl_loader",
    "version": "1.0.0",
    "author": "CalciumSilicate",
    "name": "Pearl Loader by Force Load",
    "description": "使用 forceload 命令临时加载珍珠传送器加载器",
    "requirements": ["mcdreforged>=2.0.0"],
}

# === 配置 ===
DEFAULT_CONFIG = {
    "loader_positions": {
        # 维度 -> ["x z", ...]
        "minecraft:overworld": [],
        "minecraft:the_nether": [],
        "minecraft:the_end": [],
    },
    "load_time": 60,  # 默认加载秒数
    "on_server_startup": True  # 启动时自动执行一次加载->移除
}

from pathlib import Path
import json

CONFIG_FILENAME = 'force_load_pearl_loader.json'
config: Dict = {}

# 运行时状态
_lock = threading.RLock()
_loading_flag = False

HELP_MSG = (
    '§a[Pearl Loader] 命令帮助:\n'
    '§b!!pl §f- §7显示本帮助\n'
    '§b!!pl reload §f- §7重载配置文件\n'
    '§b!!pl list §f- §7列出配置中的加载器位置\n'
    '§b!!pl add <x> <z> [dimension] §f- §7添加加载器位置，默认维度为 minecraft:the_nether\n'
    '§b!!pl delete <x> <z> [dimension] §f- §7删除加载器位置，默认维度为 minecraft:the_nether\n'
    '§b!!pl load [seconds] §f- §7临时 forceload 所有位置，结束后自动 remove；秒数默认为配置中的 load_time\n'
    '§b!!pl enable §f- §7开启 on_server_startup（重启后自动 load→remove 一次）\n'
    '§b!!pl disable §f- §7关闭 on_server_startup\n'
)


# === 工具函数 ===

def _config_path(server: PluginServerInterface) -> Path:
    return Path('config') / CONFIG_FILENAME


def _save_config(server: PluginServerInterface):
    global config
    path = _config_path(server)
    path.parent.mkdir(parents=True, exist_ok=True)
    server.logger.info(f"[Pearl Loader] Saving config to {path.resolve()} => {config}")
    with path.open('w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.flush()
        try:
            import os
            os.fsync(f.fileno())
        except Exception:
            pass


def _load_config(server: PluginServerInterface):
    global config
    path = _config_path(server)
    if path.exists():
        try:
            with path.open('r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            server.logger.warning(f"配置文件损坏，使用默认配置。原因: {e}")
            config = DEFAULT_CONFIG.copy()
    else:
        # 首次生成
        config = DEFAULT_CONFIG.copy()
        _save_config(server)

    # 防御：字段缺失时补齐
    config.setdefault('loader_positions', {})
    for d in ("minecraft:overworld", "minecraft:the_nether", "minecraft:the_end"):
        config['loader_positions'].setdefault(d, [])
    config.setdefault('load_time', 5)
    config.setdefault('on_server_startup', True)

    server.logger.info(f"[Pearl Loader] Loaded config from {path.resolve()} => {config}")


def _dim_or_default(dimension: str | None) -> str:
    return dimension if dimension else 'minecraft:the_nether'


def _pos_key(x: int, z: int) -> str:
    return f"{x} {z}"


def _unique_add(lst: List[str], value: str) -> bool:
    if value in lst:
        return False
    lst.append(value)
    return True


def _remove_once(lst: List[str], value: str) -> bool:
    if value in lst:
        lst.remove(value)
        return True
    return False


def _say(server: PluginServerInterface, text: str):
    server.say(f"§a[Pearl Loader] §r{text}")


def _log(server: PluginServerInterface, text: str):
    server.logger.info(f"[Pearl Loader] {text}")


# === forceload 执行 ===

def _forceload_add_all(server: PluginServerInterface):
    positions = config.get('loader_positions', {})
    total = 0
    for dim, lst in positions.items():
        for s in lst:
            try:
                x_str, z_str = s.split()
                cmd = f"execute in {dim} run forceload add {x_str} {z_str}"
                server.execute(cmd)
                total += 1
            except Exception as e:
                server.logger.error(f"添加 forceload 失败: {s} @ {dim}, {e}")
    return total


def _forceload_remove_all(server: PluginServerInterface):
    positions = config.get('loader_positions', {})
    total = 0
    for dim, lst in positions.items():
        # 精确按点位 remove，避免影响别的 forceload
        for s in lst:
            try:
                x_str, z_str = s.split()
                cmd = f"execute in {dim} run forceload remove {x_str} {z_str}"
                server.execute(cmd)
                total += 1
            except Exception as e:
                server.logger.error(f"移除 forceload 失败: {s} @ {dim}, {e}")
    return total


def _do_load_then_remove(server: PluginServerInterface, seconds: int):
    global _loading_flag
    with _lock:
        if _loading_flag:
            _say(server, '另一个加载任务正在进行中，请稍后再试')
            return
        _loading_flag = True

    try:
        added = _forceload_add_all(server)
        _say(server, f'已 forceload {added} 个位置，保持 {seconds}s 后自动移除')
        time.sleep(max(0, seconds))
    finally:
        removed = _forceload_remove_all(server)
        _say(server, f'已自动移除 {removed} 个位置的 forceload')
        with _lock:
            _loading_flag = False


# === 指令回调 ===

def cmd_show_help(src: CommandSource):
    src.reply(HELP_MSG)


def cmd_status(src: CommandSource):
    enabled = bool(config.get('on_server_startup', True))
    src.reply(f"§aon_server_startup: §b{'ON' if enabled else 'OFF'} §7（配置文件里即时状态）")


def cmd_reload(src: CommandSource):
    server = src.get_server()
    _load_config(server)
    src.reply('§a配置已重载')


def cmd_enable(src: CommandSource):
    server = src.get_server()
    with _lock:
        config['on_server_startup'] = True
        _save_config(server)
    src.reply('§a已开启 on_server_startup（下次服务器启动时会自动 load→remove 一次）')


def cmd_disable(src: CommandSource):
    server = src.get_server()
    with _lock:
        config['on_server_startup'] = False
        _save_config(server)
    src.reply('§e已关闭 on_server_startup')


def cmd_list(src: CommandSource):
    positions = config.get('loader_positions', {})
    if not any(positions.values()):
        src.reply('§7当前没有配置任何加载器位置')
        return
    lines = ['§a当前配置的加载器位置：']
    for dim, lst in positions.items():
        disp = ', '.join(lst) if lst else '（空）'
        lines.append(f'§b{dim}§r: §f{disp}')
    src.reply('\n'.join(lines))


def cmd_add(src: CommandSource, ctx: CommandContext):
    server = src.get_server()
    x = int(ctx['x'])
    z = int(ctx['z'])
    dim = _dim_or_default(ctx.get('dimension'))
    with _lock:
        lst = config['loader_positions'].setdefault(dim, [])
        if _unique_add(lst, _pos_key(x, z)):
            _save_config(server)
            src.reply(f'§a已添加: §b({x}, {z}) §7@ §e{dim}')
        else:
            src.reply('§e该位置已存在，无需重复添加')


def cmd_delete(src: CommandSource, ctx: CommandContext):
    server = src.get_server()
    x = int(ctx['x'])
    z = int(ctx['z'])
    dim = _dim_or_default(ctx.get('dimension'))
    with _lock:
        lst = config['loader_positions'].setdefault(dim, [])
        if _remove_once(lst, _pos_key(x, z)):
            _save_config(server)
            src.reply(f'§a已删除: §b({x}, {z}) §7@ §e{dim}')
        else:
            src.reply('§e未找到该位置，无法删除')


def cmd_load(src: CommandSource, ctx: CommandContext):
    server = src.get_server()
    seconds = int(ctx.get('seconds') or config.get('load_time', 5))

    th = threading.Thread(target=_do_load_then_remove, args=(server, seconds), daemon=True)
    th.start()
    src.reply(f'§a开始加载，持续 §b{seconds}s§a（完成后将自动移除）')


# === 生命周期 ===

def on_load(server: PluginServerInterface, old_module):
    global config
    _load_config(server)

    server.register_help_message('!!pl', 'Pearl Loader: 使用 forceload 临时加载珍珠传送器加载器')

    # 指令树
    server.register_command(
        Literal('!!pl')
        .then(Literal('reload').requires(lambda s: s.has_permission(3)).runs(cmd_reload))
        .then(Literal('list').runs(cmd_list))
        .then(Literal('add')
              .requires(lambda s: s.has_permission(3))
              .then(Integer('x')
                    .then(Integer('z')
                          .then(Text('dimension').runs(cmd_add))
                          .runs(cmd_add)))
              )
        .then(Literal('delete')
              .requires(lambda s: s.has_permission(3))
              .then(Integer('x')
                    .then(Integer('z')
                          .then(Text('dimension').runs(cmd_delete))
                          .runs(cmd_delete)))
              )
        .then(Literal('load')
              .requires(lambda s: s.has_permission(3))
              .then(Integer('seconds').runs(cmd_load))
              .runs(cmd_load))
        .then(Literal('enable').requires(lambda s: s.has_permission(3)).runs(cmd_enable))
        .then(Literal('disable').requires(lambda s: s.has_permission(3)).runs(cmd_disable))
        .then(Literal('status').runs(cmd_status))
        .runs(cmd_show_help)
    )

    _log(server, '插件已加载')


def on_server_startup(server: PluginServerInterface):
    if bool(config.get('on_server_startup', True)):
        seconds = int(config.get('load_time', 5))
        _log(server, f'服务器启动：自动执行一次 forceload（{seconds}s）并移除')
        threading.Thread(target=_do_load_then_remove, args=(server, seconds), daemon=True).start()


def on_unload(server: PluginServerInterface):
    # 卸载时尝试清理一次（非强制）
    try:
        removed = _forceload_remove_all(server)
        if removed:
            _log(server, f'插件卸载：清理了 {removed} 个 forceload 位置')
    except Exception as e:
        server.logger.warning(f"卸载清理失败: {e}")
