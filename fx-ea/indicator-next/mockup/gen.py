#!/usr/bin/env python3
"""定石 参 ─ 値幅計 の表示イメージ図を生成する。

**実測のスクリーンショットではない。説明用の作り物。**
商品ページに「実際の画面」として載せないこと。
パネルの文言は MQL5/定石参_値幅計.mq5 の Draw() に合わせてある。
"""
import glob, json, math, os, random
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))


# USDJPY 日足の平年並みを 71.8 pips = 0.718 円 と置く(パネルの「平年並み」と揃える)
BASE_PIPS = 71.8
PIP = 0.01


def candles(n, seed, tail_mult, start=157.20):
    """後半 TAIL 本だけボラを変える。パネルの数字はこの足から実際に算出する。"""
    random.seed(seed)
    # 1本の高安幅の期待値がおよそ 1.63*vol になるので、そこから逆算する
    vol0 = BASE_PIPS * PIP / 1.63
    out, p = [], start
    for i in range(n):
        vol = vol0 * (tail_mult if i >= n - TAIL else 1.0)
        o = p
        c = o + random.gauss(math.sin(i / 9.0) * vol * 0.4, vol)
        h = max(o, c) + abs(random.gauss(0, vol * 0.55))
        l = min(o, c) - abs(random.gauss(0, vol * 0.55))
        out.append((o, h, l, c)); p = c
    return out


TAIL = 40


def measured(rows, k=14):
    """直近 k 本の高安幅の平均(pips)。インジケーターの想定値幅と同じ計算。"""
    return sum(r[1] - r[2] for r in rows[-k:]) / k / PIP


SCENES = {
    "quiet": dict(gain=16.4, seed=7,  tail=0.82),
    "busy":  dict(gain=21.9, seed=21, tail=1.27),
}


def panel_lines(scene, rows):
    s = SCENES[scene]
    fc, base, gain = measured(rows), BASE_PIPS, s["gain"]
    quiet = fc / base
    if quiet < 0.85:   qs, qc = "静か", "good"
    elif quiet > 1.15: qs, qc = "荒い", "avoid"
    else:              qs, qc = "平年並み", "caution"

    L = []
    A = lambda t, c="txt": L.append({"t": t, "c": c})
    A("定石 参 ─ 値幅計  v1.00", "head")
    A("USDJPY  D1")
    A(" ")
    A(f"次のバーの想定値幅   {fc:.1f} pips", "head")
    A(f"平年並み             {base:.1f} pips  (3000本)")
    A(f"静穏度  {quiet:.2f} 倍  ─  {qs}", qc)
    A(" ")
    A("想定値幅に対する幅の目安", "head")
    A(f"  0.5倍 {fc*0.5:.1f}  /  1.0倍 {fc:.1f}  /  1.5倍 {fc*1.5:.1f}")
    A(" ")
    A("自己採点(直近 250 本 / 平年並み 3000 本)", "head")
    A(f"  平年並みより誤差 {gain:+.1f}%", "good" if gain > 0 else "avoid")
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
.head{color:#ffffff}.txt{color:#d2d2d2}.good{color:#32cd32}
.caution{color:#ffd700}.avoid{color:#ff6347}
"""


def html(scene):
    s = SCENES[scene]
    rows = candles(150, s["seed"], s["tail"])
    spans = "".join(f'<div class="{l["c"]}">{l["t"].replace(" ", "&nbsp;")}</div>'
                    for l in panel_lines(scene, rows))
    data = json.dumps(rows)
    return f"""<!doctype html><meta charset="utf-8"><style>{CSS}</style>
<div class="win">
  <div class="tab">USDJPY,Daily&nbsp;&nbsp;&nbsp;157.204&nbsp;157.288&nbsp;157.161&nbsp;157.242</div>
  <canvas id="c" width="1280" height="814"></canvas>
  <div class="pane">{spans}</div>
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
JOBS = [("mock-01-quiet.png", "quiet"), ("mock-02-busy.png", "busy")]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE, headless=True,
                          args=["--no-sandbox", "--disable-dev-shm-usage",
                                "--font-render-hinting=none"])
    pg = b.new_page(viewport={"width": 1300, "height": 860}, device_scale_factor=2)
    for fn, scene in JOBS:
        path = os.path.join(HERE, fn.replace(".png", ".html"))
        open(path, "w").write(html(scene))
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("file://" + path)
        pg.wait_for_timeout(700)
        pg.locator(".win").screenshot(path=os.path.join(HERE, fn))
        rows = candles(150, SCENES[scene]["seed"], SCENES[scene]["tail"])
        print(f"生成: {fn}  直近14本の平均値幅 {measured(rows):.1f} pips "
              f"(平年並み {BASE_PIPS} pips)"
              + ("  JSエラー: " + errs[0][:90] if errs else ""))
    b.close()
