# -*- coding: utf-8 -*-
"""docs/282 Q34: 中銀会合前 24h の指数 LONG(Lucca–Moench 型)。使い方: python3 queue/q34_cb_predrift.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
CB = pd.read_csv("data_ext/cb_meetings.csv"); CB["t"] = pd.to_datetime(CB["utc"]).dt.floor("h")
CELLS = [("FOMC", "US500"), ("FOMC", "US30"), ("FOMC", "NAS100"), ("ECB", "EUSTX50"), ("ECB", "GER40"), ("BOE", "UK100"), ("BOJ", "JP225"), ("RBA", "AUS200")]
cum = int(sys.argv[1]); R = Runner("Q34", cum, len(CELLS), "results/q34_cb_predrift.csv")
for bank, sym in CELLS:
    df = load(sym); selfcheck(sym, df); o = df["open"]; te = pd.DatetimeIndex(CB[CB.bank == bank].t); t_in = te - pd.Timedelta(hours=24)
    r = trades(sym, t_in, o.reindex(t_in).values, np.ones(len(t_in)), o.reindex(te).values); R.add("中銀前ドリフト", sym, f"{bank} 発表前 24h LONG", r)
    # 対照: 会合日以外の同時刻 24h(発表時刻の最頻 UTC 時)
    h = int(pd.Series(te.hour).mode()[0]); ta = o.index[(o.index.hour == h) & (o.index.dayofweek < 5)]; ta = ta[~ta.normalize().isin(te.normalize())]
    ra = trades(sym, ta - pd.Timedelta(hours=24), o.reindex(ta - pd.Timedelta(hours=24)).values, np.ones(len(ta)), o.reindex(ta).values)
    si, sa = st(r, IS0, IS1), st(ra, IS0, IS1); print(f"  {bank}/{sym}: 会合前 IS {si['mean']} bps(n={si['trades']}) vs 対照(非会合日) {sa['mean']} bps  | OOS 会合前 {st(r, OOS0, END)['mean']} vs 対照 {st(ra, OOS0, END)['mean']}")
R.finish()
