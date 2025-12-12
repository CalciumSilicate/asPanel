import io
import math
import os
import platform
import functools
import hashlib
import httpx
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Union, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# 尝试导入项目配置，如果没有则使用默认值
try:
    from backend.core.constants import BASE_DIR, AVATAR_MC_PATH

    # 假设你的字体路径
    FONT_REGULAR_PATH = BASE_DIR / "backend/resources/fonts/MapleMono-NF-CN-Regular.ttf"
    FONT_BOLD_PATH = BASE_DIR / "backend/resources/fonts/MapleMono-NF-CN-Bold.ttf"
except ImportError:
    BASE_DIR = "."
    AVATAR_MC_PATH = None  # <--- 本地运行时的 fallback
    FONT_REGULAR_PATH = None
    FONT_BOLD_PATH = None

# md5 工具与项目保持一致（与 /users/mc/avatar 的缓存命名相同）
try:
    from backend.core.utils import get_str_md5
except ImportError:
    def get_str_md5(text: str) -> str:
        md5_obj = hashlib.md5()
        md5_obj.update(text.encode("utf-8"))
        return md5_obj.hexdigest()


# ========= 主题配置 (保持一致性) =========

class Theme:
    BG_COLOR = (248, 249, 252)  # 全局背景
    CARD_BG = (255, 255, 255)  # 卡片背景
    SHADOW_COLOR = (20, 30, 60, 20)  # 阴影颜色

    TEXT_PRIMARY = (30, 35, 50)  # 主标题/ID
    TEXT_SECONDARY = (130, 140, 160)  # 次要信息/标签
    TEXT_TIME = (16, 185, 129)  # 在线时长 (绿色高亮)

    SERVER_TITLE_BG = (240, 242, 245)  # 服务器标题栏背景 (可选)

    WIDTH = 1080
    PADDING = 60
    CARD_RADIUS = 24
    AVATAR_SIZE = 64


# ========= 基础工具函数 =========

@functools.lru_cache(maxsize=128)
def load_font(size: int, is_bold: bool = False) -> ImageFont.FreeTypeFont:
    """加载字体，带缓存"""
    preferred_path = FONT_BOLD_PATH if is_bold else FONT_REGULAR_PATH
    try:
        if preferred_path and os.path.exists(preferred_path):
            return ImageFont.truetype(str(preferred_path), size)
    except Exception:
        pass
    # 简单的 Fallback
    return ImageFont.load_default()


def draw_shadow(img: Image.Image, bbox: Tuple[int, int, int, int], radius: int, blur: int = 15, offset=(0, 6)):
    """绘制卡片阴影"""
    x0, y0, x1, y1 = map(int, bbox)
    w, h = x1 - x0, y1 - y0
    shadow_w = w + blur * 4
    shadow_h = h + blur * 4
    shadow_img = Image.new("RGBA", (shadow_w, shadow_h), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_img)
    sx0, sy0 = blur * 2 + offset[0], blur * 2 + offset[1]
    shadow_draw.rounded_rectangle((sx0, sy0, sx0 + w, sy0 + h), radius=radius, fill=Theme.SHADOW_COLOR)
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(shadow_img, (x0 - blur * 2, y0 - blur * 2))

def _crop_to_circle(img: Image.Image, size: int) -> Image.Image:
    """通用工具：将图片裁剪为圆形"""
    img = img.convert("RGBA")
    # 使用 LANCZOS 高质量缩放
    img = img.resize((size, size), Image.LANCZOS)
    
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)
    return output

def _load_local_avatar(name: Optional[str] = None, uuid: Optional[str] = None) -> Optional[Image.Image]:
    """尝试从本地缓存加载头像。

    项目在 /users/mc/avatar 中以 md5(mc_name_or_uuid).png 方式缓存，
    这里保持一致，并兼容早期 clean_uuid.png 命名。
    """
    if not AVATAR_MC_PATH:
        return None

    candidates: List[str] = []
    if uuid:
        candidates.append(get_str_md5(uuid))
        candidates.append(uuid.replace("-", ""))  # legacy
    if name:
        candidates.append(get_str_md5(name))

    seen = set()
    for key in candidates:
        if not key or key in seen:
            continue
        seen.add(key)
        file_path = (AVATAR_MC_PATH / f"{key}.png")
        if file_path.exists() and file_path.is_file():
            try:
                return Image.open(file_path).convert("RGBA")
            except Exception:
                continue
    return None


