# -*- coding: utf-8 -*-
"""docs/244 §1b: バイナリー向けの共通判定(2026-10-21 登録・Q140〜Q142)。
判定はトレード単位の勝率 WR と損益分岐 BE(1/ペイアウト)。Dukascopy H1 の始値→始値(ミッド)。同値は負け扱い(保守側)。
合格 = 探索窓で WR−BE ≥ +3pp かつ 二項 p(BE 基準・片側)< 0.05/累積セル数、OOS と前窓で WR > BE。"""
import os, sys, numpy as np, pandas as pd
from math import comb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q_common import load, PRE0, IS0, IS1, OOS0, END
PAYOUT = {1: 1.90, 22: 1.95, 23: 1.95}          # 保有時間 → ペイアウト(それ以外は 1.90 = 最も厳しい)
def be(hold_h): return 1.0 / PAYOUT.get(hold_h, 1.90)

def outcomes(sym, dow_utc, h_utc, hold_h, high=True, dows=None):
    """建て: 曜日 dow_utc(None なら dows の集合)・h_utc 時の始値 → hold_h 時間後の始値で判定。1=勝ち 0=負け の Series(index=建て時刻)。"""
    df = load(sym); o = df["open"]
    sel = (o.index.hour == h_utc) & (o.index.dayofweek.isin(dows) if dows is not None else (o.index.dayofweek == dow_utc))
    t = o.index[sel]; p_in = o.reindex(t).values; p_out = o.reindex(t + pd.Timedelta(hours=hold_h)).values
    ok = ~np.isnan(p_in) & ~np.isnan(p_out)
    w = (p_out[ok] > p_in[ok]) if high else (p_out[ok] < p_in[ok])
    return pd.Series(w.astype(int), index=t[ok])

def p_binom(wins, n, p0):
    """P(X >= wins | n, p0)(片側・厳密)。"""
    if n == 0: return 1.0
    return float(sum(comb(n, k) * p0 ** k * (1 - p0) ** (n - k) for k in range(wins, n + 1)))

def judge(w, hold_h, alpha):
    b = be(hold_h)
    def seg(a, z):
        x = w[(w.index >= a) & (w.index <= z)]; n = int(len(x)); k = int(x.sum()); return n, k, (k / n if n else float("nan"))
    n_pre, k_pre, wr_pre = seg(PRE0, IS0 - pd.Timedelta(hours=1)); n_is, k_is, wr_is = seg(IS0, IS1); n_oos, k_oos, wr_oos = seg(OOS0, END)
    p = p_binom(k_is, n_is, b)
    passed = bool(n_is >= 100 and wr_is - b >= 0.03 and p < alpha and n_oos > 0 and wr_oos > b and n_pre > 0 and wr_pre > b)
    return dict(be=round(b * 100, 2), n_pre=n_pre, wr_pre=round(wr_pre * 100, 1), n_is=n_is, wins_is=k_is, wr_is=round(wr_is * 100, 1), edge_is_pp=round((wr_is - b) * 100, 1),
                p=p, n_oos=n_oos, wr_oos=round(wr_oos * 100, 1), edge_oos_pp=round((wr_oos - b) * 100, 1), passed=passed)

def finish(qid, cum, rows, out):
    R = pd.DataFrame(rows); n = len(R); alpha = 0.05 / (cum + n); R = R.sort_values("p"); R.to_csv(out, index=False); pd.set_option("display.width", 260)
    print(f"{qid}: cells={n} cum_before={cum} cum_after={cum+n} alpha={alpha:.2e} passed={int(R.passed.sum())} edge>=3pp(IS)={int((R.edge_is_pp>=3).sum())}")
    print(R.head(15).to_string(index=False)); print("\n-- passed --"); print(R[R.passed].to_string(index=False) if R.passed.any() else "(none)")
    return R
