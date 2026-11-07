# -*- coding: utf-8 -*-
"""docs/305 Q62(F19): Mon7 × 前金曜が JP 祝日 {のみ, 除外} + (AUDJPY+NZDJPY) × 翌火曜が豪NZ祝日 {のみ, 除外} = 4 セル。使い方: python3 queue/q62_mon_remaining_filters.py <累積>"""
import sys, os
from q_common import *
from q_cal import *
base.DATA = os.path.join(ROOT, "data_202609")
M7 = mon7(); AN = (base.mon_cell("AUDJPY").add(base.mon_cell("NZDJPY"), fill_value=0)) / 2
cum = int(sys.argv[1]); R = Runner("Q62", cum, 4, "results/q62_mon_remaining_filters.csv"); imp = []
for name, f, s, sym in [("前金曜がJP祝日", lambda t: is_jp_holiday(t - pd.Timedelta(days=3)), M7, "Mon7"), ("翌火曜が豪NZ祝日", lambda t: ((t + pd.Timedelta(days=1)) in CAL["AU"]) or ((t + pd.Timedelta(days=1)) in CAL["NZ"]), AN, "AUD+NZD")]:
    sel = pd.Series([bool(f(t)) for t in s.index], index=s.index)
    R.add(f"{name} のみ", sym, "該当月曜のみ o2o L", s[sel]); ex = s[~sel]
    R.add(f"{name} 除外(改良系)", sym, "該当月曜を建てない", ex); imp.append(dict(filter=name, n=int(sel.sum()), mean_bps_sel=round(float(s[sel].mean()) * 1e4, 2), mean_bps_rest=round(float(s[~sel].mean()) * 1e4, 2), **improved(s, ex)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q62 改良判定 ==\n" + pd.DataFrame(imp).to_string(index=False))
