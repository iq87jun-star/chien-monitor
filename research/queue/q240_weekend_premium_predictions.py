# -*- coding: utf-8 -*-
"""docs/244 Q240(改良系・5 セル・2026-11-16 登録「登録して実行」): 「週末の対価」という読みから出る予想の検証。数量は配備形 Mon4 のまま。当てはまる通貨だけ 24h・それ以外は同日 20 UTC 決済。
窓 = その通貨の金曜の最終足の終値 → 月曜 04 UTC の始値。G1 = 窓が自分の過去の下位 20%。G2 = |窓| が自分の過去の上位 20%。G3 = VIX > 25 または G1。F1 = 金曜 12 UTC の始値 → 金曜の最終足の終値が自分の過去の下位 20%。
順位はその通貨のそれ以前の週だけ(52 週未満・金曜休場は「当てはまらない」)。H1 = 月曜の指数 3 本等分(US500・NAS100・US30・13 UTC・24h)に、NYSE が月曜休場の週だけ火曜 13 UTC・24h を同じ数量で足す。
判定 = 基準(G・F は配備形 Mon4、H1 は月曜の指数 3 本等分)に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。G・F は E1 を 3 窓の Sharpe で上回るかを併記。
使い方: cd research && python3 -W ignore queue/q240_weekend_premium_predictions.py <累積セル数>   出力: results/q240_weekend_premium_predictions.csv・_parts.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q114_mon_index_intraday import shot
from q238_late_entry_after_high_vix_and_short_nights import fx_frame, MON4, HOURS
from q237_night_leg_after_high_vix import VIX, TH
from q173_skew_vvix_gate import PR
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),); IDX3 = ["US500", "NAS100", "US30"]; D1 = pd.Timedelta(days=1); Q = 0.2
_H = pd.read_csv("data_ext/holidays_us_uk_au_nz_2016_2027.csv"); _H["date"] = pd.to_datetime(_H["date"]); NYSE_MON = set(d for d in _H[_H.cal == "NYSE"].date if d.dayofweek == 0)
_J = pd.read_csv("data_ext/jp_holidays_2016_2026.csv"); JP_MON = set(d for d in pd.to_datetime(_J.iloc[:, 0]) if d.dayofweek == 0)
def past_rank(x):
    """それ以前の値だけでの順位(その値以下だった過去の割合)。過去が 52 未満・値なしは NaN。"""
    v = np.asarray(x, float); out = np.full(len(v), np.nan); hist = []
    for i, a in enumerate(v):
        if a == a:
            if len(hist) >= 52: out[i] = np.searchsorted(np.sort(hist), a, side="right") / len(hist)
            hist.append(a)
    return out
def wk_signals(sym):
    """月曜ごと: gap = 金曜の最終足の終値 → 月曜 04 UTC、pm = 金曜 12 UTC → 金曜の最終足、gap0 = 金曜の最終足 → 週明け最初の足、am = 週明け最初の足 → 月曜 04 UTC。rg・ra・rp = gap・|gap|・pm の過去だけの順位。"""
    h = load(sym); o = h["open"]; c = h["close"]; mon = pd.DatetimeIndex(sorted(set(o.index[(o.index.dayofweek == 0) & (o.index.hour == 4)].normalize())))
    f = c[c.index.dayofweek == 4]; fl = f.groupby(f.index.normalize()).last(); fc = fl.reindex(mon - 3 * D1).values; f12 = o.reindex(mon - 3 * D1 + pd.Timedelta(hours=12)).values; m4 = o.reindex(mon + pd.Timedelta(hours=4)).values
    i0 = o.index.searchsorted(mon - D1); s0 = o.values[np.minimum(i0, len(o) - 1)]
    x = pd.DataFrame({"gap": m4 / fc - 1, "pm": fc / f12 - 1, "gap0": s0 / fc - 1, "am": m4 / s0 - 1}, index=mon); x["rg"] = past_rank(x.gap); x["ra"] = past_rank(x.gap.abs()); x["rp"] = past_rank(x.pm); return x
def frame():
    P = fx_frame().copy(); cols = ("gap", "pm", "gap0", "am", "rg", "ra", "rp")
    for k in cols: P[k] = np.nan
    for s in MON4:
        S = wk_signals(s); m = (P.sym == s).values
        for k in cols: P.loc[m, k] = S[k].reindex(P.index[m]).values
    d = pd.DatetimeIndex(P.index); P["vix_thu"] = VIX.reindex(d - 4 * D1, method="ffill").values; P["skew_hi"] = (PR["SKEW"].reindex(d - 3 * D1, method="ffill").values > 0.8)
    P["G1"] = (P.rg <= Q).fillna(False); P["G2"] = (P.ra >= 1 - Q).fillna(False); P["F1"] = (P.rp <= Q).fillna(False); return P
def hold_mask(P, kind):
    return {"base": np.ones(len(P), bool), "E1": P.hot.values, "G1": P.G1.values, "G2": P.G2.values, "G3": P.hot.values | P.G1.values, "F1": P.F1.values}[kind]
def series(P, kind): return pd.Series(np.where(hold_mask(P, kind), P.r24, P.r20) * P.f.values * 0.25, index=P.index).groupby(level=0).sum()
def idx_shot(sym, dow):
    """指数の 13 UTC 建て 24h(コスト後)。index = その週の月曜。"""
    o = load(sym)["open"]; t = o.index[(o.index.dayofweek == dow) & (o.index.hour == 13)]; r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + D1).values); r.index = r.index.normalize() - dow * D1; return r
def idx_series(kind="base"):
    out = None; start = None
    for s in IDX3:
        b = idx_shot(s, 0); assert np.allclose(b.values, shot(s, 13, None).values, atol=1e-12), s; start = b.index.min() if start is None else max(start, b.index.min())
        if kind == "H1": tu = idx_shot(s, 1); b = b.add(tu[tu.index.isin(NYSE_MON)], fill_value=0.0)
        out = b / len(IDX3) if out is None else out.add(b / len(IDX3), fill_value=0.0)
    start = max(start, PRE0); return out[out.index >= start].sort_index(), start
def weekend_premium(kind="G1"):
    """紙上候補用。G1・G2・G3・F1 = 円クロス(index = 月曜)、H1 = 指数 3 本等分。"""
    return idx_series("H1")[0] if kind == "H1" else series(frame(), kind)
def fx_tue(sym):
    """円クロスの火曜 4 ショット(4/6/8/10 UTC・24h・コスト後・平均)。index = その週の月曜。"""
    o = load(sym)["open"]; acc = None
    for hh in HOURS:
        t = o.index[(o.index.dayofweek == 1) & (o.index.hour == hh)]; r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + D1).values); r.index = r.index.normalize() - D1; acc = r if acc is None else acc.add(r, fill_value=0.0)
    return acc / len(HOURS)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 5; P = frame(); B = series(P, "base"); E1 = series(P, "E1"); bs = {w: stats(B, a, b) for w, a, b in WIN}; es = {w: stats(E1, a, b) for w, a, b in WIN}; rows = []; parts = []
    LAB = {"G1": "G1 週末の窓が自分の過去の下位 20%(安く始まった)通貨だけ 24h", "G2": "G2 週末の窓の絶対値が自分の過去の上位 20% の通貨だけ 24h", "G3": "G3 VIX > 25 または G1 のとき 24h", "F1": "F1 金曜の午後(12 UTC → 最終足)が自分の過去の下位 20% の通貨だけ 24h"}
    for k in ("G1", "G2", "G3", "F1"):
        v = series(P, k); vs = {w: stats(v, a, b) for w, a, b in WIN}
        rows.append(dict(cell=LAB[k], share=round(float(hold_mask(P, k).mean()), 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], verdict=("成立" if all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN) else "不成立"), beats_E1_sharpe_3win=bool(all(vs[w][0] > es[w][0] for w, _, _ in WIN))))
    IB, s0 = idx_series("base"); IH, _ = idx_series("H1"); ib = {w: stats(IB, max(a, s0), b) for w, a, b in WIN}; ih = {w: stats(IH, max(a, s0), b) for w, a, b in WIN}; nh = int((IH.reindex(IB.index.union(IH.index)).fillna(0) != IB.reindex(IB.index.union(IH.index)).fillna(0)).sum())
    rows.append(dict(cell=f"H1 月曜の指数 3 本等分 + NYSE 月曜休場の週の火曜 13 UTC・24h({s0.date()}〜・足した週 {nh})", share=round(nh / len(IB), 3), base_PRE=ib["前窓"], var_PRE=ih["前窓"], base_IS=ib["IS"], var_IS=ih["IS"], base_OOS=ib["OOS"], var_OOS=ih["OOS"], verdict=("成立" if all(ih[w][0] > ib[w][0] and ih[w][1] >= ib[w][1] for w, _, _ in WIN) else "不成立"), beats_E1_sharpe_3win=None))
    D = pd.DataFrame(rows); D.to_csv("results/q240_weekend_premium_predictions.csv", index=False)
    def add(tab, grp, y, w):
        """y = 値の Series(index = 月曜)。t は週ごとの平均で計算(同じ週の通貨は 1 つに数える)。"""
        y = y.dropna(); wk = y.groupby(level=0).mean(); parts.append(dict(table=tab, group=grp, window=w, n=len(y), weeks=len(wk), mean_bps=round(float(y.mean()) * 1e4, 1) if len(y) else None, win=round(float((y > 0).mean()) * 100, 0) if len(y) else None, t_week=round(float(wk.mean() / wk.std() * np.sqrt(len(wk))), 2) if len(wk) > 2 and wk.std() > 0 else None))
    def cut(P, a, b): return P[(P.index >= a) & (P.index <= b)]
    hot = P.hot; G = [("窓 下位 20%(安く始まった)", P.G1), ("窓 中間", (P.rg > Q) & (P.rg < 1 - Q)), ("窓 上位 20%(高く始まった)", (P.rg >= 1 - Q).fillna(False)), ("|窓| 上位 20%", P.G2), ("|窓| それ以外", P.ra < 1 - Q),
         ("金曜午後 下位 20%(売られた)", P.F1), ("金曜午後 中間", (P.rp > Q) & (P.rp < 1 - Q)), ("金曜午後 上位 20%(買われた)", (P.rp >= 1 - Q).fillna(False)),
         ("VIX > 25 かつ 窓 下位 20%", hot & P.G1), ("VIX > 25 かつ 窓 下位 20% 以外", hot & ~P.G1 & P.rg.notna()), ("VIX ≤ 25 かつ 窓 下位 20%", ~hot & P.G1), ("VIX ≤ 25 かつ 窓 下位 20% 以外", ~hot & ~P.G1 & P.rg.notna()),
         ("VIX > 25 かつ 金曜午後 下位 20%", hot & P.F1), ("VIX ≤ 25 かつ 金曜午後 下位 20%", ~hot & P.F1)]
    for gn, m in G:
        for w, a, b in ALLW:
            x = cut(P[m.values], a, b)
            for col, nm in (("rN", "(i) 夜の部分"), ("r20", "(i) 日中"), ("r24", "(i) 24h")): add(nm, gn, x[col], w)
    hot_thu = (P.vix_thu > TH).fillna(False)          # (ii) 対価は週末の前に払われているか(コスト前の値動き)
    for gn, m, col in (("金曜午後・木曜の VIX > 25", hot_thu, "pm"), ("金曜午後・木曜の VIX ≤ 25", ~hot_thu, "pm"), ("金曜の最終足 → 月曜 04 UTC・金曜の VIX > 25", hot, "gap"), ("金曜の最終足 → 月曜 04 UTC・金曜の VIX ≤ 25", ~hot, "gap"),
                        ("金曜の最終足 → 週明け最初の足・金曜の VIX > 25", hot, "gap0"), ("金曜の最終足 → 週明け最初の足・金曜の VIX ≤ 25", ~hot, "gap0"), ("週明け最初の足 → 月曜 04 UTC・金曜の VIX > 25", hot, "am"), ("週明け最初の足 → 月曜 04 UTC・金曜の VIX ≤ 25", ~hot, "am")):
        for w, a, b in ALLW: add("(ii) 週末の前後の値動き(コスト前)", gn, cut(P[m.values], a, b)[col], w)
    sk = P.skew_hi                                     # (iii) SKEW 門 × VIX
    for gn, m in (("SKEW 高 かつ VIX > 25", sk & hot), ("SKEW 高 かつ VIX ≤ 25", sk & ~hot), ("SKEW 低 かつ VIX > 25", ~sk & hot), ("SKEW 低 かつ VIX ≤ 25", ~sk & ~hot)):
        for w, a, b in ALLW:
            x = cut(P[m.values], a, b)
            for col, nm in (("r24", "(iii) SKEW × VIX・24h"), ("r20", "(iii) SKEW × VIX・日中"), ("rN", "(iii) SKEW × VIX・夜の部分")): add(nm, gn, x[col], w)
    W = P.groupby(level=0).agg(vix=("vix", "first"), hot=("hot", "first"), sk=("skew_hi", "first")); skv = dict(weeks=len(W), skew_hi=int(W.sk.sum()), skew_hi_and_hot=int((W.sk & W.hot).sum()), hot=int(W.hot.sum()), vix_median_skew_hi=round(float(W.vix[W.sk].median()), 1), vix_median_skew_lo=round(float(W.vix[~W.sk].median()), 1), hot_share_in_skew_hi=round(float(W.hot[W.sk].mean()) * 100, 1), hot_share_in_skew_lo=round(float(W.hot[~W.sk].mean()) * 100, 1))
    TU = pd.concat([fx_tue(s) for s in MON4]).sort_index(kind="stable"); TU = TU[TU.index >= PRE0]; ITU = pd.concat([idx_shot(s, 1) for s in IDX3]).sort_index(kind="stable"); ITU = ITU[ITU.index >= s0]; IMO = pd.concat([idx_shot(s, 0) for s in IDX3]).sort_index(kind="stable"); IMO = IMO[IMO.index >= s0]   # (iv) 連休明けの火曜(銘柄をまとめて数える)
    for w, a, b in ALLW:
        x = TU[(TU.index >= a) & (TU.index <= b)]; y = cut(P, a, b).r24
        for gn, S_ in (("NYSE 月曜休場の週", NYSE_MON), ("日本の祝日月曜の週", JP_MON)):
            add("(iv) 円クロスの火曜 24h", gn, x[x.index.isin(S_)], w); add("(iv) 円クロスの月曜 24h", gn, y[y.index.isin(S_)], w)
        add("(iv) 円クロスの火曜 24h", "それ以外の週", x[~x.index.isin(NYSE_MON | JP_MON)], w); add("(iv) 円クロスの月曜 24h", "それ以外の週", y[~y.index.isin(NYSE_MON | JP_MON)], w)
        x = ITU[(ITU.index >= a) & (ITU.index <= b)]; y = IMO[(IMO.index >= a) & (IMO.index <= b)]
        add("(iv) 指数の火曜 13 UTC 24h", "NYSE 月曜休場の週", x[x.index.isin(NYSE_MON)], w); add("(iv) 指数の火曜 13 UTC 24h", "それ以外の週", x[~x.index.isin(NYSE_MON)], w); add("(iv) 指数の月曜 13 UTC 24h", "NYSE 月曜休場の週", y[y.index.isin(NYSE_MON)], w); add("(iv) 指数の月曜 13 UTC 24h", "それ以外の週", y[~y.index.isin(NYSE_MON)], w)
    d = pd.DatetimeIndex(sorted(set(P.index))); hj = load("JP225"); jo = hj["open"]; jc = hj["close"]; jf = jc[jc.index.dayofweek == 4]; jfl = jf.groupby(jf.index.normalize()).last().reindex(d - 3 * D1).values; jam = jo.reindex(d + pd.Timedelta(hours=4)).values   # (v) 日経の月曜朝の取り直し
    i0 = jo.index.searchsorted(d - D1); j0 = np.where(i0 < len(jo), jo.values[np.minimum(i0, len(jo) - 1)], np.nan); t0 = jo.index[np.minimum(i0, len(jo) - 1)]; j0 = np.where((t0 - (d - D1)) <= pd.Timedelta(hours=28), j0, np.nan)
    jold = jc.reindex(d - pd.Timedelta(hours=1), method="ffill").values; J = pd.DataFrame({"vs_fri": jam / jfl - 1, "vs_open": jam / j0 - 1, "q239": jam / jold - 1}, index=d); sun = float(np.mean([(x - pd.Timedelta(hours=1)) in jc.index for x in d[d >= hj.index.min()]]))
    for col, nm in (("vs_fri", "金曜の最終足比"), ("vs_open", "週明け最初の足比"), ("q239", "Q239 の計算のまま")):
        v = J[col].reindex(P.index).values
        for gn, m in ((f"日経 {nm} −1% 以下", v <= -0.01), (f"日経 {nm} −1〜+1%", (v > -0.01) & (v < 0.01)), (f"日経 {nm} +1% 以上", v >= 0.01)):
            for w, a, b in ALLW:
                x = cut(P[m], a, b); add("(v) 日経の月曜朝・24h", gn, x.r24, w); add("(v) 日経の月曜朝・夜の部分", gn, x.rN, w)
    T = pd.DataFrame(parts); T.to_csv("results/q240_weekend_premium_predictions_parts.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 900); pd.set_option("display.max_colwidth", 90)
    print(f"Q240: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print("基準 Mon4:", bs); print("参照 E1:", es); print(D.to_string(index=False))
    print("\nSKEW × VIX(週単位):", skv); print("JP225 の H1 開始", hj.index.min(), " 月曜のうち日曜 23 時台の足がある割合", round(sun * 100, 1), "%  NYSE 月曜休場", len([x for x in NYSE_MON if PRE0 <= x <= END]), " 日本の祝日月曜", len([x for x in JP_MON if PRE0 <= x <= END]))
    for tab in T.table.unique():
        g = T[T.table == tab]; pv = g.pivot(index="group", columns="window", values="mean_bps").reindex(g.group.unique())[[w for w, _, _ in ALLW]]; al = g[g.window == "全期間"].set_index("group")
        pv["n"] = al.n; pv["weeks"] = al.weeks; pv["win%"] = al.win; pv["t_week"] = al.t_week; print(f"\n== {tab}(平均 bps) =="); print(pv.to_string())
