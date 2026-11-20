# -*- coding: utf-8 -*-
"""docs/244 Q227(改良系・3 セル・2026-11-15 登録): 月曜の円クロス — 「下げの度合い」(200 日線からの下方乖離)と「荒れの度合い」(前金曜の VIX)を 1 つの点数にまとめる。
z1 = −(終値/SMA200 − 1) をその通貨の過去だけで標準化、z2 = VIX を過去だけで標準化。合計 = z1 + z2、そろい = min(z1, z2)。p = それ以前の全通貨の点数の中での順位(0〜1)。
G1: 0.5 + 0.5 p(合計)。G2: 0.25 + 0.75 p(合計)。G3: 0.5 + 0.5 p(そろい)。履歴不足の間は配備形(下 1.0・上 0.5)。1.0 倍を超えない。
判定 = 配備形に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。
使い方: cd research && python3 -W ignore queue/q227_mon4_decline_x_vix_score.py <累積セル数>   出力: results/q227_mon4_decline_x_vix_score.csv・_quant.csv・_grid.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS, states
import deployed_book as db
from scipy import stats as sps
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
V = pd.read_csv("data_ext/VIX_History.csv"); V["d"] = pd.to_datetime(V["DATE"]); VIX = V.set_index("d")["CLOSE"].sort_index().astype(float)
VZ = ((VIX - VIX.expanding(min_periods=252).mean().shift(1)) / VIX.expanding(min_periods=252).std().shift(1))          # その日より前の VIX だけで標準化
def frame():
    rows = []
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); m = m[(m.index >= PRE0) & (m.index <= h.index.max())]; st = states(s).shift(1).reindex(m.index, method="ffill"); fri = pd.DatetimeIndex(m.index) - pd.Timedelta(days=3)
        x1 = -st.sma200; z1 = (x1 - x1.expanding(min_periods=52).mean().shift(1)) / x1.expanding(min_periods=52).std().shift(1)        # その通貨の、それ以前の月曜の値だけで標準化
        rows.append(pd.DataFrame({"r": m.values, "sym": s, "d200": st.sma200.values, "vix": VIX.reindex(fri, method="ffill").values, "z1": z1.values, "z2": VZ.reindex(fri, method="ffill").values}, index=m.index))
    P = pd.concat(rows).sort_index(kind="stable"); P["s_sum"] = P.z1 + P.z2; P["s_and"] = P[["z1", "z2"]].min(axis=1); P.loc[P.z1.isna() | P.z2.isna(), ["s_sum", "s_and"]] = np.nan
    for c in ("s_sum", "s_and"):
        p = np.full(len(P), np.nan); dates = P.index.values; vals = P[c].values; hist = []
        for d in np.unique(dates):          # 日付ごと: それより前の点数だけで順位を付ける
            ii = np.where(dates == d)[0]
            if len(hist) >= 200:
                H = np.sort(np.array(hist)); p[ii] = [np.searchsorted(H, v, side="right") / len(H) if v == v else np.nan for v in vals[ii]]
            hist += [v for v in vals[ii] if v == v]
        P["p_" + c[2:]] = p
    P["base"] = np.where(P.d200.isna(), 1.0, np.where(P.d200 < 0, 1.0, 0.5)); return P
def fac(P, kind):
    if kind == "base": return P.base.values
    p = P["p_sum"].values if kind in ("G1", "G2") else P["p_and"].values; f = (0.25 + 0.75 * p) if kind == "G2" else (0.5 + 0.5 * p); return np.where(np.isnan(p), P.base.values, f)
def mon4_score(kind="G1"):
    """紙上候補用: 配備形 Mon4(各 0.25)に Q227 の倍率を掛けた系列。"""
    P = frame(); return (P.r * fac(P, kind) * 0.25).groupby(level=0).sum()
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 3; P = frame()
    def comp(k): return (P.r * (fac(P, k) if k else 1.0) * 0.25).groupby(level=0).sum()
    B = comp("base"); bs = {w: stats(B, a, b) for w, a, b in WIN}; rows = []
    LAB = {"G1": "G1 合計の点数の順位で 0.5〜1.0 倍", "G2": "G2 合計の点数の順位で 0.25〜1.0 倍", "G3": "G3 そろいの点数の順位で 0.5〜1.0 倍"}
    for k in ("G1", "G2", "G3"):
        v = comp(k); vs = {w: stats(v, a, b) for w, a, b in WIN}
        rows.append(dict(cell=LAB[k], mean_size=round(float(np.mean(fac(P, k))), 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), improved=bool(all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN))))
    D = pd.DataFrame(rows); D.to_csv("results/q227_mon4_decline_x_vix_score.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q227: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print("基準(配備形):", bs, " 平均の倍率", round(float(P.base.mean()), 3)); print(D.to_string(index=False))
    quant = []
    for c, lab in (("p_sum", "合計の点数"), ("p_and", "そろいの点数")):
        for w, a, b in WIN:
            x = P[(P.index >= a) & (P.index <= b)].dropna(subset=[c])
            if len(x) < 50: continue
            x = x.assign(q=pd.cut(x[c], [0, 0.2, 0.4, 0.6, 0.8, 1.0001], labels=["下位 20%", "20〜40%", "40〜60%", "60〜80%", "上位 20%"], include_lowest=True)); rho, pv = sps.spearmanr(x[c], x.r)
            for ql, y in x.groupby("q"): quant.append(dict(score=lab, window=w, bucket=ql, n=len(y), mean_bps=round(float(y.r.mean()) * 1e4, 2) if len(y) else None, win=round(float((y.r > 0).mean()) * 100, 1) if len(y) else None, sd_bps=round(float(y.r.std()) * 1e4, 1) if len(y) > 1 else None))
            quant.append(dict(score=lab, window=w, bucket="順位相関(rho / p)", n=len(x), mean_bps=round(float(rho), 3), win=round(float(pv), 4), sd_bps=None))
    Q = pd.DataFrame(quant); Q.to_csv("results/q227_mon4_decline_x_vix_score_quant.csv", index=False); print("\n== 数値化 (i): 点数の順位ごとの月曜(通貨 × 月曜・1 倍あたり。順位相関の行は mean_bps = rho・win = p) =="); print(Q.to_string(index=False))
    grid = []; LB = [("線の上", lambda d: d >= 0), ("線の下 0〜3%", lambda d: (d < 0) & (d >= -0.03)), ("線の下 3% 超", lambda d: d < -0.03)]; VB = [("VIX 15 未満", 0, 15), ("15〜20", 15, 20), ("20〜25", 20, 25), ("25 超", 25, 999)]
    for w, a, b in WIN + (("全期間", PRE0, END),):
        x = P[(P.index >= a) & (P.index <= b)].dropna(subset=["d200", "vix"])
        for ln, lf in LB:
            for vn, lo, hi in VB:
                y = x[lf(x.d200) & (x.vix >= lo) & (x.vix < hi)].r; grid.append(dict(window=w, line=ln, vix=vn, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None))
    Gd = pd.DataFrame(grid); Gd.to_csv("results/q227_mon4_decline_x_vix_score_grid.csv", index=False); print("\n== 数値化 (ii): 線からの位置 × VIX の表(平均 bps / 回数) ==")
    for w in ("前窓", "IS", "OOS", "全期間"):
        g = Gd[Gd.window == w]; print(f"-- {w} --"); print((g.pivot(index="line", columns="vix", values="mean_bps").reindex([l[0] for l in LB])[[v[0] for v in VB]].astype(str) + " (" + g.pivot(index="line", columns="vix", values="n").reindex([l[0] for l in LB])[[v[0] for v in VB]].astype(str) + ")").to_string())
