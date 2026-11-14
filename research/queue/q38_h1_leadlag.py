# -*- coding: utf-8 -*-
"""docs/284 §3 Q38: H1 リードラグ。先行資産の直前 1h の符号で次の 1h を保有。WTI↑→USDCAD S、XAUUSD↑→AUDUSD L、USTBOND↑→USDJPY S。使い方: python3 queue/q38_h1_leadlag.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
PAIRS = [("WTI", "USDCAD", -1), ("XAUUSD", "AUDUSD", +1), ("USTBOND", "USDJPY", -1)]
cum = int(sys.argv[1]); R = Runner("Q38", cum, 3, "results/q38_h1_leadlag.csv")
for lead, fol, k in PAIRS:
    L = load(lead)["open"]; F = load(fol); selfcheck(fol, F); o = F["open"]
    t = o.index[(o.index.dayofweek < 5)]; rl = L.reindex(t).values / L.reindex(t - pd.Timedelta(hours=1)).values - 1
    d = k * np.sign(np.nan_to_num(rl)); te = t + pd.Timedelta(hours=1)
    r = trades(fol, t, o.reindex(t).values, d, o.reindex(te).values)
    # 対照: 追随銘柄自身の直前 1h 符号(自己モメンタム)
    rs = o.reindex(t).values / o.reindex(t - pd.Timedelta(hours=1)).values - 1; rc = trades(fol, t, o.reindex(t).values, np.sign(np.nan_to_num(rs)), o.reindex(te).values)
    print(f"  {lead}→{fol}: IS {st(r, IS0, IS1)['mean']} bps/h (自己モメンタム対照 {st(rc, IS0, IS1)['mean']})  OOS {st(r, OOS0, END)['mean']}")
    R.add("H1 リードラグ", fol, f"{lead} 直前1h 符号×{k:+d} → 次1h", r)
R.finish()
