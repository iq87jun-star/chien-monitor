# -*- coding: utf-8 -*-
"""docs/322 §5l Q131(工学+改良系・セル 0)朝 1: 余裕比例サイジングの 10.6 年 MC。
規則: 倍率係数 f = min(1 + k × (余裕 − mdd) / mdd, 1 + k)(余裕 = equity − 床、床 = 段階の基準残高 × (1 − mdd)。余裕が mdd(= 開始時の余裕)以下なら f = 1)。
資金化後: 250 営業日。出金 = {10, 21} 営業日ごとに「基準残高 × (1 + 保持率)」を超えた分(収入)。失格 = equity ≤ 床。EA 日次ガードは口座比で固定(dll)。
評価段階: 5 月末(10/19 起点 224 日)までの 到達 / 失格。2 段階は P1 通過時に基準を更新。
データ: docs/349 §7b と同じ帳簿(2016-01〜2026-07・5 日ブロック・2 万本)。使い方: cd research && python3 queue/q131_buffer_scaled_sizing.py"""
import sys, os, datetime as dt
sys.path.insert(0, "queue"); import pandas as pd, q129_cfd_prop_expansion as q129
q129.CAL = pd.date_range(pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29"), freq="D")
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609"); import deployed_book as db
from q129_cfd_prop_expansion import on_cal, roll5
L = lambda f, s: on_cal(db.leg_series(f, s))
mon4 = sum(L("Mon", s) * 0.25 for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY"))
bplan = L("Mon", "GBPJPY") * 0.374 + L("Mon", "AUDJPY") * 0.322 + L("v4", "USDJPY") * 0.304
nonfx_noeth = L("v4nfx", "BTCUSD") * 0.211 + L("Hold", "UK100") * 0.491 + L("Hold", "WTI") * 0.153
roll = on_cal(roll5()); holdxau = on_cal(base.hold_cell("XAUUSD")); mongbpjpy = L("Mon", "GBPJPY"); monnas = on_cal(base.mon_cell("NAS100"))
mon3 = L("Mon", "EURJPY") * 0.333 + L("Mon", "USDJPY") * 0.333 + L("Mon", "NZDJPY") * 0.334
A = (holdxau + mongbpjpy + monnas) / 3
rng = np.random.default_rng(31); N, BLOCK = 20000, 5
P0, P1 = pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29")
def paths(c, days):
    r = np.asarray(c[(c.index >= P0) & (c.index <= P1)].values, float); nb = len(r) - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, days // BLOCK + 1)); return r[(stt[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N, -1)[:, :days]
def funded(c, e0, mdd, dll, k, keep, freq, days=250):
    p = paths(c, days); e = np.full(N, e0); paid = np.zeros(N); alive = np.ones(N, bool); fl = 1 - mdd
    for t in range(days):
        f = np.clip(1 + k * ((e - fl) - mdd) / mdd, 1.0, 1 + k); ret = np.clip(p[:, t] * f, -dll, None)
        e = np.where(alive, e * (1 + ret), e); hit = alive & (e <= fl); e = np.where(hit, fl, e); alive &= ~hit
        if (t + 1) % freq == 0:
            w = np.where(alive, np.maximum(e - (1 + keep), 0.0), 0.0); paid += w; e -= w
    return float((~alive).mean()), float(paid.mean()), float(np.median(paid)), float(np.quantile(paid, 0.16))
def evaluation(c, e0, targets, mdd, dll, k, D=224):
    p = paths(c, D); e = np.full(N, e0); basel = np.ones(N); stage = np.zeros(N, int); reached = np.zeros(N, bool); failed = np.zeros(N, bool); rd = np.full(N, 10**6)
    for t in range(D):
        fl = basel * (1 - mdd); act = ~reached & ~failed
        f = np.clip(1 + k * ((e - fl) / basel - mdd) / mdd, 1.0, 1 + k); ret = np.clip(p[:, t] * f, -dll, None)
        e = np.where(act, e * (1 + ret), e); failed |= act & (e <= fl)
        for s, tg in enumerate(targets):
            hit = act & ~failed & (stage == s) & (e >= basel * (1 + tg))
            if s == len(targets) - 1: reached |= hit; rd[hit] = t + 1
            else: stage[hit] = s + 1; basel[hit] = e[hit]
    return float(reached.mean()), float(failed.mean())
FUND = [("FTMO 50k Mon4 ×3.3", mon4 * 3.3, 1.04, 0.10, 0.04), ("FTMO 50k Mon4 ×5.0", mon4 * 5.0, 1.04, 0.10, 0.04), ("パール B案 ×4", bplan * 4, 1.029, 0.10, 0.028), ("パール B案 ×6", bplan * 6, 1.029, 0.10, 0.028),
        ("1-Step 資金化後 EA9 ×2.0", A * 2.0, 1.0, 0.10, 0.024), ("14074882 Mon3 ×4 + HoldXAU 0.4", mon3 * 4 + holdxau * 0.4, 0.947, 0.10, 0.04), ("FN 14166201 資金化後 非FX ×2.22 + Roll ×4.5", nonfx_noeth * 2.22 + roll * 4.5, 1.0, 0.10, 0.04)]
rows = []
print("== 資金化後 1 年(10.6 年 MC): 失格 / 出金 期待・中央・16% 点")
for nm, c, e0, mdd, dll in FUND:
    for k in (0.0, 0.5, 1.0, 2.0):
        for keep in (0.0, 0.05, 0.10, 0.15):
            for freq in (10, 21):
                if k == 0.0 and freq == 10 and keep not in (0.0, 0.10): continue
                br, mean, med, q16 = funded(c, e0, mdd, dll, k, keep, freq)
                rows.append(dict(phase="funded", book=nm, k=k, keep=keep, freq=freq, fail=round(br * 100, 1), paid_mean=round(mean * 100, 1), paid_med=round(med * 100, 1), paid_q16=round(q16 * 100, 1)))
F = pd.DataFrame(rows); pd.set_option("display.width", 250)
for nm in F.book.unique():
    g = F[F.book == nm]; b0 = g[(g.k == 0) & (g.keep == 0.10) & (g.freq == 21)].iloc[0]
    ok = g[(g.fail <= b0.fail + 5)].sort_values("paid_mean", ascending=False).head(3)
    print(f"-- {nm}: 固定(10% 保持・月次) 失格 {b0.fail}% 出金 {b0.paid_mean}%")
    for _, r in ok.iterrows(): print(f"   k={r.k} 保持 {r.keep*100:.0f}% {r.freq} 日: 失格 {r.fail}% 出金 期待 {r.paid_mean}% 中央 {r.paid_med}% 16%点 {r.paid_q16}%")
EVAL = [("FTMO 2-Step Mon4 ×3.3(新規想定)", mon4 * 3.3, 1.0, [0.10, 0.05], 0.10, 0.04), ("ルビー B案 ×10", bplan * 10, 1.003, [0.08, 0.06], 0.10, 0.028), ("トパーズ Mon4×6+Roll×3+非FX×1.5", mon4 * 6 + roll * 3 + nonfx_noeth * 1.5, 0.989, [0.08, 0.06], 0.10, 0.028),
        ("FN 14166201 ×1.5", nonfx_noeth * 2.22 + roll * 4.5, 1.044, [0.08, 0.05], 0.10, 0.04), ("宝くじ Mon4 ×10 + HoldXAU 0.9", mon4 * 10 + holdxau * 0.9, 0.927, [0.10, 0.05], 0.095, 0.04)]
print("== 評価段階(5 月末まで・10/19 起点): 到達 / 失格")
erows = []
for nm, c, e0, tg, mdd, dll in EVAL:
    line = []
    for k in (0.0, 0.5, 1.0, 2.0):
        r, f = evaluation(c, e0, tg, mdd, dll, k); erows.append(dict(phase="eval", book=nm, k=k, reach=round(r * 100, 1), fail=round(f * 100, 1))); line.append(f"k={k}: {r*100:.0f} / {f*100:.0f}%")
    print(f"-- {nm}: " + " | ".join(line))
pd.concat([F, pd.DataFrame(erows)]).to_csv("results/q131_buffer_scaled_sizing.csv", index=False)
