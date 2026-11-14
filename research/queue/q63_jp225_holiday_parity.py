# -*- coding: utf-8 -*-
"""docs/305 Q63(F20・パリティ診断): Mon JP225 / Hold JP225 × JP 祝日 {のみ}。研究系列(Yahoo 日足)が JP 休場日に行を持つかの確認。2 セル(判定なし・累積には加算)。"""
import sys, os
from q_common import *
from q_cal import *
base.DATA = os.path.join(ROOT, "data_202609")
cum = int(sys.argv[1]); R = Runner("Q63", cum, 2, "results/q63_jp225_holiday_parity.csv")
d = base.load_daily("JP225"); rows_on_hol = int(sum(is_jp_holiday(t) for t in d.index)); print(f"JP225 日足の行数 {len(d)} / うち JP 祝日の行 {rows_on_hol}")
m = base.mon_cell("JP225"); sel = pd.Series([is_jp_holiday(t) for t in m.index], index=m.index); R.add("Mon JP225 JP祝日月曜のみ", "JP225", "診断", m[sel]); print("Mon JP225 祝日月曜 n =", int(sel.sum()))
h = base.hold_cell("JP225"); selh = pd.Series([is_jp_holiday(t) for t in h.index], index=h.index); R.add("Hold JP225 JP祝日のみ", "JP225", "診断", h[selh]); print("Hold JP225 祝日行 n =", int(selh.sum()), "平均 bps", round(float(h[selh].mean()) * 1e4, 2) if selh.any() else None)
R.finish()
