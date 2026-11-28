# -*- coding: utf-8 -*-
"""docs/256 Q13 前日高安ブレイク(H1): 前日(UTC 日)の高値/安値を H1 終値が初めて越えたら次バー始値で建てる。上抜け→{追随 L, 逆行 S}、下抜け→{追随 S, 逆行 L}。保有 {4h, 当日最終バー始値}。1 日 1 回/トリガー種。14 銘柄 × 2 × 2 × 2 = 112 セル。
使い方: python3 queue/q13_prevday_hl_break.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
SYMS = ["XAUUSD", "XAGUSD", "US500", "NAS100", "GER40", "US30", "JP225", "UK100", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD"]
cum = int(sys.argv[1]); R = Runner("Q13", cum, len(SYMS) * 8, "results/q13_prevday_hl_break.csv")
for sym in SYMS:
    df = load(sym); selfcheck(sym, df); o = df["open"]; day = df.index.floor("D")
    dly = df.groupby(day).agg(hi=("high", "max"), lo=("low", "min"), n=("open", "size")); dly = dly[dly.n >= 6]
    prev = dly.shift(1); ph = prev["hi"].reindex(day).values; pl = prev["lo"].reindex(day).values
    c = df["close"].values; up = (c > ph); dn = (c < pl)
    last_open = df.groupby(day)["open"].transform(lambda s: s.iloc[-1]).values; last_t = pd.Series(df.index, index=df.index).groupby(day).transform("last").values
    nxt_t = np.append(df.index[1:].values, np.datetime64("NaT")); nxt_o = np.append(o.values[1:], np.nan); same_day = (pd.DatetimeIndex(nxt_t).floor("D").values == day.values)
    for trig, mask in (("上抜け", up), ("下抜け", dn)):
        first = pd.Series(mask, index=df.index).groupby(day).cumsum().values == 1   # その日の最初のブレイクのみ
        sel = mask & first & same_day
        t_in = pd.DatetimeIndex(nxt_t[sel]); px_in = nxt_o[sel]; base_dir = 1.0 if trig == "上抜け" else -1.0
        for hold in ("4h", "day"):
            if hold == "4h": px_out = o.reindex(t_in + pd.Timedelta(hours=4)).values
            else:
                lt = pd.DatetimeIndex(last_t[sel]); px_out = np.where(lt > t_in, last_open[sel], np.nan)
            for lab, sgn in (("追随", 1), ("逆行", -1)):
                R.add("前日高安ブレイク", sym, f"{trig} {lab} hold={hold}", trades(sym, t_in, px_in, np.full(len(t_in), sgn * base_dir), px_out))
R.finish()
