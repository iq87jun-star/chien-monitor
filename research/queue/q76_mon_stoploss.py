# -*- coding: utf-8 -*-
"""docs/313 Q76(F33): Mon レッグの災害ストップ検証。H1 で 4/6/8/10 UTC の 4 ショット × 24h、SL = k×ATR24(直前 24 本の H−L 平均・EA の iATR(24) 相当)を安値で判定(約定は SL 価格)。
Mon4 / Mon2 / Mon7 × k ∈ {1.5, 2.0, 2.5, 3.0} を SL なしと比較(改良系)= 12 セル。"""
import sys, os
from q_common import *
from q_cal import improved
HOURS = (4, 6, 8, 10)
def shots_sl(sym, k):
    df = load(sym); o = df["open"]; lo = df["low"]; atr = (df["high"] - df["low"]).rolling(24).mean().shift(1); out = None; hits = 0; n = 0
    for h in HOURS:
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]; px_in = o.reindex(t).values; px_out = o.reindex(t + pd.Timedelta(hours=24)).values.copy()
        if k is not None:
            a = atr.reindex(t).values; sl = px_in - k * a
            for i, ti in enumerate(t):
                w = lo[(lo.index > ti) & (lo.index < ti + pd.Timedelta(hours=24))]
                if len(w) and not np.isnan(sl[i]) and float(w.min()) <= sl[i]: px_out[i] = sl[i]; hits += 1
        n += len(t); r = trades(sym, t, px_in, np.ones(len(t)), px_out) / len(HOURS); r.index = r.index.normalize(); out = r if out is None else out.add(r, fill_value=0)
    return out, hits, n
W = {"Mon4": {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}, "Mon2": {"GBPJPY": .537, "AUDJPY": .463}, "Mon7": {p: 1 / 7 for p in base.MON_FX}}
cum = int(sys.argv[1]); R = Runner("Q76", cum, 12, "results/q76_mon_stoploss.csv"); rows = []; cache = {}
def comp(w, k):
    out = None; H = 0; N = 0
    for p, wt in w.items():
        key = (p, k)
        if key not in cache: cache[key] = shots_sl(p, k)
        s, h, n = cache[key]; H += h; N += n; x = s * wt; out = x if out is None else out.add(x, fill_value=0)
    return out, H, N
for nm, w in W.items():
    b, _, _ = comp(w, None)
    for k in (1.5, 2.0, 2.5, 3.0):
        v, H, N = comp(w, k); R.add(f"{nm} SL {k}×ATR(改良系)", nm, "4 ショット 24h・安値で SL 判定", v)
        x5 = lambda s: round(float(((1 + s[(s.index >= IS0) & (s.index <= END)]).prod() - 1) * 100), 1)
        rows.append(dict(comp=nm, k=k, sl_hits=H, shots=N, hit_rate=round(H / N * 100, 1), cum5y_base=x5(b), cum5y_sl=x5(v), **improved(b, v)))
R.finish(); pd.set_option("display.width", 320); print("\n== Q76 ==\n" + pd.DataFrame(rows).to_string(index=False))
