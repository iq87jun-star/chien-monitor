# -*- coding: utf-8 -*-
"""docs/244 Q225(改良系・4 セル・2026-11-15 登録): 月曜の円クロス(配備形 Mon4)で、系統の違う 4 つの手がかりをまとめて数量を減らす。
手がかり(不利): A 通貨が SMA200 以上 / B 通貨の前週が上昇 / C 前金曜の SKEW が 252 日 80 分位超 / D 前金曜の VIX > 25。
E1: 1 − 0.25u(下限 0.25)。E2: u ≥ 2 → 0.5。E3: (A or B) かつ (C or D) → 0.5。E4: 過去だけで当てはめた線形予測が過去の中央値未満 → 0.5(3 年たまるまでは A だけ)。
判定 = 配備中の形(A だけ: 下 1.0・上 0.5)に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。
使い方: cd research && python3 -W ignore queue/q225_mon4_weak_signal_ensemble.py <累積セル数>   出力: results/q225_mon4_weak_signal_ensemble.csv・_diag.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS, states
from q188_skew_gate_guard_model import skew_gate_dates
import deployed_book as db
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
PRK = skew_gate_dates(); V = pd.read_csv("data_ext/VIX_History.csv"); V["d"] = pd.to_datetime(V["DATE"]); VIX = V.set_index("d")["CLOSE"].sort_index().astype(float)
def frame():
    rows = []
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); m = m[(m.index >= PRE0) & (m.index <= h.index.max())]; st = states(s).shift(1).reindex(m.index, method="ffill"); fri = pd.DatetimeIndex(m.index) - pd.Timedelta(days=3)
        rows.append(pd.DataFrame({"r": m.values, "sym": s, "d200": st.sma200.values, "wk": st.wk.values, "skew": PRK.reindex(fri, method="ffill").values, "vix": VIX.reindex(fri, method="ffill").values}, index=m.index))
    P = pd.concat(rows); P["A"] = (P.d200 >= 0).fillna(False); P["B"] = (P.wk > 0).fillna(False); P["C"] = (P.skew > 0.8).fillna(False); P["D"] = (P.vix > 25).fillna(False); P["u"] = P[["A", "B", "C", "D"]].sum(axis=1); return P
def e4_factor(P):
    """取引年ごとに、前年末までのデータだけで最小二乗 → 予測が過去の中央値未満なら 0.5。3 年未満は A だけの形。"""
    X = ["d200", "wk", "skew", "vix"]; f = np.where(P.A, 0.5, 1.0).astype(float); coefs = {}
    for Y in sorted(set(P.index.year)):
        tr = P[(P.index < pd.Timestamp(f"{Y}-01-01"))].dropna(subset=X); te = P.index.year == Y
        if tr.index.year.nunique() < 3 or len(tr) < 300: continue
        mu, sd = tr[X].mean(), tr[X].std(); Z = np.c_[np.ones(len(tr)), ((tr[X] - mu) / sd).values]; b = np.linalg.lstsq(Z, tr.r.values, rcond=None)[0]; med = float(np.median(Z @ b)); coefs[Y] = b[1:]
        Zt = np.c_[np.ones(int(te.sum())), ((P.loc[te, X] - mu) / sd).values]; pred = Zt @ b; ok = ~np.isnan(pred); cur = f[te]; cur[ok] = np.where(pred[ok] < med, 0.5, 1.0); f[te] = cur
    return f, coefs
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 4; P = frame(); f4, coefs = e4_factor(P)
    FAC = {"base": np.where(P.A, 0.5, 1.0), "E1": np.maximum(1 - 0.25 * P.u.values, 0.25), "E2": np.where(P.u >= 2, 0.5, 1.0), "E3": np.where((P.A | P.B) & (P.C | P.D), 0.5, 1.0), "E4": f4}
    def comp(k): x = P.r * (FAC[k] if k else 1.0) * 0.25; return x.groupby(level=0).sum()
    RAW, B = comp(None), comp("base"); rs = {w: stats(RAW, a, b) for w, a, b in WIN}; bs = {w: stats(B, a, b) for w, a, b in WIN}; rows = []
    LAB = {"E1": "E1 不利な数に比例(1 − 0.25u・下限 0.25)", "E2": "E2 多数決(2 つ以上で 0.5)", "E3": "E3 通貨側と市場側の両方で不利なら 0.5", "E4": "E4 統計的な合成(過去だけで当てはめた予測)"}
    for k in ("E1", "E2", "E3", "E4"):
        v = comp(k); vs = {w: stats(v, a, b) for w, a, b in WIN}
        rows.append(dict(cell=LAB[k], mean_size=round(float(np.mean(FAC[k])), 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), improved=bool(all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN))))
    D = pd.DataFrame(rows); D.to_csv("results/q225_mon4_weak_signal_ensemble.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q225: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print("縮小なしの Mon4:", rs); print("基準(A だけ):", bs, " 平均の倍率", round(float(np.mean(FAC['base'])), 3)); print(D.to_string(index=False))
    diag = []
    for w, a, b in WIN:
        x = P[(P.index >= a) & (P.index <= b)]
        for u in range(5): y = x[x.u == u].r; diag.append(dict(window=w, item=f"不利な数 {u}", n=len(y), mean_bps=round(float(y.mean()) * 1e4, 2) if len(y) else None))
        for c in "ABCD": y1, y0 = x[x[c]].r, x[~x[c]].r; diag.append(dict(window=w, item=f"手がかり {c}: 不利 − それ以外", n=len(y1), mean_bps=round(float(y1.mean() - y0.mean()) * 1e4, 2) if len(y1) and len(y0) else None))
    G = pd.DataFrame(diag); G.to_csv("results/q225_mon4_weak_signal_ensemble_diag.csv", index=False); print("\n== 診断(通貨 × 月曜のプール・1 倍あたり) =="); print(G.pivot_table(index="item", columns="window", values=["mean_bps", "n"], sort=False).round(1).to_string())
    print("\nE4 の係数(標準化後・bps。年 = その年に使った係数):"); print(pd.DataFrame({Y: np.round(c * 1e4, 2) for Y, c in coefs.items()}, index=["200 日線からの乖離", "前週騰落", "SKEW の分位", "VIX"]).to_string())
    print("データの末尾: SKEW", PRK.dropna().index.max().date(), "VIX", VIX.index.max().date(), "/ 手がかりの出現率 %:", {c: round(float(P[c].mean()) * 100, 1) for c in "ABCD"})
