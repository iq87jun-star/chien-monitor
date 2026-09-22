# -*- coding: utf-8 -*-
"""docs/284 §3 Q37: 指数の寄り付きギャップ埋め。現地寄り付き始値 vs 前営業日の現地引け始値の差が ATR24 の 0.5 倍以上 → 逆方向に 2h。使い方: python3 queue/q37_index_gap_fade.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
SESS = {"US30": (14, 20), "US500": (14, 20), "NAS100": (14, 20), "GER40": (8, 15), "UK100": (8, 15), "JP225": (0, 5)}
cum = int(sys.argv[1]); R = Runner("Q37", cum, 6, "results/q37_index_gap_fade.csv")
for sym, (ho, hc) in SESS.items():
    df = load(sym); selfcheck(sym, df); o = df["open"]; atr = atr24(df)
    t_open = o.index[(o.index.hour == ho) & (o.index.dayofweek < 5)]
    prev_close = o[o.index.hour == hc]; pc = prev_close.reindex(prev_close.index)  # 前営業日の hc 始値
    pc_map = pd.Series(prev_close.values, index=prev_close.index.normalize())
    days = t_open.normalize(); prev_day = pd.DatetimeIndex([pc_map.index[pc_map.index < d][-1] if (pc_map.index < d).any() else pd.NaT for d in days])
    ok = ~prev_day.isna() & ((days - prev_day) <= pd.Timedelta(days=4))
    t = t_open[ok]; ref = pc_map.reindex(prev_day[ok]).values; gap = o.reindex(t).values / ref - 1; a = (atr.reindex(t).values / o.reindex(t).values)
    m = ~np.isnan(gap) & ~np.isnan(a) & (np.abs(gap) >= 0.5 * a); tt = t[m]; d = -np.sign(gap[m])
    R.add("ギャップ埋め", sym, f"|gap|>=0.5 ATR24 逆方向 {ho:02d}→{ho+2:02d} UTC", trades(sym, tt, o.reindex(tt).values, d, o.reindex(tt + pd.Timedelta(hours=2)).values))
R.finish()
