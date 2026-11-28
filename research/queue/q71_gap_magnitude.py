# -*- coding: utf-8 -*-
"""docs/311 Q71(F28): 週末ギャップ幅(H1: 金曜最終終値→月曜初値、|gap|/価格 の IS 90 分位で判定)。Mon7 × {上位10%のみ, 除外(改良系)} + 上位10%日の {順張り 24h, 逆張り 24h} = 4 セル。"""
import sys, os
from q_common import *
from q_cal import mon7, improved
base.DATA = os.path.join(ROOT, "data_202609")
G = {}
for p in base.MON_FX:
    h = load(p); o = h["open"]; c = h["close"]; mon = o.index[(o.index.dayofweek == 0) & (o.index.hour == 0)]
    rows = {}
    for t in mon:
        f = h[(h.index >= t - pd.Timedelta(days=3)) & (h.index < t - pd.Timedelta(days=2))]
        if len(f) >= 5: rows[t.normalize()] = float(o[t] / f["close"].iloc[-1] - 1.0)
    G[p] = pd.Series(rows)
thr = {p: G[p][(G[p].index >= IS0) & (G[p].index <= IS1)].abs().quantile(0.9) for p in base.MON_FX}
M7 = mon7(); big = pd.Series([any((t in G[p].index) and abs(G[p][t]) > thr[p] for p in base.MON_FX) for t in M7.index], index=M7.index)
cum = int(sys.argv[1]); R = Runner("Q71", cum, 4, "results/q71_gap_magnitude.csv")
R.add("ギャップ幅上位10% のみ", "Mon7", "いずれかのペアで |gap| > IS 90分位", M7[big]); ex = M7[~big]; R.add("ギャップ幅上位10% 除外(改良系)", "Mon7", "該当月曜を建てない", ex)
# 順張り / 逆張り: 該当ペアのみ、gap 方向 ±、月曜 00:00→24h(3pip)
def dir_leg(sign):
    out = None
    for p in base.MON_FX:
        h = load(p); o = h["open"]; g = G[p]; d = g.index[g.abs() > thr[p]]; t = pd.DatetimeIndex([x for x in d]); dirs = np.sign(g.reindex(t).values) * sign
        r = trades(p, t, o.reindex(t).values, dirs, o.reindex(t + pd.Timedelta(hours=24)).values) / 7; out = r if out is None else out.add(r, fill_value=0)
    return out
R.add("ギャップ幅上位10% 順張り 24h", "Mon7", "gap 方向に 00→24h", dir_leg(+1)); R.add("ギャップ幅上位10% 逆張り 24h", "Mon7", "gap 逆方向に 00→24h", dir_leg(-1))
print("n big weeks:", int(big.sum()), improved(M7, ex)); R.finish()
