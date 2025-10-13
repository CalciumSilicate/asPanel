from __future__ import annotations

"""
backend/tools/litematic_parser.py

功能：
- 解析 .litematic 文件，生成相对坐标的命令清单（command list，.mccl.txt）。
- 参考 reference/litematic_to_command_list.py 的实现，做轻量封装供路由调用。

依赖：litemapy, nbtlib
"""

from pathlib import Path
from typing import List, Sequence, Tuple
from datetime import datetime
from backend.core.config import LITEMATIC_COMMAND_LIST_PATH

try:
    from litemapy import Schematic
except Exception as e:  # 延迟导入异常，便于上层捕获并返回合理错误
    Schematic = None  # type: ignore
    _litemapy_import_error = e
else:
    _litemapy_import_error = None

try:
    import nbtlib
except Exception as e:  # 同上
    nbtlib = None  # type: ignore
    _nbtlib_import_error = e
else:
    _nbtlib_import_error = None


def _ensure_imports():
    if _litemapy_import_error is not None:
        raise RuntimeError(f"litemapy 未安装或导入失败: {_litemapy_import_error}")
    if _nbtlib_import_error is not None:
        raise RuntimeError(f"nbtlib 未安装或导入失败: {_nbtlib_import_error}")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _quote_snbt_string(s: str) -> str:
    s = s.replace("\\", "\\\\").replace("\"", "\\\"")
    return f'"{s}"'


def _to_snbt(tag: "nbtlib.tag.Base") -> str:  # type: ignore[name-defined]
    from nbtlib import tag as T  # type: ignore

    if isinstance(tag, T.Byte):
        return f"{int(tag)}b"
    if isinstance(tag, T.Short):
        return f"{int(tag)}s"
    if isinstance(tag, T.Int):
        return f"{int(tag)}"
    if isinstance(tag, T.Long):
        return f"{int(tag)}l"
    if isinstance(tag, T.Float):
        val = float(tag)
        if val == int(val):
            return f"{int(val)}.0f"
        return f"{val}f"
    if isinstance(tag, T.Double):
        val = float(tag)
        if val == int(val):
            return f"{int(val)}.0d"
        return f"{val}d"
    if isinstance(tag, T.String):
        return _quote_snbt_string(str(tag))

    if isinstance(tag, T.ByteArray):
        elems = ",".join(f"{int(x)}b" for x in tag)
        return f"[B;{elems}]"
    if isinstance(tag, T.IntArray):
        elems = ",".join(str(int(x)) for x in tag)
        return f"[I;{elems}]"
    if isinstance(tag, T.LongArray):
        elems = ",".join(f"{int(x)}l" for x in tag)
        return f"[L;{elems}]"

    if isinstance(tag, T.List):
        elems = ",".join(_to_snbt(x) for x in tag)
        return f"[{elems}]"

    if isinstance(tag, T.Compound):
        items = [f"{_quote_snbt_string(k)}:{_to_snbt(v)}" for k, v in tag.items()]
        return "{" + ",".join(items) + "}"

    if isinstance(tag, dict):
        items = [f"{_quote_snbt_string(str(k))}:{_to_snbt(v)}" for k, v in tag.items()]
        return "{" + ",".join(items) + "}"
    if isinstance(tag, (list, tuple)):
        return "[" + ",".join(_to_snbt(x) for x in tag) + "]"
    if isinstance(tag, str):
        return _quote_snbt_string(tag)
    if isinstance(tag, bool):
        return "1b" if tag else "0b"
    if isinstance(tag, int):
        return str(tag)
    if isinstance(tag, float):
        if tag == int(tag):
            return f"{int(tag)}.0d"
        return f"{tag}d"
    return _quote_snbt_string(str(tag))


def _patch_missing_pending_ticks(root: "nbtlib.tag.Compound") -> None:  # type: ignore[name-defined]
    try:
        regions = root.get("Regions") or root.get("regions")
        if not regions:
            return
        for _name, reg_nbt in regions.items():
            if "PendingBlockTicks" not in reg_nbt:
                reg_nbt["PendingBlockTicks"] = nbtlib.tag.List([])  # type: ignore
            if "PendingFluidTicks" not in reg_nbt:
                reg_nbt["PendingFluidTicks"] = nbtlib.tag.List([])  # type: ignore
    except Exception:
        pass


def _load_schematic_robust(file_path: str | Path) -> "Schematic":  # type: ignore[name-defined]
    _ensure_imports()
    try:
        return Schematic.load(str(file_path))  # type: ignore
    except Exception as e:
        try:
            nbt_obj = nbtlib.load(str(file_path))  # type: ignore
            root = getattr(nbt_obj, "root", nbt_obj)
            _patch_missing_pending_ticks(root)
            return Schematic.from_nbt(root)  # type: ignore
        except Exception:
            raise e


