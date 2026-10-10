# -*- coding: utf-8 -*-
"""docs/322 §5h Q124(新規・5 セル): 原油の曜日×日中格子。WTI の月〜金 13 UTC LONG → 同日 20 UTC 決済(先物口座の MCL 向け・水曜は EIA 14:30 UTC を含む)。参照: BRENT 同格子、SHORT 側。
使い方: cd research && python3 queue/q124_wti_weekday_intraday.py <累積セル数>"""
import sys
from q_common import *
from q114_mon_index_intraday import stats
DOW = ["月", "火", "水", "木", "金"]
def day(sym, dow, h_in, h_out, direction=1.0):
    o = load(sym)["open"]; t = o.index[(o.index.dayofweek == dow) & (o.index.hour == h_in)]
    t_out = pd.DatetimeIndex([x.normalize() + pd.Timedelta(hours=h_out) for x in t])
    r = trades(sym, t, o.reindex(t).values, np.full(len(t), direction), o.reindex(t_out).values); r.index = r.index.normalize(); return r
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q124", cum, 5, "results/q124_wti_weekday_intraday.csv"); rows = []
    for d in range(5):
        s = day("WTI", d, 13, 20); R.add("原油 曜日×日中(MCL)", "WTI", f"{DOW[d]}曜 13 UTC LONG → 同日 20 UTC 決済", s)
        for nm, x in ((f"WTI {DOW[d]} LONG(セル)", s), (f"WTI {DOW[d]} SHORT(参照)", day("WTI", d, 13, 20, -1.0)), (f"BRENT {DOW[d]} LONG(参照)", day("BRENT", d, 13, 20))):
            sp, si, so = stats(x, PRE0, IS0), stats(x, IS0, IS1), stats(x, OOS0, END)
            rows.append(dict(leg=nm, pre_sharpe=sp[0], is_sharpe=si[0], is_worst=si[1], is_cum=si[2], oos_sharpe=so[0], oos_worst=so[1], oos_cum=so[2]))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q124_wti_weekday_intraday_levels.csv", index=False); print("\n" + D.to_string(index=False))
