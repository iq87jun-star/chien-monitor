# -*- coding: utf-8 -*-
"""Dukascopy ティック CSV(timestamp,bid,ask)→ 時間帯別スプレッド・プロファイル(小さな要約 CSV。生ティックはコミットしない)。
使い方: python3 research/tools/tick_spread_profile.py GBPJPY [USDJPY ...]
出力: research/results/spread_profile_<SYM>.csv  (列: hour_utc, weekday, n, med_pips, p90_pips, p99_pips)"""
import os, sys, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PIP = lambda s: 0.01 if s.endswith("JPY") else (1.0 if s in ("US500", "NAS100", "GER40", "UK100", "JP225") else (0.1 if s == "XAUUSD" else 0.0001))
for sym in sys.argv[1:]:
    p = os.path.join(ROOT, "data_dukascopy", f"{sym}_tick.csv")
    if not os.path.exists(p): print("無し:", p); continue
    d = pd.read_csv(p, parse_dates=["timestamp"], usecols=["timestamp", "bid", "ask"])
    d["sp"] = (d.ask - d.bid) / PIP(sym); d = d[(d.sp >= 0) & (d.sp < 200)]
    g = d.groupby([d.timestamp.dt.hour.rename("hour_utc"), d.timestamp.dt.dayofweek.rename("weekday")])["sp"]
    out = g.agg(n="size", med_pips="median", p90_pips=lambda x: x.quantile(0.9), p99_pips=lambda x: x.quantile(0.99)).reset_index()
    out["period"] = f"{d.timestamp.min().date()}..{d.timestamp.max().date()}"
    o = os.path.join(ROOT, "results", f"spread_profile_{sym}.csv"); out.round(2).to_csv(o, index=False)
    print(f"{sym}: {len(d)} ticks {out.period.iloc[0]} → {o}")
    print(out.groupby("hour_utc")[["med_pips", "p90_pips"]].median().round(2).T.to_string())
