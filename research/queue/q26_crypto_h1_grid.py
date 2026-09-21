# -*- coding: utf-8 -*-
"""docs/271 Q26: 暗号資産の曜日 × 時間帯格子。BTCUSD/ETHUSD × 7 曜日 × 9 窓(4h×6 + 8h×3)× L/S = 252 セル。コスト往復 10 bps(docs/264)。
窓: 前窓 2018-01〜2021-09 / IS 2021-10〜2024-12 / OOS 2025-01〜末尾。判定 docs/244 §1。
使い方: python3 queue/q26_crypto_h1_grid.py <累積セル数>"""
import sys, numpy as np, pandas as pd
import q_common as qc
from q_common import *
qc.NONFX_COST.update({"BTCUSD": 10e-4, "ETHUSD": 10e-4})   # cost() は NONFX_COST を参照
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]; WINS = [(h, 4) for h in (0, 4, 8, 12, 16, 20)] + [(h, 8) for h in (0, 8, 16)]
cum = int(sys.argv[1]); R = Runner("Q26", cum, 252, "results/q26_crypto_h1_grid.csv")
for sym in ["BTCUSD", "ETHUSD"]:
    df = load(sym); o = df["open"]; assert abs(float(cost(sym, np.array([1.0]))[0]) - 1e-3) < 1e-12
    t0 = o.index[(o.index.hour == 8) & (o.index.dayofweek == 1)][:300]; p0 = o.reindex(t0).values; p1 = o.reindex(t0 + pd.Timedelta(hours=4)).values
    z = (trades(sym, t0, p0, np.ones(len(t0)), p1) + trades(sym, t0, p0, -np.ones(len(t0)), p1)).dropna(); assert len(z) > 0 and abs(float(z.max()) + 2e-3) < 1e-12, f"[COST SIGN] {sym}"
    for dow in range(7):
        for h0, span in WINS:
            t = o.index[(o.index.dayofweek == dow) & (o.index.hour == h0)]; px = o.reindex(t).values; pe = o.reindex(t + pd.Timedelta(hours=span)).values
            for sh in (False, True):
                R.add("暗号資産格子", sym, f"{DOW[dow]}{'S' if sh else ''} {h0:02d}-{(h0+span)%24:02d}UTC", trades(sym, t, px, np.full(len(t), -1.0 if sh else 1.0), pe))
R.finish()
