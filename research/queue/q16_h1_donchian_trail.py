# -*- coding: utf-8 -*-
"""docs/256 Q16 H1 ドンチャン + ATR トレイル: 直近 {24, 120} 本の高値更新で L / 安値更新で S(終値判定・次バー始値で建てる)。出口 {ATR24×2 トレイル(終値が極値から 2ATR 戻ったら次バー始値・上限 240h), 固定 24h}。同時 1 ポジ。8 銘柄 × 2 × 2 × 2 = 64 セル。
使い方: python3 queue/q16_h1_donchian_trail.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
SYMS = ["USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "XAUUSD", "US500", "NAS100", "GER40"]
cum = int(sys.argv[1]); R = Runner("Q16", cum, len(SYMS) * 8, "results/q16_h1_donchian_trail.csv")
MAXH = 240
for sym in SYMS:
    df = load(sym); selfcheck(sym, df); o = df["open"].values; c = df["close"].values; h = df["high"]; l = df["low"]; a = atr24(df).values; idx = df.index; n = len(df)
    for N in (24, 120):
        hh = h.rolling(N).max().shift(1).values; ll = l.rolling(N).min().shift(1).values
        for d, trig in ((1, c > hh), (-1, c < ll)):
            trig = trig & ~np.isnan(a)
            for ex in ("trail2ATR", "fixed24h"):
                t_in, p_in, p_out = [], [], []; i = 0; ti = np.flatnonzero(trig)
                for j in ti:
                    if j + 1 >= n or j + 1 < i: continue
                    e = j + 1; pe = o[e]; atr = a[j]
                    if ex == "fixed24h":
                        x = e + 24
                        if x >= n: break
                    else:
                        ext = c[e]; x = None
                        for k in range(e, min(e + MAXH, n - 1)):
                            ext = max(ext, c[k]) if d > 0 else min(ext, c[k])
                            if (d > 0 and c[k] < ext - 2 * atr) or (d < 0 and c[k] > ext + 2 * atr): x = k + 1; break
                        if x is None: x = min(e + MAXH, n - 1)
                    t_in.append(idx[e]); p_in.append(pe); p_out.append(o[x]); i = x
                R.add("ドンチャン", sym, f"N={N} {'L' if d>0 else 'S'} exit={ex}", trades(sym, pd.DatetimeIndex(t_in), np.array(p_in), np.full(len(t_in), float(d)), np.array(p_out)))
R.finish()
