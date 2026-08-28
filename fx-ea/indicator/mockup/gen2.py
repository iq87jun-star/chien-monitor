#!/usr/bin/env python3
"""定石 弐 ─ 待ち伏せ の表示イメージ図(実測値ではない。説明用)。"""
import random, math, json, os, glob
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))

def candles(n, seed, start=193.40, vol=0.42, crash_at=None):
    """crash_at 以降で下落を作る(4条件が揃う場面の再現)。"""
    random.seed(seed)
    out, p = [], start
    for i in range(n):
        o = p
        if crash_at is not None and i >= crash_at:
            k = i - crash_at
            drift = -vol * (1.5 if k < 5 else 0.9)
        else:
            drift = math.sin(i / 11.0) * vol * 0.30
        c = o + random.gauss(drift, vol)
        h = max(o, c) + abs(random.gauss(0, vol * 0.5))
        l = min(o, c) - abs(random.gauss(0, vol * 0.5))
        out.append((o, h, l, c)); p = c
    return out

def panel(mode):
    L = []
    A = lambda t, c="unmet": L.append({"t": t, "c": c})
    A("定石 弐 ─ 待ち伏せ", "head")
    A("GBPJPY  日足で判定中", "head")
    A(" ", "head")
    A("買い方向の条件", "buy")
    if mode == "wait":
        rows = [("●","RSI","RSI(14) < 35","met"),
                ("●","標準偏差","平均から 1.5 SD 以上","met"),
                ("○","連続本数","3本以上の連続陰線","unmet"),
                ("●","当日変動","当日 0.5% 超の下落","met")]
    else:
        rows = [("●","RSI","RSI(14) < 35","met"),
                ("●","標準偏差","平均から 1.5 SD 以上","met"),
                ("●","連続本数","3本以上の連続陰線","met"),
                ("●","当日変動","当日 0.5% 超の下落","met")]
    for mark, name, cond, cls in rows:
        A(f"  {mark} {name}{'　'*(4-len(name))}  {cond}", cls)
    A(" ", "head")
    if mode == "wait":
        A("3 / 4 成立 — 待機中", "unmet")
        A("  4つすべてが揃うまで動きません", "unmet")
    else:
        A("★ 4 / 4 すべて成立 — 買い シグナル", "buy")
        A("  翌営業日の寄り付き前後での執行を想定しています", "head")
    return L

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d0d0d;font-family:'IPAGothic','IPAPGothic',sans-serif}
.win{width:1280px;height:760px;position:relative;background:#131313;
     border:1px solid #2e2e2e;overflow:hidden}
.tab{height:26px;background:#1e1e1e;border-bottom:1px solid #2e2e2e;
     color:#c8c8c8;font-size:12px;padding:6px 12px}
canvas{display:block}
.pane{position:absolute;left:14px;top:52px;font-size:12.5px;line-height:16.5px;
      white-space:pre;padding:8px 12px 10px 8px;
      background:rgba(12,12,16,0.93);border:1px solid #303038}
.badge{position:absolute;right:0;bottom:0;font-size:12px;color:#cfcfcf;
  background:rgba(10,10,12,0.88);border-top:1px solid #3a3a42;
  border-left:1px solid #3a3a42;padding:6px 12px;letter-spacing:0.02em}
.head{color:#fff}.unmet{color:#8a8a8a}.met{color:#32cd32}
.buy{color:#00bfff}.sell{color:#ff4500}
"""

def html(mode, seed):
    lines = panel(mode)
    spans = "".join(f'<div class="{l["c"]}">{l["t"].replace(" ","&nbsp;")}</div>'
                    for l in lines)
    sig = (mode == "signal")
    data = json.dumps(candles(120, seed, crash_at=(104 if sig else 110)))
    return f"""<!doctype html><meta charset="utf-8"><style>{CSS}</style>
<div class="win">
  <div class="tab">GBPJPY,Daily&nbsp;&nbsp;&nbsp;191.882&nbsp;192.451&nbsp;190.774&nbsp;190.912</div>
  <canvas id="c" width="1280" height="734"></canvas>
  <div class="pane">{spans}</div>
  <div class="badge">表示イメージ ─ 実際の画面とは数値が異なります</div>
</div>
<script>
const d = {data}, SIG = {str(sig).lower()};
const cv=document.getElementById('c'), x=cv.getContext('2d');
const W=cv.width,H=cv.height,PAD=76;
let hi=-1e9,lo=1e9; d.forEach(k=>{{hi=Math.max(hi,k[1]);lo=Math.min(lo,k[2]);}});
const rng=hi-lo, hiP=hi+rng*0.16, loP=lo-rng*0.14;
const Y=v=>(hiP-v)/(hiP-loP)*(H-40)+12;
x.fillStyle='#131313';x.fillRect(0,0,W,H);
x.strokeStyle='#232323';x.lineWidth=1;
for(let i=0;i<=8;i++){{const yy=Math.round(i*(H-40)/8)+12.5;
  x.beginPath();x.moveTo(0,yy);x.lineTo(W-PAD,yy);x.stroke();}}
for(let i=0;i<=10;i++){{const xx=Math.round(i*(W-PAD)/10)+0.5;
  x.beginPath();x.moveTo(xx,0);x.lineTo(xx,H-22);x.stroke();}}
const bw=(W-PAD)/d.length, cw=Math.max(4,bw*0.62);
d.forEach((k,i)=>{{
  const cx=i*bw+bw/2, up=k[3]>=k[0];
  x.strokeStyle=up?'#4ec94e':'#e05252'; x.fillStyle=up?'#1d5c1d':'#7a2020';
  x.beginPath();x.moveTo(cx,Y(k[1]));x.lineTo(cx,Y(k[2]));x.stroke();
  const yo=Y(k[0]),yc=Y(k[3]);
  x.fillRect(cx-cw/2,Math.min(yo,yc),cw,Math.max(1.5,Math.abs(yc-yo)));
  x.strokeRect(cx-cw/2+0.5,Math.min(yo,yc)+0.5,cw-1,Math.max(1,Math.abs(yc-yo))-1);
}});
if (SIG) {{
  const n=d.length-1, cx=n*bw+bw/2, entry=d[n][3];
  const slDist=1.72, sl=entry-slDist, tp=entry+slDist*1.2;
  const line=(v,col,dash,label)=>{{
    x.save(); x.setLineDash(dash); x.strokeStyle=col; x.lineWidth=1.4;
    x.beginPath(); x.moveTo(0,Y(v)); x.lineTo(W-PAD,Y(v)); x.stroke(); x.restore();
    x.fillStyle=col; x.font='11px sans-serif'; x.textAlign='right';
    x.fillText(label+'  '+v.toFixed(3), W-PAD-8, Y(v)-5);
  }};
  line(tp,'#32cd32',[7,4],'目安 利確');
  line(entry,'#00bfff',[],'目安 建値');
  line(sl,'#ff6347',[7,4],'目安 損切り');
  // 買い矢印
  x.fillStyle='#00bfff';
  const ay=Y(d[n][2])+26;
  x.beginPath(); x.moveTo(cx,ay-16); x.lineTo(cx-8,ay); x.lineTo(cx+8,ay); x.closePath(); x.fill();
  x.fillRect(cx-2.5,ay,5,13);
}}
x.fillStyle='#1a1a1a';x.fillRect(W-PAD,0,PAD,H);
x.strokeStyle='#2e2e2e';x.beginPath();x.moveTo(W-PAD+0.5,0);x.lineTo(W-PAD+0.5,H);x.stroke();
x.fillStyle='#9a9a9a';x.font='11px sans-serif';x.textAlign='left';
for(let i=0;i<=8;i++){{const v=hiP-i*(hiP-loP)/8; x.fillText(v.toFixed(3),W-PAD+8,i*(H-40)/8+16);}}
const last=d[d.length-1][3];
x.fillStyle='#c9a227';x.fillRect(W-PAD,Y(last)-8,PAD,16);
x.fillStyle='#000';x.fillText(last.toFixed(3),W-PAD+8,Y(last)+4);
</script>"""

EXE = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))[-1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=EXE, headless=True,
                          args=["--no-sandbox","--disable-dev-shm-usage",
                                "--font-render-hinting=none"])
    pg = b.new_page(viewport={"width":1300,"height":790}, device_scale_factor=2)
    for fn, mode, seed in [("mock-11-wait.png","wait",5),
                           ("mock-12-signal.png","signal",13)]:
        path = os.path.join(HERE, fn.replace(".png",".html"))
        open(path,"w").write(html(mode, seed))
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("file://"+path); pg.wait_for_timeout(900)
        pg.locator(".win").screenshot(path=os.path.join(HERE, fn))
        print("生成:", fn, ("  JSエラー: "+errs[0][:80]) if errs else "")
    b.close()
