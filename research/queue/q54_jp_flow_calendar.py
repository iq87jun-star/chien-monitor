# -*- coding: utf-8 -*-
"""docs/303 Q54(F11): 日本の資金フロー暦 × 円クロス 7 本。14 セル(新規)。
 a) ゴトー日(5・10・15・20・25・月末、JP 休日なら直前の JP 営業日)の o2o LONG = 7
 b) 月初 3 JP 営業日の o2o LONG = 7
使い方: python3 queue/q54_jp_flow_calendar.py <累積>"""
import sys, os
from q_common import *
from q_jp import *
base.DATA = os.path.join(ROOT, "data_202609")
def gotobi_days(a, b):
    out = set()
    for d in pd.date_range(a, b, freq="D"):
        if d.day in (5, 10, 15, 20, 25) or d == d + pd.offsets.MonthEnd(0): out.add(prev_jp_bday(d))
    return out
def first3_days(a, b):
    out = set()
    for m in pd.period_range(a, b, freq="M"):
        d = m.start_time.normalize(); k = 0
        while k < 3:
            if is_jp_bday(d): out.add(d); k += 1
            d += pd.Timedelta(days=1)
    return out
cum = int(sys.argv[1]); R = Runner("Q54", cum, 14, "results/q54_jp_flow_calendar.csv")
G = gotobi_days(PRE0, END); F = first3_days(PRE0, END)
for p in base.MON_FX:
    d = base.load_daily(p); c = 3 * base.pip_size(p) / d["open"]
    for fam, days in (("ゴトー日 L", G), ("月初3営業日 L", F)):
        sel = d.index.isin(list(days)); R.add(fam, p, fam + " o2o(3pip)", base.clip((d["o2o"][sel] - c[sel]).dropna()))
R.finish()
