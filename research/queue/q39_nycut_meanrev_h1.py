# -*- coding: utf-8 -*-
"""docs/284 §3 Q39: NY オプションカット前の FX 平均回帰(H1 近似)。13-14 UTC の符号の逆を 14-15 UTC に保有。使い方: python3 queue/q39_nycut_meanrev_h1.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); R = Runner("Q39", cum, 6, "results/q39_nycut_meanrev_h1.csv")
for sym in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"):
    df = load(sym); selfcheck(sym, df); o = df["open"]
    t = o.index[(o.index.hour == 14) & (o.index.dayofweek < 5)]; r1 = o.reindex(t).values / o.reindex(t - pd.Timedelta(hours=1)).values - 1
    d = -np.sign(np.nan_to_num(r1)); R.add("NY カット前平均回帰", sym, "-sign(13-14) → 14-15 UTC", trades(sym, t, o.reindex(t).values, d, o.reindex(t + pd.Timedelta(hours=1)).values))
R.finish()
