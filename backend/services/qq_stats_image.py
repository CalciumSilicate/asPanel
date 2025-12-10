import io
import os
import platform
import math
import json
import httpx
from typing import List, Dict, Tuple, Optional, Any

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import matplotlib
import matplotlib.ticker as ticker

# 设置后端，必须在 pyplot 之前
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import PchipInterpolator
from matplotlib import font_manager as fm  # 新增

from backend.core.constants import BASE_DIR


# ========= 字体路径配置（你只需要改这里） =========
# 指向你的 regular.ttf / bold.ttf
FONT_REGULAR_PATH = BASE_DIR / "backend/resources/fonts/MapleMono-NF-CN-Regular.ttf"
FONT_BOLD_PATH = BASE_DIR / "backend/resources/fonts/MapleMono-NF-CN-Bold.ttf"

# ========= 配置与主题 (合并版) =========


class Theme:
    # 全局背景
    BG_COLOR = (248, 249, 252)
    # 卡片背景
    CARD_BG = (255, 255, 255)
    # 阴影颜色
    SHADOW_COLOR = (20, 30, 60, 20)

    # 文本颜色
    TEXT_PRIMARY = (30, 35, 50)
    TEXT_SECONDARY = (130, 140, 160)
    TEXT_ACCENT = (100, 100, 255)
    ONLINE_COLOR = (34, 197, 94)  # 在线昵称/状态颜色，绿

    # 统计涨跌颜色
    POSITIVE = (16, 185, 129)
    NEGATIVE = (239, 68, 68)

    # 图表颜色
    CHART_LINE_COLOR = "#6366f1"
    CHART_FILL_COLOR = "#818cf8"

    # 地图维度颜色 (路径线条颜色)
    DIM_NETHER_COLOR = (239, 68, 68)  # Red-500
    DIM_OVERWORLD_COLOR = (16, 185, 129)  # Emerald-500
    DIM_END_COLOR = (168, 85, 247)  # Purple-500
    PATH_DEFAULT_COLOR = (96, 165, 250)

    # 地图箭头颜色
    ARROW_NETHER = (127, 29, 29)
    ARROW_OVERWORLD = (6, 78, 59)
    ARROW_END = (88, 28, 135)
    ARROW_DEFAULT = (30, 58, 138)

    # 地图节点颜色
    MAP_LINE_COLOR = (203, 213, 225)
    MAP_NODE_BG = (255, 255, 255)
    MAP_NODE_BORDER = (148, 163, 184)

    # 布局常量
    WIDTH = 1080
    PADDING = 60
    CARD_RADIUS = 30


# ========= 字体管理（统一使用 FONT_*_PATH） =========


def get_default_font_path(font_type="regular"):
    """
    系统 fallback 字体查找（仅当你的 FONT_*_PATH 无效时才会用到）
    """
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


