# -*- coding: utf-8 -*-
"""docs/313 Q77(F34): ロールの SL 検証。Roll5(20→00 UTC SHORT・金利差門)× SL {0.5, 1.0, 2.0}×ATR24 + 固定 15 pip = 4 セル(改良系・高値で判定)。"""
import sys, os
from q_common import *
from q_cal import improved
from q20_wed_swap_carry import rate_series
ROLL = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]
def leg(sym, mode):
    df = load(sym); o = df["open"]; hi = df["high"]; atr = (df["high"] - df["low"]).rolling(24).mean().shift(1); days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    px_in = o.reindex(t).values; px_out = o.reindex(t + pd.Timedelta(hours=4)).values.copy(); hits = 0
    if mode is not None:
        a = atr.reindex(t).values; sl = px_in + (mode * a if isinstance(mode, float) else 15 * base.pip_size(sym))
        for i, ti in enumerate(t):
            w = hi[(hi.index > ti) & (hi.index < ti + pd.Timedelta(hours=4))]
            if len(w) and not np.isnan(sl[i]) and float(w.max()) >= sl[i]: px_out[i] = sl[i]; hits += 1
    r = trades(sym, t, px_in, -np.ones(len(t)), px_out) / 5; r.index = r.index.normalize(); return r, hits, len(t)
cum = int(sys.argv[1]); R = Runner("Q77", cum, 4, "results/q77_roll_stoploss.csv"); rows = []
def comp(mode):
    out = None; H = 0; N = 0
    for s in ROLL: r, h, n = leg(s, mode); H += h; N += n; out = r if out is None else out.add(r, fill_value=0)
    return out, H, N
b, _, _ = comp(None)
for mode, lab in ((0.5, "SL 0.5×ATR"), (1.0, "SL 1.0×ATR"), (2.0, "SL 2.0×ATR"), ("15pip", "SL 15pip 固定")):
    v, H, N = comp(mode); R.add(f"Roll5 {lab}(改良系)", "Roll5", "20→00 UTC S・高値で SL 判定", v); rows.append(dict(mode=lab, hits=H, n=N, hit_rate=round(H / N * 100, 1), **improved(b, v)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q77 ==\n" + pd.DataFrame(rows).to_string(index=False))
