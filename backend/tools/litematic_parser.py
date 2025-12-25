# backend/tools/litematic_parser.py

import math
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple

import nbtlib
from litemapy import Schematic

from backend.core.constants import LITEMATIC_COMMAND_LIST_PATH

MAX_FILL_VOLUME = 32768


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


def _merge_points_to_cuboids(
    pts: set[Tuple[int, int, int]],
) -> List[Tuple[int, int, int, int, int, int]]:
    """
    把离散点集合并成“完全填满”的长方体列表。
    返回 cuboid: (x1,x2,y1,y2,z1,z2)
    """
    if not pts:
        return []

    # Step 1: (y,z) 内按 x 合并成连续段
    yz_to_xs: dict[Tuple[int, int], List[int]] = defaultdict(list)
    for (x, y, z) in pts:
        yz_to_xs[(y, z)].append(x)

    yz_to_segments: dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for (y, z), xs in yz_to_xs.items():
        xs.sort()
        segs: List[Tuple[int, int]] = []
        s = e = xs[0]
        for xx in xs[1:]:
            if xx == e + 1:
                e = xx
            else:
                segs.append((s, e))
                s = e = xx
        segs.append((s, e))
        yz_to_segments[(y, z)] = segs

    # Step 2: 固定 y，把相同 (x1,x2) 的段沿 z 合并成矩形面
    # rect: (y, x1,x2, z1,z2)
    y_to_map: dict[int, dict[Tuple[int, int], List[int]]] = defaultdict(lambda: defaultdict(list))
    for (y, z), segs in yz_to_segments.items():
        for (x1, x2) in segs:
            y_to_map[y][(x1, x2)].append(z)

    rects: List[Tuple[int, int, int, int, int]] = []
    for y, segmap in y_to_map.items():
        for (x1, x2), zs in segmap.items():
            zs.sort()
            s = e = zs[0]
            for zz in zs[1:]:
                if zz == e + 1:
                    e = zz
                else:
                    rects.append((y, x1, x2, s, e))
                    s = e = zz
            rects.append((y, x1, x2, s, e))

    # Step 3: 相同 (x1,x2,z1,z2) 的矩形面沿 y 合并成长方体
    key_to_ys: dict[Tuple[int, int, int, int], List[int]] = defaultdict(list)
    for (y, x1, x2, z1, z2) in rects:
        key_to_ys[(x1, x2, z1, z2)].append(y)

    cuboids: List[Tuple[int, int, int, int, int, int]] = []
    for (x1, x2, z1, z2), ys in key_to_ys.items():
        ys.sort()
        s = e = ys[0]
        for yy in ys[1:]:
            if yy == e + 1:
                e = yy
            else:
                cuboids.append((x1, x2, s, e, z1, z2))
                s = e = yy
        cuboids.append((x1, x2, s, e, z1, z2))

    return cuboids


