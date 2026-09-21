# -*- coding: utf-8 -*-
"""docs/264 Q24(E): 月末ロンドンフィックス(16:00 London = BST 中 15 UTC / それ以外 16 UTC)の前後。月の最終営業日に 12 FX × {L,S} × {フィックス前 2h, フィックス後 2h} = 48 セル。
使い方: python3 queue/q24_monthend_fix.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCHF", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD", "GBPAUD"]
cum = int(sys.argv[1]); R = Runner("Q24", cum, 48, "results/q24_monthend_fix.csv")
def last_sunday(y, m): d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0); return d - pd.Timedelta(days=(d.dayofweek + 1) % 7)
def fix_hour(d): return 15 if last_sunday(d.year, 3) <= d.normalize() < last_sunday(d.year, 10) else 16
def last_bday(y, m): d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0); return d - pd.Timedelta(days=max(0, d.dayofweek - 4))
DAYS = [last_bday(y, m) for y in range(2016, 2027) for m in range(1, 13)]
for pair in PAIRS:
    df = load(pair); selfcheck(pair, df); o = df["open"]
    for w in ("pre", "post"):
        t = pd.DatetimeIndex([d + pd.Timedelta(hours=fix_hour(d) - (2 if w == "pre" else 0)) for d in DAYS]); t = t[t.isin(o.index)]
        px_in = o.reindex(t).values; px_out = o.reindex(t + pd.Timedelta(hours=2)).values
        for lab, d in (("L", 1.0), ("S", -1.0)): R.add("月末フィックス", pair, f"{w} 2h {lab}", trades(pair, t, px_in, np.full(len(t), d), px_out))
R.finish()
