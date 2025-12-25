import io
import os
import platform
import math
import json
import httpx
import functools
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import matplotlib
import matplotlib.ticker as ticker

# 设置后端，必须在 pyplot 之前
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import PchipInterpolator
from matplotlib import font_manager as fm

try:
    from backend.core.constants import BASE_DIR
except ImportError:
    BASE_DIR = Path(".")

# ========= 字体路径配置 =========
FONT_REGULAR_PATH = BASE_DIR / "backend/resources/fonts/MapleMono-NF-CN-Regular.ttf"
FONT_BOLD_PATH = BASE_DIR / "backend/resources/fonts/MapleMono-NF-CN-Bold.ttf"

# ========= 配置与主题 =========

class Theme:
    # 颜色配置保持不变
    BG_COLOR = (248, 249, 252)
    CARD_BG = (255, 255, 255)
    SHADOW_COLOR = (20, 30, 60, 20)
    
    TEXT_PRIMARY = (30, 35, 50)
    TEXT_SECONDARY = (130, 140, 160)
    TEXT_ACCENT = (100, 100, 255)
    ONLINE_COLOR = (34, 197, 94)
    POSITIVE = (16, 185, 129)
    NEGATIVE = (239, 68, 68)

    # 图表颜色
    CHART_LINE_COLOR = "#6366f1"
    CHART_FILL_COLOR = "#818cf8"
    
    # 地图相关颜色保持不变...
    DIM_NETHER_COLOR = (239, 68, 68)
    DIM_OVERWORLD_COLOR = (16, 185, 129)
    DIM_END_COLOR = (168, 85, 247)
    PATH_DEFAULT_COLOR = (96, 165, 250)
    ARROW_NETHER = (127, 29, 29)
    ARROW_OVERWORLD = (6, 78, 59)
    ARROW_END = (88, 28, 135)
    ARROW_DEFAULT = (30, 58, 138)
    MAP_LINE_COLOR = (203, 213, 225)
    MAP_NODE_BG = (255, 255, 255)
    MAP_NODE_BORDER = (148, 163, 184)

    # === [核心修改] 布局常量 ===
    WIDTH = 1800          # 总宽度拉宽
    PADDING = 50          # 边距
    LEFT_PANEL_WIDTH = 650  # 左侧数据栏宽度
    COLUMN_GAP = 40       # 左右栏间距
    CARD_RADIUS = 24

# ========= 字体管理 =========

def get_default_font_path(font_type="regular"):
    system = platform.system()
    if system == "Windows":
        if font_type == "bold":
            candidates = ["msyhbd.ttc", "arialbd.ttf", "simhei.ttf"]
        else:
            candidates = ["msyh.ttc", "arial.ttf", "simsun.ttc"]
        font_dir = "C:\\Windows\\Fonts"
        for font in candidates:
            path = os.path.join(font_dir, font)
            if os.path.exists(path):
                return path
    elif system == "Darwin":
        return "/System/Library/Fonts/PingFang.ttc"
    elif system == "Linux":
        candidates = [
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
    return None

@functools.lru_cache(maxsize=128)
def load_font(size: int, is_bold: bool = False) -> ImageFont.FreeTypeFont:
    preferred_path = FONT_BOLD_PATH if is_bold else FONT_REGULAR_PATH
    try:
        if preferred_path and os.path.exists(preferred_path):
            return ImageFont.truetype(str(preferred_path), size)
    except Exception:
        pass
    font_path = get_default_font_path("bold" if is_bold else "regular")
    try:
        if font_path and os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    except Exception:
        pass
    return ImageFont.load_default()

# ========= 文本处理辅助函数 (新增修复重叠的关键) =========

def truncate_text(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: float) -> str:
    """
    如果文本超过 max_width，则截断并添加 '...'
    """
    if not text:
        return ""
    text_w = draw.textlength(text, font=font)
    if text_w <= max_width:
        return text
    
    # 二分法或简单递减查找合适的长度，这里使用简单递减
    ellipsis_w = draw.textlength("...", font=font)
    avail_w = max_width - ellipsis_w
    if avail_w <= 0:
        return "..."
    
    # 估算字符数量以加速
    avg_char_w = text_w / len(text)
    approx_len = int(avail_w / avg_char_w) + 2
    current_text = text[:approx_len]
    
    while len(current_text) > 0:
        if draw.textlength(current_text, font=font) <= avail_w:
            return current_text + "..."
        current_text = current_text[:-1]
    
    return "..."

# ========= Matplotlib 字体初始化 =========

_MPL_FONT_INITIALIZED = False

def ensure_mpl_font():
    global _MPL_FONT_INITIALIZED
    if _MPL_FONT_INITIALIZED:
        return
    try:
        font_path = None
        if FONT_REGULAR_PATH and os.path.exists(FONT_REGULAR_PATH):
            font_path = str(FONT_REGULAR_PATH)
        else:
            fallback = get_default_font_path("regular")
            if fallback and os.path.exists(fallback):
                font_path = fallback
        if not font_path:
            return
        prop = fm.FontProperties(fname=font_path)
        fm.fontManager.addfont(font_path)
        font_name = prop.get_name()
        plt.rcParams["font.family"] = font_name
        plt.rcParams["axes.unicode_minus"] = False
        _MPL_FONT_INITIALIZED = True
    except Exception:
        pass

# ========= 通用工具函数 =========

def draw_shadow(img: Image.Image, bbox: Tuple[int, int, int, int], radius: int, blur: int = 20, offset=(0, 8)):
    x0, y0, x1, y1 = map(int, bbox)
    w, h = x1 - x0, y1 - y0
    shadow_w = w + blur * 4
    shadow_h = h + blur * 4
    shadow_img = Image.new("RGBA", (shadow_w, shadow_h), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_img)
    sx0 = blur * 2 + offset[0]
    sy0 = blur * 2 + offset[1]
    shadow_draw.rounded_rectangle((sx0, sy0, sx0 + w, sy0 + h), radius=radius, fill=Theme.SHADOW_COLOR)
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(shadow_img, (x0 - blur * 2, y0 - blur * 2))

@functools.lru_cache(maxsize=64)
def _cached_circle_avatar(img_path: str, size: int) -> Image.Image:
    try:
        if img_path and (img_path.startswith("http://") or img_path.startswith("https://")):
            resp = httpx.get(img_path, timeout=5.0)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        elif not os.path.exists(img_path):
            raise FileNotFoundError
        else:
            img = Image.open(img_path).convert("RGBA")
    except Exception:
        img = Image.new("RGBA", (size, size), (220, 220, 220))
        d = ImageDraw.Draw(img)
        font = load_font(size // 2, is_bold=True)
        d.text((size / 2, size / 2), "?", fill=(150, 150, 150), font=font, anchor="mm")
    img = img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

def crop_circle_avatar(img_path: str, size: int) -> Image.Image:
    return _cached_circle_avatar(img_path or "", size).copy()

@functools.lru_cache(maxsize=512)
def _cached_arrow_marker(angle_deg: float, size: int, color: Tuple[int, int, int]) -> Image.Image:
    canvas_size = int(size * 1.5)
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = canvas_size / 2, canvas_size / 2
    half = size / 2
    p1 = (cx + half, cy)
    p2 = (cx - half, cy - half * 0.7)
    p3 = (cx - half, cy + half * 0.7)
    p4 = (cx - half * 0.4, cy)
    d.polygon([p1, p2, p4, p3], fill=color)
    return img.rotate(-angle_deg, resample=Image.BICUBIC)

def _load_json(path: str) -> Dict:
    if not path or not os.path.exists(path):
        return {"nodes": {}, "edges": []}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON {path}: {e}")
        return {"nodes": {}, "edges": []}

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c * 2 for c in hex_str])
    try:
        return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (200, 200, 200)

