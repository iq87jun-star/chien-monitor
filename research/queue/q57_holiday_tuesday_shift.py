# -*- coding: utf-8 -*-
"""docs/304 Q57(F14): 祝日月曜の週の火曜 o2o LONG × 円クロス 7 = 7 セル(新規)。使い方: python3 queue/q57_holiday_tuesday_shift.py <累積>"""
import sys, os
from q_common import *
from q_cal import *
base.DATA = os.path.join(ROOT, "data_202609")
cum = int(sys.argv[1]); R = Runner("Q57", cum, 7, "results/q57_holiday_tuesday_shift.csv")
for p in base.MON_FX:
    d = base.load_daily(p); c = 3 * base.pip_size(p) / d["open"]
    sel = np.array([(t.dayofweek == 1) and is_jp_holiday(t - pd.Timedelta(days=1)) for t in d.index])
    R.add("祝日月曜の週の火曜 L", p, "月曜が JP 祝日の週の火曜 o2o LONG(3pip)", base.clip((d["o2o"][sel] - c[sel]).dropna()))
R.finish()
