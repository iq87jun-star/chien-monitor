# -*- coding: utf-8 -*-
"""docs/264 Q21(B): 指数のオーバーナイト・プレミアム。現物クローズ→翌オープン(夜間)と オープン→クローズ(日中)を UTC の H1 で近似。
US500/NAS100/US30: 日中 14→20、夜間 20→翌 14。GER40/UK100/EUSTX50: 日中 08→16、夜間 16→翌 08。JP225/AUS200: 日中 00→06、夜間 06→翌 00。HK50: 日中 02→08、夜間 08→翌 02。
9 指数 × {夜間 L/S, 日中 L/S}(夜間は月〜木建て)= 36 + 週末(金建て→月出口)L/S 18 = 54 セル。コスト NONFX_COST。
使い方: python3 queue/q21_index_overnight.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
SESS = {"US500": (14, 20), "NAS100": (14, 20), "US30": (14, 20), "GER40": (8, 16), "UK100": (8, 16), "EUSTX50": (8, 16), "JP225": (0, 6), "AUS200": (0, 6), "HK50": (2, 8)}
cum = int(sys.argv[1]); R = Runner("Q21", cum, 54, "results/q21_index_overnight.csv")
for sym, (ho, hc) in SESS.items():
    df = load(sym); selfcheck(sym, df); o = df["open"]
    # 日中
    t = o.index[(o.index.hour == ho) & (o.index.dayofweek <= 4)]; px_in = o.reindex(t).values; px_out = o.reindex(t + pd.Timedelta(hours=hc - ho)).values
    for lab, d in (("L", 1.0), ("S", -1.0)): R.add("日中", sym, f"{ho:02d}->{hc:02d} {lab}", trades(sym, t, px_in, np.full(len(t), d), px_out))
    # 夜間(月〜木建て → 翌営業日オープン)
    t = o.index[(o.index.hour == hc) & (o.index.dayofweek <= 3)]; px_in = o.reindex(t).values; px_out = o.reindex(t + pd.Timedelta(hours=24 - (hc - ho))).values
    for lab, d in (("L", 1.0), ("S", -1.0)): R.add("夜間", sym, f"{hc:02d}->翌{ho:02d} {lab}", trades(sym, t, px_in, np.full(len(t), d), px_out))
    # 週末(金クローズ → 月オープン)
    t = o.index[(o.index.hour == hc) & (o.index.dayofweek == 4)]; px_in = o.reindex(t).values; px_out = o.reindex(t + pd.Timedelta(hours=72 - (hc - ho))).values
    for lab, d in (("L", 1.0), ("S", -1.0)): R.add("週末", sym, f"金{hc:02d}->月{ho:02d} {lab}", trades(sym, t, px_in, np.full(len(t), d), px_out))
R.finish()
