# -*- coding: utf-8 -*-
"""docs/280 Q32: 指数の OPEX 週(第 3 金曜を含む週)LONG。月曜 00 UTC 始値 → 金曜 20 UTC 始値。使い方: python3 queue/q32_index_opex_week.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); R = Runner("Q32", cum, 6, "results/q32_index_opex_week.csv")
def third_fridays(idx):
    out = []
    for p in pd.period_range(idx[0], idx[-1], freq="M"):
        d = pd.Timestamp(p.start_time.normalize()); fr = [d + pd.Timedelta(days=k) for k in range(31) if (d + pd.Timedelta(days=k)).month == d.month and (d + pd.Timedelta(days=k)).dayofweek == 4]
        if len(fr) >= 3: out.append(fr[2])
    return out
for sym in ("US30", "US500", "NAS100", "GER40", "UK100", "JP225"):
    df = load(sym); selfcheck(sym, df); o = df["open"]; days = pd.DatetimeIndex(sorted(set(o.index.normalize())))
    t_in, t_out = [], []
    for f in third_fridays(days):
        mon = f - pd.Timedelta(days=4); a = o.index[(o.index >= mon) & (o.index < mon + pd.Timedelta(hours=12))]; b = o.index[(o.index >= f + pd.Timedelta(hours=20)) & (o.index < f + pd.Timedelta(hours=24))]
        if len(a) and len(b): t_in.append(a[0]); t_out.append(b[0])
    t_in = pd.DatetimeIndex(t_in); t_out = pd.DatetimeIndex(t_out)
    R.add("OPEX 週", sym, "L Mon00→Fri20 UTC 第3金曜週", trades(sym, t_in, o.reindex(t_in).values, np.ones(len(t_in)), o.reindex(t_out).values))
R.finish()