@functools.lru_cache(maxsize=128)
def _download_remote_avatar(mc_name_or_uuid: str) -> Optional[Image.Image]:
    """从多个来源下载头像 (带缓存)。失败返回 None。"""
    if not mc_name_or_uuid:
        return None

    urls = [
        f"https://api.mcheads.org/avatar/{mc_name_or_uuid}",
        f"https://mineskin.eu/helm/{mc_name_or_uuid}",
        f"https://crafatar.com/avatars/{mc_name_or_uuid}",
        f"https://mc-heads.net/avatar/{mc_name_or_uuid}",
        f"https://minotar.net/helm/{mc_name_or_uuid}"
    ]

    timeout = httpx.Timeout(5.0, connect=3.0)
    for url in urls:
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            if resp.status_code == 200 and resp.content:
                return Image.open(io.BytesIO(resp.content)).convert("RGBA")
        except Exception:
            continue
    return None

def get_player_avatar(name: str, uuid: str = None, size: int = 64) -> Image.Image:
    """
    获取头像流程：
    1. 优先去 AVATAR_MC_PATH 找本地 md5 缓存（兼容 legacy）。
    2. 如果本地没有，按多来源顺序下载。
    3. 统一裁剪为圆形返回。
    """
    raw_img = _load_local_avatar(name=name, uuid=uuid)

    if raw_img is None:
        key = uuid or name
        raw_img = _download_remote_avatar(key)

    if raw_img is None:
        raw_img = Image.new("RGBA", (64, 64), (200, 200, 200))

    return _crop_to_circle(raw_img, size)
def format_duration(start_time: Union[datetime, float, None]) -> str:
    """计算并格式化在线时长 (统一使用 UTC 计算)"""
    if start_time is None:
        return ""

    # 1. 获取标准的当前 UTC 时间 (带时区信息)
    now = datetime.now(timezone.utc)

    # 2. 规范化 start_time
    if isinstance(start_time, (int, float)):
        # 时间戳本身就是基于 UTC 的
        start_dt = datetime.fromtimestamp(start_time, timezone.utc)
    else:
        start_dt = start_time
        # 如果传入的时间没有时区 (Naive)，且你知道数据库存的是 UTC，则强制标记为 UTC
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        else:
            # 如果传入的时间已经有时区 (比如之前已经被转成了东八区)，则将其转回 UTC 进行对其计算
            start_dt = start_dt.astimezone(timezone.utc)

    # 3. 计算差值
    delta = now - start_dt
    total_seconds = int(delta.total_seconds())

    # 防止服务器时间不同步或微小误差导致出现负数
    if total_seconds < 0:
        total_seconds = 0

    if total_seconds < 60:
        return "< 1m"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


# ========= 渲染核心 =========

