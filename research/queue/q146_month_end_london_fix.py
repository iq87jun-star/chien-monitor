# -*- coding: utf-8 -*-
"""docs/244 Q146(週次アイデア束 #1・8 セル): 月末ロンドンフィックス前後の GBPUSD / EURUSD(Q24 docs/269 の 2h 窓を長い窓で再登録)。
フィックス = 16:00 London(BST 中 15 UTC・それ以外 16 UTC。Q24 と同じ定義)。月の最終営業日。
A: 前営業日の (fix−1) UTC 始値で建て → 当日 fix UTC 始値で決済(≈25h・フィックスに向かうフロー)× LONG/SHORT × 2 ペア = 4
B: 当日 fix UTC 始値で建て → fix+4h 始値で決済(フィックス後の反転)× LONG/SHORT × 2 ペア = 4
判定(登録どおり・前窓なし): 2016-01〜2026-08 の全期間で 1 取引 = 1 か月とし、勝ち数の二項 p(片側・0.5)< 0.05/累積、全期間平均 > 0、OOS(2025-01〜)平均 > 0。IS(2021-10〜2024-12)は参考列。コスト往復 3 pip。
使い方: cd research && python3 queue/q146_month_end_london_fix.py <累積セル数>"""
import sys, os
from q_common import *
PAIRS = ["GBPUSD", "EURUSD"]
def last_sunday(y, m): d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0); return d - pd.Timedelta(days=(d.dayofweek + 1) % 7)
def fix_hour(d): return 15 if last_sunday(d.year, 3) <= d.normalize() < last_sunday(d.year, 10) else 16
def last_bday(y, m): d = pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0); return d - pd.Timedelta(days=max(0, d.dayofweek - 4))
DAYS = [last_bday(y, m) for y in range(2016, 2027) for m in range(1, 13)]
def prev_bday(d): p = d - pd.Timedelta(days=1); return p - pd.Timedelta(days=max(0, p.dayofweek - 4))

def cell(sym, win, dir_):
    o = load(sym)["open"]; rows = []
    for d in DAYS:
        fh = fix_hour(d)
        if win == "A": t_in = prev_bday(d) + pd.Timedelta(hours=fh - 1); t_out = d + pd.Timedelta(hours=fh)
        else: t_in = d + pd.Timedelta(hours=fh); t_out = d + pd.Timedelta(hours=fh + 4)
        if t_in in o.index and t_out in o.index: rows.append((t_in, o[t_in], o[t_out]))
    if not rows: return pd.Series(dtype=float)
    t, pi, po = zip(*rows); return trades(sym, pd.DatetimeIndex(t), np.array(pi), dir_ * np.ones(len(t)), np.array(po))

def judge(r, alpha):
    full = r[(r.index >= PRE0) & (r.index <= END)]; n = len(full); k = int((full > 0).sum())
    p = sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n if n else 1.0
    si = st(r, IS0, IS1); so = st(r, OOS0, END)
    passed = bool(n >= 60 and p < alpha and full.mean() > 0 and so["n"] > 0 and so["mean"] > 0)
    return dict(n_full=n, wins_full=k, rate_full=round(k / n, 3) if n else float("nan"), mean_full_bps=round(float(full.mean()) * 1e4, 2) if n else float("nan"), p=p,
                is_rate=si["rate"], is_mean_bps=si["mean"], oos_n=so["n"], oos_rate=so["rate"], oos_mean_bps=so["mean"], passed=passed)

if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 8; alpha = 0.05 / (cum + N); rows = []
    for sym in PAIRS:
        selfcheck(sym, load(sym))
        for win, lab in (("A", "前日 fix−1h → 当日 fix(≈25h)"), ("B", "当日 fix → fix+4h")):
            for dir_, dl in ((+1, "LONG"), (-1, "SHORT")):
                rows.append(dict(symbol=sym, window=lab, direction=dl, **judge(cell(sym, win, dir_), alpha)))
    R = pd.DataFrame(rows).sort_values("p"); R.to_csv("results/q146_month_end_london_fix.csv", index=False); pd.set_option("display.width", 300)
    print(f"Q146: cells={N} cum_before={cum} cum_after={cum+N} alpha={alpha:.2e} passed={int(R.passed.sum())} p<0.05={int((R.p<0.05).sum())}")
    print(R.to_string(index=False))
