# -*- coding: utf-8 -*-
"""docs/284 §2 Q36: フィックス前後(M1 bid 13:30〜17:30 UTC・2024-01〜2026-08)。ペアごとに 3 セル:
 (a) WMR フィックス逆張り: ロンドン 16:00(英国夏時間中は 15:00 UTC)の直前 15 分の符号の逆を、フィックス時刻の始値で建て 15 分後の始値で決済
 (b) NY カット前平均回帰: NY 10:00(米夏時間中は 14:00 UTC・冬 15:00 UTC)の直前 30 分の符号の逆を建て 30 分保有
 (c) (a) を月末営業日に限定
コスト = H1 bid/ask の 15 UTC スプレッド中央値 ×2(往復)。IS = 2024-01〜2024-12(12 か月)・OOS = 2025-01〜。判定(docs/244 の免除・前窓なし): IS ≥ 9/12 かつ OOS +率 ≥ 60% かつ p < 閾値。
使い方: python3 queue/q36_fix_reversal.py <累積> EURUSD,GBPUSD"""
import sys, os, numpy as np, pandas as pd
import q_common as qc
from q_common import *
qc.PRE0, qc.IS0, qc.IS1, qc.OOS0 = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31 23:59"), pd.Timestamp("2025-01-01")
def uk_bst(d):   # 3 月最終日曜 01:00 UTC 〜 10 月最終日曜 01:00 UTC
    y = d.year; mar = max(pd.date_range(f"{y}-03-25", f"{y}-03-31")[pd.date_range(f"{y}-03-25", f"{y}-03-31").dayofweek == 6]); octo = max(pd.date_range(f"{y}-10-25", f"{y}-10-31")[pd.date_range(f"{y}-10-25", f"{y}-10-31").dayofweek == 6])
    return mar <= d.normalize() < octo
def us_dst(d):   # 3 月第 2 日曜 〜 11 月第 1 日曜
    y = d.year; m = pd.date_range(f"{y}-03-08", f"{y}-03-14"); mar = m[m.dayofweek == 6][0]; n = pd.date_range(f"{y}-11-01", f"{y}-11-07"); nov = n[n.dayofweek == 6][0]
    return mar <= d.normalize() < nov
def m1(sym):
    d = pd.read_csv(f"data_dukascopy_m1/{sym}_bid_m1_1400_1730.csv.gz"); d["t"] = pd.to_datetime(d["timestamp"]); d = d.set_index("t").sort_index(); return d[~d.index.duplicated(keep="last")]["open"]
def rt_cost(sym):
    b = load(sym)["open"]; a = pd.read_csv(f"data_dukascopy/{sym}_hour_ask.csv.gz"); a["t"] = pd.to_datetime(a["timestamp"]); a = a.set_index("t").sort_index()["open"]; a = a[~a.index.duplicated()]
    b = b[b.index >= "2024-01-01"]; a = a.reindex(b.index); sp = ((a - b) / ((a + b) / 2)); return float(sp[b.index.hour == 15].median() * 2)
def cell(o, days, t_fix_of, pre_min, hold_min, cost):
    t_in, d, t_out = [], [], []
    for day in days:
        tf = t_fix_of(day); p0 = o.get(tf - pd.Timedelta(minutes=pre_min)); p1 = o.get(tf); p2 = o.get(tf + pd.Timedelta(minutes=hold_min))
        if p0 is None or p1 is None or p2 is None or p1 == p0: continue
        t_in.append(tf); d.append(-np.sign(p1 - p0)); t_out.append(p2 / p1 - 1)
    r = pd.Series(np.array(d) * np.array(t_out) - cost, index=pd.DatetimeIndex(t_in)); return r
cum = int(sys.argv[1]); pairs = sys.argv[2].split(","); R = Runner("Q36", cum, 3 * len(pairs), f"results/q36_fix_reversal_{'_'.join(pairs)}.csv"); J = []
for sym in pairs:
    o = m1(sym); days = pd.DatetimeIndex(sorted(set(o.index.normalize()))); days = days[days.dayofweek < 5]; c = rt_cost(sym)
    print(f"[{sym}] M1 日数 {len(days)} {days[0].date()}〜{days[-1].date()}  始値例 {o.iloc[0]:.5f}  往復コスト {c*1e4:.2f} bps")
    wmr = lambda day: day + pd.Timedelta(hours=15 if uk_bst(day) else 16); nyc = lambda day: day + pd.Timedelta(hours=14 if us_dst(day) else 15)
    me = pd.DatetimeIndex([g.max() for _, g in pd.Series(days, index=days).groupby(days.to_period("M"))])
    for lab, dd, tf, pre, hold in (("a) WMR 直前15分 逆張り 15分", days, wmr, 15, 15), ("b) NYカット 直前30分 逆張り 30分", days, nyc, 30, 30), ("c) WMR 逆張り 月末営業日のみ", me, wmr, 15, 15)):
        r = cell(o, dd, tf, pre, hold, c); R.add("フィックス前後", sym, lab, r)
        si, so = st(r, qc.IS0, qc.IS1), st(r, qc.OOS0, qc.END); ok = si["n"] >= 12 and si["plus"] >= 9 and so["n"] > 0 and so["rate"] >= 0.6 and si["p"] < R.alpha
        J.append(dict(symbol=sym, spec=lab, is_plus=si["plus"], is_n=si["n"], is_bps=si["mean"], p=si["p"], oos_plus=so["plus"], oos_n=so["n"], oos_bps=so["mean"], trades=si["trades"] + so["trades"], judged_pass=ok))
R.finish(); print("\n== Q36 判定(IS 2024 ≥9/12・OOS ≥60%・p<閾値)==\n" + pd.DataFrame(J).to_string(index=False))
