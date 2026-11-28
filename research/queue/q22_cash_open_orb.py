# -*- coding: utf-8 -*-
"""docs/264 Q22(C): 現物寄り付きの初動レンジ・ブレイク。寄り後の最初の 2 本(o, o+1)の高安をレンジとし、o+2 の終値がレンジ外なら o+3 の始値で建てる。{追随, 逆行} × 保有 {2h, クローズ時刻の始値}。
寄り時刻(UTC): US 14、EU 08、JP225/AUS200 00、HK50 02。クローズ: US 20、EU 16、JP/AUS 06、HK 08。9 指数 × 2 × 2 = 36 セル。
使い方: python3 queue/q22_cash_open_orb.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
SESS = {"US500": (14, 20), "NAS100": (14, 20), "US30": (14, 20), "GER40": (8, 16), "UK100": (8, 16), "EUSTX50": (8, 16), "JP225": (0, 6), "AUS200": (0, 6), "HK50": (2, 8)}
cum = int(sys.argv[1]); R = Runner("Q22", cum, 36, "results/q22_cash_open_orb.csv")
for sym, (ho, hc) in SESS.items():
    df = load(sym); selfcheck(sym, df); o = df["open"]; h = df["high"]; l = df["low"]; c = df["close"]
    t0 = df.index[(df.index.hour == ho) & (df.index.dayofweek <= 4)]
    hi = np.maximum(h.reindex(t0).values, h.reindex(t0 + pd.Timedelta(hours=1)).values); lo = np.minimum(l.reindex(t0).values, l.reindex(t0 + pd.Timedelta(hours=1)).values)
    ct = c.reindex(t0 + pd.Timedelta(hours=2)).values; brk = np.where(ct > hi, 1.0, np.where(ct < lo, -1.0, 0.0)); brk[np.isnan(hi) | np.isnan(ct)] = 0.0
    ent = t0 + pd.Timedelta(hours=3); px_in = o.reindex(ent).values
    for hold in ("2h", "close"):
        px_out = o.reindex(ent + pd.Timedelta(hours=2)).values if hold == "2h" else o.reindex(t0 + pd.Timedelta(hours=hc - ho)).values
        if hold == "close" and hc - ho <= 3: px_out = np.full(len(ent), np.nan)   # クローズが建て時刻以前 → 判定不能
        for lab, k in (("追随", 1), ("逆行", -1)): R.add("寄りレンジ", sym, f"o={ho:02d} {lab} hold={hold}", trades(sym, ent, px_in, k * brk, px_out))
R.finish()
