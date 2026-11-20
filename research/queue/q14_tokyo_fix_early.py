# -*- coding: utf-8 -*-
"""docs/256 Q14 仲値・東京早朝(円クロス)。
(a) 仲値: {USDJPY EURJPY GBPJPY AUDJPY} × 日 {ゴトー日(5/10/15/20/25/月末・週末は前営業日に繰上), 非ゴトー, 全日} × 窓 {00→01 UTC L, 01→03 S, 01→05 S} = 36。
(b) 早朝逆張り: 7 円クロス + EURUSD GBPUSD AUDUSD USDCHF = 11 × トリガー(21 時バーの |close−open| > 0.5×ATR24)× {逆行, 追随} × 保有 {1h, 2h}(22 時始値で建て 23/00 時始値で出る)= 44。
使い方: python3 queue/q14_tokyo_fix_early.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); R = Runner("Q14", cum, 36 + 44, "results/q14_tokyo_fix_early.csv")
def gotobi_dates(a, b):
    out = set()
    for m in pd.period_range(a, b, freq="M"):
        for dd in (5, 10, 15, 20, 25):
            d = pd.Timestamp(m.year, m.month, dd)
            while d.dayofweek >= 5: d -= pd.Timedelta(days=1)
            out.add(d)
        d = m.to_timestamp(how="end").normalize()
        while d.dayofweek >= 5: d -= pd.Timedelta(days=1)
        out.add(d)
    return out
for sym in ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY"]:
    df = load(sym); selfcheck(sym, df); o = df["open"]; G = gotobi_dates(df.index[0], df.index[-1])
    for dayset in ("ゴトー日", "非ゴトー", "全日"):
        for h0, span, sh in ((0, 1, False), (1, 2, True), (1, 4, True)):
            t_in = o.index[(o.index.hour == h0) & (o.index.dayofweek <= 4)]
            isg = np.array([t.normalize() in G for t in t_in])
            if dayset == "ゴトー日": t_in = t_in[isg]
            elif dayset == "非ゴトー": t_in = t_in[~isg]
            px_in = o.reindex(t_in).values; px_out = o.reindex(t_in + pd.Timedelta(hours=span)).values
            R.add("仲値", sym, f"{dayset} {h0:02d}-{h0+span:02d}UTC {'S' if sh else 'L'}", trades(sym, t_in, px_in, np.full(len(t_in), -1.0 if sh else 1.0), px_out))
for sym in ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF"]:
    df = load(sym); selfcheck(sym, df); o = df["open"]; a = atr24(df)
    tb = df.index[(df.index.hour == 21) & (df.index.dayofweek.isin([6, 0, 1, 2, 3]))]   # JST 月〜金 06 時
    mv = (df["close"] - df["open"]).reindex(tb).values; thr = 0.5 * a.reindex(tb).values
    sel = np.abs(mv) > thr; sel &= ~np.isnan(thr); tb = tb[sel]; sgn = np.sign(mv[sel])
    t_in = tb + pd.Timedelta(hours=1); px_in = o.reindex(t_in).values
    for hold in (1, 2):
        px_out = o.reindex(t_in + pd.Timedelta(hours=hold)).values
        for lab, k in (("逆行", -1), ("追随", 1)):
            R.add("早朝", sym, f"21h>0.5ATR {lab} hold={hold}h", trades(sym, t_in, px_in, k * sgn, px_out))
R.finish()
