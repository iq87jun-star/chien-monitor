# -*- coding: utf-8 -*-
"""docs/295 Q50(改良系): Hold(連続 LONG)に 200 日移動平均の門(前日終値 > SMA200 のときだけ保有)。docs/244 §1 改良系の基準: IS・OOS の両方でベース比 Sharpe 改善 かつ 最悪月が悪化しない。
使い方: python3 queue/q50_hold_trend_gate.py <累積>"""
import sys, os
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609")
SYMS = ["US500", "NAS100", "GER40", "JP225", "UK100", "XAUUSD", "WTI"]
def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return round(float(x.mean() / x.std() * np.sqrt(252)), 2) if x.std() > 0 else 0.0, round(float(m.min()) * 100, 2)
cum = int(sys.argv[1]); R = Runner("Q50", cum, len(SYMS), "results/q50_hold_trend_gate.csv"); rows = []
for nm in SYMS:
    h = base.hold_cell(nm); d = base.load_daily(nm); sma = d["close"].rolling(200).mean(); gate = (d["close"] > sma).shift(1).reindex(h.index).fillna(False).astype(float)
    g = h * gate; R.add("Hold 200日門(改良系)", nm, "前日終値 > SMA200 のときのみ保有", g)
    bi, bo = stats(h, IS0, IS1), stats(h, OOS0, END); gi, go = stats(g, IS0, IS1), stats(g, OOS0, END)
    ok = gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]
    rows.append(dict(symbol=nm, base_IS_sharpe=bi[0], gate_IS_sharpe=gi[0], base_OOS_sharpe=bo[0], gate_OOS_sharpe=go[0], base_IS_worst=bi[1], gate_IS_worst=gi[1], base_OOS_worst=bo[1], gate_OOS_worst=go[1], improved=ok, in_market=round(float(gate.mean()), 2)))
R.finish(); print("\n== Q50 改良判定(IS・OOS 両方で Sharpe 改善 かつ 最悪月が悪化しない)==\n" + pd.DataFrame(rows).to_string(index=False))
