# backend/plugins/cmd_list_executor.py

from mcdreforged.api.all import *
from concurrent.futures import ThreadPoolExecutor, as_completed
from math import ceil
from time import perf_counter
from pathlib import Path
import uuid

HELP = (
    '!!execute <x|~dx> <y|~dy> <z|~dz> <filename> [threads]  支持相对坐标 ~dx ~dy ~dz；以执行瞬间位置为固定原点'
    '（自动生成锚点盔甲架）。流程：add→并发setblock→summon→merge→remove（并发默认4，可自定义)'
)

PLUGIN_METADATA = {
    "id": "cmd_list_executor",
    "version": "0.3.1",
    "author": "CalciumSilicate",
    "name": "CommandListExecutorINNER",
    "description": "批量执行指令清单",
    "dependencies": {},
    "requirements": ["mcdreforged>=2.0.0"]
}


def _read_command_list(path: str) -> list[str]:
    """读取指令清单，每行一条，忽略空行与以#开头的注释行"""
    try:
        with open(Path("../..") / 'litematic' / 'command-list' / path, 'r', encoding='utf-8') as f:
            lines = [ln.rstrip('\n') for ln in f]
    except Exception as e:
        raise RuntimeError(f'无法读取指令清单: {e}')
    cmds: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        cmds.append(s)
    return cmds


def _classify_commands(cmds: list[str]) -> tuple[list[str], list[str], list[str], list[str], list[str], list[str]]:
    """分类拆分：
    返回 (adds, setblocks, summons, merges, removes, others)
    """
    adds: list[str] = []
    setblocks: list[str] = []
    summons: list[str] = []
    merges: list[str] = []
    removes: list[str] = []
    others: list[str] = []
    for c in cmds:
        s = c.lstrip()
        low = s.lower()
        if low.startswith('forceload add'):
            adds.append(c)
        elif low.startswith('forceload remove'):
            removes.append(c)
        elif low.startswith('setblock '):
            setblocks.append(c)
        elif low.startswith('summon '):
            summons.append(c)
        elif low.startswith('data merge block'):
            merges.append(c)
        else:
            others.append(c)
    return adds, setblocks, summons, merges, removes, others


def _chunkify(items: list[str], n_chunks: int) -> list[list[str]]:
    if n_chunks <= 1 or len(items) == 0:
        return [items] if items else []
    size = ceil(len(items) / n_chunks)
    return [items[i:i + size] for i in range(0, len(items), size)]


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    ms = int((seconds - s) * 1000)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}小时{m}分{sec}.{ms:03d}秒"
    if m > 0:
        return f"{m}分{sec}.{ms:03d}秒"
    return f"{sec}.{ms:03d}秒"


def _get_player_name_from_source(source: CommandSource) -> str | None:
    try:
        info = source.get_info() if hasattr(source, 'get_info') else None
        if info is not None and hasattr(info, 'player') and getattr(info, 'player'):
            return getattr(info, 'player')
        if hasattr(source, 'player'):
            pn = getattr(source, 'player')
            if isinstance(pn, str) and pn:
                return pn
            if hasattr(pn, 'name') and getattr(pn, 'name'):
                return getattr(pn, 'name')
    except Exception:
        pass
    return None


