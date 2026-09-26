# -*- coding: utf-8 -*-
"""docs/305 Q60(F17): Mon 円クロスの時間帯分解(H1)。月曜の {東京 00-07, ロンドン 07-16, NY 16-24 UTC} LONG × 7 = 21 セル(新規・各窓 3pip)。
改良系 2: Mon4 / Mon2 合成で 4 ショット × 24h の建て時刻を {4,6,8,10} → {0,2,4,6} UTC に前倒し。使い方: python3 queue/q60_mon_session_windows.py <累積>"""
import sys, os
from q_common import *
from q_cal import stats, improved
WIN = [("東京 00-07", 0, 7), ("ロンドン 07-16", 7, 16), ("NY 16-24", 16, 24)]
def window_leg(sym, h0, h1):
    df = load(sym); o = df["open"]; t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h0)]
    return trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=h1 - h0)).values)
def shots(sym, hours):
    df = load(sym); o = df["open"]; out = None
    for h in hours:
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]; r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=24)).values) / len(hours)
        r.index = r.index.normalize(); out = r if out is None else out.add(r, fill_value=0)
    return out
cum = int(sys.argv[1]); R = Runner("Q60", cum, 23, "results/q60_mon_session_windows.csv"); diag = []
for p in base.MON_FX:
    for name, h0, h1 in WIN:
        r = window_leg(p, h0, h1); R.add(f"Mon {name} L", p, f"月曜 {h0:02d}:00→{h1:02d}:00 UTC LONG(3pip)", r)
        x = r[(r.index >= IS0) & (r.index <= END)]; diag.append(dict(pair=p, window=name, mean_bps_2021_10=round(float(x.mean()) * 1e4, 2), n=len(x)))
W = {"Mon4": {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}, "Mon2": {"GBPJPY": .537, "AUDJPY": .463}}
imp = []
for nm, w in W.items():
    b = None; v = None
    for p, wt in w.items():
        sb = shots(p, (4, 6, 8, 10)) * wt; sv = shots(p, (0, 2, 4, 6)) * wt
        b = sb if b is None else b.add(sb, fill_value=0); v = sv if v is None else v.add(sv, fill_value=0)
    R.add(f"{nm} ショット前倒し(改良系)", nm, "4 ショット 24h: {4,6,8,10} → {0,2,4,6} UTC", v); imp.append(dict(comp=nm, **improved(b, v)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q60 時間帯別平均(2021-10〜)==\n" + pd.DataFrame(diag).pivot(index="pair", columns="window", values="mean_bps_2021_10").to_string()); print("\n== Q60 改良判定(前倒し)==\n" + pd.DataFrame(imp).to_string(index=False))