def _split_cuboid_to_limit(
    cuboid: Tuple[int, int, int, int, int, int],
    limit: int = MAX_FILL_VOLUME,
) -> List[Tuple[int, int, int, int, int, int]]:
    """
    把超出 fill 体积上限的长方体切分为多个 <=limit 的长方体。
    """
    x1, x2, y1, y2, z1, z2 = cuboid
    lx = x2 - x1 + 1
    ly = y2 - y1 + 1
    lz = z2 - z1 + 1
    vol = lx * ly * lz
    if vol <= limit:
        return [cuboid]

    # 优先找一个轴：切成若干段，每段长度 <= max_len 就能保证子块 <=limit（other <= limit）
    axes = [
        ("x", lx, ly * lz),
        ("y", ly, lx * lz),
        ("z", lz, lx * ly),
    ]
    candidates: List[Tuple[int, int, str, int]] = []
    for name, laxis, other in axes:
        if other <= limit:
            max_len = max(1, limit // other)
            chunks = (laxis + max_len - 1) // max_len
            candidates.append((chunks, -laxis, name, max_len))

    if candidates:
        candidates.sort()
        _, _, axis, max_len = candidates[0]
    else:
        # 三个 other 都 > limit：对最长轴对半切，递归继续（保证收敛）
        axis = "x" if lx >= ly and lx >= lz else ("y" if ly >= lx and ly >= lz else "z")
        longest = lx if axis == "x" else (ly if axis == "y" else lz)
        max_len = max(1, longest // 2)

    out: List[Tuple[int, int, int, int, int, int]] = []
    if axis == "x":
        cur = x1
        while cur <= x2:
            nx2 = min(x2, cur + max_len - 1)
            out.extend(_split_cuboid_to_limit((cur, nx2, y1, y2, z1, z2), limit))
            cur = nx2 + 1
    elif axis == "y":
        cur = y1
        while cur <= y2:
            ny2 = min(y2, cur + max_len - 1)
            out.extend(_split_cuboid_to_limit((x1, x2, cur, ny2, z1, z2), limit))
            cur = ny2 + 1
    else:
        cur = z1
        while cur <= z2:
            nz2 = min(z2, cur + max_len - 1)
            out.extend(_split_cuboid_to_limit((x1, x2, y1, y2, cur, nz2), limit))
            cur = nz2 + 1

    return out


def _blocks_to_fill_cmds(
    blocks_by_state: dict[str, set[Tuple[int, int, int]]],
    limit: int = MAX_FILL_VOLUME,
) -> List[str]:
    """
    把同 blockstate 的离散 setblock 点集压缩成 fill 长方体集合，并确保单条 fill 体积 <= limit。
    合并策略：X 连续段 -> Z 连续面 -> Y 连续体（只在完全填满的情况下合并，不会“填到空洞”）。
    """
    out: List[str] = []
    for state_id, pts in blocks_by_state.items():
        if not pts:
            continue

        cuboids = _merge_points_to_cuboids(pts)

        final_cuboids: List[Tuple[int, int, int, int, int, int]] = []
        for c in cuboids:
            final_cuboids.extend(_split_cuboid_to_limit(c, limit))

        # 稳定排序，避免输出顺序漂移（不保证等同原 setblock 顺序）
        final_cuboids.sort(key=lambda t: (t[2], t[4], t[0], t[3], t[5], t[1]))  # y1,z1,x1,y2,z2,x2

        for (x1, x2, y1, y2, z1, z2) in final_cuboids:
            out.append(f"fill ~{x1} ~{y1} ~{z1} ~{x2} ~{y2} ~{z2} {state_id} replace")

    return out


def _gather_commands_relative(
    schem: "Schematic",  # type: ignore[name-defined]
    offset: Tuple[int, int, int] = (0, 0, 0),
    place_air: bool = False,
    compress_blocks_to_fill: bool = True,
) -> Tuple[List[str], List[str], List[str], List[Tuple[int, int]]]:
    """
    生成相对坐标的命令序列：fill(or setblock) / summon / data merge 及 forceload 区块偏移列表。
    返回：blocks_cmds, summons_cmds, merges_cmds, chunk_offsets

    注意：按你的要求，这里的 forceload add/remove 使用的是 x z（不是 chunkX chunkZ）。
    （保持你原来“对齐到 16 并在周围 +-1”的行为）
    """
    ox, oy, oz = offset

    blocks_cmds: List[str] = []
    summons_cmds: List[str] = []
    merges_cmds: List[str] = []

    # 收集 blockstate -> 坐标点
    blocks_by_state: dict[str, set[Tuple[int, int, int]]] = defaultdict(set)

    # 用于 forceload：记录“16 对齐后的基准 x/z”（等价于你原来的 dx//16*16, dz//16*16）
    used_core_xz: set[Tuple[int, int]] = set()

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

            if compress_blocks_to_fill:
                blocks_by_state[state_id].add((dx, dy, dz))
            else:
                blocks_cmds.append(f"setblock ~{dx} ~{dy} ~{dz} {state_id} replace")

            # 按你的要求：forceload 用 x z（保持你原对齐方式）
            base_x = (dx // 16) * 16
            base_z = (dz // 16) * 16
            used_core_xz.add((base_x, base_z))

        # 实体
        for ent in getattr(reg, "entities", []) or []:
            eid = ent.id
            ex, ey, ez = ent.position
            sx, sy, sz = reg.x + ex, reg.y + ey, reg.z + ez
            dx_f = sx - global_min_x + ox
            dy_f = sy - global_min_y + oy
            dz_f = sz - global_min_z + oz
            nbt = ent.to_nbt()
            try:
                for k in ("id", "Pos", "UUID", "UUIDMost", "UUIDLeast"):
                    if k in nbt:
                        del nbt[k]
            except Exception:
                pass
            if "TileX" in nbt:
                nbt["TileX"] = nbtlib.Int(dx_f)
            if "TileY" in nbt:
                nbt["TileY"] = nbtlib.Int(dy_f)
            if "TileZ" in nbt:
                nbt["TileZ"] = nbtlib.Int(dz_f)
            snbt = _to_snbt(nbt)
            summons_cmds.append(f"summon {eid} ~{dx_f} ~{dy_f} ~{dz_f} {snbt}")

            # forceload x z：这里用实体坐标的“落方块”位置来对齐
            edx = int(math.floor(dx_f))
            edz = int(math.floor(dz_f))
            base_x = (edx // 16) * 16
            base_z = (edz // 16) * 16
            used_core_xz.add((base_x, base_z))

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

            base_x = (dx // 16) * 16
            base_z = (dz // 16) * 16
            used_core_xz.add((base_x, base_z))

    # 压缩输出 fill
    if compress_blocks_to_fill:
        blocks_cmds = _blocks_to_fill_cmds(blocks_by_state, limit=MAX_FILL_VOLUME)

    # 生成 forceload 的 x z 列表：保持你原来的 (base + ux/uz)，ux/uz = -1,0,1
    used_xz: set[Tuple[int, int]] = set()
    for (bx, bz) in used_core_xz:
        for ux in (-1, 0, 1):
            for uz in (-1, 0, 1):
                used_xz.add((bx + ux, bz + uz))

    chunk_offsets = sorted(list(used_xz))
    return blocks_cmds, summons_cmds, merges_cmds, chunk_offsets


def generate_command_list(
    input_litematic: Path,
    output_txt: Path,
    offset: Tuple[int, int, int] = (0, 0, 0),
    place_air: bool = False,
    compress_blocks_to_fill: bool = True,
) -> Path:
    """
    从 .litematic 生成命令清单，写入 output_txt 并返回路径。
    - 生成顺序：forceload add -> fill(or setblock) -> summon -> data merge -> forceload remove
    - 坐标采用相对坐标（~dx ~dy ~dz）
    """

    input_litematic = input_litematic.resolve()
    output_txt = output_txt.resolve()
    _ensure_dir(output_txt.parent)

    schem = _load_schematic_robust(input_litematic)
    blocks_cmds, summons_cmds, merges_cmds, chunk_offsets = _gather_commands_relative(
        schem,
        offset=offset,
        place_air=place_air,
        compress_blocks_to_fill=compress_blocks_to_fill,
    )

    add_cmds = [f"forceload add ~{cx} ~{cz}" for (cx, cz) in chunk_offsets]
    remove_cmds = [f"forceload remove ~{cx} ~{cz}" for (cx, cz) in chunk_offsets]

    lines: List[str] = []
    lines.append("# Generated by backend.tools.litematic_parser")
    lines.append("# Order: forceload add -> fill(or setblock) -> summon -> data merge -> forceload remove")
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
