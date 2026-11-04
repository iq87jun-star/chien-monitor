# -*- coding: utf-8 -*-
"""docs/397(ユーザー 2026-11-04「インスタント系は有力候補はありませんか」): インスタント型(評価なし・購入日から本口座)の候補を
Q88(docs/383)と同じ帳簿・同じ乱数・36 か月で比較する参考計算(セル 0・診断)。規約は 2026-11-04 取得の公式ページ(docs/397 §1)。
床の型: static(額面 −mdd 固定) / trail_cap(最高残高 −mdd・額面で頭打ち = FN Instant) / trail(最高残高 −mdd・頭打ちなし = FTMO Instant)。
出金: 21 営業日ごと。static は「基準 ×(1+keep) 超過分 × pf」(床 10% は keep 20%・床 6% は keep 10%)、trail 系は「床 + buf を超える分 × pf」(床が追随するので残高比の保持は意味がない)。
Consistency 門(最良日 ≤ gate × 前回出金からの利益)がある口座は満たすまで繰り越し。SwiftTrader は評価段(目標 6%・60 暦日 ≈ 42 営業日・日次利益上限 3%)を先に置く。
使い方: cd research && python3 -W ignore queue/instant_candidates_2026-11.py → results/instant_candidates_2026-11.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from forward.portfolio_sim import *
FX = 158.0; N = 6000; BLOCK = 5; MONTHS = 36; DAYS = 21 * MONTHS; SEED = 44
def simulate(c):
    rng = np.random.default_rng(SEED); T = len(R(legs()["mon4"])); nb = T - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); IDX = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :DAYS]
    cf = R(book(c["book"]))[IDX] * c.get("scale", 1.0); mdd = c["mdd"]; dll = c.get("dll"); bal = c["balance_jpy"]; ftype = c["floor"]
    kk = c.get("k", 0.0); kp = c.get("keep", 0.2); buf = c.get("buf", 0.05); pf = c.get("pay_frac", 0.5); sp = c["split"]; gate = c.get("gate"); ev = c.get("eval")
    e = np.ones(N); basel = np.ones(N); hwm = np.ones(N); failed = np.zeros(N, bool); funded = np.full(N, ev is None); expired = np.zeros(N, bool)
    paid = np.zeros((N, MONTHS)); cum_since = np.zeros(N); best_since = np.zeros(N); skips = 0; ev_prog = np.zeros(N)
    for t in range(DAYS):
        act = ~failed & ~expired
        if ftype == "static": fl = basel - mdd
        elif ftype == "trail_cap": fl = np.minimum(hwm - mdd, basel)
        else: fl = np.maximum(hwm, basel) - mdd
        f = np.clip(1 + kk * ((e - fl) / basel - mdd) / mdd, 1.0, 1 + kk) if (kk > 0 and ftype == "static") else 1.0
        ret = cf[:, t] * f
        if dll: ret = np.clip(ret, -dll, None)
        e_prev = e.copy(); e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e); failed |= act & (e <= fl)
        d = np.where(act & funded, e - e_prev, 0.0); cum_since += d; best_since = np.maximum(best_since, d)
        if ev is not None:   # SwiftTrader 評価段: 日次利益は上限 3% まで目標に算入、42 営業日で未達なら失効
            g = np.where(act & ~funded, np.minimum(np.maximum(e - e_prev, 0), ev.get("daycap", 1.0)) - np.maximum(e_prev - e, 0), 0.0); ev_prog += g
            hit = act & ~funded & (ev_prog >= ev["target"]); funded |= hit; e[hit] = 1.0; hwm[hit] = 1.0; basel[hit] = 1.0
            if t + 1 == ev["days"]: expired |= ~funded & ~failed
        if (t + 1) % 21 == 0:
            m = (t + 1) // 21 - 1; ok = funded & ~failed
            if c.get("fixed_pay"): w = np.where(ok & (e >= basel * (1 + c["fixed_pay"][0])), c["fixed_pay"][1], 0.0)   # FN Instant 運用規則: +5% で $400(docs/349 §9f-4)
            elif ftype == "static": w = np.where(ok, np.maximum(e - basel * (1 + kp), 0.0) * pf, 0.0)
            else: w = np.where(ok, np.maximum(e - (fl + buf), 0.0) * pf, 0.0)
            if c.get("min_pay"): w = np.where(w >= c["min_pay"], w, 0.0)
            if gate is not None:
                blocked = (w > 0) & (best_since > gate * np.maximum(cum_since, 1e-9)); skips += int(blocked.sum()); w = np.where(blocked, 0.0, w)
            paid[:, m] = w * bal * sp; e -= w; pay = w > 0; cum_since[pay] = 0.0; best_since[pay] = 0.0
    p36 = paid.sum(1); alive = ~failed & ~expired
    steady = paid[:, 12:24].mean(1)
    return dict(reach=funded.mean() * 100, expired=expired.mean() * 100, fail=failed.mean() * 100, fail12=(failed & (np.arange(1) == 0)).mean() * 100 if False else None,
                pay12=paid[:, :12].sum(1).mean() / 1e4, pay36=p36.mean() / 1e4, pay36_med=float(np.median(p36)) / 1e4, pay36_p0=(p36 <= 0).mean() * 100,
                steady_m=float(steady.mean()) / 1e4, alive36=alive.mean() * 100, gate_skip=skips / max(1, (paid > 0).sum() + skips) * 100)
A9 = {"a9": 1.0}; MON4 = {"mon4": 1.0}; INSTG = {"instG": 1.0}
CANDS = [
 # 名前, 設定, 費用 USD, 口座数, 注記
 ("参考: FN Stellar Instant 20k(保有中)G ×1.0", dict(book=INSTG, floor="trail_cap", mdd=0.06, dll=None, split=0.7, fixed_pay=(0.05, 0.02), balance_jpy=20e3 * FX), 420, 1, "枠 $20k 使用済み(追加不可)。Tier1-2 分配 70%。出金規則 +5% で $400(docs/349 §9f-4)"),
 ("FTMO Instant 100k + A 案 ×1.5", dict(book=A9, scale=1.5, floor="trail", mdd=0.10, dll=0.03, split=0.9, buf=0.05, gate=0.30, balance_jpy=100e3 * FX), 3352, 1, "床は最高残高 −10%・頭打ちなし・出金でリセットせず。Consistency 30%"),
 ("FTMO Instant 100k + A 案 ×1.0", dict(book=A9, scale=1.0, floor="trail", mdd=0.10, dll=0.03, split=0.9, buf=0.05, gate=0.30, balance_jpy=100e3 * FX), 3352, 1, "同上"),
 ("FTMO Instant 100k + Mon4 ×3.3", dict(book=MON4, scale=3.3, floor="trail", mdd=0.10, dll=0.03, split=0.9, buf=0.05, gate=0.30, balance_jpy=100e3 * FX), 3352, 1, "同上"),
 ("FTMO Instant 100k + Mon4 ×2.0", dict(book=MON4, scale=2.0, floor="trail", mdd=0.10, dll=0.03, split=0.9, buf=0.05, gate=0.30, balance_jpy=100e3 * FX), 3352, 1, "同上"),
 ("FTMO Instant 50k + A 案 ×1.5", dict(book=A9, scale=1.5, floor="trail", mdd=0.10, dll=0.03, split=0.9, buf=0.05, gate=0.30, balance_jpy=50e3 * FX), 1676, 1, "同上"),
 ("FTMO Instant 100k + A 案 ×1.5・出金せず 36 か月(参考)", dict(book=A9, scale=1.5, floor="trail", mdd=0.10, dll=0.03, split=0.9, buf=9.0, balance_jpy=100e3 * FX), 3352, 1, "出金 0 で生存率だけ見る"),
 ("CTI Instant Funding 80k(開始残高 40k・DD $2,400 = 6% 静的・日次なし)+ A 案 ×1.5", dict(book=A9, scale=1.5, floor="static", mdd=0.06, dll=None, split=0.8, k=0.0, keep=0.1, balance_jpy=40e3 * FX), 1599, 1, "残高基準(含み損を数えない → 本 MC は equity 基準で保守側)。分配の基準値は未公表(VIP Bronze 90%)→ 0.8 仮置き。スケール(+10% で 80k・DD 3%)は取らない前提"),
 ("CTI Instant Funding 80k + A 案 ×1.0", dict(book=A9, scale=1.0, floor="static", mdd=0.06, dll=None, split=0.8, k=0.0, keep=0.1, balance_jpy=40e3 * FX), 1599, 1, "同上"),
 ("CTI Instant Funding 80k + Mon4 ×2.0", dict(book=MON4, scale=2.0, floor="static", mdd=0.06, dll=None, split=0.8, k=0.0, keep=0.1, balance_jpy=40e3 * FX), 1599, 1, "同上"),
 ("CTI Direct Funding 80k(DD $4,800 = 6% 静的)+ A 案 ×1.5", dict(book=A9, scale=1.5, floor="static", mdd=0.06, dll=None, split=0.8, k=0.0, keep=0.1, balance_jpy=80e3 * FX), 3999, 1, "同上・全額から開始"),
 ("Fintokei SwiftTrader 100k + A 案 ×1.5(評価 6%/60 日・DD 3% 静的・日次 2%・分配 90%・出金は +3% 以上)", dict(book=A9, scale=1.5, floor="static", mdd=0.03, dll=0.02, split=0.9, k=0.0, keep=0.0, pay_frac=1.0, min_pay=0.03, eval=dict(target=0.06, days=42, daycap=0.03), balance_jpy=100e3 * FX), 499, 1, "評価段あり(60 暦日)。資金化後は床が額面 −3% のまま・出金は全額(+3% 到達時)"),
 ("Fintokei SwiftTrader 100k + A 案 ×1.0", dict(book=A9, scale=1.0, floor="static", mdd=0.03, dll=0.02, split=0.9, k=0.0, keep=0.0, pay_frac=1.0, min_pay=0.03, eval=dict(target=0.06, days=42, daycap=0.03), balance_jpy=100e3 * FX), 499, 1, "同上"),
 ("Fintokei SwiftTrader 100k + Mon4 ×2.0", dict(book=MON4, scale=2.0, floor="static", mdd=0.03, dll=0.02, split=0.9, k=0.0, keep=0.0, pay_frac=1.0, min_pay=0.03, eval=dict(target=0.06, days=42, daycap=0.03), balance_jpy=100e3 * FX), 499, 1, "同上"),
 ("The5ers Hyper Growth 20k(6% 停止・日次 3%・分配 75%)+ A 案 ×1.5", dict(book=A9, scale=1.5, floor="static", mdd=0.06, dll=0.03, split=0.75, k=0.0, keep=0.1, balance_jpy=20e3 * FX), 260, 1, "初段から出金可と仮定(要確認)。上限 $40k/人。費用は目安"),
 ("The5ers Hyper Growth 20k + A 案 ×1.0", dict(book=A9, scale=1.0, floor="static", mdd=0.06, dll=0.03, split=0.75, k=0.0, keep=0.1, balance_jpy=20e3 * FX), 260, 1, "同上"),
 ("参考: The5ers High Stakes 100k + A 案 ×1.5(Q88 1 位・2 段階評価)", None, 545, 1, "docs/383: 到達 81%・失格 15%・36m 純 167 万・定常 18.1 万/月"),
]
if __name__ == "__main__":
    rows = []
    for nm, c, fee_usd, n_acc, note in CANDS:
        if c is None: continue
        r = simulate(c); fee = fee_usd * FX * n_acc / 1e4
        r.update(cand=nm, fee_usd=fee_usd, fee_man=fee, net36=r["pay36"] - fee, ev_per_fee=r["pay36"] / fee, annual_value=r["steady_m"] * 12, note=note); rows.append(r)
        print(f"{nm[:50]:<50} 資金化 {r['reach']:5.1f}% 失効 {r['expired']:4.1f}% 失格 {r['fail']:5.1f}% 生存36m {r['alive36']:5.1f}% | 出金 12m {r['pay12']:6.1f} 36m {r['pay36']:6.1f} 万(中央 {r['pay36_med']:6.1f}・0 {r['pay36_p0']:3.0f}%) 定常 {r['steady_m']:5.1f} 万/月 門繰越 {r['gate_skip']:3.0f}% | 費用 {fee:5.1f} 万 純 {r['net36']:6.1f} 万 {r['ev_per_fee']:4.1f}x")
    D = pd.DataFrame(rows); D.to_csv(os.path.join(ROOT, "results", "instant_candidates_2026-11.csv"), index=False); print("saved results/instant_candidates_2026-11.csv")
