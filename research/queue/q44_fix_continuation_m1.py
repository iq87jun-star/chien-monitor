# -*- coding: utf-8 -*-
"""docs/294 Q44: Q36 の複製検定(新ペア)。Q36 で 4 ペアとも「フィックス直前の動きは継続」だったので、未使用ペアで**継続**を事前登録して検定。
 a') WMR 直前 15 分の符号に追随・15 分保有  b') NY カット直前 30 分の符号に追随・30 分保有。使い方: python3 queue/q44_fix_continuation_m1.py <累積> USDCAD,NZDUSD,EURJPY"""
import sys
from q_m1 import *
cum = int(sys.argv[1]); syms = sys.argv[2].split(","); R = Runner("Q44", cum, len(syms) * 2, "results/q44_fix_continuation_m1.csv"); J = []
for sym in syms:
    d = m1(sym, full=False) if not os.path.exists(f"data_dukascopy_m1/{sym}_bid_m1_full.csv.gz") else m1(sym); o = d["open"]
    days = pd.DatetimeIndex(sorted(set(o.index.normalize()))); days = days[days.dayofweek < 5]; c = rt_cost(sym, 15); print(f"[{sym}] M1 日数 {len(days)}  往復コスト {c*1e4:.2f} bps")
    wmr = pd.DatetimeIndex([day + pd.Timedelta(hours=15 if uk_bst(day) else 16) for day in days]); nyc = pd.DatetimeIndex([day + pd.Timedelta(hours=14 if us_dst(day) else 15) for day in days])
    for lab, tf, pre, hold in (("a') WMR 直前 15 分の符号に追随・15 分", wmr, 15, 15), ("b') NY カット直前 30 分の符号に追随・30 分", nyc, 30, 30)):
        prev = o.reindex(tf).values / o.reindex(tf - pd.Timedelta(minutes=pre)).values - 1.0; dir_ = np.where(np.isnan(prev), 0.0, np.sign(prev))
        r = ret_series(o, tf, dir_, tf + pd.Timedelta(minutes=hold), c); R.add("フィックス継続(複製)", sym, lab, r); judge(R, J, sym, lab, r)
finish(R, J, "Q44")
