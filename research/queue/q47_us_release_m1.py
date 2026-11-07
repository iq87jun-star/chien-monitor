# -*- coding: utf-8 -*-
"""docs/294 Q47: 米指標(CPI・雇用統計)発表 08:30 ET(12:30 UTC 夏 / 13:30 UTC 冬)の初動継続。発表後 5 分の符号に +5→+30 分追随。
使い方: python3 queue/q47_us_release_m1.py <累積> EURUSD,GBPUSD,USDJPY,AUDUSD"""
import sys
from q_m1 import *
EV = {"CPI": pd.to_datetime(pd.read_csv("data_ext/events_cpi.csv")["date"]), "NFP": pd.to_datetime(pd.read_csv("data_ext/events_empsit.csv")["date"])}
cum = int(sys.argv[1]); syms = sys.argv[2].split(","); R = Runner("Q47", cum, len(syms) * 2, "results/q47_us_release_m1.csv"); J = []
for sym in syms:
    d = m1(sym); o = d["open"]; c = rt_cost(sym, 13); print(f"[{sym}] 往復コスト {c*1e4:.2f} bps")
    for ev, dates in EV.items():
        dates = pd.DatetimeIndex(dates[dates >= "2024-01-01"]); t0 = pd.DatetimeIndex([day + pd.Timedelta(hours=12 if us_dst(day) else 13, minutes=30) for day in dates])
        first = o.reindex(t0 + pd.Timedelta(minutes=5)).values / o.reindex(t0).values - 1.0; dir_ = np.where(np.isnan(first), 0.0, np.sign(first))
        lab = f"{ev} 発表後 5 分の符号に +5→+30 分追随"; r = ret_series(o, t0 + pd.Timedelta(minutes=5), dir_, t0 + pd.Timedelta(minutes=30), c); R.add("米指標初動", sym, lab, r); judge(R, J, sym, lab, r)
finish(R, J, "Q47")
