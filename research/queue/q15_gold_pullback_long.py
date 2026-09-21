# -*- coding: utf-8 -*-
"""docs/256 Q15 ゴールド押し目 LONG(トレンド門): XAUUSD XAGUSD。門 {日足 SMA50 が 5 日前より上, なし} × 押し目(H1 終値 < MA24 − k×ATR24, k∈{1,2})× 保有 {8h, 24h}。LONG のみ・同時 1 ポジ。門 2 × k 2 × 保有 2 × 銘柄 2 = 16 セル(docs/256 の 32 は門なしを二重に数えた誤り・9/22 訂正)。
使い方: python3 queue/q15_gold_pullback_long.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); R = Runner("Q15", cum, 16, "results/q15_gold_pullback_long.csv")
for sym in ["XAUUSD", "XAGUSD"]:
    df = load(sym); selfcheck(sym, df); o = df["open"]; c = df["close"]; a = atr24(df); ma = c.rolling(24).mean()
    dc = c.groupby(df.index.floor("D")).last(); sma = dc.rolling(50).mean(); gate_d = (sma > sma.shift(5)).shift(1)   # 前日までの情報
    gate = gate_d.reindex(df.index.floor("D")).values.astype(float)
    nxt_t = np.append(df.index[1:].values, np.datetime64("NaT")); nxt_o = np.append(o.values[1:], np.nan)
    for g in ("門あり", "門なし"):
        for k in (1, 2):
            trig = (c < ma - k * a).values & ~np.isnan(a.values)
            if g == "門あり": trig &= (gate == 1.0)
            for hold in (8, 24):
                ti = df.index[trig]; ti = ti[~pd.isna(pd.DatetimeIndex(nxt_t[trig]))]
                ent = pd.DatetimeIndex(nxt_t[trig]); ent = ent[~ent.isna()]
                keep = nonoverlap(ent, lambda t, h=hold: t + pd.Timedelta(hours=h))
                px_in = o.reindex(keep).values; px_out = o.reindex(keep + pd.Timedelta(hours=hold)).values
                R.add("押し目 LONG", sym, f"{g} k={k} hold={hold}h", trades(sym, keep, px_in, np.ones(len(keep)), px_out))
R.finish()
