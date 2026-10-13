# -*- coding: utf-8 -*-
"""Dukascopy 1 時間足(BID・ASK)を取得して <PAIR>_h1.csv / <PAIR>_h1_ask.csv に保存する(2016-01-01〜今日)。
使い方: mkdir data && cd data && python ../fetch_data.py   (pip install dukascopy-python pandas scipy。7 ペア × 2 で十数分)"""
import datetime as dt, os
import dukascopy_python as dk
from dukascopy_python import instruments as I
PAIRS = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "EURUSD", "GBPUSD", "AUDUSD"]
MAJ = {"USDJPY", "EURUSD", "GBPUSD", "AUDUSD"}
for p in PAIRS:
    ins = getattr(I, f"INSTRUMENT_FX_{'MAJORS' if p in MAJ else 'CROSSES'}_{p[:3]}_{p[3:]}")
    for suf, side in (("", dk.OFFER_SIDE_BID), ("_ask", dk.OFFER_SIDE_ASK)):
        f = f"{p}_h1{suf}.csv"
        if os.path.exists(f): continue
        dk.fetch(ins, dk.INTERVAL_HOUR_1, side, dt.datetime(2016, 1, 1), dt.datetime.utcnow()).to_csv(f); print(f)
