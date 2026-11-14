# -*- coding: utf-8 -*-
"""docs/315 Q81(F38・無料案): 通貨ボラ門。CBOE ユーロ通貨 VIX(EVZ・FRED EVZCLS・2007-11〜2025-03 廃止)の前金曜終値が直近 252 営業日の 80 分位を超える週を
「通貨ボラ高」とし、Mon7 × {のみ, 除外(改良系)} = 2 セル。データが 2025-03-11 で終わるため基準・変種とも同日までに切って判定(OOS は 2025-01〜03 の 3 ヶ月のみ)。"""
import sys, os
from q_common import *
from q_cal import mon7, improved
ev = pd.read_csv("data_ext/evz_fred.csv"); ev["t"] = pd.to_datetime(ev["observation_date"]); ev = ev.set_index("t")["EVZCLS"].apply(pd.to_numeric, errors="coerce").dropna()
thr = ev.rolling(252, min_periods=200).quantile(0.8); hi = (ev > thr)
M7 = mon7(); M7 = M7[M7.index <= ev.index[-1]]
def gate(t):
    w = hi[hi.index < t]
    return bool(w.iloc[-1]) if len(w) else False
sel = pd.Series([gate(t) for t in M7.index], index=M7.index)
cum = int(sys.argv[1]); R = Runner("Q81", cum, 2, "results/q81_evz_gate.csv")
R.add("EVZ 高(80 分位超)の週のみ", "Mon7", "前金曜 EVZ > 252 日 80 分位", M7[sel]); ex = M7[~sel]; R.add("EVZ 高の週 除外(改良系)", "Mon7", "該当月曜を建てない", ex)
print(f"EVZ 期間 {ev.index[0].date()}〜{ev.index[-1].date()} / 判定月曜 {len(M7)} 本(〜{M7.index[-1].date()}) / 該当 {int(sel.sum())} 本 平均 {M7[sel].mean()*1e4:.2f} bps vs {M7[~sel].mean()*1e4:.2f}")
print("年別該当:", sel.groupby(sel.index.year).sum().to_dict()); print(improved(M7, ex)); R.finish()
