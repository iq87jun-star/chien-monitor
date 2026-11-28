# -*- coding: utf-8 -*-
"""docs/312 Q72(F29): 急激な円安後(介入リスク)のガード。条件 = 月曜前日終値で USDJPY が直近 20 営業日比 +3% 超、または 252 日高値の 98% 以上。
Mon7 × {該当週のみ, 除外(改良系)} 2 + Mon4 / Mon2 除外(改良系)2 + 該当週の SHORT {Mon7, USDJPY} 2 = 6 セル。"""
import sys, os
from q_common import *
from q_cal import mon7, improved
base.DATA = os.path.join(ROOT, "data_202609")
u = base.load_daily("USDJPY")["close"]; r20 = u / u.shift(20) - 1; hi = u.rolling(252).max()
risk = ((r20 > 0.03) | (u >= 0.98 * hi)).shift(1)   # 前日終値で判定
def flag(t): return bool(risk.get(t, False)) if t in risk.index else bool(risk[risk.index < t].iloc[-1]) if (risk.index < t).any() else False
M7 = mon7(); sel = pd.Series([flag(t) for t in M7.index], index=M7.index)
cum = int(sys.argv[1]); R = Runner("Q72", cum, 6, "results/q72_intervention_guard.csv"); imp = []
R.add("介入リスク週 のみ", "Mon7", "USDJPY 20日+3% or 52週高値圏", M7[sel]); ex = M7[~sel]; R.add("介入リスク週 除外(改良系)", "Mon7", "該当月曜を建てない", ex); imp.append(dict(comp="Mon7", n=int(sel.sum()), mean_sel=round(float(M7[sel].mean()) * 1e4, 2), mean_rest=round(float(M7[~sel].mean()) * 1e4, 2), worst_sel=round(float(M7[sel].min()) * 100, 2), worst_rest=round(float(M7[~sel].min()) * 100, 2), **improved(M7, ex)))
for nm, w in {"Mon4": {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}, "Mon2": {"GBPJPY": .537, "AUDJPY": .463}}.items():
    c = None
    for p, wt in w.items(): x = base.mon_cell(p) * wt; c = x if c is None else c.add(x, fill_value=0)
    s2 = pd.Series([flag(t) for t in c.index], index=c.index); ex2 = c[~s2]; R.add(f"{nm} 介入リスク週 除外(改良系)", nm, "該当月曜を建てない", ex2); imp.append(dict(comp=nm, n=int(s2.sum()), mean_sel=round(float(c[s2].mean()) * 1e4, 2), mean_rest=round(float(c[~s2].mean()) * 1e4, 2), worst_sel=round(float(c[s2].min()) * 100, 2), worst_rest=round(float(c[~s2].min()) * 100, 2), **improved(c, ex2)))
d = base.load_daily("USDJPY"); cc = 3 * base.pip_size("USDJPY") / d["open"]; selu = np.array([(t.dayofweek == 0) and flag(t) for t in d.index])
R.add("介入リスク週 SHORT", "Mon7", "該当月曜 o2o SHORT(合成の符号反転・コスト 2 倍)", -(M7[sel]) - 2 * 2e-4); R.add("介入リスク週 SHORT", "USDJPY", "該当月曜 o2o SHORT(3pip)", base.clip((-d["o2o"][selu] - cc[selu]).dropna()))
R.finish(); pd.set_option("display.width", 300); print("\n== Q72 診断 ==\n" + pd.DataFrame(imp).to_string(index=False))
