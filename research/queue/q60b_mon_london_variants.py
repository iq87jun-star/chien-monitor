# -*- coding: utf-8 -*-
"""docs/305 Q60b(Q60 の追跡・改良系 4 セル): Q60 で月曜の利益がロンドン時間(07-16 UTC)に集中したため、
Mon4 / Mon2 合成で {a) 07→16 UTC の単発 LONG(ロンドン窓のみ), b) 4 ショット 24h を {7,8,9,10} UTC} をベース(4/6/8/10・24h)と比較。使い方: python3 queue/q60b_mon_london_variants.py <累積>"""
import sys, os
from q_common import *
from q_cal import improved
def shots(sym, hours, hold):
    df = load(sym); o = df["open"]; out = None
    for h in hours:
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]; r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=hold)).values) / len(hours)
        r.index = r.index.normalize(); out = r if out is None else out.add(r, fill_value=0)
    return out
W = {"Mon4": {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}, "Mon2": {"GBPJPY": .537, "AUDJPY": .463}}
cum = int(sys.argv[1]); R = Runner("Q60b", cum, 4, "results/q60b_mon_london_variants.csv"); imp = []
for nm, w in W.items():
    b = None; va = None; vb = None
    for p, wt in w.items():
        sb = shots(p, (4, 6, 8, 10), 24) * wt; sa = shots(p, (7,), 9) * wt; sc = shots(p, (7, 8, 9, 10), 24) * wt
        b = sb if b is None else b.add(sb, fill_value=0); va = sa if va is None else va.add(sa, fill_value=0); vb = sc if vb is None else vb.add(sc, fill_value=0)
    R.add(f"{nm} ロンドン窓のみ 07→16(改良系)", nm, "単発 LONG 9h", va); imp.append(dict(comp=nm, variant="07→16 単発", **improved(b, va)))
    R.add(f"{nm} ショット {{7,8,9,10}} 24h(改良系)", nm, "4 ショット 24h 前倒しなし・ロンドン開始", vb); imp.append(dict(comp=nm, variant="{7,8,9,10} 24h", **improved(b, vb)))
    def st5(x): x = x[(x.index >= IS0) & (x.index <= END)]; eq = (1 + x).cumprod(); return f"5y 累積 {(eq.iloc[-1]-1)*100:+.1f}% DD {(eq/eq.cummax()-1).min()*100:.1f} 平均 {x.mean()*1e4:.2f} bps"
    print(f"{nm}: base {st5(b)} | 07→16 {st5(va)} | 7-10 24h {st5(vb)}")
R.finish(); pd.set_option("display.width", 300); print("\n== Q60b 改良判定 ==\n" + pd.DataFrame(imp).to_string(index=False))