def render_player_list_image(
        group_name: str,
        servers: List[Dict],  # [{'name': 'Survival', 'players': [{'name': 'Steve', 'login_time': dt}, ...]}, ...]
) -> Image.Image:
    """
    渲染在线玩家列表图片
    """
    # 1. 计算总人数
    total_online = sum(len(s.get('players', [])) for s in servers)

    # 2. 布局预计算
    # 字体
    font_h1 = load_font(48, True)
    font_h2 = load_font(28, True)
    font_p = load_font(26, True)  # 玩家ID
    font_time = load_font(22, False)  # 时间
    font_sub = load_font(24, False)  # 空状态

    # 尺寸常量
    card_width = (Theme.WIDTH - Theme.PADDING * 2 - 40) // 2  # 双列
    if len(servers) == 1:
        card_width = Theme.WIDTH - Theme.PADDING * 2  # 单列

    player_row_h = 90
    header_h = 70

    # 计算每个卡片的高度
    server_cards = []
    for srv in servers:
        p_count = len(srv.get('players', []))
        # 标题栏 + 玩家列表 + 底部留白
        if p_count == 0:
            h = header_h + 60  # 空状态高度
        else:
            h = header_h + p_count * player_row_h + 20
        server_cards.append({
            "data": srv,
            "height": h,
            "width": card_width
        })

    # 瀑布流排版计算 (Waterfall Layout)
    col_y = [0, 0]  # 两列的当前 Y 坐标
    if len(servers) == 1:
        col_y = [0]  # 单列模式

    card_positions = []  # (x, y, card_info)

    # 顶部 Title 区域高度
    title_area_h = 160

    for card in server_cards:
        # 找当前较短的一列
        col_idx = col_y.index(min(col_y))

        x = Theme.PADDING + col_idx * (card_width + 40)
        y = title_area_h + col_y[col_idx]

        card_positions.append((x, y, card))
        col_y[col_idx] += card['height'] + 40  # 卡片间距

    total_height = max(col_y) + title_area_h + Theme.PADDING
    total_height = max(total_height, 600)  # 最小高度

    # 3. 开始绘图
    img = Image.new("RGBA", (Theme.WIDTH, total_height), Theme.BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 绘制头部
    draw.text((Theme.PADDING, 50), group_name, fill=Theme.TEXT_PRIMARY, font=font_h1, anchor="lt")

    sub_text = f"共在线: {total_online}"
    draw.text((Theme.PADDING, 110), sub_text, fill=Theme.TEXT_TIME, font=font_sub, anchor="lt")

    # 绘制生成时间
    gen_time = datetime.now().strftime("%H:%M")
    draw.text((Theme.WIDTH - Theme.PADDING, 60), f"查询于 {gen_time}", fill=Theme.TEXT_SECONDARY, font=font_sub,
              anchor="rt")

    # 绘制卡片
    for x, y, card in card_positions:
        srv_data = card['data']
        w, h = card['width'], card['height']

        # 卡片阴影与背景
        bbox = (x, y, x + w, y + h)
        draw_shadow(img, bbox, radius=Theme.CARD_RADIUS)
        draw.rounded_rectangle(bbox, radius=Theme.CARD_RADIUS, fill=Theme.CARD_BG)

        # 服务器标题栏
        # draw.rounded_rectangle((x, y, x + w, y + header_h), radius=Theme.CARD_RADIUS, corners=(True, True, False, False), fill=Theme.SERVER_TITLE_BG)

        srv_name = srv_data.get('name', 'Unknown Server')
        p_list = srv_data.get('players', [])

        # 服务器名
        draw.text((x + 25, y + header_h // 2), srv_name, fill=Theme.TEXT_PRIMARY, font=font_h2, anchor="lm")
        # 人数 Badge
        count_text = f"{len(p_list)} 在线"
        draw.text((x + w - 25, y + header_h // 2), count_text, fill=Theme.TEXT_SECONDARY, font=font_sub, anchor="rm")

        # 分割线
        draw.line((x + 15, y + header_h, x + w - 15, y + header_h), fill=(240, 240, 240), width=2)

        # 绘制玩家列表
        current_y = y + header_h + 10
        if not p_list:
            draw.text((x + w // 2, current_y + 30), "无人在线", fill=Theme.TEXT_SECONDARY, font=font_sub,
                      anchor="mm")
        else:
            for p in p_list:
                p_name = p.get('name', 'Unknown')
                p_uuid = p.get('uuid')
                p_login = p.get('login_time')

                # 头像
                avatar_img = get_player_avatar(p_name, p_uuid, Theme.AVATAR_SIZE)
                # 垂直居中偏移
                av_y = int(current_y + (player_row_h - Theme.AVATAR_SIZE) / 2)
                img.paste(avatar_img, (int(x + 25), av_y), avatar_img)

                # 名字
                text_x = x + 25 + Theme.AVATAR_SIZE + 20
                row_mid_y = current_y + player_row_h / 2
                draw.text((text_x, row_mid_y), p_name, fill=Theme.TEXT_PRIMARY, font=font_p, anchor="lm")

                # 在线时长
                duration_str = format_duration(p_login)
                if duration_str:
                    draw.text((x + w - 25, row_mid_y), duration_str, fill=Theme.TEXT_TIME, font=font_time, anchor="rm")

                current_y += player_row_h

    return img


# ========= 测试代码 (独立运行时执行) =========
if __name__ == "__main__":
    # 模拟数据
    mock_servers = [
        {
            "name": "Survival Server",
            "players": [
                {"name": "Notch", "login_time": datetime.now() - timedelta(minutes=135)},
                {"name": "Alex", "login_time": datetime.now() - timedelta(minutes=15)},
                {"name": "Steve", "login_time": datetime.now() - timedelta(hours=5, minutes=2)},
            ]
        },
        {
            "name": "Creative World",
            "players": [
                {"name": "Dream", "login_time": datetime.now() - timedelta(seconds=50)},
            ]
        },
        {
            "name": "Mirror Server",
            "players": []
        }
    ]

    img = render_player_list_image("My Server Group", mock_servers)
    img.save("test_players.png")
    print("Test image saved to test_players.png")
