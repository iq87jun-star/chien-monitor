# -*- coding: utf-8 -*-
"""docs/293 Q41(F6): 中銀発表後の継続。発表を含む H1 バーの符号に、次バー始値から 3 時間追随。使い方: python3 queue/q41_cb_postmove.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
CB = pd.read_csv("data_ext/cb_meetings.csv"); CB["t"] = pd.to_datetime(CB["utc"]).dt.floor("h")
CELLS = [("FOMC", "EURUSD"), ("FOMC", "US500"), ("FOMC", "XAUUSD"), ("ECB", "EURUSD"), ("ECB", "EUSTX50"), ("BOE", "GBPUSD"), ("BOE", "UK100"),
         ("BOJ", "USDJPY"), ("BOJ", "JP225"), ("RBA", "AUDUSD"), ("RBA", "AUS200")]
cum = int(sys.argv[1]); R = Runner("Q41", cum, len(CELLS), "results/q41_cb_postmove.csv")
for bank, sym in CELLS:
    df = load(sym); selfcheck(sym, df); o, c = df["open"], df["close"]; te = pd.DatetimeIndex(CB[CB.bank == bank].t)
    bar = c.reindex(te).values / o.reindex(te).values - 1.0; dir_ = np.where(np.isnan(bar), 0.0, np.sign(bar))
    t_in = te + pd.Timedelta(hours=1); r = trades(sym, t_in, o.reindex(t_in).values, dir_, o.reindex(t_in + pd.Timedelta(hours=3)).values)
    R.add("中銀後継続", sym, f"{bank} 発表バー符号に追随 +1h→+4h", r)
R.finish()
