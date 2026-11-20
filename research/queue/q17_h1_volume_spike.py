# -*- coding: utf-8 -*-
"""docs/256 Q17 出来高スパイク(H1): tick volume > 2×直近 24 本平均 かつ レンジ > 1.5×ATR24 のバーの方向(close−open の符号)に {追随, 逆行} × 保有 {2h, 4h}。次バー始値で建て、同時 1 ポジ。14 銘柄 × 2 × 2 = 56 セル。
使い方: python3 queue/q17_h1_volume_spike.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
SYMS = ["XAUUSD", "XAGUSD", "US500", "NAS100", "GER40", "US30", "JP225", "UK100", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD"]
cum = int(sys.argv[1]); R = Runner("Q17", cum, len(SYMS) * 4, "results/q17_h1_volume_spike.csv")
for sym in SYMS:
    df = load(sym); selfcheck(sym, df); o = df["open"]; a = atr24(df); v24 = df["volume"].rolling(24).mean().shift(1)
    rng = df["high"] - df["low"]; trig = (df["volume"] > 2 * v24) & (rng > 1.5 * a) & ~a.isna() & ~v24.isna()
    sgn = np.sign((df["close"] - df["open"]).values); trig &= (sgn != 0)
    nxt_t = np.append(df.index[1:].values, np.datetime64("NaT")); nxt_o = np.append(o.values[1:], np.nan)
    ent_all = pd.DatetimeIndex(nxt_t[trig.values]); sg_all = sgn[trig.values]; okm = ~ent_all.isna(); ent_all = ent_all[okm]; sg_all = sg_all[okm]
    for hold in (2, 4):
        keep = nonoverlap(ent_all, lambda t, h=hold: t + pd.Timedelta(hours=h)); pos = ent_all.get_indexer(keep); sg = sg_all[pos]
        px_in = o.reindex(keep).values; px_out = o.reindex(keep + pd.Timedelta(hours=hold)).values
        for lab, k in (("追随", 1), ("逆行", -1)):
            R.add("出来高スパイク", sym, f"{lab} hold={hold}h", trades(sym, keep, px_in, k * sg, px_out))
R.finish()
