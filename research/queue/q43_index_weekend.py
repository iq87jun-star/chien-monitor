# -*- coding: utf-8 -*-
"""docs/293 Q43(F8): 指数の週末反転/継続。月曜(00→翌 00 UTC)を金曜(00→翌 00 UTC)の符号で反転 or 追随。使い方: python3 queue/q43_index_weekend.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
SYMS = ["US500", "US30", "NAS100", "GER40", "UK100", "JP225"]
cum = int(sys.argv[1]); R = Runner("Q43", cum, len(SYMS) * 2, "results/q43_index_weekend.csv")
for sym in SYMS:
    df = load(sym); selfcheck(sym, df); o = df["open"]
    c = df["close"]; last_close = c.groupby(c.index.normalize()).last(); first_open = o.groupby(o.index.normalize()).first(); first_t = pd.Series(o.index, index=o.index).groupby(o.index.normalize()).min()
    dates = pd.DatetimeIndex(first_open.index); mon = dates[dates.dayofweek == 0]; fri = mon - pd.Timedelta(days=3)
    fri_r = last_close.reindex(fri).values / first_open.reindex(fri).values - 1.0          # 金曜: 初バー始値 → 最終バー終値
    t_mon = pd.DatetimeIndex(first_t.reindex(mon).values); px_in = first_open.reindex(mon).values; px_out = last_close.reindex(mon).values   # 月曜: 初バー始値 → 最終バー終値
    for lab, sgn in (("反転", -1.0), ("追随", 1.0)):
        dir_ = np.where(np.isnan(fri_r), 0.0, sgn * np.sign(fri_r)); r = trades(sym, t_mon, px_in, dir_, px_out)
        R.add("指数週末", sym, f"月曜 {lab}(金曜符号)", r)
R.finish()
