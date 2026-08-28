#!/usr/bin/env python3
"""環境計の表示イメージ図を生成する(実測値ではない。説明用)。"""
import random, math, json, os, glob
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))

def candles(n, seed, start=157.20, vol=0.055):
    random.seed(seed)
    out, p = [], start
    for i in range(n):
        o = p
        drift = math.sin(i / 9.0) * vol * 0.5
        c = o + random.gauss(drift, vol)
        h = max(o, c) + abs(random.gauss(0, vol * 0.55))
        l = min(o, c) - abs(random.gauss(0, vol * 0.55))
        out.append((o, h, l, c)); p = c
    return out

# 時間帯別スプレッド中央値(典型的なJPYペアの形。0時前後に跳ねる)
HOURS = [4.2, 2.1, 0.8, 0.8, 0.7, 0.7, 0.8, 0.9, 1.0, 1.1, 1.0, 0.9,
         0.8, 0.8, 0.9, 1.0, 1.1, 1.2, 1.1, 1.0, 1.1, 1.4, 2.3, 3.6]

def bar(v, mx, width=18):
    return "|" * max(0, int(round(v / mx * width)))

def panel_lines(mode):
    """v1.09 の実際の出力に合わせる(上位5+現在、行頭の印、矩形の棒)。"""
    mx = max(HOURS)
    TOPN = 5
    if mode == "good":
        hour, spr = 9, 0.9
        atr, mc = 32.4, 36.0
    else:
        hour, spr = 23, 7.8
        atr, mc = 21.6, 2.8
    med = HOURS[hour]
    ratio = round(spr / med, 2)
    togo = (0 - hour + 24) % 24
    samples, hours_ready = 1284, 24

    L = []
    A = lambda t, c="txt", bar=None: L.append({"t": t, "c": c, "bar": bar})
    A("定石 零 ─ 環境計  v1.09", "head")
    A(f"USDJPY  H1   {hour:02d}:14 サーバー時刻")
    A(" ")
    A(f"スプレッド        {spr:.1f} pips", "head")
    A(f"  この時間帯の中央値  {med:.1f} pips")
    if ratio >= 2.5:   rt, rcls = "回避推奨", "avoid"
    elif ratio >= 1.5: rt, rcls = "割高", "caution"
    else:              rt, rcls = "適正", "good"
    A(f"  割高度  {ratio:.2f} 倍   {rt}", rcls)
    A(f"想定変動幅 ATR(14)  {atr:.1f} pips", "head")
    if mc >= 12:  mt, mcls = "十分", "good"
    elif mc >= 8: mt, mcls = "やや不足", "caution"
    else:         mt, mcls = "不足", "avoid"
    A(f"  変動幅 / スプレッド  {mc:.1f} 倍   {mt}", mcls)
    A("最もスプレッドが開く時間帯  00:00", "head")
    A(f"  中央値 {HOURS[0]:.1f} pips / あと {togo} 時間",
      "avoid" if togo <= 1 else "txt")
    A(" ")
    score = 0
    if ratio >= 2.5: score = 2
    elif ratio >= 1.5: score = 1
    if mc < 8: score = 2
    elif mc < 12 and score < 1: score = 1
    A(f"判定   {['○  コスト条件は良好','△  コスト警戒','×  コストが割高'][score]}",
      ["good", "caution", "avoid"][score])
    A(" ")
    A(f"スプレッドが開く時間帯 上位{TOPN} ─ 有効{samples}件/{hours_ready}時間帯", "head")

    top = sorted(range(24), key=lambda h: -HOURS[h])[:TOPN]
    for h in sorted(set(top) | {hour}):
        cls = "head" if h == hour else ("avoid" if HOURS[h] == mx else "txt")
        mark = "&gt; " if h == hour else "&nbsp;&nbsp;"
        A(f"{mark}{h:02d}  {HOURS[h]:5.1f}".replace(" ", "&nbsp;"),
          cls, bar=HOURS[h] / mx)
    return L


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d0d0d;font-family:'IPAGothic','IPAPGothic',sans-serif}
.win{width:1280px;height:840px;position:relative;background:#131313;
     border:1px solid #2e2e2e;overflow:hidden}
.tab{height:26px;background:#1e1e1e;border-bottom:1px solid #2e2e2e;
     color:#c8c8c8;font-size:12px;padding:6px 12px}
canvas{display:block}
.pane{position:absolute;left:14px;top:52px;font-size:12.5px;
      line-height:16.5px;white-space:pre;padding:8px 10px 10px 8px;
      background:rgba(12,12,16,0.93);border:1px solid #303038}
.badge{position:absolute;right:0;bottom:0;font-size:12px;color:#cfcfcf;
  background:rgba(10,10,12,0.88);border-top:1px solid #3a3a42;
  border-left:1px solid #3a3a42;padding:6px 12px;letter-spacing:0.02em}
.row{position:relative}
.bar{position:absolute;left:96px;top:4px;height:8px}
.head{color:#ffffff}.txt{color:#d2d2d2}.good{color:#32cd32}
.caution{color:#ffd700}.avoid{color:#ff6347}
"""

def html(mode, seed):
    lines = panel_lines(mode)
    COL = {"head": "#ffffff", "txt": "#d2d2d2", "good": "#32cd32",
           "caution": "#ffd700", "avoid": "#ff6347"}
    parts = []
    for l in lines:
        txt = l["t"] if "&nbsp;" in l["t"] else l["t"].replace(" ", "&nbsp;")
        bar = ""
        if l.get("bar") is not None:
            w = max(2, int(round(l["bar"] * 156)))
            bar = (f'<span class="bar" style="width:{w}px;'
                   f'background:{COL[l["c"]]}"></span>')
        parts.append(f'<div class="{l["c"]} row">{txt}{bar}</div>')
    spans = "".join(parts)
    data = json.dumps(candles(150, seed))
    return f"""<!doctype html><meta charset="utf-8"><style>{CSS}</style>
<div class="win">
  <div class="tab">USDJPY,H1&nbsp;&nbsp;&nbsp;157.204&nbsp;157.288&nbsp;157.161&nbsp;157.242</div>
  <canvas id="c" width="1280" height="814"></canvas>
  <div class="pane">{spans}</div>
  <div class="badge">表示イメージ ─ 実際の画面とは数値が異なります</div>
</div>
<script>
const d = {data};
const cv = document.getElementById('c'), x = cv.getContext('2d');
const W = cv.width, H = cv.height, PAD = 74;
let hi = -1e9, lo = 1e9;
d.forEach(k => {{ hi = Math.max(hi, k[1]); lo = Math.min(lo, k[2]); }});
const rng = hi - lo, hiP = hi + rng*0.10, loP = lo - rng*0.10;
const Y = v => (hiP - v) / (hiP - loP) * (H - 40) + 12;
x.fillStyle = '#131313'; x.fillRect(0,0,W,H);
x.strokeStyle = '#232323'; x.lineWidth = 1;
for (let i=0;i<=8;i++) {{ const yy=Math.round(i*(H-40)/8)+12.5;
  x.beginPath(); x.moveTo(0,yy); x.lineTo(W-PAD,yy); x.stroke(); }}
for (let i=0;i<=10;i++) {{ const xx=Math.round(i*(W-PAD)/10)+0.5;
  x.beginPath(); x.moveTo(xx,0); x.lineTo(xx,H-22); x.stroke(); }}
const bw = (W-PAD)/d.length, cw = Math.max(3, bw*0.62);
d.forEach((k,i) => {{
  const cx = i*bw + bw/2, up = k[3] >= k[0];
  x.strokeStyle = up ? '#4ec94e' : '#e05252';
  x.fillStyle   = up ? '#1d5c1d' : '#7a2020';
  x.beginPath(); x.moveTo(cx, Y(k[1])); x.lineTo(cx, Y(k[2])); x.stroke();
  const yo=Y(k[0]), yc=Y(k[3]);
  x.fillRect(cx-cw/2, Math.min(yo,yc), cw, Math.max(1.5, Math.abs(yc-yo)));
  x.strokeRect(cx-cw/2+0.5, Math.min(yo,yc)+0.5, cw-1, Math.max(1, Math.abs(yc-yo))-1);
}});
x.fillStyle='#1a1a1a'; x.fillRect(W-PAD,0,PAD,H);
x.strokeStyle='#2e2e2e'; x.beginPath(); x.moveTo(W-PAD+0.5,0); x.lineTo(W-PAD+0.5,H); x.stroke();
x.fillStyle='#9a9a9a'; x.font='11px sans-serif'; x.textAlign='left';
for (let i=0;i<=8;i++) {{ const v = hiP - i*(hiP-loP)/8;
  x.fillText(v.toFixed(3), W-PAD+8, i*(H-40)/8+16); }}
const last = d[d.length-1][3];
x.fillStyle='#c9a227'; x.fillRect(W-PAD, Y(last)-8, PAD, 16);
x.fillStyle='#000'; x.fillText(last.toFixed(3), W-PAD+8, Y(last)+4);
</script>"""

EXE = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))[-1]
jobs = [("mock-01-good.png", "good", 7), ("mock-02-avoid.png", "avoid", 21)]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE, headless=True,
                          args=["--no-sandbox", "--disable-dev-shm-usage",
                                "--font-render-hinting=none"])
    pg = b.new_page(viewport={"width": 1300, "height": 860},
                    device_scale_factor=2)
    for fn, mode, seed in jobs:
        path = os.path.join(HERE, fn.replace(".png", ".html"))
        open(path, "w").write(html(mode, seed))
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("file://" + path)
        pg.wait_for_timeout(900)
        pg.locator(".win").screenshot(path=os.path.join(HERE, fn))
        print("生成:", fn, ("  JSエラー: " + errs[0][:90]) if errs else "")
    b.close()
