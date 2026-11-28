# -*- coding: utf-8 -*-
"""docs/244 Q213(改良系・3 セル・2026-11-15 登録「登録して実行」): 月曜の円クロスの「下げた後に取る」を下げの深さで定義し直す。
形 = 配備形 Mon4 の「減らすだけ」(弱い通貨 1.0 倍・それ以外 0.5 倍)。基準 = 金曜終値 < SMA200。
V1: 13 週前(65 営業日前)の終値より安い。V2: 直近 252 営業日の終値の高値から 5% 以上下。V3: 線の上 0.5・浅い下 0.75・深い下 1.0(深い = 乖離が過去の『線の下の日』の乖離の中央値以下)。
判定 = 基準に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。指標が未計算の間は 1.0 倍。
使い方: cd research && python3 -W ignore queue/q213_mon4_decline_depth_state.py <累積セル数>   出力: results/q213_mon4_decline_depth_state.csv・_diag.csv"""
import sys, os
from q_common import *
from q147_roll_rate_diff_gate import stats
from q194_mon_own_technical_state_gate import PAIRS, daily_close
import deployed_book as db
from scipy import stats as sps
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
def depth_states(sym):
    c = daily_close(sym); d200 = c / c.rolling(200).mean() - 1; below = d200 < 0
    med = d200.where(below).expanding(min_periods=60).median().shift(1)          # 当日より前の『線の下の日』の乖離の中央値
    return pd.DataFrame({"d200": d200, "roc13": c / c.shift(65) - 1, "dd252": c / c.rolling(252).max() - 1, "med": med})
def at(sym, dates): return depth_states(sym).shift(1).reindex(pd.DatetimeIndex(dates), method="ffill")
def fac(S, kind):
    """S = 月曜時点の指標。戻り値 = その月曜の倍率。"""
    if kind == "base": return np.where(S.d200.isna(), 1.0, np.where(S.d200 < 0, 1.0, 0.5))
    if kind == "V1": return np.where(S.roc13.isna(), 1.0, np.where(S.roc13 < 0, 1.0, 0.5))
    if kind == "V2": return np.where(S.dd252.isna(), 1.0, np.where(S.dd252 <= -0.05, 1.0, 0.5))
    if kind == "V3": deep = (S.d200 < 0) & (S.med.isna() | (S.d200 <= S.med)); return np.where(S.d200.isna(), 1.0, np.where(S.d200 >= 0, 0.5, np.where(deep, 1.0, 0.75)))
def mon4_depth(kind="V3"):
    """紙上候補用: 配備形 Mon4(各 0.25)に Q213 の倍率を掛けた系列。"""
    out = None
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); x = m[(m.index >= PRE0) & (m.index <= h.index.max())]; x = x * fac(at(s, x.index), kind) * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
    return out
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 3; M = {}; ST = {}
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); M[s] = m[(m.index >= PRE0) & (m.index <= h.index.max())]; ST[s] = at(s, M[s].index)
    def comp(kind):
        out = None
        for s in PAIRS:
            x = M[s] * (fac(ST[s], kind) if kind else 1.0) * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
        return out
    RAW, B = comp(None), comp("base"); rows = []
    LAB = {"V1": "V1 13 週前より安い", "V2": "V2 1 年の高値から 5% 以上下", "V3": "V3 深さ 3 段階(上 0.5・浅い 0.75・深い 1.0)"}
    bs = {k: stats(B, a, b) for k, a, b in WIN}; rs = {k: stats(RAW, a, b) for k, a, b in WIN}
    for kind in ("V1", "V2", "V3"):
        v = comp(kind); vs = {k: stats(v, a, b) for k, a, b in WIN}; ok = all(vs[k][0] > bs[k][0] and vs[k][1] >= bs[k][1] for k, _, _ in WIN)
        share = float(np.mean(np.concatenate([fac(ST[s], kind) for s in PAIRS]) == 1.0)) * 100
        rows.append(dict(cell=LAB[kind], full_size_share=round(share, 1), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], improved=bool(ok)))
    D = pd.DataFrame(rows); D.to_csv("results/q213_mon4_decline_depth_state.csv", index=False); pd.set_option("display.width", 320); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    print(f"Q213: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)")
    print("縮小なしの Mon4:", rs); print("基準(200 日線の下 1.0・上 0.5):", bs, " 1.0 倍の割合", round(float(np.mean(np.concatenate([fac(ST[s], 'base') for s in PAIRS]) == 1.0)) * 100, 1)); print(D.to_string(index=False))
    # 診断: 通貨 × 月曜のプール
    P = pd.concat([pd.DataFrame({"r": M[s], "d200": ST[s].d200, "med": ST[s].med, "dd": ST[s].dd252, "roc": ST[s].roc13, "sym": s}) for s in PAIRS]); diag = []
    def add(wn, grp, lab, x): diag.append(dict(window=wn, group=grp, bucket=lab, n=len(x), mean_bps=round(float(x.mean()) * 1e4, 2) if len(x) else None, win=round(float((x > 0).mean()) * 100, 1) if len(x) else None))
    for wn, a, b in WIN:
        w = P[(P.index >= a) & (P.index <= b)]; k = w.dropna(subset=["d200"])
        add(wn, "200 日線", "上", k[k.d200 >= 0].r); bl = k[k.d200 < 0]; dp = bl.med.isna() | (bl.d200 <= bl.med); add(wn, "200 日線", "浅い下", bl[~dp].r); add(wn, "200 日線", "深い下", bl[dp].r)
        k = w.dropna(subset=["dd"])
        for lab, lo, hi in (("0〜−3%", -0.03, 0.01), ("−3〜−6%", -0.06, -0.03), ("−6〜−10%", -0.10, -0.06), ("−10% 以下", -9, -0.10)): add(wn, "1 年の高値から", lab, k[(k.dd > lo) & (k.dd <= hi)].r if lab != "0〜−3%" else k[k.dd > lo].r)
        k = w.dropna(subset=["roc"]); add(wn, "13 週前比", "安い", k[k.roc < 0].r); add(wn, "13 週前比", "高い", k[k.roc >= 0].r)
        if len(bl) > 20: rho, pv = sps.spearmanr(bl.d200, bl.r); diag.append(dict(window=wn, group="線の下だけ: 乖離と損益の順位相関(負 = 深いほど高い)", bucket=f"rho {rho:+.3f} p {pv:.3f}", n=len(bl), mean_bps=None, win=None))
    G = pd.DataFrame(diag); G.to_csv("results/q213_mon4_decline_depth_state_diag.csv", index=False); print("\n== 診断(通貨 × 月曜のプール・1 倍あたり) =="); print(G.to_string(index=False))