def _extract_map_json_paths(map_config: Any) -> Tuple[Optional[str], Optional[str]]:
    if not map_config:
        return None, None
    if isinstance(map_config, dict):
        nether_json = map_config.get("nether_json") or map_config.get("the_nether") or map_config.get("the_overworld")
        end_json = map_config.get("end_json") or map_config.get("the_end")
    else:
        nether_json = getattr(map_config, "nether_json", None) or getattr(map_config, "the_nether", None) or getattr(map_config, "the_overworld", None)
        end_json = getattr(map_config, "end_json", None) or getattr(map_config, "the_end", None)
    return (str(nether_json) if nether_json else None, str(end_json) if end_json else None)

def _resolve_map_json_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    s = str(path)
    if os.path.exists(s):
        return s
    try:
        candidate = str((BASE_DIR / s).resolve())
        if os.path.exists(candidate):
            return candidate
    except Exception:
        pass
    return s

# ========= 图表生成逻辑 (Stats) =========

def create_smooth_chart(width: int, height: int, x_labels: List[str], values: List[float], label: str) -> Image.Image:
    ensure_mpl_font()
    dpi = 150
    fig_w, fig_h = width / dpi, height / dpi
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)

    x = np.array(range(len(values)))
    y = np.array(values)
    y_min, y_max = np.min(y), np.max(y)
    y_spread = y_max - y_min
    if y_spread == 0:
        y_spread = 1 if y_max == 0 else y_max * 0.1

    if len(values) > 2:
        x_smooth = np.linspace(x.min(), x.max(), 300)
        try:
            pch = PchipInterpolator(x, y)
            y_smooth = pch(x_smooth)
        except Exception:
            x_smooth, y_smooth = x, y
    else:
        x_smooth, y_smooth = x, y

    is_zoomed = False
    if y_min < 0 or y_min > 0 and y_spread < (y_min * 0.5):
        is_zoomed = True
        padding = y_spread * 0.15
        if padding == 0:
            padding = y_max * 0.01
        limit_bottom = y_min - padding
        limit_top = y_max + padding
        ax.set_ylim(bottom=limit_bottom, top=limit_top)
    else:
        limit_bottom = 0
        y_smooth = np.clip(y_smooth, a_min=0, a_max=None)
        ax.set_ylim(bottom=0, top=y_max * 1.1)

    fill_base = limit_bottom if is_zoomed else 0
    ax.fill_between(x_smooth, y_smooth, y2=fill_base, alpha=0.2, color=Theme.CHART_FILL_COLOR, linewidth=0)
    ax.plot(x_smooth, y_smooth, color=Theme.CHART_LINE_COLOR, linewidth=2.5)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(True)
    ax.spines['bottom'].set_color('#E0E0E0')

    def large_num_formatter(x_val, pos):
        if x_val >= 100_000:
            return f'{x_val * 1e-4:,.2f}'.rstrip('0').rstrip('.') + 'W'
        if x_val >= 1_000:
            return f'{x_val * 1e-3:,.2f}'.rstrip('0').rstrip('.') + 'K'
        return f'{x_val:,.2f}'.rstrip('0').rstrip('.')

    ax.yaxis.set_major_formatter(ticker.FuncFormatter(large_num_formatter))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=5))

    mpl_text_color = tuple(c / 255.0 for c in Theme.TEXT_SECONDARY)
    ax.grid(axis='y', linestyle='--', alpha=0.3, color='#B0B0B0')
    ax.tick_params(axis='y', length=0, labelcolor=mpl_text_color, labelsize=9)

    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, fontsize=8, color=mpl_text_color)

    if len(x_labels) > 7:
        for i, tick_label in enumerate(ax.xaxis.get_ticklabels()):
            if i % 2 != 0:
                tick_label.set_visible(False)

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True)
    plt.close(fig)
    buf.seek(0)
    img = Image.open(buf).convert("RGBA")
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)
    return img

