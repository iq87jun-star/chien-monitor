# -*- coding: utf-8 -*-
"""docs/314 Q79(F36): H1 オシレーター。RSI(14) 30/70・ボリンジャー(20,2σ)・ストキャス(14,3) 20/80・CCI(20) ±100 の終値クロス → 次バー始値で建て、
{逆張り fade, 追随 follow} × 保有 {4h, 24h}(固定・重複しない)。19 銘柄 × 4 指標 × 2 × 2 = 304 セル。
使い方: python3 queue/q79_h1_oscillators.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
SYMS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD", "USDCAD", "EURJPY", "GBPJPY", "AUDJPY", "EURGBP", "XAUUSD", "XAGUSD", "US500", "NAS100", "GER40", "US30", "JP225", "UK100"]
HOLDS = (4, 24)
def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean(); return 100 - 100 / (1 + up / dn)
def signals(df):
    """各指標について (下側イベント, 上側イベント) の bool 配列。下側 = 売られすぎ入り(fade なら L)、上側 = 買われすぎ入り(fade なら S)。"""
    c = df["close"]; h = df["high"]; l = df["low"]; out = {}
    r = rsi(c); out["RSI14"] = ((r.shift(1) >= 30) & (r < 30), (r.shift(1) <= 70) & (r > 70))
    m = c.rolling(20).mean(); s = c.rolling(20).std(); lo = m - 2 * s; up = m + 2 * s
    out["BB20"] = ((c.shift(1) > lo.shift(1)) & (c <= lo), (c.shift(1) < up.shift(1)) & (c >= up))
    k = 100 * (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min()); k = k.rolling(3).mean(); d = k.rolling(3).mean()
    out["Stoch"] = ((k.shift(1) <= d.shift(1)) & (k > d) & (k < 20), (k.shift(1) >= d.shift(1)) & (k < d) & (k > 80))
    tp = (h + l + c) / 3; md = tp.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True); cci = (tp - tp.rolling(20).mean()) / (0.015 * md)
    out["CCI20"] = ((cci.shift(1) >= -100) & (cci < -100), (cci.shift(1) <= 100) & (cci > 100))
    return {k_: (a.fillna(False).values, b.fillna(False).values) for k_, (a, b) in out.items()}
def run(sym, df, low, high, mode, hold):
    o = df["open"].values; idx = df.index; n = len(df); t_in, p_in, d_in, p_out = [], [], [], []; busy = -1
    ev = [(j, 1 if mode == "fade" else -1) for j in np.flatnonzero(low)] + [(j, -1 if mode == "fade" else 1) for j in np.flatnonzero(high)]
    for j, d in sorted(ev):
        e = j + 1; x = e + hold
        if e <= busy or x >= n: continue
        t_in.append(idx[e]); p_in.append(o[e]); d_in.append(d); p_out.append(o[x]); busy = x
    return trades(sym, pd.DatetimeIndex(t_in), np.array(p_in), np.array(d_in, float), np.array(p_out))
cum = int(sys.argv[1]); R = Runner("Q79", cum, len(SYMS) * 4 * 2 * len(HOLDS), "results/q79_h1_oscillators.csv")
for sym in SYMS:
    df = load(sym); selfcheck(sym, df); sig = signals(df)
    for ind, (low, high) in sig.items():
        for mode in ("fade", "follow"):
            for hold in HOLDS:
                R.add(ind, sym, f"{mode} hold={hold}h", run(sym, df, low, high, mode, hold))
    print(f"  {sym} 済", flush=True)
R.finish()
