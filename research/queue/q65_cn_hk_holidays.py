# -*- coding: utf-8 -*-
"""docs/306 Q65(F22): 中国・香港の連休週(週内に CN 祝日が 3 日以上)× {AUDJPY+NZDJPY 合成, Mon7} × {のみ, 除外} = 4 セル。使い方: python3 queue/q65_cn_hk_holidays.py <累積>"""
import sys, os
from q_common import *
from q_cal import *
base.DATA = os.path.join(ROOT, "data_202609")
h = pd.read_csv(os.path.join(ROOT, "data_ext", "holidays_cn_hk_2016_2027.csv")); CN = set(pd.to_datetime(h[h.cal == "CN"]["date"]).dt.normalize())
def cn_week(t): m = week_of(t); return sum((m + pd.Timedelta(days=k)) in CN for k in range(5)) >= 3
M7 = mon7(); AN = (base.mon_cell("AUDJPY").add(base.mon_cell("NZDJPY"), fill_value=0)) / 2
cum = int(sys.argv[1]); R = Runner("Q65", cum, 4, "results/q65_cn_hk_holidays.csv"); imp = []
for nm, s in (("AUD+NZD", AN), ("Mon7", M7)):
    sel = pd.Series([cn_week(t) for t in s.index], index=s.index)
    R.add("中国連休週の月曜 のみ", nm, "週内 CN 祝日 ≥3 日", s[sel]); ex = s[~sel]; R.add("中国連休週の月曜 除外(改良系)", nm, "該当週を建てない", ex)
    imp.append(dict(comp=nm, n=int(sel.sum()), mean_sel=round(float(s[sel].mean()) * 1e4, 2), mean_rest=round(float(s[~sel].mean()) * 1e4, 2), **improved(s, ex)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q65 改良判定 ==\n" + pd.DataFrame(imp).to_string(index=False))
