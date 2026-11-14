# -*- coding: utf-8 -*-
"""docs/244 Q216(改良系・5 セル・2026-11-15 登録): 月曜の円クロスの 200 日線の縮小を EMA で。
形 = 配備形 Mon4 の「減らすだけ」(金曜終値が EMA(N) の下 1.0 倍・上 0.5 倍)。N ∈ {50, 100, 150, 200, 250}・α = 2/(N+1)・N 日分たまるまでは 1.0 倍。
読み方: (1) 縮小なしに対して 3 窓すべてで Sharpe 改善 かつ 最悪月が悪化しないか。(2) 配備中の形(SMA200)に対して同じ条件を満たせば改良成立。配備は変えない。
使い方: cd research && python3 -W ignore queue/q216_mon4_ema_state.py <累積セル数>   出力: results/q216_mon4_ema_state.csv・_diag.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS, daily_close
import deployed_book as db
NS = (50, 100, 150, 200, 250); PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
def dist(sym, n, dates, kind):
    c = daily_close(sym); ma = c.ewm(span=n, adjust=False, min_periods=n).mean() if kind == "ema" else c.rolling(n).mean()
    return (c / ma - 1).shift(1).reindex(pd.DatetimeIndex(dates), method="ffill")
def mon4_ema(n=200):
    """紙上候補用: 配備形 Mon4(各 0.25)で EMA(n) の下 1.0 倍・上 0.5 倍。"""
    out = None
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); x = m[(m.index >= PRE0) & (m.index <= h.index.max())]; d = dist(s, n, x.index, "ema"); x = x * np.where(d.isna(), 1.0, np.where(d < 0, 1.0, 0.5)) * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
    return out
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 5; M = {}
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); M[s] = m[(m.index >= PRE0) & (m.index <= h.index.max())]
    DS = {(s, n, k): dist(s, n, M[s].index, k) for s in PAIRS for n in NS for k in ("ema", "sma")}
    def fac(s, n, k): d = DS[(s, n, k)]; return np.where(d.isna(), 1.0, np.where(d < 0, 1.0, 0.5))
    def comp(n, k):
        out = None
        for s in PAIRS:
            x = M[s] * (fac(s, n, k) if n else 1.0) * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
        return out
    RAW = comp(None, None); B = comp(200, "sma"); rs = {w: stats(RAW, a, b) for w, a, b in WIN}; bs = {w: stats(B, a, b) for w, a, b in WIN}; rows = []; diag = []
    for n in NS:
        v = comp(n, "ema"); vs = {w: stats(v, a, b) for w, a, b in WIN}; sv = comp(n, "sma"); ss = {w: stats(sv, a, b) for w, a, b in WIN}
        e = np.concatenate([(DS[(s, n, "ema")] < 0).values for s in PAIRS]); m_ = np.concatenate([(DS[(s, n, "sma")] < 0).values for s in PAIRS]); ok = np.concatenate([(DS[(s, n, "ema")].notna() & DS[(s, n, "sma")].notna()).values for s in PAIRS])
        rows.append(dict(N=n, full_size_share=round(float(np.mean(np.concatenate([fac(s, n, "ema") for s in PAIRS]) == 1.0)) * 100, 1), agree_with_sma_same_N=round(float((e[ok] == m_[ok]).mean()) * 100, 1),
                         ema_PRE=vs["前窓"], sma_PRE=ss["前窓"], ema_IS=vs["IS"], sma_IS=ss["IS"], ema_OOS=vs["OOS"], sma_OOS=ss["OOS"],
                         improved_vs_raw=bool(all(vs[w][0] > rs[w][0] and vs[w][1] >= rs[w][1] for w, _, _ in WIN)), improved_vs_sma200=bool(all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN))))
        P = pd.concat([pd.DataFrame({"r": M[s], "d": DS[(s, n, "ema")]}) for s in PAIRS]).dropna()
        for w, a, b in WIN:
            x = P[(P.index >= a) & (P.index <= b)]; lo, hi = x[x.d < 0].r, x[x.d >= 0].r
            diag.append(dict(N=n, window=w, n_below=len(lo), mean_below_bps=round(float(lo.mean()) * 1e4, 2), n_above=len(hi), mean_above_bps=round(float(hi.mean()) * 1e4, 2), diff_bps=round(float(lo.mean() - hi.mean()) * 1e4, 2)))
    D = pd.DataFrame(rows); D.to_csv("results/q216_mon4_ema_state.csv", index=False); G = pd.DataFrame(diag); G.to_csv("results/q216_mon4_ema_state_diag.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q216: cells={N} cum_before={cum} cum_after={cum + N} improved_vs_sma200={int(D.improved_vs_sma200.sum())}/{N} improved_vs_raw={int(D.improved_vs_raw.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)")
    print("縮小なしの Mon4:", rs); print("配備中(SMA200):", bs); print(D.to_string(index=False)); print("\n== 診断: EMA の下 / 上 の平均(bps) =="); print(G.pivot_table(index="N", columns="window", values=["mean_below_bps", "mean_above_bps", "diff_bps"]).round(1).to_string())
