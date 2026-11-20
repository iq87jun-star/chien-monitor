# -*- coding: utf-8 -*-
"""docs/305 Q61(F18): 参加者フィルター × ロール 5 本合成。{ゴトー日の水曜, 月末最終JP営業日の水曜, BoJ会合週, FOMC週} × {のみ, 除外} = 8 セル。使い方: python3 queue/q61_roll_participant_filters.py <累積>"""
import sys, os
from q_common import *
from q_cal import *
from q20_wed_swap_carry import rate_series
FOMC = set(pd.to_datetime(pd.read_csv(os.path.join(ROOT, "data_ext", "events_fomc.csv"))["date"]).dt.normalize())
ROLL = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]
def leg(sym):
    df = load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    r = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values); r.index = r.index.normalize(); return r / 5.0
R5 = None
for s in ROLL: r = leg(s); R5 = r if R5 is None else R5.add(r, fill_value=0)
FIL = [("ゴトー日の水曜", lambda t: gotobi(t)), ("月末最終JP営業日の水曜", jp_month_end), ("BoJ会合週の水曜", lambda t: in_week(t, BOJ)), ("FOMC週の水曜", lambda t: in_week(t, FOMC))]
cum = int(sys.argv[1]); R = Runner("Q61", cum, 8, "results/q61_roll_participant_filters.csv"); imp = []
for name, f in FIL:
    sel = pd.Series([bool(f(t)) for t in R5.index], index=R5.index)
    R.add(f"Roll5 {name} のみ", "Roll5", "該当水曜のみ 20-00 S", R5[sel]); ex = R5[~sel]
    R.add(f"Roll5 {name} 除外(改良系)", "Roll5", "該当水曜を建てない", ex); imp.append(dict(filter=name, n=int(sel.sum()), mean_bps_sel=round(float(R5[sel].mean()) * 1e4, 2), mean_bps_rest=round(float(R5[~sel].mean()) * 1e4, 2), **improved(R5, ex)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q61 改良判定 ==\n" + pd.DataFrame(imp).to_string(index=False))
