# -*- coding: utf-8 -*-
"""docs/294 Q46: 東京仲値(09:55 JST = 00:55 UTC)の M1 版(Q14 の H1 版は 00〜01 UTC バーに仲値前後が同居し検定不能だった)。
 a) 仲値前 LONG: 00:30 建て → 00:55 決済(輸入企業のドル買い) b) 仲値後 SHORT: 00:55 建て → 01:25 決済(需要の剥落) c)・d) = a)・b) をゴトー日(5・10 日と月末営業日)のみ。
使い方: python3 queue/q46_tokyo_fix_m1.py <累積> USDJPY"""
import sys
from q_m1 import *
cum = int(sys.argv[1]); syms = sys.argv[2].split(","); R = Runner("Q46", cum, len(syms) * 4, "results/q46_tokyo_fix_m1.csv"); J = []
for sym in syms:
    d = m1(sym); o = d["open"]; days = pd.DatetimeIndex(sorted(set(o.index.normalize()))); days = days[days.dayofweek < 5]; c = rt_cost(sym, 1); print(f"[{sym}] M1 日数 {len(days)} 往復コスト {c*1e4:.2f} bps")
    me = pd.DatetimeIndex([g.max() for _, g in pd.Series(days, index=days).groupby(days.to_period("M"))]); goto = days[(days.day % 5 == 0) | days.isin(me)]
    for lab, dd, h0, m0, h1, m1_, dr in (("a) 仲値前 LONG 00:30→00:55", days, 0, 30, 0, 55, 1.0), ("b) 仲値後 SHORT 00:55→01:25", days, 0, 55, 1, 25, -1.0),
                                          ("c) a) ゴトー日のみ", goto, 0, 30, 0, 55, 1.0), ("d) b) ゴトー日のみ", goto, 0, 55, 1, 25, -1.0)):
        t_in = dd + pd.Timedelta(hours=h0, minutes=m0); t_out = dd + pd.Timedelta(hours=h1, minutes=m1_)
        r = ret_series(o, t_in, np.full(len(t_in), dr), t_out, c); R.add("東京仲値M1", sym, lab, r); judge(R, J, sym, lab, r)
finish(R, J, "Q46")
