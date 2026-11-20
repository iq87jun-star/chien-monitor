# -*- coding: utf-8 -*-
"""docs/322 Q86(診断・セル 0): 資金化後の固定倍率(維持 / 逓減)× 出金頻度 × 保持率 の 12 か月 MC。
規則: 10.6 年帳簿(2016-01〜2026-07・5 日ブロック・2 万本)。静的床 = 初期残高 × (1 − mdd)。EA 日次ガード dll(口座比)。
出金 = {10, 21} 営業日ごとに「初期残高 × (1 + 保持率)」を超えた分 × 0.8(FTMO 80/20・Fintokei も 80% とみなす)。出金後の残高は初期 × (1+保持率) に戻る(床は動かない)。
逓減 = 最初の出金の後に倍率を m1 に落とす(維持 = m0 == m1)。比較対象: Q131 の余裕比例(採用設定 k・保持 20%)。
使い方: cd research && timeout 1500 python3 queue/q86_funded_mult_payout.py"""
import sys, os
sys.path.insert(0, "queue"); import pandas as pd, q129_cfd_prop_expansion as q129
q129.CAL = pd.date_range(pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29"), freq="D")
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609"); import deployed_book as db
from q129_cfd_prop_expansion import on_cal
L = lambda f, s: on_cal(db.leg_series(f, s))
mon4 = sum(L("Mon", s) * 0.25 for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY"))
ger = on_cal(base.mon_cell("GER40")) if hasattr(base, "mon_cell") else None
bplan = L("Mon", "GBPJPY") * 0.374 + L("Mon", "AUDJPY") * 0.322 + L("v4", "USDJPY") * 0.304
rng = np.random.default_rng(86); N, BLOCK = 20000, 5
P0, P1 = pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29")
def paths(c, days):
    r = np.asarray(c[(c.index >= P0) & (c.index <= P1)].values, float); nb = len(r) - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, days // BLOCK + 1)); return r[(stt[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N, -1)[:, :days]
def funded(p1, e0, mdd, dll, m0, m1, keep, freq, k=0.0, days=250, split=0.8):
    """p1 = 倍率 1 の経路。m0 → 最初の出金後 m1。k>0 なら Q131 の余裕比例(m0 固定のまま f 倍)。"""
    e = np.full(N, e0); paid = np.zeros(N); alive = np.ones(N, bool); fl = 1 - mdd; m = np.full(N, m0); npay = np.zeros(N, int)
    for t in range(days):
        f = np.clip(1 + k * ((e - fl) - mdd) / mdd, 1.0, 1 + k) if k > 0 else 1.0
        ret = np.clip(p1[:, t] * m * f, -dll, None)
        e = np.where(alive, e * (1 + ret), e); hit = alive & (e <= fl); e = np.where(hit, fl, e); alive &= ~hit
        if (t + 1) % freq == 0:
            w = np.where(alive, np.maximum(e - (1 + keep), 0.0), 0.0); paid += w * split; e -= w; npay += (w > 0); m = np.where(npay > 0, m1, m)
    return dict(fail=float((~alive).mean()) * 100, mean=float(paid.mean()) * 100, med=float(np.median(paid)) * 100, q16=float(np.quantile(paid, 0.16)) * 100, p0=float((paid <= 0).mean()) * 100)
BOOKS = [("FTMO 50k Mon4(EA3)", mon4, 1.04, 0.10, 0.04, 1.5), ("パール B案", bplan, 1.029, 0.10, 0.028, 1.0)]
MULTS = [(1.5, 1.5), (2.0, 2.0), (3.3, 3.3), (3.3, 2.0), (3.3, 1.5), (5.0, 5.0), (6.0, 6.0), (6.0, 3.3), (8.0, 8.0)]
rows = []
for nm, c, e0, mdd, dll, kcap in BOOKS:
    p1 = paths(c, 250)
    for m0, m1 in MULTS:
        for keep in (0.0, 0.05, 0.10, 0.20):
            for freq in (10, 21):
                r = funded(p1, e0, mdd, dll, m0, m1, keep, freq); rows.append(dict(book=nm, m0=m0, m1=m1, keep=keep, freq=freq, k=0.0, **r))
    for m0 in (3.3, 5.0, 6.0, 8.0):
        r = funded(p1, e0, mdd, dll, m0, m0, 0.20, 21, k=kcap); rows.append(dict(book=nm, m0=m0, m1=m0, keep=0.20, freq=21, k=kcap, **r))
F = pd.DataFrame(rows); F[["fail", "mean", "med", "q16", "p0"]] = F[["fail", "mean", "med", "q16", "p0"]].round(1); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
os.makedirs("results", exist_ok=True); F.to_csv("results/q86_funded_mult_payout.csv", index=False)
for nm in F.book.unique():
    g = F[F.book == nm]
    print(f"== {nm}: 月次・保持 10%(固定)"); print(g[(g.freq == 21) & (g.keep == 0.10) & (g.k == 0)][["m0", "m1", "fail", "mean", "med", "q16", "p0"]].to_string(index=False))
    print("-- 維持 ×3.3 / ×6: 保持 × 頻度"); print(g[(g.m0 == g.m1) & (g.m0.isin([3.3, 6.0])) & (g.k == 0)][["m0", "keep", "freq", "fail", "mean", "med", "q16"]].to_string(index=False))
    print("-- 逓減 vs 維持(月次・保持 10%)"); print(g[(g.freq == 21) & (g.keep == 0.10) & (g.k == 0) & (g.m0.isin([3.3, 6.0]))][["m0", "m1", "fail", "mean", "med"]].to_string(index=False))
    print("-- Q131 余裕比例(採用: 保持 20%・月次)"); print(g[g.k > 0][["m0", "k", "fail", "mean", "med", "q16"]].to_string(index=False))