def _parse_coord(token: str, base: int) -> int:
    s = str(token).strip()
    if s.startswith('~'):
        if s == '~':
            return base
        try:
            delta = float(s[1:]) if len(s) > 1 else 0.0
        except Exception:
            delta = 0.0
        return int((base + delta) // 1)
    try:
        return int(float(s))
    except Exception:
        return base


def run_execute(server: ServerInterface, source: CommandSource, ctx: dict):
    if not source.has_permission(PermissionLevel.ADMIN):
        source.reply(RText('[CommandListExecuter] 权限不足：需要 MCDR ADMIN 权限').set_color(RColor.red))
        return

    x = ctx.get('x')
    y = ctx.get('y')
    z = ctx.get('z')
    path = ctx.get('path')
    threads = ctx.get('threads')
    try:
        cmds = _read_command_list(path)
    except Exception as e:
        source.reply(RText(f'[CommandListExecuter] 读取失败: {e}').set_color(RColor.red))
        return

    if len(cmds) == 0:
        source.reply('[CommandListExecuter] 清单为空')
        return

    adds, setblocks, summons, merges, removes, others = _classify_commands(cmds)
    source.reply(
        '[CommandListExecuter] 总 {} 条 | add:{} | setblock:{}(并发) | summon:{} | merge:{} | remove:{} | 其它:{}'.format(
            len(cmds), len(adds), len(setblocks), len(summons), len(merges), len(removes), len(others)
        ))

    # 通过“锚点盔甲架”冻结原点：
    anchor_tag = f"cmdlist_anchor_{uuid.uuid4().hex}"

    def _is_rel(tok: object) -> bool:
        return isinstance(tok, str) and tok.strip().startswith('~')

    if _is_rel(x) or _is_rel(y) or _is_rel(z):
        player_name = _get_player_name_from_source(source)
        if not player_name:
            source.reply(RText('[CommandListExecuter] 相对坐标需要玩家来源').set_color(RColor.red))
            return
        # 在玩家当前位置对齐整块并生成锚点
        server.execute(
            f"execute as {player_name} at @s align xyz run summon armor_stand ~ ~ ~ {{Invisible:1b,NoGravity:1b,Marker:1b,Invulnerable:1b,Tags:[\"{anchor_tag}\"]}}"
        )
        # 将传入的 x y z 作为 positioned 偏移应用到锚点，再执行清单命令
        prefix = f"execute as @e[tag={anchor_tag},limit=1] at @s positioned {x} {y} {z} run "
    else:
        # 绝对坐标：直接在目标位置生成锚点
        try:
            ax = int(float(str(x)));
            ay = int(float(str(y)));
            az = int(float(str(z)))
        except Exception:
            source.reply(RText('[CommandListExecuter] 无法解析绝对坐标').set_color(RColor.red))
            return
        server.execute(
            f"summon armor_stand {ax} {ay} {az} {{Invisible:1b,NoGravity:1b,Marker:1b,Invulnerable:1b,Tags:[\"{anchor_tag}\"]}}"
        )
        prefix = f"execute as @e[tag={anchor_tag},limit=1] at @s run "

    t0 = perf_counter()

    # 1) 顺序执行 forceload add
    for c in adds:
        server.execute(prefix + c)

    # 2) 并发执行 setblock
    if setblocks:
        # 线程数默认 4，可由命令参数覆盖；且不超过任务数
        try:
            req_workers = int(threads) if threads is not None else 4
        except Exception:
            req_workers = 4
        if req_workers < 1:
            req_workers = 1
        workers = min(req_workers, len(setblocks))
        chunks = _chunkify(setblocks, workers)
        source.reply(f'[CommandListExecuter] 启动 {workers} 个线程并发执行 {len(setblocks)} 条 setblock')

        def run_chunk(chunk: list[str]):
            for cmd in chunk:
                server.execute(prefix + cmd)

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='cmdlist') as exe:
            futures = [exe.submit(run_chunk, ch) for ch in chunks]
            for fut in as_completed(futures):
                _ = fut.result()

    # 3) 顺序执行 summon
    for c in summons:
        server.execute(prefix + c)

    # 4) 顺序执行 data merge block
    for c in merges:
        server.execute(prefix + c)

    # 5) 顺序执行 forceload remove（必须最后）
    for c in removes:
        server.execute(prefix + c)

    elapsed = perf_counter() - t0
    source.reply(f'[CommandListExecuter] 执行完成，用时 {_format_duration(elapsed)}')
    # 清理锚点
    server.execute(f"kill @e[tag={anchor_tag}]")


def on_load(server: ServerInterface, old):
    server.register_help_message('!!execute', HELP)
    server.register_command(
        Literal('!!execute')
        .requires(
            lambda src: src.has_permission(PermissionLevel.ADMIN),
            lambda src: RText('[CommandListExecuter] 权限不足：需要 MCDR ADMIN 权限').set_color(RColor.red),
        )
        .then(
            Text('x').then(
                Text('y').then(
                    Text('z').then(
                        Text('path').runs(lambda src, ctx: run_execute(server, src, ctx)).then(
                            Integer('threads').runs(lambda src, ctx: run_execute(server, src, ctx))
                        )
                    )
                )
            )
        )
    )
