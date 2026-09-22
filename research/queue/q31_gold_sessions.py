# -*- coding: utf-8 -*-
"""docs/280 Q31: ゴールド・銀のセッション偏り。XAUUSD/XAGUSD × {L 00-08, S 08-16, S 10-15} 平日毎日。使い方: python3 queue/q31_gold_sessions.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); R = Runner("Q31", cum, 6, "results/q31_gold_sessions.csv")
for sym in ("XAUUSD", "XAGUSD"):
    df = load(sym); selfcheck(sym, df); o = df["open"]
    for h0, h1, d, lab in ((0, 8, 1, "L 00-08 アジア"), (8, 16, -1, "S 08-16 ロンドン"), (10, 15, -1, "S 10-15 AM→PM fix")):
        t = o.index[(o.index.hour == h0) & (o.index.dayofweek < 5)]; te = t + pd.Timedelta(hours=h1 - h0)
        R.add("金属セッション", sym, lab, trades(sym, t, o.reindex(t).values, np.full(len(t), float(d)), o.reindex(te).values))
R.finish()
