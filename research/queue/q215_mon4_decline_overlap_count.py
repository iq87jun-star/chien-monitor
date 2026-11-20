# -*- coding: utf-8 -*-
"""docs/244 Q215(改良系・4 セル・2026-11-15 登録「登録して実行」): 月曜の円クロス — 「下げた」条件の重なりの数で数量を刻む。
4 条件(通貨ごと・月曜より前の最後の確定日足): 終値 < SMA50 / 終値 < SMA200 / 65 営業日前の終値より安い / 252 営業日の終値の高値から 5% 以上下。k = 当てはまる数。
W1: k=0 → 0.5・1〜2 → 0.75・3〜4 → 1.0。W2: 0.5 + 0.125k。W3: k=4 のみ 1.0・他 0.5。W4: k≥1 → 1.0・k=0 → 0.5。未計算の間は 1.0。
判定 = 配備中の形(SMA200 の下 1.0・上 0.5)に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。
使い方: cd research && python3 -W ignore queue/q215_mon4_decline_overlap_count.py <累積セル数>   出力: results/q215_mon4_decline_overlap_count.csv・_diag.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS, daily_close
import deployed_book as db
from scipy import stats as sps
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
def conds(sym, dates):
    c = daily_close(sym); X = pd.DataFrame({"c50": c / c.rolling(50).mean() - 1, "c200": c / c.rolling(200).mean() - 1, "roc13": c / c.shift(65) - 1, "dd252": c / c.rolling(252).max() - 1}).shift(1).reindex(pd.DatetimeIndex(dates), method="ffill")
    ok = X.notna().all(axis=1); k = (X.c50 < 0).astype(int) + (X.c200 < 0).astype(int) + (X.roc13 < 0).astype(int) + (X.dd252 <= -0.05).astype(int)
    return pd.DataFrame({"k": k.where(ok), "below200": (X.c200 < 0).where(X.c200.notna())})
def fac(S, kind):
    k = S.k.values; b = S.below200.values
    if kind == "base": return np.where(pd.isna(b), 1.0, np.where(b == 1, 1.0, 0.5))
    if kind == "W1": f = np.where(k == 0, 0.5, np.where(k <= 2, 0.75, 1.0))
    elif kind == "W2": f = 0.5 + 0.125 * k
    elif kind == "W3": f = np.where(k == 4, 1.0, 0.5)
    elif kind == "W4": f = np.where(k >= 1, 1.0, 0.5)
    return np.where(np.isnan(k), 1.0, f)
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 4; M = {}; ST = {}
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); M[s] = m[(m.index >= PRE0) & (m.index <= h.index.max())]; ST[s] = conds(s, M[s].index)
    def comp(kind):
        out = None
        for s in PAIRS:
            x = M[s] * (fac(ST[s], kind) if kind else 1.0) * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
        return out
    RAW, B = comp(None), comp("base"); rs = {k: stats(RAW, a, b) for k, a, b in WIN}; bs = {k: stats(B, a, b) for k, a, b in WIN}; rows = []
    LAB = {"W1": "W1 0 個 0.5・1〜2 個 0.75・3〜4 個 1.0", "W2": "W2 0.5 + 0.125 × 個数", "W3": "W3 4 個そろった時だけ 1.0", "W4": "W4 1 個でもあれば 1.0"}
    for kind in ("W1", "W2", "W3", "W4"):
        v = comp(kind); vs = {k: stats(v, a, b) for k, a, b in WIN}; ok = all(vs[k][0] > bs[k][0] and vs[k][1] >= bs[k][1] for k, _, _ in WIN)
        rows.append(dict(cell=LAB[kind], mean_size=round(float(np.mean(np.concatenate([fac(ST[s], kind) for s in PAIRS]))), 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[k][0] > bs[k][0] for k, _, _ in WIN)), improved=bool(ok)))
    D = pd.DataFrame(rows); D.to_csv("results/q215_mon4_decline_overlap_count.csv", index=False); pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q215: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)")
    print("縮小なしの Mon4:", rs); print("基準(200 日線の下 1.0・上 0.5):", bs, " 平均の倍率", round(float(np.mean(np.concatenate([fac(ST[s], 'base') for s in PAIRS]))), 3)); print(D.to_string(index=False))
    P = pd.concat([pd.DataFrame({"r": M[s], "k": ST[s].k, "sym": s}) for s in PAIRS]).dropna(); diag = []
    for wn, a, b in WIN:
        w = P[(P.index >= a) & (P.index <= b)]
        for k in range(5):
            x = w[w.k == k].r; diag.append(dict(window=wn, k=k, n=len(x), mean_bps=round(float(x.mean()) * 1e4, 2) if len(x) else None, win=round(float((x > 0).mean()) * 100, 1) if len(x) else None))
        rho, pv = sps.spearmanr(w.k, w.r); diag.append(dict(window=wn, k="順位相関(正 = 重なるほど高い)", n=len(w), mean_bps=round(float(rho), 3), win=round(float(pv), 3)))
    G = pd.DataFrame(diag); G.to_csv("results/q215_mon4_decline_overlap_count_diag.csv", index=False); print("\n== 診断: 重なりの数ごとの月曜(通貨 × 月曜のプール・1 倍あたり。順位相関の行は mean_bps = rho・win = p) =="); print(G.to_string(index=False))
