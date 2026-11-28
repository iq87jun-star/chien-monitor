# -*- coding: utf-8 -*-
"""docs/244 週次アイデア束 #2 Q153(診断・セル 3): 出金サイクル {21, 10, 1} 営業日 × 「基準残高 +5% 残し」の 12 か月失格率と出金合計(docs/370 §5 A・Q134 docs/352 の拡張)。
枠組み: forward/portfolio_sim.run_portfolio と同じ同時シミュレーション(10.6 年・5 日ブロック・同じ相場経路)に出金頻度 freq を足したもの。
Q131(余裕比例 k)併用・pay_frac は現行 0.5。参考行として 保持 20%(現行)と pay_frac 1.0 も出す(参考行はセルに数えない)。
使い方: cd research && python3 queue/q153_payout_cycle_buffer.py"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from forward.portfolio_sim import *
def run_cycle(cfg, freq, keep, pf, N=6000, seed=44, months_after=12):
    g = cfg["global"]; k = g["k"]; start = pd.Timestamp(g["start"]); d0 = (pd.Timestamp(g["income_from"]) - start).days
    DAYS = int(d0 * 250 / 365) + 21 * months_after + 21; BLOCK = 5; rng = np.random.default_rng(seed)
    T = len(R(legs()["mon4"])); nb = T - BLOCK + 1; stt = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); IDX = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :DAYS]
    m0 = int(d0 * 250 / 365) // 21; t0 = m0 * 21; t1 = t0 + 21 * months_after; per = {}
    for a in cfg["accounts"]:
        if not a.get("active", True): continue
        ce = R(book(a["eval"]))[IDX]; cf = R(book(a["funded"]))[IDX]; e0 = a["e0"]; tg = a["targets"]; mdd = a["mdd"]; dll = a["dll"]; bal = a["balance_jpy"]
        kk = a.get("k", k); fn = a.get("funded_now", False); trail = a.get("trail", False)
        e = np.full(N, e0); basel = np.ones(N); stage = np.zeros(N, int); funded = np.full(N, fn); failed = np.zeros(N, bool); hwm = np.full(N, e0)
        paid = np.zeros(N); fail_t0 = np.zeros(N, bool); fund_t0 = np.zeros(N, bool)
        for t in range(DAYS):
            if t == t0: fail_t0 = failed.copy(); fund_t0 = funded.copy()
            act = ~failed; fl = np.minimum(hwm - mdd, 1.0) if (trail and not fn) else basel * (1 - mdd)
            if trail and fn: fl = basel * (1 - mdd)
            f = np.where(funded, np.clip(1 + kk * ((e - fl) / basel - mdd) / mdd, 1.0, 1 + kk), 1.0)
            ret = np.clip(np.where(funded, cf[:, t] * f, ce[:, t]), -dll, None); e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e); failed |= act & (e <= fl)
            if not fn:
                for s in range(len(tg)):
                    hit = act & ~failed & ~funded & (stage == s) & (e >= basel * (1 + tg[s]))
                    if s == len(tg) - 1: funded |= hit; e[hit] = 1.0; basel[hit] = 1.0; hwm[hit] = 1.0
                    else: stage[hit] = s + 1; basel[hit] = e[hit]
            if (t + 1) % freq == 0:
                w = np.where(funded & ~failed, np.maximum(e - basel * (1 + keep), 0.0) * pf, 0.0)
                if t0 <= t < t1: paid += w * bal * 0.8
                e -= w
        # 12 か月窓内の失格: 窓開始時に資金化済み・生存だった経路のうち、窓末までに失格した割合
        alive0 = fund_t0 & ~fail_t0; fw = (failed & alive0).sum() / max(alive0.sum(), 1)
        per[a["name"]] = dict(paid=paid, fail12=float(fw), funded0=float(alive0.mean()))
    return per
if __name__ == "__main__":
    cfg = json.load(open(os.path.join(ROOT, "config", "portfolio_current.json"), encoding="utf-8")); pf0 = cfg["global"].get("pay_frac", 1.0); keep0 = cfg["global"]["keep"]
    CELLS = [("セル 1: 月次(21 日)・残し 5%", 21, 0.05, pf0, True), ("セル 2: 隔週(10 日)・残し 5%", 10, 0.05, pf0, True), ("セル 3: 毎日(1 日)・残し 5%", 1, 0.05, pf0, True),
             (f"参考: 月次・残し {keep0*100:.0f}%(現行)", 21, keep0, pf0, False), (f"参考: 隔週・残し {keep0*100:.0f}%", 10, keep0, pf0, False), (f"参考: 毎日・残し {keep0*100:.0f}%", 1, keep0, pf0, False),
             ("参考: 月次・残し 5%・全額(pay_frac 1.0)", 21, 0.05, 1.0, False), ("参考: 毎日・残し 5%・全額(pay_frac 1.0)", 1, 0.05, 1.0, False)]
    rows = []; names = None
    for lab, fq, kp, pf, is_cell in CELLS:
        per = run_cycle(cfg, fq, kp, pf); names = list(per)
        tot = sum(v["paid"] for v in per.values()) / 1e4
        rows.append(dict(label=lab, cell=is_cell, freq=fq, keep=kp, pay_frac=pf, total_mean=round(tot.mean(), 1), total_p16=round(float(np.quantile(tot, .16)), 1), total_p50=round(float(np.quantile(tot, .5)), 1), total_p0=round(float((tot <= 0).mean()) * 100, 1),
                         **{f"fail12__{n}": round(v["fail12"] * 100, 1) for n, v in per.items()}, **{f"paid__{n}": round(v["paid"].mean() / 1e4, 1) for n, v in per.items()}))
        print(f"{lab:<40} 出金合計(12 か月・万円) 期待 {tot.mean():6.0f} | 16% 点 {np.quantile(tot,.16):6.0f} | 中央 {np.quantile(tot,.5):6.0f} | 0 の確率 {(tot<=0).mean()*100:4.1f}%")
        print("   失格 12 か月(資金化済み生存経路のうち): " + " | ".join(f"{n.split()[0]} {v['fail12']*100:4.1f}" for n, v in per.items()))
    D = pd.DataFrame(rows); D.to_csv(os.path.join(ROOT, "results", "q153_payout_cycle_buffer.csv"), index=False); print("saved results/q153_payout_cycle_buffer.csv")
