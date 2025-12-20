import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from backend.services.qq_stats_image import Theme, crop_circle_avatar, draw_shadow, load_font, truncate_text


def _hex_to_rgb(s: str) -> Tuple[int, int, int]:
    s = (s or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join([c * 2 for c in s])
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return (120, 120, 120)


_LINE_RGB = _hex_to_rgb(getattr(Theme, "CHART_LINE_COLOR", "#6366f1"))
_FILL_RGB = _hex_to_rgb(getattr(Theme, "CHART_FILL_COLOR", "#818cf8"))


@dataclass
class RankRow:
    rank: int
    player_name: str
    player_uuid: str
    score_text: str
    avatar_big: str
    avatar_small: str
    trend_values: Optional[List[float]] = None


def _create_sparkline(values: Sequence[float], width: int, height: int) -> Image.Image:
    vals = [0.0 if v is None else float(v) for v in values]
    vals = [0.0 if v < 0 else v for v in vals]
    n = len(vals)
    if n <= 0:
        vals = [0.0]
        n = 1

    max_v = max(vals) if vals else 0.0
    if not math.isfinite(max_v) or max_v <= 0:
        max_v = 0.0

    scale = 2
    w2, h2 = int(width * scale), int(height * scale)
    pad = int(8 * scale)
    img = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    base_y = h2 - pad
    inner_h = max(1, h2 - pad * 2)
    inner_w = max(1, w2 - pad * 2)

    xs: List[float] = []
    ys: List[float] = []
    for i, v in enumerate(vals):
        if n == 1:
            x = pad + inner_w / 2
        else:
            x = pad + (inner_w * i / (n - 1))
        if max_v <= 0:
            y = base_y
        else:
            y = base_y - (float(v) / max_v) * inner_h
        xs.append(x)
        ys.append(y)

    points = list(zip(xs, ys))
    if len(points) >= 2:
        poly = [(xs[0], base_y), *points, (xs[-1], base_y)]
    else:
        poly = [(xs[0], base_y), (xs[0], ys[0]), (xs[0], base_y)]

    draw.polygon(poly, fill=(*_FILL_RGB, 55))
    draw.line(points, fill=(*_LINE_RGB, 255), width=int(3 * scale), joint="curve")

    # baseline
    draw.line([(pad, base_y), (w2 - pad, base_y)], fill=(210, 215, 225, 140), width=int(1 * scale))

    out = img.resize((width, height), Image.LANCZOS)
    return out


def render_rank_image(*, title: str, subtitle: str, rows: List[RankRow], show_trend: bool) -> Image.Image:
    width = 1500 if show_trend else 1200
    padding = 60
    card_radius = 24
    card_gap = 18

    font_title = load_font(52, is_bold=True)
    font_sub = load_font(26, is_bold=False)
    font_rank = load_font(34, is_bold=True)
    font_name = load_font(30, is_bold=True)
    font_uuid = load_font(18, is_bold=False)
    font_score = load_font(28, is_bold=True)
    font_score_small = load_font(22, is_bold=True)

    header_h = 0
    header_h += padding
    header_h += int(font_title.size * 1.15)
    header_h += 10
    header_h += int(font_sub.size * 1.2)
    header_h += 30

    row_h = 118
    total_h = header_h + (row_h + card_gap) * len(rows) - (card_gap if rows else 0) + padding
    total_h = max(total_h, header_h + padding + 120)

    img = Image.new("RGBA", (width, int(total_h)), Theme.BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Header
    x0 = padding
    y = padding
    draw.text((x0, y), title, fill=Theme.TEXT_PRIMARY, font=font_title, anchor="lt")
    y += int(font_title.size * 1.15) + 8
    draw.text((x0, y), subtitle, fill=Theme.TEXT_SECONDARY, font=font_sub, anchor="lt")
    y = header_h

    # Columns config
    inner_pad_x = 28
    col_gap = 20
    rank_w = 90
    avatar_w = 120
    score_w = 240
    trend_w = 320 if show_trend else 0

    card_w = width - padding * 2
    inner_w = card_w - inner_pad_x * 2
    cols = 5 if show_trend else 4
    gaps = (cols - 1) * col_gap
    name_w = inner_w - rank_w - avatar_w - score_w - trend_w - gaps
    name_w = max(220, int(name_w))

    def _rank_color(n: int):
        if n == 1:
            return (234, 179, 8)  # gold
        if n == 2:
            return (156, 163, 175)  # silver
        if n == 3:
            return (194, 120, 63)  # bronze
        return Theme.TEXT_SECONDARY

    for row in rows:
        cy = y
        bbox = (padding, cy, padding + card_w, cy + row_h)
        draw_shadow(img, bbox, radius=card_radius, blur=10, offset=(0, 4))
        draw.rounded_rectangle(bbox, radius=card_radius, fill=Theme.CARD_BG)

        content_x = padding + inner_pad_x
        center_y = cy + row_h / 2

        # Rank
        rx_center = content_x + rank_w / 2
        draw.text((rx_center, center_y), str(row.rank), fill=_rank_color(row.rank), font=font_rank, anchor="mm")
        content_x += rank_w + col_gap

        # Avatars
        avatar_size = 64
        badge_size = 24
        big_left = int(content_x + (avatar_w - avatar_size) / 2)
        big_top = int(center_y - avatar_size / 2)
        big = crop_circle_avatar(row.avatar_big, avatar_size)
        img.paste(big, (big_left, big_top), big)

        # badge
        badge_left = big_left + avatar_size - badge_size + 4
        badge_top = big_top + avatar_size - badge_size + 4
        draw.ellipse((badge_left - 3, badge_top - 3, badge_left + badge_size + 3, badge_top + badge_size + 3), fill=Theme.CARD_BG)
        small = crop_circle_avatar(row.avatar_small, badge_size)
        img.paste(small, (badge_left, badge_top), small)

        content_x += avatar_w + col_gap

        # Name + uuid
        name_x = content_x
        name_text = truncate_text(draw, row.player_name or "Unknown", font_name, name_w)
        draw.text((name_x, center_y - 16), name_text, fill=Theme.TEXT_PRIMARY, font=font_name, anchor="lm")
        uuid_text = truncate_text(draw, row.player_uuid or "", font_uuid, name_w)
        draw.text((name_x, center_y + 20), uuid_text, fill=Theme.TEXT_SECONDARY, font=font_uuid, anchor="lm")
        content_x += name_w + col_gap

        # Score (right aligned)
        score_right = content_x + score_w
        score_font = font_score
        if draw.textlength(row.score_text or "", font=score_font) > (score_w - 10):
            score_font = font_score_small
        draw.text((score_right - 8, center_y), row.score_text or "", fill=Theme.TEXT_PRIMARY, font=score_font, anchor="rm")
        content_x += score_w + col_gap

        # Trend sparkline
        if show_trend:
            trend_h = 64
            if row.trend_values:
                spark = _create_sparkline(row.trend_values, trend_w, trend_h)
                img.paste(spark, (int(content_x), int(center_y - trend_h / 2)), spark)
            else:
                draw.text((content_x + trend_w / 2, center_y), "—", fill=Theme.TEXT_SECONDARY, font=font_sub, anchor="mm")

        y += row_h + card_gap

    return img

