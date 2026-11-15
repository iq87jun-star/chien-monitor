# -*- coding: utf-8 -*-
"""docs/244 Q232(改良系・5 セル・2026-11-15 登録「登録して実行」): 月曜の円クロスの決済の切り替え(同日 20 UTC か 24 時間後か)を VIX・他の移動平均線で行う。
数量は配備形のまま(SMA200 の下 1.0 倍・上 0.5 倍)。E1 = 前金曜 VIX ≤ 25 の週は全通貨 20 UTC・25 超は 24h。E2 = 24h は SMA200 の下 かつ VIX > 25 の通貨だけ。E3 / E4 / E5 = EMA50 / SMA50 / SMA100 の上は 20 UTC・下は 24h。
判定 = Q229 の M3(SMA200 の上だけ 20 UTC)に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。配備形(全通貨 24h)との比較を併記。
使い方: cd research && python3 -W ignore queue/q232_mon4_exit_switch_vix_other_ma.py <累積セル数>   出力: results/q232_mon4_exit_switch_vix_other_ma.csv・_ref.csv・_night.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q216_mon4_ema_state import dist
from q229_state_dependent_exit import mon_frame, MON_PAIRS
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
def frame():
    P = mon_frame()
    for nm, n, kind in (("ema50", 50, "ema"), ("sma50", 50, "sma"), ("sma100", 100, "sma")):
        P[nm] = np.nan
        for s in MON_PAIRS: m = (P.sym == s).values; P.loc[m, nm] = dist(s, n, P.index[m], kind).values
    return P
def hold_mask(P, kind):
    """True = 24 時間持つ、False = 同日 20 UTC に決済。"""
    hot = lambda th: (P.vix > th).fillna(False).values
    if kind == "base": return np.ones(len(P), bool)
    if kind == "M3": return ~P.above.values
    if kind == "E1": return hot(25)
    if kind == "E2": return P.below.values & hot(25)
    if kind in ("E3", "E4", "E5"): d = P[{"E3": "ema50", "E4": "sma50", "E5": "sma100"}[kind]]; return ~(d >= 0).fillna(False).values
    if kind == "OR": return (~P.above.values) | hot(25)
    if kind in ("V20", "V30"): return hot(int(kind[1:]))
    raise ValueError(kind)
def series(P, kind): h = hold_mask(P, kind); return pd.Series(np.where(h, P.r24, P.r20) * P.f.values * 0.25, index=P.index).groupby(level=0).sum()
def mon4_exit_switch(kind="E1"):
    """紙上候補用。index = 月曜。"""
    return series(frame(), kind)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 5; P = frame(); B0 = series(P, "base"); M3 = series(P, "M3"); b0 = {w: stats(B0, a, b) for w, a, b in WIN}; m3 = {w: stats(M3, a, b) for w, a, b in WIN}; rows = []; ref = []
    LAB = {"E1": "E1 VIX ≤ 25 の週は全通貨 20 UTC・25 超は 24h", "E2": "E2 24h は 200 日線の下 かつ VIX > 25 だけ", "E3": "E3 EMA50 の上は 20 UTC・下は 24h", "E4": "E4 50 日線の上は 20 UTC・下は 24h", "E5": "E5 100 日線の上は 20 UTC・下は 24h"}
    for k in ("E1", "E2", "E3", "E4", "E5"):
        v = series(P, k); vs = {w: stats(v, a, b) for w, a, b in WIN}
        rows.append(dict(cell=LAB[k], share_24h=round(float(hold_mask(P, k).mean()), 3), deployed_PRE=b0["前窓"], M3_PRE=m3["前窓"], var_PRE=vs["前窓"], deployed_IS=b0["IS"], M3_IS=m3["IS"], var_IS=vs["IS"], deployed_OOS=b0["OOS"], M3_OOS=m3["OOS"], var_OOS=vs["OOS"],
                         beats_deployed=bool(all(vs[w][0] > b0[w][0] and vs[w][1] >= b0[w][1] for w, _, _ in WIN)), improved_vs_M3=bool(all(vs[w][0] > m3[w][0] and vs[w][1] >= m3[w][1] for w, _, _ in WIN))))
    D = pd.DataFrame(rows); D.to_csv("results/q232_mon4_exit_switch_vix_other_ma.csv", index=False); pd.set_option("display.width", 360); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300); pd.set_option("display.max_colwidth", 70)
    print(f"Q232: cells={N} cum_before={cum} cum_after={cum + N} improved_vs_M3={int(D.improved_vs_M3.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print("配備形(全通貨 24h):", b0, " share_24h 1.0"); print("M3(200 日線の上だけ 20 UTC):", m3, " share_24h", round(float(hold_mask(P, "M3").mean()), 3)); print(D.to_string(index=False))
    for k, nm in (("OR", "24h は 200 日線の下 または VIX > 25"), ("V20", "VIX ≤ 20 の週は全通貨 20 UTC"), ("V30", "VIX ≤ 30 の週は全通貨 20 UTC"), ("base", "全通貨 24h(配備形)"), ("M3", "200 日線の上だけ 20 UTC(M3)")):
        v = series(P, k); ref.append(dict(variant=nm, share_24h=round(float(hold_mask(P, k).mean()), 3), PRE=stats(v, *WIN[0][1:]), IS=stats(v, *WIN[1][1:]), OOS=stats(v, *WIN[2][1:])))
    v = pd.Series(P.r20.values * P.f.values * 0.25, index=P.index).groupby(level=0).sum(); ref.append(dict(variant="全通貨 20 UTC", share_24h=0.0, PRE=stats(v, *WIN[0][1:]), IS=stats(v, *WIN[1][1:]), OOS=stats(v, *WIN[2][1:])))
    RF = pd.DataFrame(ref); RF.to_csv("results/q232_mon4_exit_switch_vix_other_ma_ref.csv", index=False); print("\n== 参照(判定に使わない) ==\n" + RF.to_string(index=False))
    ng = []; X = P.dropna(subset=["segN", "vix"])
    G = [("VIX 15 未満", X.vix < 15), ("VIX 15〜20", (X.vix >= 15) & (X.vix < 20)), ("VIX 20〜25", (X.vix >= 20) & (X.vix < 25)), ("VIX 25 超", X.vix >= 25), ("VIX 25 以下", X.vix < 25), ("200 日線の上", X.above), ("200 日線の下", X.below), ("EMA50 の上", X.ema50 >= 0), ("EMA50 の下", X.ema50 < 0), ("50 日線の上", X.sma50 >= 0), ("50 日線の下", X.sma50 < 0), ("100 日線の上", X.sma100 >= 0), ("100 日線の下", X.sma100 < 0),
         ("200 日線の下 × VIX 25 超", X.below & (X.vix >= 25)), ("200 日線の下 × VIX 25 以下", X.below & (X.vix < 25)), ("200 日線の上 × VIX 25 超", X.above & (X.vix >= 25)), ("200 日線の上 × VIX 25 以下", X.above & (X.vix < 25))]
    for gn, m in G:
        for w, a, b in ALLW:
            y = X[m.values & (X.index >= a) & (X.index <= b)].segN; ng.append(dict(group=gn, window=w, n=len(y), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, sd_bps=round(float(y.std()) * 1e4, 1) if len(y) > 1 else None, t=round(float(y.mean() / y.std() * np.sqrt(len(y))), 2) if len(y) > 2 and y.std() > 0 else None))
    NG = pd.DataFrame(ng); NG.to_csv("results/q232_mon4_exit_switch_vix_other_ma_night.csv", index=False); print("\n== 夜の部分(月曜 20 UTC → 建ての 24h 後・買い・コストなし)の平均 bps (本数) / 全期間の t ==")
    pv = (NG.pivot(index="group", columns="window", values="mean_bps").reindex([g[0] for g in G])[[w[0] for w in ALLW]].astype(str) + " (" + NG.pivot(index="group", columns="window", values="n").reindex([g[0] for g in G])[[w[0] for w in ALLW]].astype(str) + ")"); pv["t(全期間)"] = NG[NG.window == "全期間"].set_index("group").t.reindex([g[0] for g in G]).values; print(pv.to_string())
