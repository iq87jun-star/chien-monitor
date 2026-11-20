# -*- coding: utf-8 -*-
"""docs/304 Q58(F15): ロールの値日シフト。木曜または金曜が USD(連邦)または JPY の祝日の週は多日分スワップが火曜に移る仮説。
5 ペア × {火曜 20-00 S(新規), 水曜 20-00 S 該当週のみ(診断・新規扱い), 該当週の水曜を除外(改良系)} = 15。金利差門は Q20 と同じ(≥1.0pp)。
使い方: python3 queue/q58_roll_value_date.py <累積>"""
import sys, os
from q_common import *
from q_cal import *
from q20_wed_swap_carry import rate_series
ROLL = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]
def shift_week(t):   # t: 建て時刻(火/水)。同じ週の木・金に USD 連邦祝日または JP 祝日があるか
    m = week_of(t); thu, fri = m + pd.Timedelta(days=3), m + pd.Timedelta(days=4)
    return any(d in CAL["USFED"] or d in JPHOL for d in (thu, fri))
def leg(sym, dow):
    df = load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
    t = o.index[(o.index.dayofweek == dow) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    return trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values)
cum = int(sys.argv[1]); R = Runner("Q58", cum, 15, "results/q58_roll_value_date.csv"); imp = []
for s in ROLL:
    tue, wed = leg(s, 1), leg(s, 2)
    st_ = pd.Series([shift_week(t) for t in tue.index], index=tue.index); sw = pd.Series([shift_week(t) for t in wed.index], index=wed.index)
    R.add("値日シフト週の火曜 20-00 S", s, "木/金に USD・JPY 祝日がある週の火曜", tue[st_])
    R.add("値日シフト週の水曜 20-00 S(診断)", s, "同週の水曜(ロールが火曜に移れば弱いはず)", wed[sw])
    ex = wed[~sw]; R.add("値日シフト週の水曜を除外(改良系)", s, "該当週の水曜を建てない", ex)
    imp.append(dict(sym=s, n_shift_weeks=int(sw.sum()), tue_shift_mean_bps=round(float(tue[st_].mean()) * 1e4, 2), wed_shift_mean_bps=round(float(wed[sw].mean()) * 1e4, 2), wed_normal_mean_bps=round(float(wed[~sw].mean()) * 1e4, 2), tue_normal_mean_bps=round(float(tue[~st_].mean()) * 1e4, 2), **improved(wed, ex)))
R.finish(); pd.set_option("display.width", 320); print("\n== Q58 値日シフト診断 ==\n" + pd.DataFrame(imp).to_string(index=False))
