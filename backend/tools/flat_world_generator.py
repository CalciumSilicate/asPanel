# backend/tools/flat_world_generator.py

import base64
import io
import os
import shutil
import tempfile
import uuid
import nbtlib
from nbtlib import File
from nbtlib.tag import Compound, List as NbtList, String, Int, Long
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.tools.server_parser import parse_properties


# 将 leveldatgenerator/level.dat 嵌入为 BASE64
LEVEL_DAT_TEMPLATE_BASE64 = (
    "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"
)


def _ns_block_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValueError("空的方块名")
    if ":" not in name:
        return f"minecraft:{name}"
    return name


def _to_nbt_layers(layers_py: List[Dict[str, Any]]) -> NbtList[Compound]:
    items: List[Compound] = []
    for it in layers_py:
        block = _ns_block_name(str(it.get("block", "minecraft:air")))
        height = int(it.get("height", 1))
        if height <= 0:
            raise ValueError("层厚度必须为正整数")
        items.append(Compound({"block": String(block), "height": Int(height)}))
    return NbtList[Compound](items)


def _to_nbt_string_list(items: List[str]) -> NbtList[String]:
    return NbtList[String]([String(str(x)) for x in items])


def _ensure_worldgen_paths(data_compound: Compound, dimension_key: str) -> Compound:
    wgs = data_compound.get("WorldGenSettings")
    if wgs is None or not isinstance(wgs, Compound):
        wgs = Compound()
        data_compound["WorldGenSettings"] = wgs
    dims = wgs.get("dimensions")
    if dims is None or not isinstance(dims, Compound):
        dims = Compound()
        wgs["dimensions"] = dims
    dim = dims.get(dimension_key)
    if dim is None or not isinstance(dim, Compound):
        dim = Compound()
        dims[dimension_key] = dim
    gen = dim.get("generator")
    if gen is None or not isinstance(gen, Compound):
        gen = Compound()
        dim["generator"] = gen
    gen["type"] = String("minecraft:flat")  # 强制 flat
    settings = gen.get("settings")
    if settings is None or not isinstance(settings, Compound):
        settings = Compound()
        gen["settings"] = settings
    return settings


def _pick_dimension_key(data_compound: Compound, prefer_key: Optional[str]) -> str:
    wgs = data_compound.get("WorldGenSettings")
    candidate_keys: List[str] = []
    if wgs and isinstance(wgs.get("dimensions"), Compound):
        candidate_keys = list(wgs["dimensions"].keys())
    if prefer_key and (prefer_key in candidate_keys or not candidate_keys):
        return prefer_key
    if "minecraft:overworld" in candidate_keys:
        return "minecraft:overworld"
    if "minecraft:world" in candidate_keys:
        return "minecraft:world"
    return "minecraft:overworld"


def _seed_to_long(seed: Any) -> int:
    """支持数字字符串或任意字符串 -> 64 位有符号整数(FNV-1a 64 简化)。"""
    if seed is None or seed == "":
        return 0
    s = str(seed)
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    # FNV-1a 64
    hash_val = 0xCBF29CE484222325
    prime = 0x100000001B3
    for ch in s:
        hash_val ^= ord(ch)
        hash_val = (hash_val * prime) & 0xFFFFFFFFFFFFFFFF
    # 转为有符号
    if hash_val & (1 << 63):
        hash_val = -((~hash_val + 1) & 0xFFFFFFFFFFFFFFFF)
    return hash_val


def _load_template_file() -> File:
    """从内嵌 BASE64 载入模板 level.dat（保持 gzip）。"""
    raw = base64.b64decode(LEVEL_DAT_TEMPLATE_BASE64)
    # nbtlib.load 需文件路径或文件对象，这里写入临时文件再读取
    with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as f:
        f.write(raw)
        temp_path = f.name
    try:
        return nbtlib.load(temp_path)
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass


