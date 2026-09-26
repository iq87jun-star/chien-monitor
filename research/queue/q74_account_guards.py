# -*- coding: utf-8 -*-
"""docs/312 Q74(F31): 口座レベルのガード検証。EA の残高ガード(日次 −4% で全決済・月 2 回で月末まで停止)と日次停止を研究系列(配備倍率)に当て、ガードあり vs なしを比較。
Mon4 ×3.3 / Instant G / #14074882 ×5 / EA7g(日次 1.9%・月 2 回)= 4 セル(改良系: IS・OOS Sharpe と最悪月)。"""
import sys, os
from q_common import *
from q_cal import improved
HERE = os.path.dirname(os.path.abspath(__file__)); RES = os.path.dirname(HERE)
src = open(os.path.join(RES, "ea_filter_before_after.py"), encoding="utf-8").read().split("ACC={")[0]
ns = {"__name__": "ba", "__file__": os.path.join(RES, "ea_filter_before_after.py")}; exec(compile(src, "ba", "exec"), ns); logic = ns["logic"]
def guarded(c, day_guard, max_fires=2):
    x = c.copy(); mk = pd.PeriodIndex(x.index, freq="M"); out = x.copy()
    for m in mk.unique():
        idx = x.index[mk == m]; fires = 0; halted = False
        for t in idx:
            if halted: out[t] = 0.0; continue
            if x[t] <= -day_guard: out[t] = -day_guard; fires += 1
            if fires >= max_fires: halted = True
    return out
cum = int(sys.argv[1]); R = Runner("Q74", cum, 4, "results/q74_account_guards.csv"); rows = []
for key, g in (("EA3 Mon4 ×2.5", 0.04), ("Instant G", 0.04), ("#14074882 ギャンブル", 0.04), ("EA7g", 0.019)):
    c = logic(key, True); v = guarded(c, g); fires = int((c <= -g).sum()); halts = 0
    mk = pd.PeriodIndex(c.index, freq="M"); halts = int(sum((c[mk == m] <= -g).sum() >= 2 for m in mk.unique()))
    R.add("口座ガード(改良系)", key, f"日次 −{g*100:.1f}% で全決済・月 {2} 回で月末停止", v); rows.append(dict(comp=key, fires_5y=fires, month_halts=halts, **improved(c, v)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q74 ==\n" + pd.DataFrame(rows).to_string(index=False))