def _gather_commands_relative(
    schem: "Schematic",  # type: ignore[name-defined]
    offset: Tuple[int, int, int] = (0, 0, 0),
    place_air: bool = False,
) -> Tuple[List[str], List[str], List[str], List[Tuple[int, int]]]:
    """
    生成相对坐标的命令序列：setblock / summon / data merge 及 forceload 区块偏移列表。
    返回：blocks_cmds, summons_cmds, merges_cmds, chunk_offsets
    """
    import math

    ox, oy, oz = offset
    blocks_cmds: List[str] = []
    summons_cmds: List[str] = []
    merges_cmds: List[str] = []
    used_chunks: set[Tuple[int, int]] = set()

    # 计算 schematic 全局最小坐标
    global_min_x = None
    global_min_y = None
    global_min_z = None
    for reg in schem.regions.values():
        try:
            rx_min = min(reg.xrange()) + reg.x
            ry_min = min(reg.yrange()) + reg.y
            rz_min = min(reg.zrange()) + reg.z
        except Exception:
            rx_min, ry_min, rz_min = reg.x, reg.y, reg.z
        global_min_x = rx_min if global_min_x is None else min(global_min_x, rx_min)
        global_min_y = ry_min if global_min_y is None else min(global_min_y, ry_min)
        global_min_z = rz_min if global_min_z is None else min(global_min_z, rz_min)
    if global_min_x is None:
        global_min_x, global_min_y, global_min_z = 0, 0, 0

    # 遍历方块
    for reg in schem.regions.values():
        for x, y, z in reg.allblockpos():
            bs = reg[x, y, z]
            if not place_air and bs.id == "minecraft:air":
                continue
            sx, sy, sz = reg.x + x, reg.y + y, reg.z + z
            dx = int(math.floor((sx - global_min_x) + ox))
            dy = int(math.floor((sy - global_min_y) + oy))
            dz = int(math.floor((sz - global_min_z) + oz))
            state_id = bs.to_block_state_identifier()
            blocks_cmds.append(f"setblock ~{dx} ~{dy} ~{dz} {state_id} replace")
            used_chunks.update({
                (dx // 16 * 16 + ux, dz // 16 * 16 + uz)
                for ux in (-1, 0, 1)
                for uz in (-1, 0, 1)
            })

        # 实体
        for ent in getattr(reg, "entities", []) or []:
            eid = ent.id
            ex, ey, ez = ent.position
            sx, sy, sz = reg.x + ex, reg.y + ey, reg.z + ez
            dx = sx - global_min_x + ox
            dy = sy - global_min_y + oy
            dz = sz - global_min_z + oz
            nbt = ent.to_nbt()
            try:
                for k in ("id", "Pos", "UUID", "UUIDMost", "UUIDLeast"):
                    if k in nbt:
                        del nbt[k]
            except Exception:
                pass
            if "TileX" in nbt:
                nbt["TileX"] = nbtlib.Int(dx)
            if "TileY" in nbt:
                nbt["TileY"] = nbtlib.Int(dy)
            if "TileZ" in nbt:
                nbt["TileZ"] = nbtlib.Int(dz)
            snbt = _to_snbt(nbt)
            summons_cmds.append(f"summon {eid} ~{dx} ~{dy} ~{dz} {snbt}")
            used_chunks.update({
                (dx // 16 * 16 + ux, dz // 16 * 16 + uz)
                for ux in (-1, 0, 1)
                for uz in (-1, 0, 1)
            })

        # 方块实体
        for te in getattr(reg, "tile_entities", []) or []:
            tx, ty, tz = te.position
            sx, sy, sz = reg.x + tx, reg.y + ty, reg.z + tz
            dx = int(math.floor((sx - global_min_x) + ox))
            dy = int(math.floor((sy - global_min_y) + oy))
            dz = int(math.floor((sz - global_min_z) + oz))
            tnbt = te.to_nbt()
            try:
                for k in ("x", "y", "z"):
                    if k in tnbt:
                        del tnbt[k]
            except Exception:
                pass
            snbt = _to_snbt(tnbt)
            merges_cmds.append(f"data merge block ~{dx} ~{dy} ~{dz} {snbt}")
            used_chunks.update({
                (dx // 16 * 16 + ux, dz // 16 * 16 + uz)
                for ux in (-1, 0, 1)
                for uz in (-1, 0, 1)
            })

    chunk_offsets = sorted(list(set(used_chunks)))
    return blocks_cmds, summons_cmds, merges_cmds, chunk_offsets


def generate_command_list(
    input_litematic: Path,
    output_txt: Path,
    offset: Tuple[int, int, int] = (0, 0, 0),
    place_air: bool = False,
) -> Path:
    """
    从 .litematic 生成命令清单，写入 output_txt 并返回路径。
    - 生成顺序：forceload add -> setblock -> summon -> data merge -> forceload remove
    - 坐标采用相对坐标（~dx ~dy ~dz）
    """
    _ensure_imports()

    input_litematic = input_litematic.resolve()
    output_txt = output_txt.resolve()
    _ensure_dir(output_txt.parent)

    schem = _load_schematic_robust(input_litematic)
    blocks_cmds, summons_cmds, merges_cmds, chunk_offsets = _gather_commands_relative(
        schem, offset=offset, place_air=place_air
    )

    add_cmds = [f"forceload add ~{cx} ~{cz}" for (cx, cz) in chunk_offsets]
    remove_cmds = [f"forceload remove ~{cx} ~{cz}" for (cx, cz) in chunk_offsets]

    lines: List[str] = []
    lines.append("# Generated by backend.tools.litematic_parser")
    lines.append("# Order: forceload add -> setblock -> summon -> data merge -> forceload remove")
    lines.append("# Coordinates are relative (~dx ~dy ~dz) to execution origin")
    lines.extend(add_cmds)
    lines.extend(blocks_cmds)
    lines.extend(summons_cmds)
    lines.extend(merges_cmds)
    lines.extend(remove_cmds)

    output_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_txt


def get_command_list_output_path_for(litematic_path: Path) -> Path:
    """基于 litematic 物理文件路径（UUID.litematic）计算对应的命令清单输出路径。"""
    uuid_stem = Path(litematic_path).stem
    return LITEMATIC_COMMAND_LIST_PATH / f"{uuid_stem}.mccl.txt"


def has_command_list_for(litematic_path: Path) -> bool:
    """判断指定 litematic 是否已有生成的命令清单（仅检查物理文件存在）。"""
    return get_command_list_output_path_for(litematic_path).exists()


def get_command_list_output_file_name_for(litematic_path: Path) -> str:
    """返回对应 mccl 的文件名（不包含目录路径）。"""
    return get_command_list_output_path_for(litematic_path).name
