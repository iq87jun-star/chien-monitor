# -*- coding: utf-8 -*-
"""docs/280 Q33: 指数の日中モメンタム。第 1 時間(H1 バー)の符号で最終時間を同方向に保有。使い方: python3 queue/q33_index_intraday_mom.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); R = Runner("Q33", cum, 6, "results/q33_index_intraday_mom.csv")
HOURS = {"US30": (14, 19), "US500": (14, 19), "NAS100": (14, 19), "GER40": (8, 15), "UK100": (8, 15), "JP225": (0, 5)}
for sym, (hf, hl) in HOURS.items():
    df = load(sym); selfcheck(sym, df); o = df["open"]
    t1 = o.index[(o.index.hour == hf) & (o.index.dayofweek < 5)]; r1 = o.reindex(t1 + pd.Timedelta(hours=1)).values / o.reindex(t1).values - 1
    tl = t1 + pd.Timedelta(hours=hl - hf); d = np.sign(np.nan_to_num(r1))
    R.add("日中モメンタム", sym, f"sign({hf:02d}-{hf+1:02d}) → {hl:02d}-{hl+1:02d} UTC", trades(sym, tl, o.reindex(tl).values, d, o.reindex(tl + pd.Timedelta(hours=1)).values))
R.finish()
