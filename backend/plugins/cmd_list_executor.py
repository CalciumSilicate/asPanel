# backend/plugins/cmd_list_executor.py

from mcdreforged.api.all import *
from time import perf_counter
from pathlib import Path
import uuid

HELP = (
    '!!execute <x|~dx> <y|~dy> <z|~dz> <filename> [threads]  支持相对坐标 ~dx ~dy ~dz；以执行瞬间位置为固定原点'
    '（自动生成锚点盔甲架）。流程：add→fill→summon→merge→remove'
)


PLUGIN_METADATA = {
    "id": "cmd_list_executor",
    "version": "0.3.2",
    "author": "CalciumSilicate",
    "name": "CommandListExecutorINNER",
    "description": "批量执行指令清单",
    "dependencies": {},
    "requirements": ["mcdreforged>=2.14.0"]  # schedule_task 从 v2.14.0 起提供（Beta API） :contentReference[oaicite:1]{index=1}
}

# 每个 task 执行多少条 fill（按你服的承受能力调大/调小）
FILL_BATCH_SIZE = 64


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
    返回 (adds, fills, summons, merges, removes, others)
    """
    adds: list[str] = []
    fills: list[str] = []
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
        elif low.startswith('fill '):
            fills.append(c)
        elif low.startswith('summon '):
            summons.append(c)
        elif low.startswith('data merge block'):
            merges.append(c)
        else:
            others.append(c)
    return adds, fills, summons, merges, removes, others


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


def run_execute(server: ServerInterface, source: CommandSource, ctx: dict):
    if not source.has_permission(PermissionLevel.ADMIN):
        source.reply(RText('[CommandListExecuter] 权限不足：需要 MCDR ADMIN 权限').set_color(RColor.red))
        return

    x = ctx.get('x')
    y = ctx.get('y')
    z = ctx.get('z')
    path = ctx.get('path')
    try:
        cmds = _read_command_list(path)
    except Exception as e:
        source.reply(RText(f'[CommandListExecuter] 读取失败: {e}').set_color(RColor.red))
        return

    if len(cmds) == 0:
        source.reply('[CommandListExecuter] 清单为空')
        return

    adds, fills, summons, merges, removes, others = _classify_commands(cmds)
    source.reply(
        '[CommandListExecuter] 总 {} 条 | add:{} | fill:{} | summon:{} | merge:{} | remove:{} | 其它:{}'.format(
            len(cmds), len(adds), len(fills), len(summons), len(merges), len(removes), len(others)
        ))

    server.execute("gamerule sendCommandFeedback false")
    anchor_tag = f"cmdlist_anchor_{uuid.uuid4().hex}"

    def _cleanup():
        # 清理锚点 + 恢复 gamerule（尽量保证最后能恢复）
        server.execute(f"kill @e[tag={anchor_tag}]")
        server.execute("gamerule sendCommandFeedback true")

    def _is_rel(tok: object) -> bool:
        return isinstance(tok, str) and tok.strip().startswith('~')

    # 计算执行前缀（固定原点锚点）
    if _is_rel(x) or _is_rel(y) or _is_rel(z):
        player_name = _get_player_name_from_source(source)
        if not player_name:
            source.reply(RText('[CommandListExecuter] 相对坐标需要玩家来源').set_color(RColor.red))
            _cleanup()
            return
        server.execute(
            f"execute as {player_name} at @s align xyz run summon armor_stand ~ ~ ~ "
            f"{{Invisible:1b,NoGravity:1b,Marker:1b,Invulnerable:1b,Tags:[\"{anchor_tag}\"]}}"
        )
        prefix = f"execute as @e[tag={anchor_tag},limit=1] at @s positioned {x} {y} {z} run "
    else:
        try:
            ax = int(float(str(x)))
            ay = int(float(str(y)))
            az = int(float(str(z)))
        except Exception:
            source.reply(RText('[CommandListExecuter] 无法解析绝对坐标').set_color(RColor.red))
            _cleanup()
            return
        server.execute(
            f"summon armor_stand {ax} {ay} {az} "
            f"{{Invisible:1b,NoGravity:1b,Marker:1b,Invulnerable:1b,Tags:[\"{anchor_tag}\"]}}"
        )
        prefix = f"execute as @e[tag={anchor_tag},limit=1] at @s run "

    # 用闭包贯穿计时（跨 task）
    t0 = perf_counter()

    def _final_success():
        elapsed = perf_counter() - t0
        source.reply(f'[CommandListExecuter] 执行完成，用时 {_format_duration(elapsed)}')
        _cleanup()

    def _final_error(e: Exception):
        source.reply(RText(f'[CommandListExecuter] 执行中断: {e}').set_color(RColor.red))
        _cleanup()

    def _after_fills():
        """fill 全部跑完后，继续 summon/merge/remove（保持原来的顺序约束）"""
        try:
            # 3) 顺序执行 summon
            for c in summons:
                server.execute(prefix + c)

            # 4) 顺序执行 data merge block
            for c in merges:
                server.execute(prefix + c)

            # 5) 顺序执行 forceload remove（必须最后）
            for c in removes:
                server.execute(prefix + c)

            _final_success()
        except Exception as e:
            _final_error(e)

    def _run_fill_batch(start_idx: int = 0):
        """用 schedule_task 分批执行 fill，避免一次性在同一个回调里跑完"""
        try:
            end = min(start_idx + FILL_BATCH_SIZE, len(fills))
            for c in fills[start_idx:end]:
                server.execute(prefix + c)

            if end < len(fills):
                # 继续排队下一批
                server.schedule_task(lambda: _run_fill_batch(end))  # :contentReference[oaicite:2]{index=2}
            else:
                # fill 结束，排队后续阶段
                server.schedule_task(_after_fills)  # :contentReference[oaicite:3]{index=3}
        except Exception as e:
            _final_error(e)

    try:
        # 1) 顺序执行 forceload add
        for c in adds:
            server.execute(prefix + c)

        # 2) fill：改为 schedule_task 分批处理
        if fills:
            if hasattr(server, 'schedule_task'):
                server.schedule_task(lambda: _run_fill_batch(0))  # :contentReference[oaicite:4]{index=4}
            else:
                # 兼容极老版本：直接执行（但你既然要 schedule_task，建议直接提高 requirements）
                for c in fills:
                    server.execute(prefix + c)
                _after_fills()
        else:
            # 没有 fill，直接进入后续阶段
            _after_fills()

    except Exception as e:
        _final_error(e)


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
                        Text('path').runs(lambda src, ctx: run_execute(server, src, ctx))
                    )
                )
            )
        )
    )
