# -*- coding: utf-8 -*-
"""docs/244 Q6: ボラ・レジーム門(改良系)。VIX 期間構造・VIX 水準の門は docs/203・204(external_gates_10y.py)で検定済みのため再検定しない。
本項は「原資産の 20 日実現ボラの分位(直近 252 日の三分位・前日まで)」で Mon 合成 / v4 合成をオン・オフする 2 × 3 = 6 セル。
判定: 門ありが門なし(全日)に対し IS(2021-10〜2024-12)・OOS(2025-01〜)両方で Sharpe 改善 かつ 最悪月が悪化しない。research/ で実行。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT)
import recentfit_screen as base, deployed_book as db
IS0, IS1, OOS0 = pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31"), pd.Timestamp("2025-01-01")
WA = {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}
def comp(parts):
    idx = sorted(set().union(*[set(s.index) for s, _ in parts])); out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s, w in parts: out = out.add(s.reindex(out.index).fillna(0) * w, fill_value=0)
    return out
mon = comp([(db.leg_series("Mon", s), w) for s, w in WA.items()])
v4 = comp([(db.leg_series("v4", s), 1.0 / len(base.V4_PAIRS)) for s in base.V4_PAIRS])
def rv(syms):   # 原資産 20 日実現ボラ(平均)→ 直近 252 日の三分位(前日まで・先読みなし)
    r = pd.concat([base.load_daily(s)["close"].pct_change() for s in syms], axis=1).mean(axis=1)
    v = r.rolling(20).std(); lo = v.rolling(252).quantile(1 / 3).shift(1); hi = v.rolling(252).quantile(2 / 3).shift(1); v = v.shift(1)
    t = pd.Series(np.where(v <= lo, 0, np.where(v <= hi, 1, 2)), index=v.index).where(~(v.isna() | lo.isna() | hi.isna()))
    return t
def perf(r):
    d = r[r != 0]
    if len(d) < 20: return dict(sharpe=np.nan, worst_m=np.nan, cum=np.nan, n=len(d))
    m = r.groupby(pd.PeriodIndex(r.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return dict(sharpe=round(float(d.mean() / d.std() * np.sqrt(252)), 2), worst_m=round(float(m.min()) * 100, 2), cum=round(float((1 + r).prod() - 1) * 100, 1), n=len(d))
rows = []
for name, s, syms in (("Mon 4", mon, list(WA)), ("v4", v4, base.V4_PAIRS)):
    ter = rv(syms).reindex(s.index)
    for k, lab in ((None, "門なし"), (0, "低ボラ 1/3"), (1, "中 1/3"), (2, "高ボラ 1/3")):
        g = s if k is None else s.where(ter == k, 0.0)
        pi, po = perf(g[(g.index >= IS0) & (g.index <= IS1)]), perf(g[g.index >= OOS0])
        rows.append(dict(sleeve=name, gate=lab, is_sharpe=pi["sharpe"], is_worst_m=pi["worst_m"], is_cum=pi["cum"], oos_sharpe=po["sharpe"], oos_worst_m=po["worst_m"], oos_cum=po["cum"]))
R = pd.DataFrame(rows)
def flag(g):
    b = g[g.gate == "門なし"].iloc[0]; g = g.copy()
    g["improve"] = (g.gate != "門なし") & (g.is_sharpe > b.is_sharpe) & (g.oos_sharpe > b.oos_sharpe) & (g.is_worst_m >= b.is_worst_m) & (g.oos_worst_m >= b.oos_worst_m); return g
R = R.groupby("sleeve", group_keys=False).apply(flag); R.to_csv("results/q6_vol_regime_gate.csv", index=False)
pd.set_option("display.width", 200); print(R.to_string(index=False)); print("improve:", int(R.improve.sum()))
