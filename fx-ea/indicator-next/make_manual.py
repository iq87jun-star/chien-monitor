#!/usr/bin/env python3
"""SALES.md の「取扱説明書(同梱用)」から 取扱説明書.pdf を生成する。

  python3 make_manual.py

出品zipに同梱するPDF。文面の源は SALES.md ただ一つで、ここでは整形だけを行う。
SALES.md を直したら、これを回してPDFも作り直すこと。
"""
import os, re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                Paragraph, Preformatted, Spacer)
from reportlab.lib.styles import ParagraphStyle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "取扱説明書.pdf")

pdfmetrics.registerFont(TTFont("JPGothic", "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"))
pdfmetrics.registerFont(TTFont("JPMono", "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"))

INK = HexColor("#1a1a1a")
SUB = HexColor("#555555")
ACC = HexColor("#2f4f6f")

S_TITLE = ParagraphStyle("t", fontName="JPGothic", fontSize=20, leading=26,
                         textColor=INK, spaceAfter=2)
S_SUB   = ParagraphStyle("s", fontName="JPGothic", fontSize=10.5, leading=15,
                         textColor=SUB, spaceAfter=14)
S_H     = ParagraphStyle("h", fontName="JPGothic", fontSize=13, leading=18,
                         textColor=ACC, spaceBefore=14, spaceAfter=6)
S_BODY  = ParagraphStyle("b", fontName="JPGothic", fontSize=10.5, leading=16.5,
                         textColor=INK, spaceAfter=3)
S_PRE   = ParagraphStyle("p", fontName="JPMono", fontSize=9.5, leading=14,
                         textColor=INK, backColor=HexColor("#f4f4f6"),
                         borderPadding=6, leftIndent=4, spaceBefore=4, spaceAfter=8)


def manual_text():
    s = open(os.path.join(HERE, "SALES.md"), encoding="utf-8").read()
    m = re.search(r"## 取扱説明書[((]同梱用[))]\s*```(.*?)```", s, re.S)
    if not m:
        raise SystemExit("SALES.md に取扱説明書の節が見つからない")
    return m.group(1).strip("\n")


def build():
    lines = manual_text().split("\n")
    story = []
    # 1行目 = 題名
    title = lines[0].strip()
    story.append(Paragraph(title.replace("取扱説明書", "").strip(" ()(v1.01)"), S_TITLE))
    story.append(Paragraph("取扱説明書(v1.01)", S_SUB))
    i = 1
    buf = []          # 整形済みブロックの行だまり

    def flush():
        if buf:
            story.append(Preformatted("\n".join(buf), S_PRE))
            buf.clear()

    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.startswith("■ "):
            flush()
            story.append(Paragraph(ln[2:], S_H))
        elif ln.startswith("  ") and ln.strip():
            buf.append(ln)
        elif not ln.strip():
            if buf and i + 1 < len(lines) and lines[i + 1].startswith("  "):
                buf.append("")     # 整形ブロック内の空行
            else:
                flush()
        else:
            flush()
            story.append(Paragraph(ln, S_BODY))
        i += 1
    flush()

    def deco(canv, doc):
        canv.saveState()
        canv.setFont("JPGothic", 8)
        canv.setFillColor(SUB)
        canv.drawString(20 * mm, 12 * mm, "定石 参 ─ 値幅計 取扱説明書")
        canv.drawRightString(A4[0] - 20 * mm, 12 * mm, f"{doc.page}")
        canv.restoreState()

    doc = BaseDocTemplate(OUT, pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title="定石 参 ─ 値幅計 取扱説明書", author="定石ラボ")
    fr = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[fr], onPage=deco)])
    doc.build(story)
    print("生成:", OUT)


if __name__ == "__main__":
    build()
