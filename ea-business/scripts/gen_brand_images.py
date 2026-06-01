#!/usr/bin/env python3
"""Generate X (Twitter) brand images for @kensho_log (MT5 tool maker).

Produces, in the same dark-navy brand as the listing images:
  - header        : X header 1500x500 (3:1)
  - lineup        : 3-tool summary card 1600x900 (16:9) — pinned-post image
  - agency        : indicator/EA commission price card 1200x1500 (4:5)

All text is Japanese (system IPA gothic). A compliance line is always drawn.
No GenAI; pure PIL composition.

Usage:
    python gen_brand_images.py [--outdir ../marketing/images]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG_TOP = (11, 16, 32)
BG_BOT = (20, 27, 48)
CARD   = (26, 34, 58)
LINE   = (36, 49, 82)
FG     = (230, 236, 255)
MUTED  = (159, 176, 217)
ACCENT = (59, 130, 246)
GREEN  = (34, 197, 94)
PURPLE = (124, 58, 237)
CYAN   = (8, 145, 178)
RED    = (225, 29, 72)
AMBER  = (217, 119, 6)


def find_font() -> str:
    for c in [
        os.environ.get("RG_FONT", ""),
        "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
        "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/etc/alternatives/fonts-japanese-gothic.ttf",
    ]:
        if c and os.path.exists(c):
            return c
    raise SystemExit("Japanese font not found. Set RG_FONT or install IPA gothic.")


FONT_PATH = find_font()


def font(sz):
    return ImageFont.truetype(FONT_PATH, sz)


def vgradient(w, h):
    top = Image.new("RGB", (w, h), BG_TOP)
    bot = Image.new("RGB", (w, h), BG_BOT)
    mask = Image.new("L", (w, h))
    md = mask.load()
    for y in range(h):
        v = int(255 * y / max(1, h - 1))
        for x in range(w):
            md[x, y] = v
    return Image.composite(bot, top, mask)


def tw(draw, s, f):
    b = draw.textbbox((0, 0), s, font=f)
    return b[2] - b[0]


def rounded(draw, box, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def chip(draw, x, y, text, fg, bg, fsize=26, padx=18, pady=10):
    f = font(fsize)
    w = tw(draw, text, f)
    rounded(draw, [x, y, x + w + padx * 2, y + fsize + pady * 2], (fsize + pady * 2) // 2, fill=bg)
    draw.text((x + padx, y + pady), text, font=f, fill=fg)
    return w + padx * 2


# ---------------------------------------------------------------- header
def make_header(w=1500, h=500):
    img = vgradient(w, h)
    d = ImageDraw.Draw(img)
    # left brand block
    d.text((60, 120), "検証ログ", font=font(96), fill=FG)
    d.text((64, 232), "｜ MT5ツール制作", font=font(46), fill=ACCENT)
    d.text((66, 300), "機械学習で検証しながら、MT5補助ツールを自作・公開。", font=font(30), fill=MUTED)
    # right: three tool chips stacked, right-aligned within the canvas
    chips = [("RiskGuard ・ 発注", GREEN),
             ("TrailManager ・ 管理", PURPLE),
             ("TradeCloser ・ 決済", RED)]
    f = font(28)
    chip_w = max(tw(d, lbl, f) for lbl, _ in chips) + 64
    cx = w - 60 - chip_w
    cy = 150
    for label, col in chips:
        rounded(d, [cx, cy, cx + chip_w, cy + 56], 12, fill=CARD, outline=col, width=3)
        d.ellipse([cx + 18, cy + 20, cx + 34, cy + 36], fill=col)
        d.text((cx + 48, cy + 14), label, font=f, fill=FG)
        cy += 72
    d.text((60, h - 46), "※相場予測・利益保証はしません／個人の検証ログです。", font=font(20), fill=MUTED)
    return img


# ---------------------------------------------------------------- lineup
def tool_card(d, x, y, w, h, name, role, price, feats, col):
    rounded(d, [x, y, x + w, y + h], 16, fill=CARD, outline=LINE, width=2)
    d.rectangle([x, y, x + 8, y + h], fill=col)  # accent bar
    d.text((x + 26, y + 22), name, font=font(34), fill=FG)
    d.text((x + 26, y + 66), role, font=font(22), fill=col)
    fy = y + 110
    for ft in feats:
        d.ellipse([x + 26, fy + 6, x + 38, fy + 18], fill=col)
        d.text((x + 50, fy), ft, font=font(21), fill=MUTED)
        fy += 36
    d.text((x + 26, y + h - 50), price, font=font(26), fill=FG)


def make_lineup(w=1600, h=900):
    img = vgradient(w, h)
    d = ImageDraw.Draw(img)
    d.text((60, 48), "MT5 補助ツール 3点", font=font(60), fill=FG)
    d.text((64, 124), "発注 → 管理 → 決済。トレードの「作業」を機械化する道具。", font=font(28), fill=MUTED)

    cw, ch, gap = 480, 520, 30
    x0 = 60
    y0 = 200
    tool_card(d, x0, y0, cw, ch, "RiskGuard", "発注＋リスク管理", "買い切り ¥7,500（$49）",
              ["リスク%でロット自動計算", "SL・TP付きで発注", "建値移動・トレーリング", "スプレッドガード"], GREEN)
    tool_card(d, x0 + (cw + gap), y0, cw, ch, "TrailManager", "ポジション管理", "買い切り ¥6,800（$45）",
              ["どの玉にもトレーリング後付け", "FIXED/ATR/STEP 3モード", "建値移動を自動", "他ツール・手動の玉もOK"], PURPLE)
    tool_card(d, x0 + 2 * (cw + gap), y0, cw, ch, "TradeCloser", "決済・管理", "買い切り ¥5,900（$39）",
              ["全/銘柄別/勝ち負け別決済", "部分決済（%指定）", "利益目標・損失上限で自動決済", "緊急停止 PANIC"], RED)

    d.text((60, h - 52), "※すべて補助ツールです。相場予測・利益保証はしません。取引にはリスクが伴い、過去の成績は将来を保証しません。",
           font=font(20), fill=MUTED)
    return img


# ---------------------------------------------------------------- agency
def make_agency(w=1200, h=1500):
    img = vgradient(w, h)
    d = ImageDraw.Draw(img)
    chip(d, 60, 56, "［ 受付中 ］", FG, ACCENT, fsize=28)
    d.text((60, 130), "インジ・EA", font=font(86), fill=FG)
    d.text((60, 228), "作成代行", font=font(86), fill=FG)
    d.text((64, 340), "「こんなインジが欲しい」をMQL5で形にします。", font=font(30), fill=MUTED)

    rows = [
        ("カスタムインジ作成", "¥5,000〜"),
        ("標準的なツール作成", "¥10,000〜"),
        ("EA（ロジックは依頼者提供）", "¥20,000〜"),
        ("改造・不具合修正・移植", "¥5,000〜"),
    ]
    y = 430
    for label, price in rows:
        rounded(d, [60, y, w - 60, y + 96], 14, fill=CARD, outline=LINE, width=2)
        d.text((86, y + 28), label, font=font(34), fill=FG)
        pf = font(36)
        d.text((w - 86 - tw(d, price, pf), y + 26), price, font=pf, fill=ACCENT)
        y += 116

    y += 14
    d.text((60, y), "ご依頼の流れ", font=font(34), fill=FG)
    y += 56
    for i, step in enumerate(["DMで要件をお知らせ", "見積もり・納期を回答", "合意後に着手 → 納品", "動作確認・軽微な修正"], 1):
        d.ellipse([60, y, 96, y + 36], fill=ACCENT)
        d.text((72, y + 2), str(i), font=font(28), fill=FG)
        d.text((112, y + 2), step, font=font(30), fill=MUTED)
        y += 56

    y += 20
    rounded(d, [60, y, w - 60, y + 150], 14, fill=(26, 18, 5), outline=(90, 68, 16), width=2)
    d.text((84, y + 24),
           "※ 仕様通りの動作は保証しますが、収益は保証しません。",
           font=font(26), fill=AMBER_TEXT())
    d.text((84, y + 64),
           "※ 投資助言は行いません。売買判断はご自身で。",
           font=font(26), fill=AMBER_TEXT())
    d.text((84, y + 104),
           "▶ ご相談は X DM / ココナラ まで",
           font=font(28), fill=FG)
    return img


def AMBER_TEXT():
    return (255, 217, 138)


SIZES = {
    "x-header": make_header,
    "lineup": make_lineup,
    "agency-card": make_agency,
}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", default=str(Path(__file__).parent.parent / "marketing" / "images"))
    args = ap.parse_args(argv)
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for name, fn in SIZES.items():
        img = fn()
        fp = out / f"kensho-{name}.png"
        img.save(fp, "PNG")
        made.append(str(fp))
    print("\n".join(made))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
