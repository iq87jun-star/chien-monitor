# -*- coding: utf-8 -*-
"""docs/253 Q1 パリティ A: MT5 側の符号表(Chien_TsmomSignalDump.mq5 が MQL5/Files/tsmom_signals_mt5.csv に書く)と研究側を突合。
使い方: python3 queue/q01_tsmom_parity.py <tsmom_signals_mt5.csv> [銘柄対応 "SPX500=US500,NDX100=NAS100"]
合格: 銘柄ごとに符号一致率 ≥ 95%(docs/244 Q1)。不一致月を列挙。"""
import sys, pandas as pd
mt5 = pd.read_csv(sys.argv[1]); py = pd.read_csv("results/tsmom_signals_python.csv")
alias = dict(kv.split("=") for kv in sys.argv[2].split(",")) if len(sys.argv) > 2 else {}
mt5["symbol"] = mt5["symbol"].map(lambda s: alias.get(s, s))
m = py.merge(mt5[["symbol", "month", "sign"]], on=["symbol", "month"], suffixes=("_py", "_mt5"))
for sym, g in m.groupby("symbol"):
    agree = (g.sign_py == g.sign_mt5).mean(); bad = g[g.sign_py != g.sign_mt5]
    print(f"{sym:8s} n={len(g):3d} 一致 {agree*100:5.1f}% {'PASS' if agree >= 0.95 else 'FAIL'}  不一致: {', '.join(bad.month.tolist()[:12])}")
