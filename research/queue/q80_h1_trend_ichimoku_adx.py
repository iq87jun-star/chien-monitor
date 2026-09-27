# -*- coding: utf-8 -*-
"""docs/314 Q80(F37): H1 トレンド指標。一目均衡表(転換 9/基準 26/先行 52: 転換線が基準線を上抜け かつ 終値が雲の上 → L、逆で S)と
ADX(14) > 25 への上抜け時に +DI > −DI → L / −DI > +DI → S。終値判定 → 次バー始値で建て、保有 24h 固定・重複しない。19 銘柄 × 2 指標 × {L, S} = 76 セル。
使い方: python3 queue/q80_h1_trend_ichimoku_adx.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
SYMS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD", "USDCAD", "EURJPY", "GBPJPY", "AUDJPY", "EURGBP", "XAUUSD", "XAGUSD", "US500", "NAS100", "GER40", "US30", "JP225", "UK100"]
HOLD = 24
def mid(h, l, n): return (h.rolling(n).max() + l.rolling(n).min()) / 2
def signals(df):
    c = df["close"]; h = df["high"]; l = df["low"]; out = {}
    ten = mid(h, l, 9); kij = mid(h, l, 26); spa = ((ten + kij) / 2).shift(26); spb = mid(h, l, 52).shift(26); top = np.maximum(spa, spb); bot = np.minimum(spa, spb)
    out["Ichimoku"] = ((ten.shift(1) <= kij.shift(1)) & (ten > kij) & (c > top), (ten.shift(1) >= kij.shift(1)) & (ten < kij) & (c < bot))
    up = h.diff(); dn = -l.diff(); pdm = up.where((up > dn) & (up > 0), 0.0); ndm = dn.where((dn > up) & (dn > 0), 0.0)
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1); a = 1 / 14
    atr = tr.ewm(alpha=a, adjust=False).mean(); pdi = 100 * pdm.ewm(alpha=a, adjust=False).mean() / atr; ndi = 100 * ndm.ewm(alpha=a, adjust=False).mean() / atr
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi); adx = dx.ewm(alpha=a, adjust=False).mean()
    out["ADX14"] = ((adx.shift(1) <= 25) & (adx > 25) & (pdi > ndi), (adx.shift(1) <= 25) & (adx > 25) & (ndi > pdi))
    return {k: (x.fillna(False).values, y.fillna(False).values) for k, (x, y) in out.items()}
def run(sym, df, trig, d):
    o = df["open"].values; idx = df.index; n = len(df); t_in, p_in, p_out = [], [], []; busy = -1
    for j in np.flatnonzero(trig):
        e = j + 1; x = e + HOLD
        if e <= busy or x >= n: continue
        t_in.append(idx[e]); p_in.append(o[e]); p_out.append(o[x]); busy = x
    return trades(sym, pd.DatetimeIndex(t_in), np.array(p_in), np.full(len(t_in), float(d)), np.array(p_out))
cum = int(sys.argv[1]); R = Runner("Q80", cum, len(SYMS) * 2 * 2, "results/q80_h1_trend_ichimoku_adx.csv")
for sym in SYMS:
    df = load(sym); selfcheck(sym, df); sig = signals(df)
    for ind, (lo, hi) in sig.items():
        R.add(ind, sym, "L hold=24h", run(sym, df, lo, 1)); R.add(ind, sym, "S hold=24h", run(sym, df, hi, -1))
    print(f"  {sym} 済", flush=True)
R.finish()
