# -*- coding: utf-8 -*-
"""docs/244 Q214(改良系・5 セル・2026-11-15 登録「登録して実行」): 月曜の円クロスの 200 日線の縮小 — 移動平均の日数の感度。
形 = 配備形 Mon4 の「減らすだけ」(金曜終値が N 日線の下 1.0 倍・上 0.5 倍)。N ∈ {50, 100, 150, 200(配備・基準), 250, 300}。未計算の間は 1.0 倍。
読み方: 各 N を縮小なしの Mon4 と比べ、前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しないか。丈夫 = 150 と 250 の両方が満たす / 孤立 = どちらも満たさない。配備の 200 は結果にかかわらず変えない。
使い方: cd research && python3 -W ignore queue/q214_mon4_sma_length_sensitivity.py <累積セル数>   出力: results/q214_mon4_sma_length_sensitivity.csv・_diag.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS, daily_close
import deployed_book as db
NS = (50, 100, 150, 200, 250, 300); PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
def dist(sym, n, dates):
    c = daily_close(sym); return (c / c.rolling(n).mean() - 1).shift(1).reindex(pd.DatetimeIndex(dates), method="ffill")
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 5; M = {}
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); M[s] = m[(m.index >= PRE0) & (m.index <= h.index.max())]
    DS = {(s, n): dist(s, n, M[s].index) for s in PAIRS for n in NS}
    def fac(s, n): d = DS[(s, n)]; return np.where(d.isna(), 1.0, np.where(d < 0, 1.0, 0.5))
    def comp(n):
        out = None
        for s in PAIRS:
            x = M[s] * (fac(s, n) if n else 1.0) * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
        return out
    RAW = comp(None); rs = {k: stats(RAW, a, b) for k, a, b in WIN}; rows = []; diag = []; b200 = np.concatenate([(DS[(s, 200)] < 0).values for s in PAIRS]); ok200 = np.concatenate([DS[(s, 200)].notna().values for s in PAIRS])
    for n in NS:
        v = comp(n); vs = {k: stats(v, a, b) for k, a, b in WIN}; good = all(vs[k][0] > rs[k][0] and vs[k][1] >= rs[k][1] for k, _, _ in WIN)
        bn = np.concatenate([(DS[(s, n)] < 0).values for s in PAIRS]); okn = np.concatenate([DS[(s, n)].notna().values for s in PAIRS]); both = ok200 & okn
        rows.append(dict(N=n, deployed=(n == 200), full_size_share=round(float(np.mean(np.concatenate([fac(s, n) for s in PAIRS]) == 1.0)) * 100, 1), agree_with_200=round(float((bn[both] == b200[both]).mean()) * 100, 1), first_valid=str(min(DS[(s, n)].dropna().index.min() for s in PAIRS).date()),
                         raw_PRE=rs["前窓"], var_PRE=vs["前窓"], raw_IS=rs["IS"], var_IS=vs["IS"], raw_OOS=rs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[k][0] > rs[k][0] for k, _, _ in WIN)), improved_vs_raw=bool(good)))
        P = pd.concat([pd.DataFrame({"r": M[s], "d": DS[(s, n)]}) for s in PAIRS]).dropna()
        for k, a, b in WIN:
            w = P[(P.index >= a) & (P.index <= b)]; lo, hi = w[w.d < 0].r, w[w.d >= 0].r
            diag.append(dict(N=n, window=k, n_below=len(lo), mean_below_bps=round(float(lo.mean()) * 1e4, 2) if len(lo) else None, n_above=len(hi), mean_above_bps=round(float(hi.mean()) * 1e4, 2) if len(hi) else None, diff_bps=round(float(lo.mean() - hi.mean()) * 1e4, 2) if len(lo) and len(hi) else None))
    D = pd.DataFrame(rows); D.to_csv("results/q214_mon4_sma_length_sensitivity.csv", index=False); G = pd.DataFrame(diag); G.to_csv("results/q214_mon4_sma_length_sensitivity_diag.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    g150, g250 = bool(D[D.N == 150].improved_vs_raw.iloc[0]), bool(D[D.N == 250].improved_vs_raw.iloc[0]); verdict = "丈夫" if (g150 and g250) else ("孤立" if not (g150 or g250) else "部分的")
    print(f"Q214: cells={N} cum_before={cum} cum_after={cum + N}  読み方の結果 = {verdict}(150 日 {g150}・250 日 {g250})  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)")
    print("縮小なしの Mon4:", rs); print(D.to_string(index=False)); print("\n== 診断: 線の下 / 上 の平均(通貨 × 月曜のプール・1 倍あたり) =="); print(G.pivot_table(index="N", columns="window", values=["mean_below_bps", "mean_above_bps", "diff_bps"]).round(1).to_string())
