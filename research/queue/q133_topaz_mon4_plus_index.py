# -*- coding: utf-8 -*-
"""docs/322 §5m Q133(診断・セル 0): トパーズ(Fintokei スイング 3,500万・2.8% 全決済ガード)の帳簿を Mon4 ×8 のみ(docs/349 §8e)から、指数 Mon(NAS100 / US500・日足 o2o・Instant G と同型)を
各 {0.5, 1.0, 2.0} 足した場合と比較する。10.6 年 MC(2016-01〜2026-07・5 日ブロック・2 万本)・起点 10/19・5 月末までの到達 / 失格、資金化後(倍率半分)1 年の失格 / 期待収益。
使い方: cd research && python3 queue/q133_topaz_mon4_plus_index.py"""
import sys, os, datetime as dt
sys.path.insert(0, "queue"); import pandas as pd, q129_cfd_prop_expansion as q129
q129.CAL = pd.date_range(pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29"), freq="D")
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609"); import deployed_book as db
from q129_cfd_prop_expansion import on_cal, roll5
L = lambda f, s: on_cal(db.leg_series(f, s))
mon4 = sum(L("Mon", s) * 0.25 for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY")); nas = on_cal(base.mon_cell("NAS100")); spx = on_cal(base.mon_cell("US500")); roll = on_cal(roll5())
nonfx_noeth = L("v4nfx", "BTCUSD") * 0.211 + L("Hold", "UK100") * 0.491 + L("Hold", "WTI") * 0.153
rng = np.random.default_rng(33); N, BLOCK = 20000, 5; G = 0.028; P0, P1 = pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29")
start = dt.date(2026, 10, 19); D = (dt.date(2027, 5, 31) - start).days
def paths(c, days):
    r = np.asarray(c[(c.index >= P0) & (c.index <= P1)].values, float); nb = len(r) - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, days // BLOCK + 1)); return r[(stt[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N, -1)[:, :days]
def guard(p):   # 2.8% 全決済 + 月 2 回で月末まで停止
    p = np.clip(p, -G, None); w = p.reshape(N, -1, 21); hit = (w <= -G + 1e-12); prior = np.cumsum(hit, axis=2) - hit; return np.where(prior >= 2, 0.0, w).reshape(N, -1)
def evaluation(c, e0=0.989, targets=(0.08, 0.06), mdd=0.10, days=735):
    p = guard(paths(c, days)); e = e0 * np.cumprod(1 + p, axis=1); fl = 1 - mdd; dq = e <= fl; fd = np.where(dq.any(1), dq.argmax(1), 10**6)
    hit1 = e >= 1 + targets[0]; f1 = np.where(hit1.any(1), hit1.argmax(1), 10**6); ok1 = f1 < fd; rd = np.full(N, 10**6); fdd = np.where(fd < f1, fd + 1, 10**6)
    for i in np.flatnonzero(ok1):
        b2 = e[i, f1[i]]; e2 = e[i, f1[i] + 1:] / b2
        if len(e2) == 0: continue
        hh = np.where(e2 >= 1 + targets[1])[0]; dd = np.where(e2 <= fl)[0]
        if len(dd) and (not len(hh) or dd[0] < hh[0]): fdd[i] = f1[i] + 1 + dd[0] + 1; continue
        if len(hh): rd[i] = f1[i] + 1 + hh[0] + 1
    d = rd[rd < 10**6]; return (rd <= D).mean(), (fdd <= D).mean(), (start + dt.timedelta(days=int(np.median(d))) if len(d) else None), (start + dt.timedelta(days=int(np.quantile(d, .977))) if len(d) else None)
def funded(c, days=252, mdd=0.10):
    p = guard(paths(c, days)); e = np.cumprod(1 + p, axis=1); fl = 1 - mdd; br = (e <= fl).any(1); fin = np.where(br, fl, e[:, -1]); return br.mean(), float(np.mean(fin - 1))
BOOKS = [("現行(切替案) Mon4×6 + Roll×3 + 非FX×1.5", mon4 * 6 + roll * 3 + nonfx_noeth * 1.5), ("Mon4 ×8 のみ(§8e)", mon4 * 8),
         ("Mon4 ×8 + 指数 Mon 各 0.5", mon4 * 8 + (nas + spx) * 0.5), ("Mon4 ×8 + 指数 Mon 各 1.0", mon4 * 8 + (nas + spx) * 1.0), ("Mon4 ×8 + 指数 Mon 各 2.0", mon4 * 8 + (nas + spx) * 2.0),
         ("Mon4 ×6 + 指数 Mon 各 1.0", mon4 * 6 + (nas + spx) * 1.0), ("Mon4 ×10 + 指数 Mon 各 1.0", mon4 * 10 + (nas + spx) * 1.0)]
rows = []
for nm, c in BOOKS:
    r, f, med, p977 = evaluation(c); br, ret = funded(c * 0.5); inc = 35_000_000 / 158 * max(ret, 0) * 0.8 / 12 * 158 / 10000
    rows.append(dict(book=nm, reach=round(r * 100), fail=round(f * 100), median=str(med), p977=str(p977), funded_fail=round(br * 100), funded_ret=round(ret * 100, 1), monthly_man=round(inc), june_exp=round(r * inc)))
    print(f"{nm:<36} 5月末まで 到達 {r*100:3.0f}% 失格 {f*100:3.0f}% 中央 {med} +2σ {p977} | 資金化後(半分) 失格 {br*100:3.0f}% 期待 {ret*100:+.1f}% 月 {inc:3.0f} 万 → 6 月期待 {r*inc:3.0f} 万")
pd.DataFrame(rows).to_csv("results/q133_topaz_mon4_plus_index.csv", index=False)
