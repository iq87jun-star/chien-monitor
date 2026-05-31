#!/usr/bin/env python3
"""Generate listing / promo images (PNG) for the auxiliary tools.

Produces clean, on-brand product images with Japanese text for:
  - Coconala (ココナラ) cover  : 4:3  (1200x900)
  - X / Twitter promo          : 16:9 (1600x900)

Design matches the landing page (dark navy theme). A mandatory risk
disclaimer is always rendered on the image (compliance: no profit claims,
function-only messaging).

Requires Pillow and a Japanese font. The font is taken from
japanize-matplotlib (IPAexGothic) if available; install with:
    pip install japanize-matplotlib

Usage:
    python gen_listing_images.py            # generate all
    python gen_listing_images.py --outdir ../marketing/images
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---- theme (matches landing/index.html) ----
BG_TOP   = (11, 16, 32)     # #0b1020
BG_BOT   = (20, 27, 48)     # #141b30
CARD     = (26, 34, 58)
LINE     = (36, 49, 82)
FG       = (230, 236, 255)
MUTED    = (159, 176, 217)
ACCENT   = (59, 130, 246)   # blue
GREEN    = (34, 197, 94)
RED      = (225, 29, 72)
AMBER    = (255, 217, 138)


def find_font() -> str:
    candidates = [
        "/usr/lib/python3.11/site-packages/japanize_matplotlib/data/IPAexGothic.ttf",
    ]
    try:
        import japanize_matplotlib  # noqa
        base = Path(japanize_matplotlib.__file__).parent / "data" / "IPAexGothic.ttf"
        candidates.insert(0, str(base))
    except Exception:
        pass
    for c in candidates:
        if os.path.exists(c):
            return c
    raise SystemExit("Japanese font not found. Run: pip install japanize-matplotlib")


FONT_PATH = find_font()


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size)


def vgradient(w: int, h: int) -> Image.Image:
    base = Image.new("RGB", (w, h), BG_TOP)
    top = Image.new("RGB", (w, h), BG_TOP)
    bot = Image.new("RGB", (w, h), BG_BOT)
    mask = Image.new("L", (w, h))
    md = mask.load()
    for y in range(h):
        v = int(255 * y / max(1, h - 1))
        for x in range(w):
            md[x, y] = v
    base = Image.composite(bot, top, mask)
    return base


def rounded(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_w(draw, s, f):
    b = draw.textbbox((0, 0), s, font=f)
    return b[2] - b[0]


def draw_checks(draw, x, y, items, f, gap=58):
    for i, it in enumerate(items):
        cy = y + i * gap
        # check circle
        r = 14
        draw.ellipse([x, cy, x + 2 * r, cy + 2 * r], fill=GREEN)
        draw.line([x + 7, cy + 14, x + 12, cy + 19], fill=BG_TOP, width=3)
        draw.line([x + 12, cy + 19, x + 22, cy + 8], fill=BG_TOP, width=3)
        draw.text((x + 2 * r + 16, cy - 2), it, font=f, fill=FG)


def draw_panel_mock(draw, x, y, w, buttons):
    """Draw a small mock on-chart panel with labeled buttons."""
    pad = 16
    bh = 46
    rows = (len(buttons) + 1) // 2
    h = pad * 2 + 26 + rows * (bh + 10)
    rounded(draw, [x, y, x + w, y + h], 14, fill=CARD, outline=LINE, width=2)
    draw.text((x + pad, y + pad), "MT5 パネル", font=font(20), fill=MUTED)
    by = y + pad + 30
    bw = (w - pad * 2 - 10) // 2
    for i, (label, col) in enumerate(buttons):
        col_i = i % 2
        row_i = i // 2
        bx = x + pad + col_i * (bw + 10)
        ny = by + row_i * (bh + 10)
        rounded(draw, [bx, ny, bx + bw, ny + bh], 8, fill=col)
        f = font(20)
        tw = text_w(draw, label, f)
        draw.text((bx + (bw - tw) // 2, ny + (bh - 26) // 2), label, font=f, fill=(255, 255, 255))
    return h


def price_badge(draw, x, y, text):
    f = font(30)
    tw = text_w(draw, text, f)
    pad = 18
    rounded(draw, [x, y, x + tw + pad * 2, y + 52], 26, fill=ACCENT)
    draw.text((x + pad, y + 10), text, font=f, fill=(255, 255, 255))


def disclaimer(draw, w, h, text):
    f = font(18)
    draw.text((48, h - 40), text, font=f, fill=MUTED)


def make_image(spec: dict, size: tuple[int, int], variant: str) -> Image.Image:
    w, h = size
    img = vgradient(w, h)
    d = ImageDraw.Draw(img)

    # left text column
    lx = 48
    d.text((lx, 54), spec["name"], font=font(76), fill=FG)
    d.text((lx, 150), spec["tag"], font=font(30), fill=MUTED)

    draw_checks(d, lx, 232, spec["features"], font(28))

    price_badge(d, lx, 232 + len(spec["features"]) * 58 + 18, spec["price"])

    # right column: panel mock (only on wide enough)
    panel_w = 430
    px = w - panel_w - 48
    py = 150
    draw_panel_mock(d, px, py, panel_w, spec["buttons"])

    # "MT5 / 補助ツール" tag top-right
    tagf = font(22)
    tt = "MetaTrader 5 ・ 補助ツール"
    d.text((w - 48 - text_w(d, tt, tagf), 60), tt, font=tagf, fill=MUTED)

    disclaimer(d, w, h, spec["disclaimer"])
    return img


SPECS = {
    "riskguard": {
        "name": "RiskGuard",
        "tag": "リスク％を決めれば、ロット計算もSL/TPもおまかせ。",
        "features": [
            "リスク％から適正ロットを自動計算",
            "ワンクリックでSL・TP付き発注",
            "建値移動・トレーリングを自動管理",
            "スプレッドが広い時はエントリー抑止",
        ],
        "price": "買い切り ¥7,500（$49）",
        "buttons": [("BUY", GREEN), ("SELL", RED), ("CLOSE ALL", (90, 90, 100))],
        "disclaimer": "※相場予測・利益保証はしません。取引にはリスクが伴い、過去の成績は将来を保証しません。",
    },
    "tradecloser": {
        "name": "TradeCloser",
        "tag": "保有ポジションも待機注文も、1クリックで思い通りに決済。",
        "features": [
            "全決済／銘柄別／勝ち・負けのみ決済",
            "部分決済（％指定）で段階的に縮小",
            "合計損益が目標・上限で自動全決済",
            "緊急停止 PANIC ボタン搭載",
        ],
        "price": "買い切り ¥5,900（$39）",
        "buttons": [
            ("CLOSE ALL", RED), ("WINNERS", GREEN),
            ("LOSERS", (217, 119, 6)), ("PANIC", (220, 20, 60)),
        ],
        "disclaimer": "※決済作業の補助です。利益保証はしません。取引にはリスクが伴い、過去の成績は将来を保証しません。",
    },
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", default=str(Path(__file__).parent.parent / "marketing" / "images"))
    args = ap.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    sizes = {"coconala": (1200, 900), "twitter": (1600, 900)}
    made = []
    for key, spec in SPECS.items():
        for variant, size in sizes.items():
            img = make_image(spec, size, variant)
            fp = outdir / f"{key}-{variant}.png"
            img.save(fp, "PNG")
            made.append(str(fp))
    print("\n".join(made))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
