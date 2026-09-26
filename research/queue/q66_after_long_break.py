# -*- coding: utf-8 -*-
"""docs/306 Q66(F23): 日本の連休明け最初の月曜(直前に JP 非営業日が 4 日以上連続した週の月曜、または月曜自体がその連休直後の最初の営業週)× Mon7 × {のみ, 除外} = 2 セル。"""
import sys, os
from q_common import *
from q_cal import *
base.DATA = os.path.join(ROOT, "data_202609")
def after_break(t):   # 月曜 t の直前 10 日以内に JP 非営業日が 4 日以上連続する区間があり、t がその後最初の月曜
    d = pd.Timestamp(t).normalize() - pd.Timedelta(days=1); run = 0; best = 0
    for k in range(10):
        if not is_jp_bday(d): run += 1; best = max(best, run)
        else:
            if best >= 4: return True
            run = 0
        d -= pd.Timedelta(days=1)
    return best >= 4
M7 = mon7(); sel = pd.Series([after_break(t) for t in M7.index], index=M7.index)
cum = int(sys.argv[1]); R = Runner("Q66", cum, 2, "results/q66_after_long_break.csv")
R.add("連休明け最初の月曜 のみ", "Mon7", "直前 10 日に JP 非営業日 4 日以上連続", M7[sel]); ex = M7[~sel]; R.add("連休明け最初の月曜 除外(改良系)", "Mon7", "該当月曜を建てない", ex)
print(f"n={int(sel.sum())} 平均 {M7[sel].mean()*1e4:.2f} bps vs 通常 {M7[~sel].mean()*1e4:.2f}", improved(M7, ex)); R.finish()