# ========= 地图生成逻辑 (Position View) =========

class PositionMapRenderer:
    def __init__(self, nether_json_path: str, end_json_path: str):
        self.maps = {}
        self.maps[0] = self._load_single_json(nether_json_path)
        self.maps[1] = self._load_single_json(end_json_path)

    def _load_single_json(self, path: str) -> Dict:
        data = _load_json(path)
        nodes = {}
        edges = []
        raw_nodes = data.get("graph", {}).get("nodes", [])
        raw_edges = data.get("graph", {}).get("edges", [])

        for n in raw_nodes:
            key = n["key"]
            attrs = n.get("attributes", {})
            nodes[key] = {
                "x": attrs.get("x", 0),
                "z": attrs.get("y", 0),
                "name": self._extract_name(attrs),
                "visible": attrs.get("visible", True),
                "is_station": attrs.get("type") != "virtual",
            }

        for e in raw_edges:
            src, tgt = e["source"], e["target"]
            color_hex = "#cbd5e1"
            try:
                style = e.get("attributes", {}).get("style", {})
                if "single-color" in style:
                    c_arr = style["single-color"].get("color", [])
                    if len(c_arr) >= 3:
                        color_hex = c_arr[2]
            except Exception:
                pass
            if src in nodes and tgt in nodes:
                edges.append({
                    "u": src,
                    "v": tgt,
                    "p1": (nodes[src]["x"], nodes[src]["z"]),
                    "p2": (nodes[tgt]["x"], nodes[tgt]["z"]),
                    "color": hex_to_rgb(color_hex),
                })
        return {"nodes": nodes, "edges": edges}

    def _extract_name(self, attrs):
        if attrs.get("type") != "virtual":
            names = attrs.get(attrs.get("type"), {}).get("names", [])
            if names:
                return names[0].split('\n')[0]
        return None

    def _get_dim_color(self, dim):
        if dim == 0: return Theme.DIM_OVERWORLD_COLOR
        if dim == 1: return Theme.DIM_END_COLOR
        if dim == -1: return Theme.DIM_NETHER_COLOR
        return Theme.PATH_DEFAULT_COLOR

    def _get_arrow_color(self, dim):
        if dim == 0: return Theme.ARROW_OVERWORLD
        if dim == 1: return Theme.ARROW_END
        if dim == -1: return Theme.ARROW_NETHER
        return Theme.ARROW_DEFAULT

    def _transform_coord(self, x, z, dim):
        if dim == 0: return x / 8, z / 8
        return x, z

    def _world_to_screen(self, wx, wz, cx, cz, scale, w, h):
        return (wx - cx) * scale + w / 2, (wz - cz) * scale + h / 2

    def create_arrow_marker(self, angle_deg: float, size: int, color: Tuple[int, int, int]) -> Image.Image:
        return _cached_arrow_marker(angle_deg, size, color).copy()

    def _render_layer(self, ctx_w, ctx_h, center_x, center_z, scale, path_segments: List[dict], group_id: int, markers: List[dict] = None, player_marker: dict = None):
        ss = 4
        w, h = ctx_w * ss, ctx_h * ss
        s_scale = scale * ss

        img = Image.new("RGBA", (w, h), Theme.BG_COLOR)
        draw = ImageDraw.Draw(img)

        self._draw_grid(draw, center_x, center_z, s_scale, w, h, ss)

        map_data = self.maps.get(group_id, {"nodes": {}, "edges": []})
        for edge in map_data["edges"]:
            p1, p2 = edge["p1"], edge["p2"]
            s1 = self._world_to_screen(p1[0], p1[1], center_x, center_z, s_scale, w, h)
            s2 = self._world_to_screen(p2[0], p2[1], center_x, center_z, s_scale, w, h)
            if max(s1[0], s2[0]) < 0 or min(s1[0], s2[0]) > w: continue
            if max(s1[1], s2[1]) < 0 or min(s1[1], s2[1]) > h: continue
            draw.line([s1, s2], fill=edge["color"], width=2 * ss)

        node_radius = 5 * ss
        font_name = load_font(18 * ss, True)
        
        # 碰撞检测：先将所有可见节点（圆点）作为障碍物
        text_occupied = []
        visible_nodes = []
        for _k, n in map_data["nodes"].items():
            if not n["visible"] or not n["is_station"]: continue
            sx, sy = self._world_to_screen(n["x"], n["z"], center_x, center_z, s_scale, w, h)
            if -50 * ss <= sx <= w + 50 * ss and -50 * ss <= sy <= h + 50 * ss:
                visible_nodes.append((n, sx, sy))
                # 保护圆点不被文字覆盖
                r_protect = node_radius + 2 * ss
                text_occupied.append((sx - r_protect, sy - r_protect, sx + r_protect, sy + r_protect))

        # 绘制圆点
        for n, sx, sy in visible_nodes:
            draw.ellipse(
                (sx - node_radius, sy - node_radius, sx + node_radius, sy + node_radius),
                fill=Theme.MAP_NODE_BG, outline=Theme.MAP_NODE_BORDER, width=2 * ss,
            )

        def is_colliding(box):
            # 略微缩小box检测范围，允许边缘轻微接触，但防止大幅重叠
            b0, b1, b2, b3 = box
            pad = 2 * ss
            check_box = (b0 + pad, b1 + pad, b2 - pad, b3 - pad)
            
            for other in text_occupied:
                if not (check_box[2] < other[0] or check_box[0] > other[2] or check_box[3] < other[1] or check_box[1] > other[3]):
                    return True
            return False

        # 绘制文字
        for n, sx, sy in visible_nodes:
            if not n["name"]: continue
            text = n["name"]
            bbox = draw.textbbox((0, 0), text, font=font_name)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            padding = 10 * ss
            tx = sx - tw / 2
            ty = sy - node_radius - th - padding
            
            # 这里的box包含一点外边距，用于占据空间
            box_candidate = (tx - 5 * ss, ty - 5 * ss, tx + tw + 5 * ss, ty + th + 5 * ss)

            if not is_colliding(box_candidate):
                draw.text(
                    (sx, ty + th / 2 + padding / 2),
                    text, font=font_name, fill=Theme.TEXT_PRIMARY,
                    stroke_fill=(255, 255, 255), stroke_width=3 * ss, anchor="mb",
                )
                text_occupied.append(box_candidate)

        # 绘制轨迹
        arrow_step = 160 * ss
        for segment in path_segments:
            coords = segment["coords"]
            seg_dim = segment.get("dim", 0)
            seg_color = self._get_dim_color(seg_dim)
            arrow_color = self._get_arrow_color(seg_dim)
            screen_pts = [self._world_to_screen(wx, wz, center_x, center_z, s_scale, w, h) for wx, wz in coords]

            if len(screen_pts) > 1:
                draw.line(screen_pts, fill=seg_color, width=1 * ss, joint="curve")
                dist_accum = 0
                for i in range(len(screen_pts) - 1):
                    p1, p2 = screen_pts[i], screen_pts[i + 1]
                    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                    seg_len = math.hypot(dx, dy)
                    if seg_len == 0: continue
                    current_dist = 0
                    while current_dist < seg_len:
                        remaining = arrow_step - dist_accum
                        if current_dist + remaining <= seg_len:
                            t = (current_dist + remaining) / seg_len
                            ax_ = p1[0] + dx * t
                            ay_ = p1[1] + dy * t
                            angle = math.degrees(math.atan2(dy, dx))
                            arrow_img = self.create_arrow_marker(angle, 6 * ss, arrow_color)
                            img.paste(arrow_img, (int(ax_ - arrow_img.width / 2), int(ay_ - arrow_img.height / 2)), arrow_img)
                            dist_accum = 0
                            current_dist += remaining
                        else:
                            dist_accum += (seg_len - current_dist)
                            break

        if markers:
            font_mk = load_font(18 * ss, True)
            for m in markers:
                mx, mz = m["pos"]
                sx, sy = self._world_to_screen(mx, mz, center_x, center_z, s_scale, w, h)
                r = 12 * ss
                draw.ellipse((sx - r, sy - r, sx + r, sy + r), fill=m.get("color", Theme.DIM_END_COLOR), outline=(255, 255, 255), width=2 * ss)
                draw.text((sx, sy - 1 * ss), m.get("label", ""), font=font_mk, fill=(255, 255, 255), anchor="mm")

        if player_marker:
            pm = player_marker
            sx, sy = self._world_to_screen(pm["x"], pm["z"], center_x, center_z, s_scale, w, h)
            p_dim = pm.get("dim", 0)
            p_color = self._get_dim_color(p_dim)
            point_r = 6 * ss
            draw.ellipse((sx - point_r, sy - point_r / 2, sx + point_r, sy + point_r / 2), fill=(0, 0, 0, 100))
            draw.ellipse((sx - point_r, sy - point_r, sx + point_r, sy + point_r), fill=p_color, outline=(255, 255, 255), width=2 * ss)
            if pm.get("avatar"):
                avatar_size = 64 * ss
                offset_y = 60 * ss
                av_cx, av_cy = sx, sy - offset_y
                draw.polygon([(sx, sy - point_r - 2 * ss), (sx - 10 * ss, av_cy + avatar_size / 2 - 2 * ss), (sx + 10 * ss, av_cy + avatar_size / 2 - 2 * ss)], fill=(255, 255, 255))
                avatar = crop_circle_avatar(pm["avatar"], avatar_size)
                img.paste(avatar, (int(av_cx - avatar_size / 2), int(av_cy - avatar_size / 2)), avatar)
                draw.ellipse((av_cx - avatar_size / 2, av_cy - avatar_size / 2, av_cx + avatar_size / 2, av_cy + avatar_size / 2), outline=(255, 255, 255), width=4 * ss)

        self._draw_scale_bar(draw, w, h, s_scale, ss)
        return img.resize((ctx_w, ctx_h), Image.LANCZOS)

    def _draw_grid(self, draw, cx, cz, scale, w, h, ss):
        target_px = 120 * ss
        world_step = target_px / scale
        steps = [10, 50, 100, 500, 1000, 5000]
        step = steps[0]
        for s in steps:
            if world_step > s: step = s
            else: break
        view_w, view_h = w / scale, h / scale
        start_x = (cx - view_w / 2) // step * step
        end_x = (cx + view_w / 2) // step * step + step
        start_z = (cz - view_h / 2) // step * step
        end_z = (cz + view_h / 2) // step * step + step
        c = (235, 238, 245)
        curr = start_x
        while curr <= end_x:
            sx, _ = self._world_to_screen(curr, cz, cx, cz, scale, w, h)
            draw.line([(sx, 0), (sx, h)], fill=c, width=1 * ss)
            curr += step
        curr = start_z
        while curr <= end_z:
            _, sy = self._world_to_screen(cx, curr, cx, cz, scale, w, h)
            draw.line([(0, sy), (w, sy)], fill=c, width=1 * ss)
            curr += step

    def _draw_scale_bar(self, draw, w, h, scale, ss):
        target_bar_px = 180 * ss
        world_dist_raw = target_bar_px / scale
        if world_dist_raw <= 0: return
        exponent = math.floor(math.log10(world_dist_raw))
        fraction = world_dist_raw / (10 ** exponent)
        nice_fraction = 1 if fraction < 1.5 else (2 if fraction < 3.5 else (5 if fraction < 7.5 else 10))
        world_dist_nice = nice_fraction * (10 ** exponent)
        bar_px = world_dist_nice * scale
        margin_x, margin_y = 40 * ss, 50 * ss
        x_end = w - margin_x
        x_start = x_end - bar_px
        y_pos = margin_y
        bar_color = (80, 80, 80)
        draw.line([(x_start, y_pos), (x_end, y_pos)], fill=bar_color, width=3 * ss)
        draw.line([(x_start, y_pos - 8 * ss), (x_start, y_pos + 8 * ss)], fill=bar_color, width=3 * ss)
        draw.line([(x_end, y_pos - 8 * ss), (x_end, y_pos + 8 * ss)], fill=bar_color, width=3 * ss)
        label = f"{int(world_dist_nice)} Blocks"
        font = load_font(24 * ss, True)
        draw.text(((x_start + x_end) / 2, y_pos - 15 * ss), label, fill=bar_color, font=font, anchor="mb")

    def _get_sorted_stations(self, x, z, group_id):
        stations = []
        nodes = self.maps.get(group_id, {}).get("nodes", {})
        for _k, n in nodes.items():
            if n["is_station"]:
                d = math.hypot(x - n["x"], z - n["z"])
                stations.append((n, d))
        stations.sort(key=lambda item: item[1])
        return stations

    def generate_location_image(self, width: int, height: int, x: float, z: float, dim: int, avatar_path: str = "", yaw: float = 0) -> Tuple[Image.Image, Dict]:
        group_id = 1 if dim == 1 else 0
        mx, mz = self._transform_coord(x, z, dim)
        sorted_stations = self._get_sorted_stations(mx, mz, group_id)
        nearest = sorted_stations[0] if sorted_stations else (None, 0)
        target_radius = 500
        if len(sorted_stations) >= 2: target_radius = sorted_stations[1][1] * 1.2
        elif len(sorted_stations) == 1: target_radius = sorted_stations[0][1] * 2.5
        else: target_radius = 50
        view_radius = min(max(50, target_radius), 3000)
        scale = width / 2 / view_radius
        player_info = {"x": mx, "z": mz, "dim": dim, "avatar": avatar_path, "yaw": yaw}
        img = self._render_layer(width, height, mx, mz, scale, [], group_id, markers=[], player_marker=player_info)
        info = {
            "x": x, "z": z, "dim": dim,
            "nearest_name": nearest[0]["name"] if nearest[0] else None,
            "nearest_dist": nearest[1],
        }
        return img, info

    def generate_path_image(self, width: int, height: int, points: List[Tuple[float, float, int]], avatar_path: str = "") -> Image.Image:
        if not points: return Image.new("RGBA", (width, height), Theme.BG_COLOR)
        
        # 分离末地和其他维度的点
        pts_end = [p for p in points if p[2] == 1]
        pts_other = [p for p in points if p[2] != 1]
        
        # 生成标记点逻辑保持不变...
        markers_other, markers_end = [], []
        marker_counter = 1
        for i in range(len(points) - 1):
            curr, next_p = points[i], points[i + 1]
            if curr[2] != next_p[2]:
                p1c = self._transform_coord(curr[0], curr[1], curr[2])
                m1 = {"pos": p1c, "label": str(marker_counter), "color": Theme.DIM_END_COLOR}
                (markers_end if curr[2] == 1 else markers_other).append(m1)
                marker_counter += 1
                p2c = self._transform_coord(next_p[0], next_p[1], next_p[2])
                m2 = {"pos": p2c, "label": str(marker_counter), "color": Theme.DIM_END_COLOR}
                (markers_end if next_p[2] == 1 else markers_other).append(m2)
                marker_counter += 1
        
        last = points[-1]
        lp_conv = self._transform_coord(last[0], last[1], last[2])
        dest_pm = {"x": lp_conv[0], "z": lp_conv[1], "dim": last[2], "avatar": avatar_path}
        
        has_end, has_other = len(pts_end) > 0, len(pts_other) > 0
        pm_other = dest_pm if (not has_end) or (last[2] != 1) else None
        pm_end = dest_pm if (last[2] == 1) else None

        # === 修改后的 _render_sub 函数 ===
        def _render_sub(pts, w_, h_, gid, mks, pm_):
            if not pts: return Image.new("RGBA", (w_, h_), Theme.BG_COLOR)
            
            # 整理轨迹段
            segments, curr_seg = [], []
            last_dim = pts[0][2]
            xs, zs = [], []
            for x, z, d in pts:
                mx, mz = self._transform_coord(x, z, d)
                xs.append(mx)
                zs.append(mz)
                if d != last_dim:
                    if curr_seg: segments.append({"coords": curr_seg, "dim": last_dim})
                    curr_seg = []
                    last_dim = d
                curr_seg.append((mx, mz))
            if curr_seg: segments.append({"coords": curr_seg, "dim": last_dim})

            # --- 核心修改开始：极简紧凑的比例尺逻辑 ---
            min_x, max_x, min_z, max_z = min(xs), max(xs), min(zs), max(zs)
            
            # 1. 计算实际物理跨度
            geo_w = max_x - min_x
            geo_h = max_z - min_z
            
            # 2. 设定最小视窗跨度 (Block单位)
            # 以前是 600，现在改为 20。
            # 只要不是原地不动(0跨度)，基本都能撑满。保留20是为了防止单点时计算出错，以及给线宽留一点余地。
            MIN_VIEW_SPAN = 20
            
            effective_w = max(geo_w, MIN_VIEW_SPAN)
            effective_h = max(geo_h, MIN_VIEW_SPAN)
            
            # 3. 计算中心点
            center_x = (min_x + max_x) / 2
            center_z = (min_z + max_z) / 2
            
            # 4. 计算缩放比例 (Scale)
            # 改为 0.95，意味着路径会占据画布 95% 的空间，非常紧凑
            PADDING_FACTOR = 0.95
            
            scale_x = (w_ * PADDING_FACTOR) / effective_w
            scale_z = (h_ * PADDING_FACTOR) / effective_h
            
            scale_ = min(scale_x, scale_z)
            
            # 5. 移除最大缩放限制
            # scale_ = min(scale_, 5.0)  <-- 这行代码删掉，允许无限放大
            # ---------------------------

            img_ = self._render_layer(w_, h_, center_x, center_z, scale_, segments, gid, mks, pm_)
            d_ = ImageDraw.Draw(img_)
            lbl = "THE END" if gid == 1 else "NETHER & OVERWORLD"
            # 调整一下标签位置，稍微往里缩一点，防止贴边太近
            d_.text((w_ - 30, h_ - 30), lbl, fill=Theme.TEXT_SECONDARY, font=load_font(24, True), anchor="rb")
            return img_

        # 布局逻辑保持不变
        if has_end and has_other:
            h1 = int(height * 0.55)
            h2 = height - h1
            img = Image.new("RGBA", (width, height), Theme.BG_COLOR)
            img.paste(_render_sub(pts_other, width, h1, 0, markers_other, pm_other), (0, 0))
            img.paste(_render_sub(pts_end, width, h2, 1, markers_end, pm_end), (0, h1))
            ImageDraw.Draw(img).line([(0, h1), (width, h1)], fill=(200, 200, 200), width=2)
            return img
        if has_end: return _render_sub(pts_end, width, height, 1, markers_end, pm_end)
        return _render_sub(pts_other, width, height, 0, markers_other, pm_other)

