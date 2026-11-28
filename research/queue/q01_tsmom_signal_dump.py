# -*- coding: utf-8 -*-
"""docs/253 Q1 パリティ A: 研究側 TSMOM の月次符号表を出す(tsmom_cell と同一ロジック)。→ results/tsmom_signals_python.csv
列: symbol, month(適用月 YYYY-MM), sign(+1/-1/0), sum(符号和), c_last(直近確定月の終値)。research/ で実行。"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT)
import recentfit_screen as base
rows = []
for nm in base.TSMOM_SYMS:
    df = base.load_daily(nm); px = df["close"].resample("ME").last().dropna()
    sig = sum(np.sign(px.pct_change(lb)) for lb in (1, 3, 6, 12)); pos = np.sign(sig).shift(1)   # 前月末で確定 → 当月に適用
    for m, s in pos.dropna().items():
        rows.append(dict(symbol=nm, month=(m + pd.offsets.MonthBegin(0)).strftime("%Y-%m") if False else (m.to_period("M") + 1).strftime("%Y-%m"), sign=int(s), sum=int(sig.shift(1).loc[m]), c_last=float(px.loc[m])))
R = pd.DataFrame(rows); R = R[R.month >= "2016-01"]; R.to_csv("results/tsmom_signals_python.csv", index=False)
print(R.groupby("symbol").agg(n=("sign", "size"), long=("sign", lambda s: int((s > 0).sum())), short=("sign", lambda s: int((s < 0).sum())), flat=("sign", lambda s: int((s == 0).sum()))).to_string())
print(R.tail(6).to_string(index=False))
