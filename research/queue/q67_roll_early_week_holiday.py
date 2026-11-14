# -*- coding: utf-8 -*-
"""docs/306 Q67(F24): ロール × 週初(月・火)に JP 祝日がある週。5 ペア × {該当週の水曜のみ, 除外(改良系)} = 10 セル。"""
import sys, os
from q_common import *
from q_cal import *
from q20_wed_swap_carry import rate_series
ROLL = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]
def early_hol(t): m = week_of(t); return any((m + pd.Timedelta(days=k)) in JPHOL for k in (0, 1))
def leg(sym):
    df = load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    return trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values)
cum = int(sys.argv[1]); R = Runner("Q67", cum, 10, "results/q67_roll_early_week_holiday.csv"); imp = []
for s in ROLL:
    r = leg(s); sel = pd.Series([early_hol(t) for t in r.index], index=r.index)
    R.add("週初JP祝日週の水曜 のみ", s, "月/火が JP 祝日の週の水曜 20-00 S", r[sel]); ex = r[~sel]; R.add("週初JP祝日週の水曜 除外(改良系)", s, "該当週の水曜を建てない", ex)
    imp.append(dict(sym=s, n=int(sel.sum()), mean_sel=round(float(r[sel].mean()) * 1e4, 2), mean_rest=round(float(r[~sel].mean()) * 1e4, 2), **improved(r, ex)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q67 ==\n" + pd.DataFrame(imp).to_string(index=False))
