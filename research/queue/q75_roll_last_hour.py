# -*- coding: utf-8 -*-
"""docs/312 Q75(F32): ロールの最終 1 時間(23→00 UTC・東京前場前の指標時間帯)を外す改良判定。5 ペア × {20→23 UTC で決済} + Roll5 合成 = 6 セル(改良系)。"""
import sys, os
from q_common import *
from q_cal import improved
from q20_wed_swap_carry import rate_series
ROLL = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]
def leg(sym, hold):
    df = load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    r = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=hold)).values); r.index = r.index.normalize(); return r
cum = int(sys.argv[1]); R = Runner("Q75", cum, 6, "results/q75_roll_last_hour.csv"); rows = []; B = None; V = None
for s in ROLL:
    b, v = leg(s, 4), leg(s, 3); R.add("Roll 23:00 決済(改良系)", s, "20→23 UTC(最終 1 時間を外す)", v); rows.append(dict(sym=s, last_hour_bps=round(float((b - v.reindex(b.index)).mean()) * 1e4, 2), **improved(b, v)))
    B = b / 5 if B is None else B.add(b / 5, fill_value=0); V = v / 5 if V is None else V.add(v / 5, fill_value=0)
R.add("Roll5 23:00 決済(改良系)", "Roll5", "20→23 UTC", V); rows.append(dict(sym="Roll5", last_hour_bps=round(float((B - V.reindex(B.index)).mean()) * 1e4, 2), **improved(B, V)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q75 ==\n" + pd.DataFrame(rows).to_string(index=False))
