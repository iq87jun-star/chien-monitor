# -*- coding: utf-8 -*-
"""docs/244 Q217(改良系・3 セル・2026-11-15 登録「登録して実行」): 月曜の円クロスの 200 日線の縮小を性格の違う 3 本の線で。
形 = 配備形 Mon4 の「減らすだけ」(金曜終値が線の下 1.0 倍・上 0.5 倍)。線: H = HMA(200)、K = KAMA(効率比の窓 200・速い 2・遅い 30・最初の 200 日は助走)、M = 終値の 200 日中央値。未計算は 1.0 倍。
読み方: (1) 縮小なしに対して 3 窓すべてで Sharpe 改善 かつ 最悪月が悪化しないか(3 本とも満たせば『線の種類は関係ない』)。(2) SMA200 に対して同じ条件を満たせば改良成立。配備は変えない。
使い方: cd research && python3 -W ignore queue/q217_mon4_ma_variants.py <累積セル数>   出力: results/q217_mon4_ma_variants.csv・_diag.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS, daily_close
import deployed_book as db
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); NN = 200
def wma(x, n):
    w = np.arange(1, n + 1, dtype=float); return x.rolling(n).apply(lambda v: float(np.dot(v, w) / w.sum()), raw=True)
def hma(c, n=NN): return wma(2 * wma(c, n // 2) - wma(c, n), int(round(np.sqrt(n))))
def kama(c, n=NN, fast=2, slow=30):
    v = c.values.astype(float); out = np.full(len(v), np.nan); fs, ss = 2.0 / (fast + 1), 2.0 / (slow + 1); vol = np.abs(np.diff(v, prepend=v[0])); cs = np.cumsum(vol)
    if len(v) <= n: return pd.Series(out, index=c.index)
    k = v[n]
    for i in range(n, len(v)):
        ch = abs(v[i] - v[i - n]); vv = cs[i] - cs[i - n]; er = ch / vv if vv > 0 else 0.0; sc = (er * (fs - ss) + ss) ** 2; k = k + sc * (v[i] - k); out[i] = k
    out[: 2 * n] = np.nan          # 助走: 最初の n 日は未計算扱い
    return pd.Series(out, index=c.index)
LINES = {"sma": lambda c: c.rolling(NN).mean(), "H": hma, "K": kama, "M": lambda c: c.rolling(NN).median()}
def dist(sym, kind, dates):
    c = daily_close(sym); return (c / LINES[kind](c) - 1).shift(1).reindex(pd.DatetimeIndex(dates), method="ffill")
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 3; M = {}
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); M[s] = m[(m.index >= PRE0) & (m.index <= h.index.max())]
    DS = {(s, k): dist(s, k, M[s].index) for s in PAIRS for k in LINES}
    def fac(s, k): d = DS[(s, k)]; return np.where(d.isna(), 1.0, np.where(d < 0, 1.0, 0.5))
    def comp(k):
        out = None
        for s in PAIRS:
            x = M[s] * (fac(s, k) if k else 1.0) * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
        return out
    RAW, B = comp(None), comp("sma"); rs = {w: stats(RAW, a, b) for w, a, b in WIN}; bs = {w: stats(B, a, b) for w, a, b in WIN}; rows = []; diag = []
    LAB = {"H": "H ハル移動平均 HMA(200)", "K": "K カウフマン適応型 KAMA(200, 2, 30)", "M": "M 200 日中央値"}
    def flips(k): return sum(int(pd.Series((DS[(s, k)] < 0).astype(int).values[DS[(s, k)].notna().values]).diff().abs().sum()) for s in PAIRS)
    for k in ("H", "K", "M"):
        v = comp(k); vs = {w: stats(v, a, b) for w, a, b in WIN}
        e = np.concatenate([(DS[(s, k)] < 0).values for s in PAIRS]); m_ = np.concatenate([(DS[(s, "sma")] < 0).values for s in PAIRS]); ok = np.concatenate([(DS[(s, k)].notna() & DS[(s, "sma")].notna()).values for s in PAIRS])
        rows.append(dict(cell=LAB[k], full_size_share=round(float(np.mean(np.concatenate([fac(s, k) for s in PAIRS]) == 1.0)) * 100, 1), agree_with_sma200=round(float((e[ok] == m_[ok]).mean()) * 100, 1), flips=flips(k), flips_sma200=flips("sma"), first_valid=str(min(DS[(s, k)].dropna().index.min() for s in PAIRS).date()),
                         var_PRE=vs["前窓"], var_IS=vs["IS"], var_OOS=vs["OOS"], improved_vs_raw=bool(all(vs[w][0] > rs[w][0] and vs[w][1] >= rs[w][1] for w, _, _ in WIN)), improved_vs_sma200=bool(all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN))))
        P = pd.concat([pd.DataFrame({"r": M[s], "d": DS[(s, k)]}) for s in PAIRS]).dropna()
        for w, a, b in WIN:
            x = P[(P.index >= a) & (P.index <= b)]; lo, hi = x[x.d < 0].r, x[x.d >= 0].r
            diag.append(dict(line=k, window=w, n_below=len(lo), mean_below_bps=round(float(lo.mean()) * 1e4, 2) if len(lo) else None, n_above=len(hi), mean_above_bps=round(float(hi.mean()) * 1e4, 2) if len(hi) else None, diff_bps=round(float(lo.mean() - hi.mean()) * 1e4, 2) if len(lo) and len(hi) else None))
    D = pd.DataFrame(rows); D.to_csv("results/q217_mon4_ma_variants.csv", index=False); G = pd.DataFrame(diag); G.to_csv("results/q217_mon4_ma_variants_diag.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q217: cells={N} cum_before={cum} cum_after={cum + N} improved_vs_sma200={int(D.improved_vs_sma200.sum())}/{N} improved_vs_raw={int(D.improved_vs_raw.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)")
    print("縮小なしの Mon4:", rs); print("配備中(SMA200):", bs); print(D.to_string(index=False)); print("\n== 診断: 線の下 / 上 の平均(bps) =="); print(G.to_string(index=False))
