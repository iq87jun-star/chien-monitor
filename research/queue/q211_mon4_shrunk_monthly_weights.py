# -*- coding: utf-8 -*-
"""docs/244 Q211(改良系・3 セル・2026-11-15 登録「登録して実行」): 月曜の円クロス(配備形 Mon4)に「薄めた月別重み」を掛ける。
重み = (1 − λ) + λ × r_m、λ ∈ {0.25, 0.50, 1.00}。r_m は取引年 Y より前(2016-01〜Y−1 年 12 月)の Mon4 の月次損益だけで決める:
暦月 m の過去平均が正ならその値・負なら 0 を raw_m とし、r_m = raw_m ÷ 12 か月の raw の平均(上限 3.0)。過去 3 年未満の年・raw がすべて 0 の年は 1.0。
判定 = §1 改良系(IS・OOS の両方で Sharpe 改善 かつ 最悪月が悪化しない)+ 前窓で Sharpe が悪化しない。
診断: 年ごとの重み表、λ = 0.5 の重みを月の間で入れ替えたプラセボ 200 回(乱数 187)。
使い方: cd research && python3 -W ignore queue/q211_mon4_shrunk_monthly_weights.py <累積セル数>   出力: results/q211_mon4_shrunk_monthly_weights.csv・_weights.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats, improved
from q194_mon_own_technical_state_gate import PAIRS
import deployed_book as db
LAMS = (0.25, 0.50, 1.00); MINY = 3; CAP = 3.0
def base_mon4():
    out = None
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); x = m[(m.index >= PRE0) & (m.index <= h.index.max())] * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
    return out
def month_r(B):
    """年 Y → 12 か月の r_m(Y より前の月次損益だけで決める)。"""
    mo = B.groupby([B.index.year, B.index.month]).sum(); y0 = int(B.index.year.min()); R = {}
    for Y in sorted(set(B.index.year)):
        if Y - y0 < MINY: R[Y] = np.ones(12); continue
        hist = mo[mo.index.get_level_values(0) < Y]; mean = hist.groupby(level=1).mean().reindex(range(1, 13)).fillna(0.0).values; raw = np.maximum(mean, 0.0)
        R[Y] = np.ones(12) if raw.sum() <= 0 else np.minimum(raw / raw.mean(), CAP)
    return R
def weighted(B, R, lam, perm=None):
    w = np.array([(1 - lam) + lam * (R[d.year][(perm[d.year][d.month - 1] if perm is not None else d.month - 1)]) for d in B.index]); return B * w
def mon4_monthly(lam=0.5):
    """紙上候補用: 配備形 Mon4 に薄めた月別重み(λ)を掛けた系列。index = 建て日(月曜)。"""
    B = base_mon4(); return weighted(B, month_r(B), lam)
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = len(LAMS); B = base_mon4(); R = month_r(B); rows = []
    for lam in LAMS:
        v = weighted(B, R, lam); r = improved(B, v); ok = bool(r["ok"] and r["var_PRE"][0] >= r["base_PRE"][0])
        rows.append(dict(cell=f"λ = {lam:.2f}", base_PRE=r["base_PRE"], var_PRE=r["var_PRE"], base_IS=r["base_IS"], var_IS=r["var_IS"], base_OOS=r["base_OOS"], var_OOS=r["var_OOS"], improved_IS_OOS=r["ok"], improved=ok))
    D = pd.DataFrame(rows); D.to_csv("results/q211_mon4_shrunk_monthly_weights.csv", index=False); pd.set_option("display.width", 300); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q211: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  データ末尾 {B.index.max().date()}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)")
    print(D.to_string(index=False))
    W = pd.DataFrame({Y: R[Y] for Y in sorted(R)}, index=range(1, 13)).T.round(2); W.index.name = "year"; W.to_csv("results/q211_mon4_shrunk_monthly_weights_weights.csv"); print("\n== r_m(年 × 暦月) =="); print(W.to_string())
    mo = B.groupby([B.index.year, B.index.month]).sum().unstack() * 100; print("\n== Mon4 の月次損益 %(年 × 暦月) =="); print(mo.round(2).to_string()); print("暦月の平均 %:", mo.mean().round(2).tolist(), " +の年の割合:", ((mo > 0).sum() / mo.notna().sum()).round(2).tolist())
    # プラセボ: 各年の r_m を月の間で入れ替える(λ = 0.5)。探索 + OOS の Sharpe
    def sh(x): x = x[x.index >= IS0]; return float(x.mean() / x.std() * np.sqrt(52))
    act = sh(weighted(B, R, 0.5)); rng = np.random.default_rng(187); S = []
    for _ in range(200):
        perm = {Y: rng.permutation(12) for Y in R}; S.append(sh(weighted(B, R, 0.5, perm)))
    S = np.array(S); print(f"\nプラセボ(λ = 0.5・探索 + OOS): 実際 {act:.3f} / ベース {sh(B):.3f} / 入れ替え 200 回の平均 {S.mean():.3f}・中央 {np.median(S):.3f}・実際以上の割合 p = {(S >= act).mean():.3f}")
    for lam in LAMS:
        v = weighted(B, R, lam); x = v[v.index >= IS0]; b = B[B.index >= IS0]; print(f"λ = {lam:.2f}: 探索 + OOS 平均 {x.mean() * 1e4:+.2f} bps / 週(ベース {b.mean() * 1e4:+.2f})・重みの平均 {np.mean([(1 - lam) + lam * R[d.year][d.month - 1] for d in b.index]):.3f}・最大 {max((1 - lam) + lam * R[Y].max() for Y in R):.2f}")
