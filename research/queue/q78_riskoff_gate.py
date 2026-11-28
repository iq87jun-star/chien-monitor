# -*- coding: utf-8 -*-
"""docs/313 Q78(F35): リスクオフ相場ゲート。S&P500(US500 日足)前日終値 < SMA200 の週の Mon7 × {のみ, 除外(改良系)} = 2 セル。"""
import sys, os
from q_common import *
from q_cal import mon7, improved
base.DATA = os.path.join(ROOT, "data_202609")
u = base.load_daily("US500")["close"]; bear = (u < u.rolling(200).mean()).shift(1)
M7 = mon7(); sel = pd.Series([bool(bear[bear.index <= t].iloc[-1]) if (bear.index <= t).any() else False for t in M7.index], index=M7.index)
cum = int(sys.argv[1]); R = Runner("Q78", cum, 2, "results/q78_riskoff_gate.csv")
R.add("S&P<SMA200 の週のみ", "Mon7", "前日終値 < 200 日線", M7[sel]); ex = M7[~sel]; R.add("S&P<SMA200 の週 除外(改良系)", "Mon7", "該当月曜を建てない", ex)
print(f"n bear Mondays={int(sel.sum())} 平均 {M7[sel].mean()*1e4:.2f} bps vs {M7[~sel].mean()*1e4:.2f}", improved(M7, ex)); R.finish()
