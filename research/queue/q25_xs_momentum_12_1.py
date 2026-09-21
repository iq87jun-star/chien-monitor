# -*- coding: utf-8 -*-
"""docs/264 Q25(F): クロスセクション 12-1 モメンタム(月次)。ユニバース FX7(対 USD: EUR GBP AUD NZD JPY CHF CAD)は上位 2 L / 下位 2 S、マルチ 12(US500 NAS100 GER40 UK100 JP225 US30 EUSTX50 AUS200 XAUUSD XAGUSD BRENT WTI)は上位 3 / 下位 3。
ルックバック {6, 12} ヶ月 × スキップ {0, 1} ヶ月 × 2 ユニバース = 8 セル。月末終値でランクし翌月保有。コスト: 各レグ往復(FX 3pip / NONFX 表)を月次で控除。
使い方: python3 queue/q25_xs_momentum_12_1.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); R = Runner("Q25", cum, 8, "results/q25_xs_momentum_12_1.csv")
def monthly_close(sym, invert=False):
    df = load(sym); c = df["close"].groupby(df.index.to_period("M")).last(); return (1 / c) if invert else c
FX = {"EUR": ("EURUSD", False), "GBP": ("GBPUSD", False), "AUD": ("AUDUSD", False), "NZD": ("NZDUSD", False), "JPY": ("USDJPY", True), "CHF": ("USDCHF", True), "CAD": ("USDCAD", True)}
MULTI = ["US500", "NAS100", "GER40", "UK100", "JP225", "US30", "EUSTX50", "AUS200", "XAUUSD", "XAGUSD", "BRENT", "WTI"]
def run(name, series, costs, k):
    P = pd.DataFrame(series).sort_index(); ret = P.pct_change()
    for L in (6, 12):
        for S in (0, 1):
            sig = P.shift(S) / P.shift(L + S) - 1   # 月末時点の過去 L ヶ月(直近 S ヶ月スキップ)リターン
            out = []
            for i in range(1, len(P)):
                s = sig.iloc[i - 1].dropna()
                if len(s) < 2 * k + 1: continue
                r = ret.iloc[i]; top = s.nlargest(k).index; bot = s.nsmallest(k).index
                x = np.nanmean(r[top].values) - np.nanmean(r[bot].values) - np.mean([costs[a] for a in list(top) + list(bot)])
                out.append((P.index[i].to_timestamp(), x))
            r = pd.Series(dict(out)); R.add("XS モメンタム", name, f"L={L} S={S} top/bottom {k}", r)
fx_series = {c: monthly_close(s, inv) for c, (s, inv) in FX.items()}; fx_cost = {c: float(cost(FX[c][0], np.array([1.0]))[0]) if not FX[c][1] else 3 * base.pip_size(FX[c][0]) / float(monthly_close(FX[c][0]).mean()) for c in FX}
run("FX7", fx_series, fx_cost, 2)
mu_series = {s: monthly_close(s) for s in MULTI}; mu_cost = {s: float(cost(s, np.array([1.0]))[0]) for s in MULTI}
run("MULTI12", mu_series, mu_cost, 3)
R.finish()
