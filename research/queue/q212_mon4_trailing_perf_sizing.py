# -*- coding: utf-8 -*-
"""docs/244 Q212(改良系・3 セル・2026-11-15 登録「登録して実行」): 月曜の円クロス(配備形 Mon4)を、その枠自身の直近の成績で縮小する。
規則: その月曜より前の L 回分のベース週次損益の合計 < 0 なら 0.5 倍・それ以外 1.0 倍。L ∈ {13, 26, 52}。履歴が L 回未満の間は 1.0 倍。束単位。
判定 = §1 改良系(IS・OOS の両方で Sharpe 改善 かつ 最悪月が悪化しない)+ 前窓で Sharpe が悪化しない。
診断: 自己相関、窓ごとの 直近マイナス / それ以外 の平均と Welch t、縮小の割合、200 日線の縮小との重なり。
使い方: cd research && python3 -W ignore queue/q212_mon4_trailing_perf_sizing.py <累積セル数>   出力: results/q212_mon4_trailing_perf_sizing.csv・_diag.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats, improved
from q194_mon_own_technical_state_gate import PAIRS
from q195_mon_weak_state_tilt import st_at
from q211_mon4_shrunk_monthly_weights import base_mon4
LS = (13, 26, 52); LOW = 0.5; PRE1 = IS0 - pd.Timedelta(hours=1)
def flag(B, L):
    """その月曜より前の L 回分の合計 < 0 か。戻り値: (マイナスか, 計算済みか)"""
    t = B.rolling(L).sum().shift(1); return (t < 0).fillna(False).values, t.notna().values
def mon4_trailing(L=26):
    """紙上候補用: 配備形 Mon4 を直近 L 週の成績で縮小した系列。index = 建て日(月曜)。"""
    B = base_mon4(); neg, ok = flag(B, L); return B * np.where(neg & ok, LOW, 1.0)
def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 5 or len(b) < 5: return None
    return round(float((a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))), 2)
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = len(LS); B = base_mon4(); rows = []; diag = []; WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
    above = pd.DataFrame({s: (st_at(s, B.index).sma200 >= 0).values for s in PAIRS}, index=B.index).mean(axis=1) >= 0.5   # 通貨の半分以上が 200 日線の上
    for L in LS:
        neg, ok = flag(B, L); v = B * np.where(neg & ok, LOW, 1.0); r = improved(B, v); good = bool(r["ok"] and r["var_PRE"][0] >= r["base_PRE"][0])
        rows.append(dict(cell=f"L = {L} 週", base_PRE=r["base_PRE"], var_PRE=r["var_PRE"], base_IS=r["base_IS"], var_IS=r["var_IS"], base_OOS=r["base_OOS"], var_OOS=r["var_OOS"], improved_IS_OOS=r["ok"], improved=good))
        for wn, a, b in WIN:
            m = (B.index >= a) & (B.index <= b) & ok; x = B[m]; n_ = neg[m]; ab = above.values[m]
            diag.append(dict(L=L, window=wn, weeks=int(m.sum()), neg_share=round(float(n_.mean()) * 100, 1) if m.sum() else None, mean_neg_bps=round(float(x[n_].mean()) * 1e4, 2) if n_.sum() else None, mean_other_bps=round(float(x[~n_].mean()) * 1e4, 2) if (~n_).sum() else None,
                             win_neg=round(float((x[n_] > 0).mean()) * 100, 1) if n_.sum() else None, win_other=round(float((x[~n_] > 0).mean()) * 100, 1) if (~n_).sum() else None, welch_t_neg_minus_other=welch(x[n_], x[~n_]),
                             neg_and_above200_share=round(float((n_ & ab).mean()) * 100, 1) if m.sum() else None, above200_share=round(float(ab.mean()) * 100, 1) if m.sum() else None))
    D = pd.DataFrame(rows); D.to_csv("results/q212_mon4_trailing_perf_sizing.csv", index=False); G = pd.DataFrame(diag); G.to_csv("results/q212_mon4_trailing_perf_sizing_diag.csv", index=False)
    pd.set_option("display.width", 300); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q212: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  データ末尾 {B.index.max().date()}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)")
    print(D.to_string(index=False)); print("\n== 診断: 直近 L 週の合計がマイナスの週 / それ以外 =="); print(G.to_string(index=False))
    m4 = B.rolling(4).sum().dropna()
    print(f"\n自己相関: 1 週 {B.autocorr(1):+.3f}・2 週 {B.autocorr(2):+.3f}・4 週 {B.autocorr(4):+.3f} / 4 週合計どうし(重なりなし) {m4.iloc[::4].autocorr(1):+.3f} / 13 週合計どうし {B.rolling(13).sum().dropna().iloc[::13].autocorr(1):+.3f}(n = {len(B)})")
