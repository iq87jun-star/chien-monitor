# -*- coding: utf-8 -*-
"""Q146(新規 5 セル・結果前に固定): 米大型株 40 銘柄の決算前後。反応日 R = 発表が 12 時前(寄り前)なら当日、12 時以降(引け後)なら翌営業日。0 時ちょうどは時刻不明として除外。
C1 決算前ラン LONG: 終値 R−6 → 終値 R−1(発表をまたがない)
C2L / C2S EPS サプライズ追随: サプライズ ≥ +5% は LONG、< 0%(未達)は SHORT。終値 R → 終値 R+10
C3L / C3S 株価反応追随: 反応日リターン(終値 R−1 → 終値 R)≥ +5% は LONG、≤ −5% は SHORT。終値 R → 終値 R+10
コスト 10 bps/往復。主評価は SPY 控除(超過)リターン。窓 PRE 2016〜2021-09 / IS 2021-10〜2024 / OOS 2025〜。
標準 = IS の月次(その月のイベント平均)二項 p < 0.05/9,806・OOS 平均 > 0・PRE +月率 ≥ 50%。"""
import pandas as pd, numpy as np, sys
from math import comb
D = sys.argv[1]; CST = 1e-3
px = pd.read_pickle(f"{D}/px.pkl"); E = pd.read_pickle(f"{D}/earn.pkl")
C = {t: px[t]["Close"].dropna() for t in px.columns.get_level_values(0).unique()}
spy = C["SPY"]; days = spy.index
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31"), pd.Timestamp("2025-01-01")
ev = []
for _, r in E.iterrows():
    ts = r["Earnings Date"]; t = r["ticker"]
    if pd.isna(r.get("Reported EPS")) or ts.hour == 0 and ts.minute == 0: continue
    d = pd.Timestamp(ts.date())
    i = days.searchsorted(d)
    if i >= len(days): continue
    if days[i] != d and ts.hour < 12: pass
    R = i if ts.hour < 12 else (i + 1 if days[i] == d else i)
    if R - 6 < 0 or R + 10 >= len(days): continue
    c = C[t]
    def at(k): return c.get(days[k], np.nan)
    def sp(k): return spy.get(days[k], np.nan)
    react = at(R) / at(R - 1) - 1
    ev.append(dict(t=t, R=days[R], surprise=r["Surprise(%)"], react=react,
                   pre=at(R - 1) / at(R - 6) - 1, pre_spy=sp(R - 1) / sp(R - 6) - 1,
                   post=at(R + 10) / at(R) - 1, post_spy=sp(R + 10) / sp(R) - 1))
V = pd.DataFrame(ev).dropna(subset=["pre", "post", "react"])
V = V[(V.R >= PRE0)]
cells = {
 "C1 決算前ラン LONG(R−6→R−1)": (V, "pre", 1),
 "C2L EPS サプライズ ≥ +5% LONG(R→R+10)": (V[V.surprise >= 5], "post", 1),
 "C2S EPS 未達(< 0%)SHORT(R→R+10)": (V[V.surprise < 0], "post", -1),
 "C3L 反応 ≥ +5% LONG(R→R+10)": (V[V.react >= 0.05], "post", 1),
 "C3S 反応 ≤ −5% SHORT(R→R+10)": (V[V.react <= -0.05], "post", -1),
}
def stats(s):
    out = {}
    for lab, a, b in [("PRE", PRE0, IS0), ("IS", IS0, IS1), ("OOS", OOS0, pd.Timestamp("2027-01-01"))]:
        x = s[(s.index >= a) & (s.index < b + pd.Timedelta(days=1))]
        m = x.groupby(x.index.to_period("M")).mean(); n = len(m); k = int((m > 0).sum())
        p = sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n if n else 1.0
        out[lab] = dict(ev=len(x), bps=round(float(x.mean() * 1e4), 1) if len(x) else np.nan, hit=round(float((x > 0).mean()), 3) if len(x) else np.nan,
                        t=round(float(x.mean() / x.std() * np.sqrt(len(x))), 2) if len(x) > 2 else np.nan, mrate=round(k / n, 3) if n else np.nan, p=p)
    return out
rows = []
for name, (g, col, d) in cells.items():
    raw = pd.Series(d * g[col].values - CST, index=g.R.values).sort_index()
    exc = pd.Series(d * (g[col].values - g[col + "_spy"].values) - CST, index=g.R.values).sort_index()
    for kind, s in [("超過", exc), ("生", raw)]:
        st = stats(s)
        rows.append(dict(cell=name, kind=kind, **{f"{k}_{f}": v[f] for k, v in st.items() for f in ("ev", "bps", "hit", "t")},
                         IS_p=round(st["IS"]["p"], 4), sign3=bool(all(st[k]["bps"] > 0 for k in st)),
                         std=bool(st["IS"]["p"] < 0.05 / 9806 and st["OOS"]["bps"] > 0 and st["PRE"]["mrate"] >= 0.5)))
R = pd.DataFrame(rows); pd.set_option("display.width", 300); print(R.to_string(index=False)); R.to_csv(f"{D}/q146_earnings.csv", index=False)
print("\nイベント数:", len(V), "銘柄:", V.t.nunique(), "期間:", V.R.min().date(), "〜", V.R.max().date())
