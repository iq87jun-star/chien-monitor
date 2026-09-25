# -*- coding: utf-8 -*-
"""docs/294 Q45: ロンドン現物寄り付き(08:00 London = 07 UTC BST / 08 UTC GMT)の初動継続。A) 初 15 分の符号に +15→+60 分追随、B) 初 5 分の符号に +5→+30 分追随。
使い方: python3 queue/q45_london_open_m1.py <累積> EURUSD,GBPUSD,USDJPY,AUDUSD"""
import sys
from q_m1 import *
cum = int(sys.argv[1]); syms = sys.argv[2].split(","); R = Runner("Q45", cum, len(syms) * 2, "results/q45_london_open_m1.csv"); J = []
for sym in syms:
    d = m1(sym); o = d["open"]; days = pd.DatetimeIndex(sorted(set(o.index.normalize()))); days = days[days.dayofweek < 5]; c = rt_cost(sym, 8)
    t0 = pd.DatetimeIndex([day + pd.Timedelta(hours=7 if uk_bst(day) else 8) for day in days])
    print(f"[{sym}] M1 日数 {len(days)}  往復コスト {c*1e4:.2f} bps")
    for lab, w, h in (("A) 寄り 15 分の符号に +15→+60 分追随", 15, 60), ("B) 寄り 5 分の符号に +5→+30 分追随", 5, 30)):
        first = o.reindex(t0 + pd.Timedelta(minutes=w)).values / o.reindex(t0).values - 1.0; dir_ = np.where(np.isnan(first), 0.0, np.sign(first))
        r = ret_series(o, t0 + pd.Timedelta(minutes=w), dir_, t0 + pd.Timedelta(minutes=h), c); R.add("ロンドン寄り初動", sym, lab, r); judge(R, J, sym, lab, r)
finish(R, J, "Q45")
