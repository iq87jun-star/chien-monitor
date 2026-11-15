# -*- coding: utf-8 -*-
"""docs/244 Q228(改良系・3 セル・2026-11-15 登録): 水曜ロール(Roll5・金利差門 2.0pp)× VIX、200 日線との掛け合わせ。
ベース = Q205 と同じ(水曜 20:00 UTC → 木曜 00:00 UTC・円クロス 5 本 SHORT・5 本等分・門 2.0pp・往復 3pip)。VIX = 建て日の前日(火曜)の終値。
V25: VIX > 25 の週 1.0 倍・それ以外 0.5 倍。G1: 0.5 + 0.5 p(合計の点数)。G3: 0.5 + 0.5 p(そろいの点数)。点数は Q227 と同じ作り方(先読みなし)。履歴不足は 1.0 倍。
判定 = ベースに対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。
使い方: cd research && python3 -W ignore queue/q228_roll5_vix_x_sma200_score.py <累積セル数>   出力: results/q228_roll5_vix_x_sma200_score.csv・_vix.csv・_grid.csv・_quant.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q20_wed_swap_carry import rate_series
from q147_roll_rate_diff_gate import stats
from q205_roll5_sma200_state import PAIRS, GATE, leg, bars
from scipy import stats as sps
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
V = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data_ext", "VIX_History.csv")); V["d"] = pd.to_datetime(V["DATE"]); VIX = V.set_index("d")["CLOSE"].sort_index().astype(float)
VZ = ((VIX - VIX.expanding(min_periods=252).mean().shift(1)) / VIX.expanding(min_periods=252).std().shift(1))          # その日より前の VIX だけで標準化
def d200(sym, dates):
    """建て日より前の最後の確定日足の 終値 / SMA200 − 1(Q205 の below200 と同じ日足)。"""
    c = bars(sym)["close"]; d = (c.index + pd.Timedelta(hours=2)).normalize(); x = c.groupby(d).last(); x = x[x.index.dayofweek < 5]
    return (x / x.rolling(200).mean() - 1).shift(1).reindex(pd.DatetimeIndex(dates), method="ffill")
def frame():
    L = {s: leg(s) for s in PAIRS}; days = pd.DatetimeIndex(sorted(set().union(*[set(L[s].index) for s in PAIRS]))); jp = rate_series("JPY", days); tue = days - pd.Timedelta(days=1); rows = []
    vix = pd.Series(VIX.reindex(tue, method="ffill").values, index=days); vz = pd.Series(VZ.reindex(tue, method="ffill").values, index=days)
    vix[days > VIX.index.max() + pd.Timedelta(days=1)] = np.nan; vz[days > VIX.index.max() + pd.Timedelta(days=1)] = np.nan          # VIX の無い週は使わない
    for s in PAIRS:
        g = (rate_series(s[:3], days) - jp >= GATE); dd = d200(s, days); x1 = -dd; z1 = (x1 - x1.expanding(min_periods=52).mean().shift(1)) / x1.expanding(min_periods=52).std().shift(1)        # その通貨の、それ以前の水曜の値だけで標準化
        r = L[s]; rows.append(pd.DataFrame({"r": r.values, "sym": s, "g": pd.Series(np.asarray(g, bool), index=days).reindex(r.index).values, "d200": dd.reindex(r.index).values, "vix": vix.reindex(r.index).values, "z1": z1.reindex(r.index).values, "z2": vz.reindex(r.index).values}, index=r.index))
    P = pd.concat(rows).sort_index(kind="stable"); P["s_sum"] = P.z1 + P.z2; P["s_and"] = P[["z1", "z2"]].min(axis=1); P.loc[P.z1.isna() | P.z2.isna(), ["s_sum", "s_and"]] = np.nan
    for c in ("s_sum", "s_and"):
        p = np.full(len(P), np.nan); dates = P.index.values; vals = P[c].values; hist = []
        for d in np.unique(dates):          # 日付ごと: それより前の点数だけで順位を付ける(門に関係なく全週)
            ii = np.where(dates == d)[0]
            if len(hist) >= 200:
                H = np.sort(np.array(hist)); p[ii] = [np.searchsorted(H, v, side="right") / len(H) if v == v else np.nan for v in vals[ii]]
            hist += [v for v in vals[ii] if v == v]
        P["p_" + c[2:]] = p
    return P, days
def fac(P, kind):
    if kind == "base": return np.ones(len(P))
    if kind == "V25": return np.where(P.vix.isna(), 1.0, np.where(P.vix > 25, 1.0, 0.5))
    p = P["p_sum"].values if kind == "G1" else P["p_and"].values; return np.where(np.isnan(p), 1.0, 0.5 + 0.5 * p)
def roll5_score(kind="G1"):
    """紙上候補用: Roll5(門 2.0pp)に Q228 の倍率を掛けた系列。index = 建て日(水曜)。"""
    P, days = frame(); return (P.r * P.g.astype(float) * fac(P, kind)).groupby(level=0).sum().reindex(days).fillna(0.0) / len(PAIRS)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 3; P, days = frame()
    def comp(k): return (P.r * P.g.astype(float) * fac(P, k)).groupby(level=0).sum().reindex(days).fillna(0.0) / len(PAIRS)
    B = comp("base"); bs = {w: stats(B, a, b) for w, a, b in WIN}; rows = []
    LAB = {"V25": "V25 火曜の VIX が 25 超の週 1.0 倍・それ以外 0.5 倍", "G1": "G1 合計の点数の順位で 0.5〜1.0 倍", "G3": "G3 そろいの点数の順位で 0.5〜1.0 倍"}
    for k in ("V25", "G1", "G3"):
        v = comp(k); vs = {w: stats(v, a, b) for w, a, b in WIN}; gg = P.g.values.astype(bool)
        rows.append(dict(cell=LAB[k], mean_size_gated=round(float(np.mean(fac(P, k)[gg])), 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), improved=bool(all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN))))
    D = pd.DataFrame(rows); D.to_csv("results/q228_roll5_vix_x_sma200_score.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 400)
    print(f"Q228: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  データ末尾 {days.max().date()}・VIX 末尾 {VIX.index.max().date()}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print("基準(全週 1.0 倍):", bs); print(D.to_string(index=False))
    VB = [("VIX 15 未満", 0, 15), ("15〜20", 15, 20), ("20〜25", 20, 25), ("25 超", 25, 999)]; ALLW = WIN + (("全期間", PRE0, END),); vx = []
    for gl, gated in (("門 2.0pp あり", True), ("門なし", False)):
        X = P[(P.g | (not gated))].dropna(subset=["vix"])
        for w, a, b in ALLW:
            x = X[(X.index >= a) & (X.index <= b)]
            for vn, lo, hi in VB:
                y = x[(x.vix >= lo) & (x.vix < hi)].r; wk = y.groupby(level=0).sum() / len(PAIRS)
                vx.append(dict(gate=gl, window=w, vix=vn, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 2) if len(y) else None, win=round(float((y > 0).mean()) * 100, 1) if len(y) else None, sd_bps=round(float(y.std()) * 1e4, 1) if len(y) > 1 else None,
                               weeks=len(wk), week_mean_bps=round(float(wk.mean()) * 1e4, 2) if len(wk) else None, week_sd_bps=round(float(wk.std()) * 1e4, 2) if len(wk) > 1 else None, week_t=round(float(wk.mean() / wk.std() * np.sqrt(len(wk))), 2) if len(wk) > 2 and wk.std() > 0 else None))
    VX = pd.DataFrame(vx); VX.to_csv("results/q228_roll5_vix_x_sma200_score_vix.csv", index=False); print("\n== 数値化 (i): 火曜の VIX ごとのロール(本ごと・コスト後。week_* は 5 本合計 ÷ 5 の週単位) =="); print(VX.to_string(index=False))
    grid = []; LB = [("線の上", lambda d: d >= 0), ("線の下 0〜3%", lambda d: (d < 0) & (d >= -0.03)), ("線の下 3% 超", lambda d: d < -0.03)]
    for gl, gated in (("門 2.0pp あり", True), ("門なし", False)):
        X = P[(P.g | (not gated))].dropna(subset=["d200", "vix"])
        for w, a, b in ALLW:
            x = X[(X.index >= a) & (X.index <= b)]
            for ln, lf in LB:
                for vn, lo, hi in VB:
                    y = x[lf(x.d200) & (x.vix >= lo) & (x.vix < hi)].r; grid.append(dict(gate=gl, window=w, line=ln, vix=vn, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None, sd_bps=round(float(y.std()) * 1e4, 1) if len(y) > 1 else None))
    Gd = pd.DataFrame(grid); Gd.to_csv("results/q228_roll5_vix_x_sma200_score_grid.csv", index=False); print("\n== 数値化 (ii): 線からの位置 × VIX の表(平均 bps (本数)) ==")
    for gl in ("門 2.0pp あり", "門なし"):
        for w in ("前窓", "IS", "OOS", "全期間"):
            g = Gd[(Gd.window == w) & (Gd.gate == gl)]; print(f"-- {gl}・{w} --"); print((g.pivot(index="line", columns="vix", values="mean_bps").reindex([l[0] for l in LB])[[v[0] for v in VB]].astype(str) + " (" + g.pivot(index="line", columns="vix", values="n").reindex([l[0] for l in LB])[[v[0] for v in VB]].astype(str) + ")").to_string())
    quant = []
    for gl, gated in (("門 2.0pp あり", True), ("門なし", False)):
        for c, lab in (("p_sum", "合計の点数"), ("p_and", "そろいの点数")):
            for w, a, b in ALLW:
                x = P[(P.g | (not gated)) & (P.index >= a) & (P.index <= b)].dropna(subset=[c])
                if len(x) < 50: continue
                x = x.assign(q=pd.cut(x[c], [0, 0.2, 0.4, 0.6, 0.8, 1.0001], labels=["下位 20%", "20〜40%", "40〜60%", "60〜80%", "上位 20%"], include_lowest=True)); rho, pv = sps.spearmanr(x[c], x.r)
                for ql, y in x.groupby("q", observed=False): quant.append(dict(gate=gl, score=lab, window=w, bucket=ql, n=len(y), mean_bps=round(float(y.r.mean()) * 1e4, 2) if len(y) else None, win=round(float((y.r > 0).mean()) * 100, 1) if len(y) else None, sd_bps=round(float(y.r.std()) * 1e4, 1) if len(y) > 1 else None))
                quant.append(dict(gate=gl, score=lab, window=w, bucket="順位相関(rho / p)", n=len(x), mean_bps=round(float(rho), 3), win=round(float(pv), 4), sd_bps=None))
    Q = pd.DataFrame(quant); Q.to_csv("results/q228_roll5_vix_x_sma200_score_quant.csv", index=False); print("\n== 数値化 (iii): 点数の順位ごとのロール(通貨 × 水曜。順位相関の行は mean_bps = rho・win = p) =="); print(Q.to_string(index=False))