def generate_flat_level_dat(config: Dict[str, Any]) -> bytes:
    """根据配置生成 level.dat（gzip NBT 字节）。

    config 期望字段：
      - version / versionName: str
      - seed: str|int
      - layers: List[{block: str, height: int}]
      - structure_overrides / structureOverrides: List[str]
      - biomes / biome: List[str] or str（取第一项作为 biome）
      - dimension_key: Optional[str]
    """
    nbt_obj = _load_template_file()
    root = getattr(nbt_obj, "root", nbt_obj)  # 兼容不同 nbtlib
    if not isinstance(root, Compound):
        root = nbt_obj.root  # 尝试取 root

    # 确保 Data
    data = root.get("Data")
    if data is None or not isinstance(data, Compound):
        data = Compound()
        root["Data"] = data

    # LevelName 设置为 UUID
    data["LevelName"] = String(str(uuid.uuid4()))

    # Version.Name
    version_name = config.get("version") or config.get("versionName")
    if version_name:
        ver = data.get("Version")
        if ver is None or not isinstance(ver, Compound):
            ver = Compound()
            data["Version"] = ver
        ver["Name"] = String(str(version_name))

    # seed
    if "seed" in config and config.get("seed") not in (None, ""):
        wgs = data.get("WorldGenSettings")
        if wgs is None or not isinstance(wgs, Compound):
            wgs = Compound()
            data["WorldGenSettings"] = wgs
        wgs["seed"] = Long(int(_seed_to_long(config.get("seed"))))

    dim_key = _pick_dimension_key(data, config.get("dimension_key"))
    settings = _ensure_worldgen_paths(data, dim_key)

    # biome（取第一项）
    biome_value: Optional[str] = None
    if "biomes" in config and isinstance(config["biomes"], list) and config["biomes"]:
        biome_value = str(config["biomes"][0])
    elif "biome" in config and config["biome"]:
        biome_value = str(config["biome"])
    if biome_value:
        settings["biome"] = String(biome_value)
    else:
        # 若未提供群系，显式写入空字符串，交由游戏/后端后续逻辑处理
        settings["biome"] = String("")

    # layers
    layers = config.get("layers") or []
    if layers:
        settings["layers"] = _to_nbt_layers(layers)

    # structure_overrides
    structures = (
        config.get("structure_overrides")
        or config.get("structureOverrides")
        or []
    )
    if structures:
        settings["structure_overrides"] = _to_nbt_string_list(structures)
    else:
        # 若未提供结构覆盖，按需求写入空对象 {}
        settings["structure_overrides"] = Compound()

    # 导出 gzip NBT 字节
    # 使用 File 保存到内存
    file_obj = File(root)
    buf = io.BytesIO()
    file_obj.save(buf, gzipped=True)
    return buf.getvalue()


def apply_level_dat_to_server(
    server_root: str | Path,
    data_bytes: bytes,
    overwrite: bool = False,
    world_name: Optional[str] = None,
) -> Path:
    """将 level.dat 写入到指定服务器世界目录。

    - server_root: MCDR 实例根目录（包含 config.yml 的目录）
    - data_bytes: gzip NBT 的 level.dat 字节
    - overwrite: 如世界目录存在则是否删除再写入
    - world_name: 指定世界名；若为空则根据 server.properties 的 level-name 或默认 world
    返回：最终写入的 level.dat 路径
    """
    server_root = Path(server_root)
    server_dir = server_root / "server"
    server_dir.mkdir(parents=True, exist_ok=True)

    if not world_name:
        props = parse_properties(server_dir / "server.properties")
        world_name = str(props.get("level-name", "world"))
    world_path = server_dir / world_name

    if world_path.exists():
        if not overwrite:
            raise FileExistsError(
                f"世界目录已存在：{world_path}. 请设置 overwrite=True 以覆盖现有存档。"
            )
        shutil.rmtree(world_path, ignore_errors=True)

    world_path.mkdir(parents=True, exist_ok=True)
    out_path = world_path / "level.dat"
    with open(out_path, "wb") as f:
        f.write(data_bytes)
    return out_path
