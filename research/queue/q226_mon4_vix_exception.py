# -*- coding: utf-8 -*-
"""docs/244 Q226(改良系・4 セル・2026-11-15 登録「登録して実行」): 月曜の円クロスの 200 日線の縮小に VIX の例外を足す。
基準 = 配備形 Mon4(線の下 1.0・上 0.5)。例外 = 前金曜の VIX が高い週明けは、線より上の通貨も 1.0。基準 = V20(>20)・V25(>25)・V30(>30)・VP(252 日 80 分位超)。
判定 = 基準に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。事後の着想。
使い方: cd research && python3 -W ignore queue/q226_mon4_vix_exception.py <累積セル数>   出力: results/q226_mon4_vix_exception.csv・_diag.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS, states
import deployed_book as db
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
V = pd.read_csv("data_ext/VIX_History.csv"); V["d"] = pd.to_datetime(V["DATE"]); VIX = V.set_index("d")["CLOSE"].sort_index().astype(float); VPCT = VIX.rolling(252).rank(pct=True)
def frame():
    rows = []
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); m = m[(m.index >= PRE0) & (m.index <= h.index.max())]; st = states(s).shift(1).reindex(m.index, method="ffill"); fri = pd.DatetimeIndex(m.index) - pd.Timedelta(days=3)
        rows.append(pd.DataFrame({"r": m.values, "sym": s, "d200": st.sma200.values, "vix": VIX.reindex(fri, method="ffill").values, "vpct": VPCT.reindex(fri, method="ffill").values}, index=m.index))
    P = pd.concat(rows); P["above"] = (P.d200 >= 0).fillna(False); return P
def hot(P, kind):
    if kind == "VP": return (P.vpct > 0.8).fillna(False)
    return (P.vix > {"V20": 20, "V25": 25, "V30": 30}[kind]).fillna(False)
def mon4_vix_exception(kind="V25"):
    """紙上候補用: 配備形 Mon4(線の下 1.0・上 0.5)で、前金曜の VIX が高い週明けは線の上も 1.0。"""
    P = frame(); f = np.where(P.above & ~hot(P, kind), 0.5, 1.0); return (P.r * f * 0.25).groupby(level=0).sum()
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 4; P = frame()
    def comp(kind): f = np.where(P.above & (~hot(P, kind) if kind else True), 0.5, 1.0); return (P.r * f * 0.25).groupby(level=0).sum(), float(np.mean(f))
    B, bsz = comp(None); bs = {w: stats(B, a, b) for w, a, b in WIN}; rows = []
    LAB = {"V20": "V20 VIX > 20", "V25": "V25 VIX > 25(主)", "V30": "V30 VIX > 30", "VP": "VP 252 日 80 分位超"}
    for k in ("V20", "V25", "V30", "VP"):
        v, sz = comp(k); vs = {w: stats(v, a, b) for w, a, b in WIN}
        rows.append(dict(cell=LAB[k], hot_share=round(float(hot(P, k).mean()) * 100, 1), mean_size=round(sz, 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), improved=bool(all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN))))
    D = pd.DataFrame(rows); D.to_csv("results/q226_mon4_vix_exception.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    v25 = bool(D.iloc[1].improved); oth = bool(D.iloc[0].sharpe_up_3win or D.iloc[2].sharpe_up_3win); read = ("区切りに頼らない" if (v25 and oth) else ("区切り依存" if v25 else "V25 不成立"))
    print(f"Q226: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  読み方 = {read}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print("基準(例外なし):", bs, " 平均の倍率", round(bsz, 3)); print(D.to_string(index=False))
    diag = []
    for k in ("V20", "V25", "V30", "VP"):
        h = hot(P, k)
        for w, a, b in WIN:
            m = (P.index >= a) & (P.index <= b)
            for ln, lm in (("線の上", P.above), ("線の下", ~P.above)):
                hi, lo = P[m & lm & h].r, P[m & lm & ~h].r
                diag.append(dict(vix=k, window=w, line=ln, n_hot=len(hi), mean_hot_bps=round(float(hi.mean()) * 1e4, 2) if len(hi) else None, n_calm=len(lo), mean_calm_bps=round(float(lo.mean()) * 1e4, 2) if len(lo) else None, diff_bps=round(float(hi.mean() - lo.mean()) * 1e4, 2) if len(hi) and len(lo) else None))
            hh = P[m & h]; diag.append(dict(vix=k, window=w, line="VIX が高い週のうち線の下の割合 %", n_hot=len(hh), mean_hot_bps=round(float((~hh.above).mean()) * 100, 1) if len(hh) else None, n_calm=int(hh.index.nunique()), mean_calm_bps=None, diff_bps=None))
    G = pd.DataFrame(diag); G.to_csv("results/q226_mon4_vix_exception_diag.csv", index=False); print("\n== 診断(通貨 × 月曜のプール・1 倍あたり。『線の下の割合』の行は mean_hot_bps = 割合 %・n_calm = 該当した月曜の数) =="); print(G.to_string(index=False))