def load_font(size: int, is_bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    统一字体入口：
    - 优先使用你配置的 FONT_BOLD_PATH / FONT_REGULAR_PATH
    - 若不存在则 fallback 到系统字体
    - 再不行用 PIL 默认字体
    """
    preferred_path = FONT_BOLD_PATH if is_bold else FONT_REGULAR_PATH

    try:
        if preferred_path and os.path.exists(preferred_path):
            return ImageFont.truetype(str(preferred_path), size)
    except Exception:
        pass

    # fallback
    font_path = get_default_font_path("bold" if is_bold else "regular")
    try:
        if font_path and os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    except Exception:
        pass

    return ImageFont.load_default()


# ========= Matplotlib ���体初始化 =========

_MPL_FONT_INITIALIZED = False


def ensure_mpl_font():
    """
    确保 Matplotlib 使用与 PIL 一致的中文字体：
    - 优先使用 FONT_REGULAR_PATH
    - 失败则使用系统 fallback
    """
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
            # 找不到有效字体就保持 Matplotlib 默认
            return

        # 用 FontProperties 获取 family 名字
        prop = fm.FontProperties(fname=font_path)
        fm.fontManager.addfont(font_path)
        font_name = prop.get_name()

        # 设置全局 rcParams
        plt.rcParams["font.family"] = font_name
        plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

        _MPL_FONT_INITIALIZED = True
    except Exception:
        # 字体初始化失败则回退默认，不抛异常影响绘图
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


def crop_circle_avatar(img_path: str, size: int) -> Image.Image:
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
        # 使用统一字体
        font = load_font(size // 2, is_bold=True)
        d.text((size / 2, size / 2), "?", fill=(150, 150, 150), font=font, anchor="mm")

    img = img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c * 2 for c in hex_str])
    try:
        return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (200, 200, 200)


# ========= 图表生成逻辑 (Stats) =========


def create_smooth_chart(width: int, height: int, x_labels: List[str], values: List[float], label: str) -> Image.Image:
    """
    使用 Matplotlib 生成平滑曲线图，并统一使用自定义字体
    """
    # 确保 Matplotlib 字体已经根据 FONT_REGULAR_PATH 配置
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
    if y_min > 0 and y_spread < (y_min * 0.5):
        is_zoomed = True
        padding = y_spread * 0.15
        if padding == 0:
            padding = y_max * 0.01

        limit_bottom = max(0, y_min - padding)
        limit_top = y_max + padding
        ax.set_ylim(bottom=limit_bottom, top=limit_top)
    else:
        limit_bottom = 0
        y_smooth = np.clip(y_smooth, a_min=0, a_max=None)
        ax.set_ylim(bottom=0, top=y_max * 1.1)

    fill_base = limit_bottom if is_zoomed else 0
    ax.fill_between(x_smooth, y_smooth, y2=fill_base, alpha=0.2, color=Theme.CHART_FILL_COLOR, linewidth=0)
    ax.plot(x_smooth, y_smooth, color=Theme.CHART_LINE_COLOR, linewidth=2.5)

    # 坐标轴样式
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(True)
    ax.spines['bottom'].set_color('#E0E0E0')

    def large_num_formatter(x_val, pos):
        if x_val >= 10_000:
            return f'{x_val * 1e-4:.2f}W'
        return f'{x_val: .2f}'

    ax.yaxis.set_major_formatter(ticker.FuncFormatter(large_num_formatter))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=4))

    mpl_text_color = tuple(c / 255.0 for c in Theme.TEXT_SECONDARY)
    ax.grid(axis='y', linestyle='--', alpha=0.3, color='#B0B0B0')
    ax.tick_params(axis='y', length=0, labelcolor=mpl_text_color, labelsize=9)

    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, fontsize=8, color=mpl_text_color)

    # x 轴标签太多的时候隔一个隐藏一个
    if len(x_labels) > 7:
        for i, tick_label in enumerate(ax.xaxis.get_ticklabels()):
            if i % 2 != 0:
                tick_label.set_visible(False)

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGBA").resize((width, height), Image.LANCZOS)


# ========= 地图生成逻辑 (Position View) =========


class PositionMapRenderer:
    def __init__(self, nether_json_path: str, end_json_path: str):
        self.maps = {}
        self.maps[0] = self._load_single_json(nether_json_path)
        self.maps[1] = self._load_single_json(end_json_path)

        # 预加载字体（统一走 load_font）
        self.font_h1 = load_font(48, True)
        self.font_h2 = load_font(32, True)
        self.font_sub = load_font(24, False)
        self.font_mark = load_font(20, True)

    def _load_single_json(self, path: str) -> Dict:
        if not path or not os.path.exists(path):
            return {"nodes": {}, "edges": []}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading JSON {path}: {e}")
            return {"nodes": {}, "edges": []}

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
                "is_station": attrs.get("type") == "shmetro-basic",
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
        if attrs.get("type") == "shmetro-basic":
            names = attrs.get("shmetro-basic", {}).get("names", [])
            if names:
                return names[0].split('\n')[0]
        return None

    def _get_dim_color(self, dim):
        if dim == 0:
            return Theme.DIM_OVERWORLD_COLOR
        if dim == 1:
            return Theme.DIM_END_COLOR
        if dim == -1:
            return Theme.DIM_NETHER_COLOR
        return Theme.PATH_DEFAULT_COLOR

    def _get_arrow_color(self, dim):
        if dim == 0:
            return Theme.ARROW_OVERWORLD
        if dim == 1:
            return Theme.ARROW_END
        if dim == -1:
            return Theme.ARROW_NETHER
        return Theme.ARROW_DEFAULT

    def _transform_coord(self, x, z, dim):
        if dim == 0:
            return x / 8, z / 8
        return x, z

    def _world_to_screen(self, wx, wz, cx, cz, scale, w, h):
        return (wx - cx) * scale + w / 2, (wz - cz) * scale + h / 2

    def create_arrow_marker(self, angle_deg: float, size: int, color: Tuple[int, int, int]) -> Image.Image:
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

    def _render_layer(
        self,
        ctx_w,
        ctx_h,
        center_x,
        center_z,
        scale,
        path_segments: List[dict],
        group_id: int,
        markers: List[dict] = None,
        player_marker: dict = None,
    ):
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
            if max(s1[0], s2[0]) < 0 or min(s1[0], s2[0]) > w:
                continue
            if max(s1[1], s2[1]) < 0 or min(s1[1], s2[1]) > h:
                continue
            draw.line([s1, s2], fill=edge["color"], width=2 * ss)

        node_radius = 5 * ss
        font_name = load_font(18 * ss, True)
        text_occupied = []
        visible_nodes = []

        for _k, n in map_data["nodes"].items():
            if not n["visible"] or not n["is_station"]:
                continue
            sx, sy = self._world_to_screen(n["x"], n["z"], center_x, center_z, s_scale, w, h)
            if -50 * ss <= sx <= w + 50 * ss and -50 * ss <= sy <= h + 50 * ss:
                visible_nodes.append((n, sx, sy))

        for n, sx, sy in visible_nodes:
            draw.ellipse(
                (sx - node_radius, sy - node_radius, sx + node_radius, sy + node_radius),
                fill=Theme.MAP_NODE_BG,
                outline=Theme.MAP_NODE_BORDER,
                width=2 * ss,
            )

        def is_colliding(box):
            for other in text_occupied:
                if not (box[2] < other[0] or box[0] > other[2] or box[3] < other[1] or box[1] > other[3]):
                    return True
            return False

        for n, sx, sy in visible_nodes:
            if not n["name"]:
                continue
            text = n["name"]
            bbox = draw.textbbox((0, 0), text, font=font_name)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            padding = 10 * ss
            tx = sx - tw / 2
            ty = sy - node_radius - th - padding
            box_candidate = (tx - 5 * ss, ty - 5 * ss, tx + tw + 5 * ss, ty + th + 5 * ss)

            if not is_colliding(box_candidate):
                draw.text(
                    (sx, ty + th / 2 + padding / 2),
                    text,
                    font=font_name,
                    fill=Theme.TEXT_PRIMARY,
                    stroke_fill=(255, 255, 255),
                    stroke_width=3 * ss,
                    anchor="mb",
                )
                text_occupied.append(box_candidate)

        arrow_step = 160 * ss
        for segment in path_segments:
            coords = segment["coords"]
            seg_dim = segment.get("dim", 0)
            seg_color = self._get_dim_color(seg_dim)
            arrow_color = self._get_arrow_color(seg_dim)

            screen_pts = [self._world_to_screen(wx, wz, center_x, center_z, s_scale, w, h) for wx, wz in coords]

            if len(screen_pts) > 1:
                draw.line(screen_pts, fill=seg_color, width=4 * ss, joint="curve")
                dist_accum = 0
                for i in range(len(screen_pts) - 1):
                    p1, p2 = screen_pts[i], screen_pts[i + 1]
                    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                    seg_len = math.hypot(dx, dy)
                    if seg_len == 0:
                        continue
                    current_dist = 0
                    while current_dist < seg_len:
                        remaining = arrow_step - dist_accum
                        if current_dist + remaining <= seg_len:
                            t = (current_dist + remaining) / seg_len
                            ax_ = p1[0] + dx * t
                            ay_ = p1[1] + dy * t
                            angle = math.degrees(math.atan2(dy, dx))
                            arrow_img = self.create_arrow_marker(angle, 14 * ss, arrow_color)
                            img.paste(
                                arrow_img,
                                (int(ax_ - arrow_img.width / 2), int(ay_ - arrow_img.height / 2)),
                                arrow_img,
                            )
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
                draw.ellipse(
                    (sx - r, sy - r, sx + r, sy + r),
                    fill=m.get("color", Theme.DIM_END_COLOR),
                    outline=(255, 255, 255),
                    width=2 * ss,
                )
                draw.text((sx, sy - 1 * ss), m.get("label", ""), font=font_mk, fill=(255, 255, 255), anchor="mm")

        if player_marker:
            pm = player_marker
            sx, sy = self._world_to_screen(pm["x"], pm["z"], center_x, center_z, s_scale, w, h)
            p_dim = pm.get("dim", 0)
            p_color = self._get_dim_color(p_dim)
            point_r = 6 * ss
            draw.ellipse((sx - point_r, sy - point_r / 2, sx + point_r, sy + point_r / 2), fill=(0, 0, 0, 100))
            draw.ellipse(
                (sx - point_r, sy - point_r, sx + point_r, sy + point_r),
                fill=p_color,
                outline=(255, 255, 255),
                width=2 * ss,
            )

            if pm.get("avatar"):
                avatar_size = 64 * ss
                offset_y = 60 * ss
                av_cx, av_cy = sx, sy - offset_y
                draw.polygon(
                    [
                        (sx, sy - point_r - 2 * ss),
                        (sx - 10 * ss, av_cy + avatar_size / 2 - 2 * ss),
                        (sx + 10 * ss, av_cy + avatar_size / 2 - 2 * ss),
                    ],
                    fill=(255, 255, 255),
                )
                avatar = crop_circle_avatar(pm["avatar"], avatar_size)
                img.paste(avatar, (int(av_cx - avatar_size / 2), int(av_cy - avatar_size / 2)), avatar)
                draw.ellipse(
                    (
                        av_cx - avatar_size / 2,
                        av_cy - avatar_size / 2,
                        av_cx + avatar_size / 2,
                        av_cy + avatar_size / 2,
                    ),
                    outline=(255, 255, 255),
                    width=4 * ss,
                )

        self._draw_scale_bar(draw, w, h, s_scale, ss)

        return img.resize((ctx_w, ctx_h), Image.LANCZOS)

    def _draw_grid(self, draw, cx, cz, scale, w, h, ss):
        target_px = 120 * ss
        world_step = target_px / scale
        steps = [10, 50, 100, 500, 1000, 5000]
        step = steps[0]
        for s in steps:
            if world_step > s:
                step = s
            else:
                break

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
        if world_dist_raw <= 0:
            return

        exponent = math.floor(math.log10(world_dist_raw))
        fraction = world_dist_raw / (10 ** exponent)
        if fraction < 1.5:
            nice_fraction = 1
        elif fraction < 3.5:
            nice_fraction = 2
        elif fraction < 7.5:
            nice_fraction = 5
        else:
            nice_fraction = 10

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

    def generate_location_image(
        self,
        width: int,
        height: int,
        x: float,
        z: float,
        dim: int,
        avatar_path: str = "",
        yaw: float = 0,
    ) -> Tuple[Image.Image, Dict]:
        group_id = 1 if dim == 1 else 0
        mx, mz = self._transform_coord(x, z, dim)

        sorted_stations = self._get_sorted_stations(mx, mz, group_id)
        nearest = sorted_stations[0] if sorted_stations else (None, 0)

        if len(sorted_stations) >= 2:
            target_radius = sorted_stations[1][1] * 1.2
        elif len(sorted_stations) == 1:
            target_radius = sorted_stations[0][1] * 2.5
        else:
            target_radius = 500
        view_radius = min(max(250, target_radius), 3000)
        scale = width / 2 / view_radius

        player_info = {"x": mx, "z": mz, "dim": dim, "avatar": avatar_path, "yaw": yaw}

        img = self._render_layer(width, height, mx, mz, scale, [], group_id, markers=[], player_marker=player_info)

        info = {
            "x": x,
            "z": z,
            "dim": dim,
            "nearest_name": nearest[0]["name"] if nearest[0] else None,
            "nearest_dist": nearest[1],
        }
        return img, info

    def generate_path_image(
        self,
        width: int,
        height: int,
        points: List[Tuple[float, float, int]],
        avatar_path: str = "",
    ) -> Image.Image:
        if not points:
            return Image.new("RGBA", (width, height), Theme.BG_COLOR)

        pts_end = [p for p in points if p[2] == 1]
        pts_other = [p for p in points if p[2] != 1]

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

        def _render_sub(pts, w_, h_, gid, mks, pm_):
            if not pts:
                return Image.new("RGBA", (w_, h_), Theme.BG_COLOR)
            segments, curr_seg = [], []
            last_dim = pts[0][2]
            xs, zs = [], []
            for x, z, d in pts:
                mx, mz = self._transform_coord(x, z, d)
                xs.append(mx)
                zs.append(mz)
                if d != last_dim:
                    if curr_seg:
                        segments.append({"coords": curr_seg, "dim": last_dim})
                    curr_seg = []
                    last_dim = d
                curr_seg.append((mx, mz))
            if curr_seg:
                segments.append({"coords": curr_seg, "dim": last_dim})

            min_x, max_x = min(xs), max(xs)
            min_z, max_z = min(zs), max(zs)
            pad = 200
            span_x = max((max_x - min_x) + pad * 2, 400)
            span_z = max((max_z - min_z) + pad * 2, 400)
            scale_ = min(min(w_ / span_x, h_ / span_z), 2.0)

            img_ = self._render_layer(
                w_,
                h_,
                (min_x + max_x) / 2,
                (min_z + max_z) / 2,
                scale_,
                segments,
                gid,
                mks,
                pm_,
            )
            d_ = ImageDraw.Draw(img_)
            lbl = "THE END" if gid == 1 else "NETHER & OVERWORLD"
            d_.text((w_ - 20, h_ - 20), lbl, fill=Theme.TEXT_SECONDARY, font=load_font(24, True), anchor="rb")
            return img_

        if has_end and has_other:
            h1 = int(height * 0.55)
            h2 = height - h1
            img = Image.new("RGBA", (width, height), Theme.BG_COLOR)
            img.paste(_render_sub(pts_other, width, h1, 0, markers_other, pm_other), (0, 0))
            img.paste(_render_sub(pts_end, width, h2, 1, markers_end, pm_end), (0, h1))
            ImageDraw.Draw(img).line([(0, h1), (width, h1)], fill=(200, 200, 200), width=2)
            return img
        if has_end:
            return _render_sub(pts_end, width, height, 1, markers_end, pm_end)
        return _render_sub(pts_other, width, height, 0, markers_other, pm_other)


# ========= 主渲染流程 (Stats + Map) =========


def render_combined_view(
        data: Dict,
        map_config: Dict[str, str],
):
    # === 先根据数据“预估”一个足够大的画布高度 ===
    totals = data.get("totals", [])
    charts = data.get("charts", [])

    is_online = data.get("is_online", True)
    in_server = data.get("in_server", "Survival")

    # 和排版使用的数值保持一致
    avatar_size = 180
    card_height = 110
    card_gap = 30
    chart_card_h = 300
    chart_gap = 50

    # 统计卡片行数（两列）
    rows = (len(totals) + 1) // 2

    # 头像区高度：padding + 顶部余量 + 头像 + 下方留白
    header_height = Theme.PADDING + 20 + avatar_size + 80
    # 统计卡片区高度：rows * (卡片高度 + 间隔) + 底部额外 40px
    stats_height = rows * (card_height + card_gap) + 40
    # 图表区高度：每个图表 card 高度 + 之间的 50px 间隔
    chart_area_height = len(charts) * (chart_card_h + chart_gap)

    # 是否有地图
    has_map = "location" in data or "path" in data
    map_height = 800 if has_map else 0

    # 预估总高度，再加一点额外余量
    total_height = header_height + stats_height + chart_area_height + map_height + 100
    total_height = max(total_height, 1000)

    # === 真正开始画图 ===
    img = Image.new("RGBA", (Theme.WIDTH, total_height), Theme.BG_COLOR)
    draw = ImageDraw.Draw(img)

    # --- 字体 (全部统一走 load_font) ---
    font_h1 = load_font(64, is_bold=True)
    font_h2 = load_font(36, is_bold=True)
    font_label = load_font(26, is_bold=False)
    font_sub = load_font(26, is_bold=False)
    font_info = load_font(22, is_bold=False)
    font_delta = load_font(22, is_bold=True)
    font_chart_title = load_font(32, is_bold=True)

    cursor_y = Theme.PADDING + 20

    # --- 2. 头部区域 (Avatar + Info) ---
    qq_avatar = crop_circle_avatar(data.get("qq_avatar", ""), avatar_size)
    
    # 顶部生成时间 (左上角，灰色)
    gen_time = data.get("generated_at", "")
    if gen_time:
        draw.text((Theme.PADDING, 15), f"Generated: {gen_time}", fill=Theme.TEXT_SECONDARY, font=font_info, anchor="lt")

    draw.ellipse((Theme.PADDING, cursor_y, Theme.PADDING + avatar_size, cursor_y + avatar_size),
                 fill=Theme.SHADOW_COLOR)
    border_w = 8
    draw.ellipse(
        (Theme.PADDING - border_w, cursor_y - border_w, Theme.PADDING + avatar_size + border_w,
         cursor_y + avatar_size + border_w),
        fill=Theme.CARD_BG,
    )
    img.paste(qq_avatar, (Theme.PADDING, cursor_y), qq_avatar)

    mc_size = 70
    mc_avatar = crop_circle_avatar(data.get("mc_avatar", ""), mc_size)
    badge_x = Theme.PADDING + avatar_size - mc_size + 10
    badge_y = cursor_y + avatar_size - mc_size + 10
    draw.ellipse((badge_x - 4, badge_y - 4, badge_x + mc_size + 4, badge_y + mc_size + 4), fill=Theme.CARD_BG)
    img.paste(mc_avatar, (badge_x, badge_y), mc_avatar)

    text_x = Theme.PADDING + avatar_size + 50
    date_text = data.get("time_range_label", "")
    draw.text((text_x, cursor_y + 10), date_text, fill=Theme.TEXT_SECONDARY, font=font_sub, anchor="lt")

    name_text = data.get("player_name", "Player")
    draw.text((text_x, cursor_y + 45), name_text, fill=Theme.TEXT_PRIMARY, font=font_h1, anchor="lt")

    uuid_str = data.get("uuid", "N/A")
    draw.text((text_x, cursor_y + 125), f"{uuid_str}", fill=Theme.TEXT_SECONDARY, font=font_info, anchor="lt")

    last_seen = data.get("last_seen", "N/A")
    if is_online:
        status_text = f"当前在线于 {in_server}" if in_server else "当前在线"
        status_color = Theme.ONLINE_COLOR
    else:
        status_text = f"最后在线: {last_seen}"
        status_color = Theme.TEXT_SECONDARY
    draw.text((text_x, cursor_y + 155), status_text, fill=status_color, font=font_info,
              anchor="lt")

    cursor_y += avatar_size + 80

    # --- 3. 统计网格 (Grid Stats) ---
    card_gap = 30
    card_height = 110
    card_width = (Theme.WIDTH - 2 * Theme.PADDING - card_gap) // 2

    for idx, item in enumerate(totals):
        row = idx // 2
        col = idx % 2
        cx = Theme.PADDING + col * (card_width + card_gap)
        cy = cursor_y + row * (card_height + card_gap)
        bbox = (cx, cy, cx + card_width, cy + card_height)

        draw_shadow(img, bbox, radius=Theme.CARD_RADIUS, blur=15, offset=(0, 6))
        draw.rounded_rectangle(bbox, radius=Theme.CARD_RADIUS, fill=Theme.CARD_BG)

        y_mid = cy + card_height / 2
        label = item.get("label", "Stat")
        draw.text((cx + 30, y_mid), label, fill=Theme.TEXT_SECONDARY, font=font_label, anchor="lm")

        right_edge_x = cx + card_width - 30
        val_raw = item.get("total", 0)
        val_str = f"{val_raw:,}" if isinstance(val_raw, (int, float)) else str(val_raw)
        delta = item.get("delta", 0)

        if delta != 0:
            delta_str = f"{'+' if delta > 0 else ''}{delta}"
            delta_color = Theme.POSITIVE if delta > 0 else Theme.NEGATIVE
            draw.text((right_edge_x, y_mid), delta_str, fill=delta_color, font=font_delta, anchor="rm")
            delta_len = draw.textlength(delta_str, font=font_delta)
            draw.text((right_edge_x - delta_len - 15, y_mid), val_str, fill=Theme.TEXT_PRIMARY, font=font_h2,
                      anchor="rm")
        else:
            draw.text((right_edge_x, y_mid), val_str, fill=Theme.TEXT_PRIMARY, font=font_h2, anchor="rm")

    rows = (len(totals) + 1) // 2
    cursor_y += rows * (card_height + card_gap) + 40

    # --- 4. 底部图表区 (Charts) ---
    chart_card_h = 300

    for chart in charts:
        bbox = (Theme.PADDING, cursor_y, Theme.WIDTH - Theme.PADDING, cursor_y + chart_card_h)
        draw_shadow(img, bbox, radius=Theme.CARD_RADIUS, blur=25)
        draw.rounded_rectangle(bbox, radius=Theme.CARD_RADIUS, fill=Theme.CARD_BG)

        cx, cy = bbox[0], bbox[1]
        title = chart.get("label", "Trend")
        total_v = chart.get("total", 0)

        draw.text((cx + 40, cy + 30), title, fill=Theme.TEXT_PRIMARY, font=font_chart_title, anchor="lt")
        total_str = f"Total: {total_v}"
        draw.text((bbox[2] - 40, cy + 35), total_str, fill=Theme.TEXT_SECONDARY, font=font_sub, anchor="rt")

        chart_w = (bbox[2] - bbox[0]) - 60
        chart_h = chart_card_h - 100
        chart_img = create_smooth_chart(chart_w, chart_h, chart.get("x", []), chart.get("y", []), title)
        img.paste(chart_img, (cx + 30, cy + 80), chart_img)

        cursor_y += chart_card_h + 50

    # --- 5. 地图展示区 (Map View) ---
    if has_map:
        bbox = (Theme.PADDING, cursor_y, Theme.WIDTH - Theme.PADDING, cursor_y + map_height - 50)

        draw_shadow(img, bbox, radius=Theme.CARD_RADIUS, blur=25)
        mask = Image.new("L", (bbox[2] - bbox[0], bbox[3] - bbox[1]), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, bbox[2] - bbox[0], bbox[3] - bbox[1]), radius=Theme.CARD_RADIUS, fill=255
        )

        renderer = PositionMapRenderer(map_config.get("nether_json"), map_config.get("end_json"))
        map_img = None
        info_data = {}

        inner_w, inner_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        if "location" in data:
            loc = data["location"]
            map_raw, info_data = renderer.generate_location_image(
                inner_w,
                inner_h,
                loc["x"],
                loc["z"],
                loc["dim"],
                data.get("mc_avatar", ""),
                loc.get("yaw", 0),
            )
            map_img = map_raw
            title = "当前位置"

        elif "path" in data:
            path_pts = data["path"]
            map_raw = renderer.generate_path_image(inner_w, inner_h, path_pts, data.get("mc_avatar", ""))
            map_img = map_raw
            title = "最近轨迹"
            info_data = {"is_path": True}

        if map_img:
            container = Image.new("RGBA", (inner_w, inner_h), (0, 0, 0, 0))
            container.paste(map_img, (0, 0))
            img.paste(container, (bbox[0], bbox[1]), mask)

            if info_data and "is_path" not in info_data:
                card_w, card_h = 500, 140
                cx = bbox[0] + (inner_w - card_w) // 2
                cy = bbox[1] + inner_h - card_h - 30

                overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
                od = ImageDraw.Draw(overlay)
                od.rounded_rectangle((0, 0, card_w, card_h), radius=20, fill=(255, 255, 255, 230))
                od.rounded_rectangle((0, 0, card_w, card_h), radius=20, outline=Theme.MAP_LINE_COLOR, width=2)

                dim_str = "The End" if info_data["dim"] == 1 else ("Nether" if info_data["dim"] == -1 else "Overworld")
                dim_color = renderer._get_dim_color(info_data["dim"])

                font_loc = load_font(36, True)
                font_dim = load_font(24, True)
                font_near = load_font(22, False)

                od.text((30, 20), f"{int(info_data['x'])}, {int(info_data['z'])}", fill=Theme.TEXT_PRIMARY,
                        font=font_loc)
                od.text((30, 70), dim_str, fill=dim_color, font=font_dim)

                if info_data.get("nearest_name"):
                    od.text((card_w - 30, 20), "Nearest Station", fill=Theme.TEXT_SECONDARY, font=font_near,
                            anchor="rt")
                    n_name = info_data['nearest_name']
                    if len(n_name) > 12:
                        n_name = n_name[:11] + "..."
                    od.text((card_w - 30, 50), n_name, fill=Theme.TEXT_PRIMARY, font=load_font(26, True), anchor="rt")
                    od.text(
                        (card_w - 30, 90),
                        f"{int(info_data['nearest_dist'])} blocks",
                        fill=Theme.TEXT_SECONDARY,
                        font=font_near,
                        anchor="rt",
                    )

                img.alpha_composite(overlay.convert("RGBA"), (cx, cy))

            draw.text(
                (bbox[0] + 30, bbox[1] + 20),
                title,
                fill=Theme.TEXT_PRIMARY,
                font=font_chart_title,
                stroke_fill=(255, 255, 255),
                stroke_width=4,
            )

        cursor_y += map_height

    # 底部数据来源 (左下角，灰色)
    data_source = data.get("data_source_text", "")
    if data_source:
        ds_font = load_font(20, is_bold=False)
        # 确保不超出边界：简单截断或者换行（这里先简单处理，防止太长）
        if len(data_source) > 60:
             data_source = data_source[:57] + "..."
        draw.text((Theme.PADDING, cursor_y + 10), data_source, fill=Theme.TEXT_SECONDARY, font=ds_font, anchor="lt")
        cursor_y += 40

    # 最终裁剪到实际内容高度
    final_img = img.crop((0, 0, Theme.WIDTH, cursor_y))
    return final_img




if __name__ == "__main__":
    MAP_CONFIG = {
        "nether_json": "the_nether.json",
        "end_json": "the_end.json",
    }

    sample_data = {
        "qq_avatar": "qq_avatar.png",
        "mc_avatar": "mc_avatar.png",
        "player_name": "CalciumSilicate",
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "last_seen": "2025-01-07 14:30",
        "time_range_label": "Weekly Report",
        "totals": [
            {"label": "上线次数", "total": 222, "delta": -5},
            {"label": "挖掘方块", "total": 2587394, "delta": 4321},
            {"label": "在线时长 (hr)", "total": 1345, "delta": 120},
            {"label": "击杀生物", "total": 222, "delta": -5},
        ],
        "charts": [
            {
                "label": "每日活跃 (hr)",
                "total": 1345,
                "x": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "y": [2, 3.5, 4.5, 3.0, 8.5, 12.0, 9.0],
            },
            {
                "label": "挖掘总量",
                "total": 2587394,
                "x": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "y": [2587194, 2587294, 2587394, 2587494, 2587594, 2587694, 2598794],
            },
        ],
        "path": [
            (0, 0, 0),
            (100, 100, -1),
            (200, 100, -1),
            (-254, -37, -1),
            (100, 0, 1),
            (77, 262, 1),
            (-919, 621, 1),
            (0, 0, 1),
        ],
    }

    render_combined_view(sample_data, MAP_CONFIG).save("A.png")
