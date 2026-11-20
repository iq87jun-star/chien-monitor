# -*- coding: utf-8 -*-
"""docs/311 Q70(F27): ガードで外した月曜(JP 祝日月曜・翌火曜 JP 祝日・豪NZ祝日 [AUD/NZD])の SHORT。7 ペア + Mon7 合成 + AUD+NZD 合成 = 9 セル(新規)。"""
import sys, os
from q_common import *
from q_cal import *
base.DATA = os.path.join(ROOT, "data_202609")
def skip_day(p, t): return is_jp_holiday(t) or is_jp_holiday(t + pd.Timedelta(days=1)) or ((p[:3] in ("AUD", "NZD")) and ((t in CAL["AU"]) or (t in CAL["NZ"])))
cum = int(sys.argv[1]); R = Runner("Q70", cum, 9, "results/q70_holiday_monday_short.csv"); S = {}
for p in base.MON_FX:
    d = base.load_daily(p); c = 3 * base.pip_size(p) / d["open"]; sel = np.array([(t.dayofweek == 0) and skip_day(p, t) for t in d.index])
    s = base.clip((-d["o2o"][sel] - c[sel]).dropna()); S[p] = s; R.add("ガード日の月曜 SHORT", p, "JP祝日/翌火曜祝日/豪NZ祝日 の月曜 o2o SHORT", s)
def comp(keys):
    out = None
    for k in keys: x = S[k] / len(keys); out = x if out is None else out.add(x, fill_value=0)
    return out
R.add("ガード日の月曜 SHORT", "Mon7", "7 ペア等ウェイト", comp(base.MON_FX)); R.add("ガード日の月曜 SHORT", "AUD+NZD", "AUDJPY+NZDJPY", comp(["AUDJPY", "NZDJPY"]))
R.finish()
