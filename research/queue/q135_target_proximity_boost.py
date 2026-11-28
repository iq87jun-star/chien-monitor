# -*- coding: utf-8 -*-
"""docs/322 §5m Q135(改良系・セル 0): 評価段階の目標直前ブースト。P1/P2 の目標まで残り {1, 2}% の局面だけ倍率を {×0.5, ×1.5, ×2.0} にする規則が、
5 月末(10/19 起点 224 日)までの到達率を +2pt 以上上げ、失格率を悪化させないか。10.6 年 MC(2016-01〜2026-07・5 日ブロック・2 万本)、5 口座型。
使い方: cd research && python3 queue/q135_target_proximity_boost.py"""
import sys, os, datetime as dt
sys.path.insert(0, "queue"); import pandas as pd, q129_cfd_prop_expansion as q129
q129.CAL = pd.date_range(pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29"), freq="D")
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609"); import deployed_book as db
from q129_cfd_prop_expansion import on_cal, roll5
L = lambda f, s: on_cal(db.leg_series(f, s))
mon4 = sum(L("Mon", s) * 0.25 for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY")); bplan = L("Mon", "GBPJPY") * 0.374 + L("Mon", "AUDJPY") * 0.322 + L("v4", "USDJPY") * 0.304
roll = on_cal(roll5()); holdxau = on_cal(base.hold_cell("XAUUSD")); nas = on_cal(base.mon_cell("NAS100")); hold_uw = L("Hold", "UK100") * 0.491 + L("Hold", "WTI") * 0.153
A = (holdxau + L("Mon", "GBPJPY") + nas) / 3
rng = np.random.default_rng(35); N, BLOCK = 20000, 5; P0, P1 = pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29"); D = 224
def paths(c, days):
    r = np.asarray(c[(c.index >= P0) & (c.index <= P1)].values, float); nb = len(r) - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, days // BLOCK + 1)); return r[(stt[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N, -1)[:, :days]
def evaluation(c, e0, targets, mdd, dll, prox, boost, trail=False):
    p = paths(c, D); e = np.full(N, e0); basel = np.ones(N); stage = np.zeros(N, int); reached = np.zeros(N, bool); failed = np.zeros(N, bool); hwm = np.full(N, e0)
    for t in range(D):
        act = ~reached & ~failed; tg = np.array([targets[min(s, len(targets) - 1)] for s in stage]); dist = basel * (1 + tg) - e
        f = np.where(dist <= basel * prox, boost, 1.0); ret = np.clip(p[:, t] * f, -dll, None)
        e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e)
        fl = np.minimum(hwm - mdd, 1.0) if trail else basel * (1 - mdd); failed |= act & (e <= fl)
        for s in range(len(targets)):
            hit = act & ~failed & (stage == s) & (e >= basel * (1 + targets[s]))
            if s == len(targets) - 1: reached |= hit
            else: stage[hit] = s + 1; basel[hit] = e[hit]
    return float(reached.mean()), float(failed.mean())
BOOKS = [("1-Step EA9 ×2.5(トレーリング 9%)", A * 2.5, 1.003, [0.10], 0.09, 0.024, True), ("FTMO 2-Step Mon4 ×3.3 新規", mon4 * 3.3, 1.0, [0.10, 0.05], 0.10, 0.04, False), ("ルビー B案 ×10", bplan * 10, 1.003, [0.08, 0.06], 0.10, 0.028, False),
         ("トパーズ Mon4 ×8", mon4 * 8, 0.989, [0.08, 0.06], 0.10, 0.028, False), ("FN 14166201 Hold UK100/WTI ×2.22 + Roll ×4.5", hold_uw * 2.22 + roll * 4.5, 1.044, [0.08, 0.05], 0.10, 0.04, False), ("宝くじ Mon4 ×10 + HoldXAU 0.9", mon4 * 10 + holdxau * 0.9, 0.927, [0.10, 0.05], 0.095, 0.04, False)]
rows = []
for nm, c, e0, tg, mdd, dll, trail in BOOKS:
    r0, f0 = evaluation(c, e0, tg, mdd, dll, 0.0, 1.0, trail); line = [f"基準 {r0*100:.0f} / {f0*100:.0f}%"]
    for prox in (0.01, 0.02):
        for boost in (0.5, 1.5, 2.0):
            r, f = evaluation(c, e0, tg, mdd, dll, prox, boost, trail); ok = (r - r0 >= 0.02) and (f <= f0 + 0.001)
            rows.append(dict(book=nm, prox=prox, boost=boost, reach=round(r * 100, 1), fail=round(f * 100, 1), base_reach=round(r0 * 100, 1), base_fail=round(f0 * 100, 1), improved=ok)); line.append(f"残 {prox*100:.0f}%×{boost}: {r*100:.0f} / {f*100:.0f}%{' ○' if ok else ''}")
    print(nm + " | " + " | ".join(line))
pd.DataFrame(rows).to_csv("results/q135_target_proximity_boost.csv", index=False)