# ========= 主渲染流程 (Stats + Map) =========

def render_combined_view(
        data: Dict,
        map_config: Any = None,
):
    # === 1. 数据准备与高度预计算 ===
    totals = data.get("totals", [])
    charts = data.get("charts", [])
    is_online = data.get("is_online", True)
    in_server = data.get("in_server", "Survival")

    # 左侧栏配置
    # 统计卡片：在左侧栏内，使用双列布局比较合适
    stats_cols = 2
    stats_gap = 20
    stats_card_h = 100
    stats_rows = (len(totals) + stats_cols - 1) // stats_cols
    
    # 图表：在左侧栏内，使用单列垂直堆叠，显示更清晰
    chart_cols = 1
    chart_gap = 30
    chart_card_h = 260
    chart_rows = len(charts)

    # 头像区高度
    avatar_size = 140
    header_height = Theme.PADDING + 20 + avatar_size + 60

    # 各区域高度
    stats_area_height = stats_rows * (stats_card_h + stats_gap) + 20
    charts_area_height = chart_rows * (chart_card_h + chart_gap) + 20
    
    # 计算左侧内容总高度
    left_content_height = header_height + stats_area_height + charts_area_height + 50 # +Footer buffer
    
    # 决定画布总高度：至少要有 900px，否则以内容为准
    total_height = max(left_content_height, 900)

    # === 2. 初始化画布 ===
    img = Image.new("RGBA", (Theme.WIDTH, total_height), Theme.BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 字体加载
    font_h1 = load_font(48, is_bold=True)
    font_h2 = load_font(30, is_bold=True)
    font_label = load_font(20, is_bold=False)
    font_sub = load_font(22, is_bold=False)
    font_info = load_font(18, is_bold=False)
    font_delta = load_font(18, is_bold=True)
    font_chart_title = load_font(26, is_bold=True)

    # === 3. 绘制左侧栏 (Left Panel) ===
    # 左侧栏的 X 范围: [Theme.PADDING, Theme.PADDING + Theme.LEFT_PANEL_WIDTH]
    cursor_y = Theme.PADDING + 20
    left_x = Theme.PADDING
    
    # --- Header (Avatar + Info) ---
    qq_avatar = crop_circle_avatar(data.get("qq_avatar", ""), avatar_size)
    
    # 绘制头像
    draw.ellipse((left_x, cursor_y, left_x + avatar_size, cursor_y + avatar_size), fill=Theme.SHADOW_COLOR)
    draw.ellipse(
        (left_x - 4, cursor_y - 4, left_x + avatar_size + 4, cursor_y + avatar_size + 4),
        fill=Theme.CARD_BG,
    )
    img.paste(qq_avatar, (left_x, cursor_y), qq_avatar)

    # MC 角标
    mc_size = 50
    mc_avatar = crop_circle_avatar(data.get("mc_avatar", ""), mc_size)
    badge_x = left_x + avatar_size - mc_size + 5
    badge_y = cursor_y + avatar_size - mc_size + 5
    draw.ellipse((badge_x - 3, badge_y - 3, badge_x + mc_size + 3, badge_y + mc_size + 3), fill=Theme.CARD_BG)
    img.paste(mc_avatar, (badge_x, badge_y), mc_avatar)

    # 个人信息文本
    text_x = left_x + avatar_size + 30
    info_limit_w = Theme.LEFT_PANEL_WIDTH - (avatar_size + 30)

    # 生成时间
    generated_at = data.get("generated_at", "")
    draw.text((text_x, cursor_y + 5), f"Generated at: {generated_at}", fill=Theme.TEXT_SECONDARY, font=font_info, anchor="lt")

    # 统计区间
    time_range_label = data.get("time_range_label", "")
    draw.text((text_x, cursor_y - 25), time_range_label, fill=Theme.TEXT_SECONDARY, font=font_info, anchor="lt")

    # 玩家名字
    name_text = data.get("player_name", "Player")
    name_text = truncate_text(draw, name_text, font_h1, info_limit_w)
    draw.text((text_x, cursor_y + 30), name_text, fill=Theme.TEXT_PRIMARY, font=font_h1, anchor="lt")

    # UUID & Status
    uuid_str = data.get("uuid", "N/A")
    draw.text((text_x, cursor_y + 85), f"{uuid_str}", fill=Theme.TEXT_SECONDARY, font=font_info, anchor="lt")
    
    status_text = f"● Online in {in_server}" if is_online else f"● Last seen: {data.get('last_seen', 'N/A')}"
    status_color = Theme.ONLINE_COLOR if is_online else Theme.TEXT_SECONDARY
    draw.text((text_x, cursor_y + 110), status_text, fill=status_color, font=font_info, anchor="lt")

    cursor_y += avatar_size + 40

    # --- Stats Grid (Left Column) ---
    draw.text((left_x, cursor_y - 10), "Statistics", fill=Theme.TEXT_SECONDARY, font=font_sub, anchor="lb")
    
    stats_card_w = (Theme.LEFT_PANEL_WIDTH - (stats_cols - 1) * stats_gap) // stats_cols

    for idx, item in enumerate(totals):
        row = idx // stats_cols
        col = idx % stats_cols
        
        cx = left_x + col * (stats_card_w + stats_gap)
        cy = cursor_y + row * (stats_card_h + stats_gap)
        bbox = (cx, cy, cx + stats_card_w, cy + stats_card_h)

        draw_shadow(img, bbox, radius=Theme.CARD_RADIUS, blur=10, offset=(0, 4))
        draw.rounded_rectangle(bbox, radius=Theme.CARD_RADIUS, fill=Theme.CARD_BG)

        # Label
        label = truncate_text(draw, item.get("label", "Stat"), font_label, stats_card_w - 30)
        draw.text((cx + 20, cy + 25), label, fill=Theme.TEXT_SECONDARY, font=font_label, anchor="lt")
        
        # Value
        val_raw = item.get("total", 0)
        label_total = item.get("label_total", 0)
        val_str = f"{label_total:,}" if isinstance(label_total, (int, float)) else str(label_total)
        
        # 动态字体大小防止溢出
        curr_font_val = font_h2
        if draw.textlength(val_str, font_h2) > stats_card_w * 0.65:
            curr_font_val = load_font(24, True)
            
        draw.text((cx + 20, cy + 65), val_str, fill=Theme.TEXT_PRIMARY, font=curr_font_val, anchor="lm")

        # Delta
        delta = item.get("delta", 0)
        label_delta = item.get("label_delta", 0)
        if delta != 0:
            delta_str = f"{'+' if delta > 0 else ''}{label_delta}"
            c = Theme.POSITIVE if delta > 0 else Theme.NEGATIVE
            draw.text((cx + stats_card_w - 20, cy + 65), delta_str, fill=c, font=font_delta, anchor="rm")

    cursor_y += stats_rows * (stats_card_h + stats_gap) + 30

    # --- Charts (Left Column) ---
    if charts:
        draw.text((left_x, cursor_y - 10), "Activity Trends", fill=Theme.TEXT_SECONDARY, font=font_sub, anchor="lb")
        
        chart_card_w = Theme.LEFT_PANEL_WIDTH # 全宽

        for chart in charts:
            cx = left_x
            cy = cursor_y
            bbox = (cx, cy, cx + chart_card_w, cy + chart_card_h)

            draw_shadow(img, bbox, radius=Theme.CARD_RADIUS, blur=15)
            draw.rounded_rectangle(bbox, radius=Theme.CARD_RADIUS, fill=Theme.CARD_BG)

            title = chart.get("label", "Trend")
            draw.text((cx + 20, cy + 20), title, fill=Theme.TEXT_PRIMARY, font=font_chart_title, anchor="lt")
            
            total_v = chart.get("total", 0)
            t_str = f"Total: {total_v:,}" if isinstance(total_v, (int, float)) else str(total_v)
            draw.text((cx + chart_card_w - 20, cy + 24), t_str, fill=Theme.TEXT_SECONDARY, font=font_info, anchor="rt")

            # 绘制图表
            c_w = chart_card_w - 40
            c_h = chart_card_h - 70
            chart_img = create_smooth_chart(c_w, c_h, chart.get("x", []), chart.get("y", []), title)
            img.paste(chart_img, (cx + 20, cy + 60), chart_img)

            cursor_y += chart_card_h + chart_gap

    # Footer Info
    data_source = data.get("data_source_text", "")
    if data_source:
        ds_font = load_font(16, is_bold=False)
        data_source = truncate_text(draw, data_source, ds_font, Theme.LEFT_PANEL_WIDTH)
        draw.text((left_x, total_height - 30), data_source, fill=Theme.TEXT_SECONDARY, font=ds_font, anchor="lm")


    # === 4. 绘制右侧栏 (Map Panel) ===
    has_map = "location" in data or "path" in data
    
    # 计算右侧栏位置
    right_x = Theme.PADDING + Theme.LEFT_PANEL_WIDTH + Theme.COLUMN_GAP
    right_w = Theme.WIDTH - right_x - Theme.PADDING
    right_h = total_height - 2 * Theme.PADDING - 20 # 上下对齐
    right_y = Theme.PADDING + 20

    if has_map:
        bbox = (right_x, right_y, right_x + right_w, right_y + right_h)
        
        # 阴影与背景
        draw_shadow(img, bbox, radius=Theme.CARD_RADIUS, blur=20)
        # 创建遮罩以裁剪圆角
        mask = Image.new("L", (right_w, right_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, right_w, right_h), radius=Theme.CARD_RADIUS, fill=255)

        nether_json, end_json = _extract_map_json_paths(map_config)
        nether_json = _resolve_map_json_path(nether_json)
        end_json = _resolve_map_json_path(end_json)
        renderer = PositionMapRenderer(nether_json, end_json)

        map_img = None
        info_data = {}
        title = "Position"

        # 生成地图图片
        if "location" in data:
            loc = data["location"]
            # 注意：这里我们传入了 right_w 和 right_h，地图会自动适应这个长宽比
            map_raw, info_data = renderer.generate_location_image(
                right_w, right_h, loc["x"], loc["z"], loc["dim"], data.get("mc_avatar", ""), loc.get("yaw", 0)
            )
            map_img = map_raw
            title = "Location"
        elif "path" in data:
            path_pts = data["path"]
            map_raw = renderer.generate_path_image(right_w, right_h, path_pts, data.get("mc_avatar", ""))
            map_img = map_raw
            title = "Path"
            try:
                # 获取最后一个点的信息用于显示
                last = path_pts[-1] if path_pts else None
                if last and len(last) >= 3:
                    last_x, last_z, last_dim = float(last[0]), float(last[1]), int(last[2])
                    gid = 1 if last_dim == 1 else 0
                    mx, mz = renderer._transform_coord(last_x, last_z, last_dim)
                    sorted_stations = renderer._get_sorted_stations(mx, mz, gid)
                    nearest = sorted_stations[0] if sorted_stations else (None, 0)
                    info_data = {
                        "x": last_x, "z": last_z, "dim": last_dim,
                        "nearest_name": nearest[0]["name"] if nearest[0] else None,
                        "nearest_dist": nearest[1],
                    }
            except Exception: pass

        if map_img:
            container = Image.new("RGBA", (right_w, right_h), (0, 0, 0, 0))
            container.paste(map_img, (0, 0))
            img.paste(container, (right_x, right_y), mask)

            # 地图左上角的标题
            draw.text(
                (right_x + 30, right_y + 30), title,
                fill=Theme.TEXT_PRIMARY, font=font_h2,
                stroke_fill=(255, 255, 255), stroke_width=4
            )

            # 地图信息卡片 (悬浮在右侧地图的底部)
            if info_data and all(k in info_data for k in ["x", "z", "dim"]):
                card_w, card_h = 450, 140
                
                # 悬浮位置：右侧面板的底部居中
                cx = right_x + (right_w - card_w) // 2
                cy = right_y + right_h - card_h - 30

                overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
                od = ImageDraw.Draw(overlay)
                od.rounded_rectangle((0, 0, card_w, card_h), radius=20, fill=(255, 255, 255, 245))
                od.rounded_rectangle((0, 0, card_w, card_h), radius=20, outline=Theme.MAP_LINE_COLOR, width=1)
                
                dim_str = "The End" if info_data["dim"] == 1 else ("Nether" if info_data["dim"] == -1 else "Overworld")
                dim_color = renderer._get_dim_color(info_data["dim"])

                # 坐标
                od.text((25, 20), "Coordinate", fill=Theme.TEXT_SECONDARY, font=font_info, anchor="lt")
                od.text((25, 45), f"{int(info_data['x'])}, {int(info_data['z'])}", fill=Theme.TEXT_PRIMARY, font=load_font(28, True), anchor="lt")
                od.text((25, 85), dim_str, fill=dim_color, font=load_font(20, True), anchor="lt")

                # 最近站点
                if info_data.get("nearest_name"):
                    n_name = info_data['nearest_name']
                    n_name = truncate_text(od, n_name, load_font(22, True), 200)
                    
                    od.text((card_w - 25, 20), "Nearest Station", fill=Theme.TEXT_SECONDARY, font=font_info, anchor="rt")
                    od.text((card_w - 25, 45), n_name, fill=Theme.TEXT_PRIMARY, font=load_font(22, True), anchor="rt")
                    od.text((card_w - 25, 80), f"{int(info_data['nearest_dist'])}m away", fill=Theme.TEXT_SECONDARY, font=font_info, anchor="rt")

                img.alpha_composite(overlay.convert("RGBA"), (cx, cy))

    else:
        # 如果没有地图，右侧显示一个占位图或空白
        # 这里选择画一个简单的虚线框表示无数据
        bbox = (right_x, right_y, right_x + right_w, right_y + right_h)
        draw.rounded_rectangle(bbox, radius=Theme.CARD_RADIUS, fill=(240, 242, 245))
        draw.text((right_x + right_w/2, right_y + right_h/2), "No Location Data", fill=Theme.TEXT_SECONDARY, font=font_h2, anchor="mm")

    return img

if __name__ == "__main__":
    # 测试用例
    MAP_CONFIG = {
        "nether_json": "/home/arch/assX/asPanel/storages/maps/3/the_nether.json",
        "end_json": "/home/arch/assX/asPanel/storages/maps/3/the_end.json",
    }
    sample_data = {
        "qq_avatar": "", 
        "mc_avatar": "",
        "player_name": "ThisIsAVeryLongPlayerNameForTesting", # 测试长名字
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "last_seen": "2025-01-07 14:30",
        "time_range_label": "Weekly Report",
        "totals": [
            {"label": "Very Long Stat Label That Should Be Truncated", "total": 123456789, "delta": 4321}, # 测试文字重叠
            {"label": "Short Label", "total": 222, "delta": -5},
        ],
        "charts": [],
        "path": [(1,1,1),(1,10,1),(1,100,1),(42341,19,1),(1,120,-1)]
    }
    # 模拟生成
    render_combined_view(sample_data, MAP_CONFIG).save("test_output.png")
