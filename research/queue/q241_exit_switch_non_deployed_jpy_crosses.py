# -*- coding: utf-8 -*-
"""docs/244 Q241(改良系・12 セル・2026-11-16 登録): 決済の切り替え(E1・G1・G3)を、採用していない円クロス 3 本(NZDJPY・CADJPY・CHFJPY)とその等分の束で確かめる。
月曜 4/6/8/10 UTC 建て・200 日線の下 1.0 倍・上 0.5 倍。E1 = 前金曜の VIX > 25 の週だけ 24h・それ以外は同日 20 UTC。G1 = 週末の窓(金曜の最終足 → 月曜 04 UTC)が自分の過去の下位 20% の通貨だけ 24h。G3 = VIX > 25 または G1。
判定 = その系列の「常に 24h」に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。定義は Q232・Q240 と同じ。
使い方: cd research && python3 -W ignore queue/q241_exit_switch_non_deployed_jpy_crosses.py <累積セル数>   出力: results/q241_exit_switch_non_deployed_jpy_crosses.csv・_parts.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import states
from q237_night_leg_after_high_vix import VIX, TH
from q240_weekend_premium_predictions import wk_signals, Q, HOURS
import deployed_book as db
EXTRA = ["NZDJPY", "CADJPY", "CHFJPY"]; PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
def frame(syms=EXTRA):
    """q238.fx_frame と同じ作り(通貨 × 月曜: r24・r20・rN・f・vix・hot)に、週末の窓の順位(G1)を付ける。"""
    rows = []
    for s in syms:
        h = load(s); o = h["open"]; acc = {}
        for hh in HOURS:
            t = o.index[(o.index.dayofweek == 0) & (o.index.hour == hh)]; ok = (t + pd.Timedelta(hours=24)).isin(o.index); t = t[ok]; p0 = o.reindex(t).values; c = cost(s, p0)
            p24 = o.reindex(t + pd.Timedelta(hours=24)).values; p20 = o.reindex(t.normalize() + pd.Timedelta(hours=20)).values; r24 = p24 / p0 - 1 - c
            d = pd.DataFrame({"r24": r24, "r20": np.where(np.isnan(p20), r24, p20 / p0 - 1 - c), "rN": np.where(np.isnan(p20), r24, p24 / p20 - 1 - c)}, index=t.normalize())
            for k in d.columns: acc[k] = d[k] if k not in acc else acc[k].add(d[k], fill_value=0.0)
        m = pd.DataFrame({k: v / len(HOURS) for k, v in acc.items()}).sort_index(); m = m[(m.index >= PRE0) & (m.index <= h.index.max())]; assert np.allclose(m.r24.values, db.mon_cell_h1(s).reindex(m.index).values, atol=1e-12), s
        d200 = states(s).shift(1).reindex(m.index, method="ffill").sma200.values; m["sym"] = s; m["f"] = np.where(np.isnan(d200), 1.0, np.where(d200 < 0, 1.0, 0.5)); m["vix"] = VIX.reindex(pd.DatetimeIndex(m.index) - pd.Timedelta(days=3), method="ffill").values
        S = wk_signals(s); m["rg"] = S.rg.reindex(m.index).values; rows.append(m)
    P = pd.concat(rows).sort_index(kind="stable"); P["hot"] = (P.vix > TH).fillna(False); P["G1"] = (P.rg <= Q).fillna(False); return P
def hold_mask(P, kind): return {"base": np.ones(len(P), bool), "E1": P.hot.values, "G1": P.G1.values, "G3": P.hot.values | P.G1.values}[kind]
def series(P, kind, sym=None):
    """sym = 通貨名ならその 1 本(数量 1.0)、None なら P にある通貨の等分の束。index = 月曜。"""
    X = P if sym is None else P[P.sym == sym]; w = 1.0 / X.sym.nunique(); return pd.Series(np.where(hold_mask(X, kind), X.r24, X.r20) * X.f.values * w, index=X.index).groupby(level=0).sum()
def extra3_exit(kind="E1"):
    """紙上候補用: 採用していない円クロス 3 本等分の束。"""
    return series(frame(), kind)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 12; P = frame(); rows = []; parts = []; LAB = {"E1": "E1 VIX > 25 の週だけ 24h", "G1": "G1 週末に安く始まった通貨だけ 24h", "G3": "G3 VIX > 25 または G1"}
    for sym in EXTRA + [None]:
        b = series(P, "base", sym); bs = {w: stats(b, a, e) for w, a, e in WIN}; X = P if sym is None else P[P.sym == sym]
        for k in ("E1", "G1", "G3"):
            v = series(P, k, sym); vs = {w: stats(v, a, e) for w, a, e in WIN}
            rows.append(dict(series=(sym or "3 本等分の束"), cell=LAB[k], end=str(X.index.max().date()), share=round(float(hold_mask(X, k).mean()), 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), verdict=("成立" if all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN) else "不成立")))
    D = pd.DataFrame(rows); D.to_csv("results/q241_exit_switch_non_deployed_jpy_crosses.csv", index=False)
    def add(grp, x, w):
        for col, nm in (("rN", "夜の部分"), ("r20", "日中"), ("r24", "24h")):
            y = x[col].dropna(); wk = y.groupby(level=0).mean(); parts.append(dict(part=nm, group=grp, window=w, n=len(y), weeks=len(wk), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None, t_week=round(float(wk.mean() / wk.std() * np.sqrt(len(wk))), 2) if len(wk) > 2 and wk.std() > 0 else None))
    hot = P.hot; G = [("全部", pd.Series(True, index=P.index)), ("VIX > 25", hot), ("VIX ≤ 25", ~hot), ("窓 下位 20%", P.G1), ("窓 下位 20% 以外", ~P.G1 & P.rg.notna()), ("VIX > 25 かつ 窓 下位 20%", hot & P.G1), ("VIX > 25 かつ 窓 下位 20% 以外", hot & ~P.G1 & P.rg.notna()), ("VIX ≤ 25 かつ 窓 下位 20%", ~hot & P.G1), ("VIX ≤ 25 かつ 窓 下位 20% 以外", ~hot & ~P.G1 & P.rg.notna())]
    for gn, m in G:
        for w, a, e in ALLW: add(gn, P[m.values][(P.index[m.values] >= a) & (P.index[m.values] <= e)], w)
    T = pd.DataFrame(parts); T.to_csv("results/q241_exit_switch_non_deployed_jpy_crosses_parts.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 60)
    print(f"Q241: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N} sharpe_up_3win={int(D.sharpe_up_3win.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print(D.to_string(index=False))
    for pn in ("夜の部分", "日中", "24h"):
        g = T[T.part == pn]; pv = g.pivot(index="group", columns="window", values="mean_bps").reindex(g.group.unique())[[w for w, _, _ in ALLW]]; al = g[g.window == "全期間"].set_index("group"); pv["n"] = al.n; pv["weeks"] = al.weeks; pv["win%"] = al.win; pv["t_week"] = al.t_week; print(f"\n== 3 本まとめ・{pn}(コスト込み・平均 bps) =="); print(pv.to_string())
