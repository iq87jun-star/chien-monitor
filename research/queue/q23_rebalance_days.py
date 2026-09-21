# -*- coding: utf-8 -*-
"""docs/264 Q23(D): 指数リバランス日の引け前フロー。MSCI 四半期(2/5/8/11 月の最終営業日)・Russell 再構成(6 月の指定金曜)。
MSCI: 6 指数 × 引け前 2h {L,S} 12 + 翌日寄り 2h {L,S} 12。Russell: US 3 指数 × 引け前 2h {L,S} 6。= 30 セル。窓: US 18→20 / 翌 14→16、EU 14→16 / 翌 08→10。
イベント数が IS 13 回(MSCI)・3 回(Russell)のため月数 ≥ 24 を満たさず判定不能になる(事前に承知)。診断として記録し累積に数える。
使い方: python3 queue/q23_rebalance_days.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); R = Runner("Q23", cum, 30, "results/q23_rebalance_days.csv")
def last_bday(y, m): d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0); return d - pd.Timedelta(days=max(0, d.dayofweek - 4))
MSCI = [last_bday(y, m) for y in range(2016, 2027) for m in (2, 5, 8, 11)]
RUSSELL = [pd.Timestamp(x) for x in ("2016-06-24", "2017-06-23", "2018-06-22", "2019-06-28", "2020-06-26", "2021-06-25", "2022-06-24", "2023-06-23", "2024-06-28", "2025-06-27", "2026-06-26")]
WIN = {"US500": (18, 14), "NAS100": (18, 14), "US30": (18, 14), "GER40": (14, 8), "UK100": (14, 8), "EUSTX50": (14, 8)}
for sym, (hpre, hnext) in WIN.items():
    df = load(sym); selfcheck(sym, df); o = df["open"]
    for ev, days in (("MSCI", MSCI), ("Russell", RUSSELL)):
        if ev == "Russell" and sym not in ("US500", "NAS100", "US30"): continue
        t = pd.DatetimeIndex([d + pd.Timedelta(hours=hpre) for d in days]); t = t[t.isin(o.index)]
        px_in = o.reindex(t).values; px_out = o.reindex(t + pd.Timedelta(hours=2)).values
        for lab, d in (("L", 1.0), ("S", -1.0)): R.add(f"{ev} 引け前", sym, f"{hpre:02d}-{hpre+2:02d} {lab}", trades(sym, t, px_in, np.full(len(t), d), px_out))
        if ev == "MSCI":
            t2 = pd.DatetimeIndex([d + pd.Timedelta(days=1 if d.dayofweek < 4 else 3, hours=hnext) for d in days]); t2 = t2[t2.isin(o.index)]
            px_in = o.reindex(t2).values; px_out = o.reindex(t2 + pd.Timedelta(hours=2)).values
            for lab, d in (("L", 1.0), ("S", -1.0)): R.add("MSCI 翌日寄り", sym, f"翌 {hnext:02d}-{hnext+2:02d} {lab}", trades(sym, t2, px_in, np.full(len(t2), d), px_out))
R.finish()
