# -*- coding: utf-8 -*-
"""docs/322 Q88(診断・セル 0): 11 月の購入候補を同じ MC で比較(ユーザー 2026-10-28「Q88 を実施してください」で前倒し)。
枠組み: forward/portfolio_sim と同じ帳簿(10.6 年・5 日ブロック・同じ乱数)で、購入日 2026-11-02 から 18 か月を各候補 1 口座で同時シミュレーション。
評価(目標・静的 / トレーリング床・EA 日次ガード)→ 資金化(額面から再出発・Q131 余裕比例 k・残し 20%・毎月 超過分の半分を出金・分配率)。
E8 One は本口座の出金関門(最良日の利益 ≤ 総利益の 40%)を月次出金に適用。指標: 到達 / 失格 / 中央到達日・12 か月と 18 か月の期待出金(円・分配後)・費用あたり。
使い方: cd research && python3 queue/q88_purchase_mc_2026-11.py"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from forward.portfolio_sim import *
# GER40 ブレイク(EA10S 用・q52 のドンチャン 120・トレイル出口)
try:
    q = open(os.path.join(ROOT, "queue", "q52_donchian_vs_hold.py"), encoding="utf-8").read().split("cum = int(sys.argv[1])")[0]
    qn = {"__name__": "q52"}; exec(compile(q, "q52", "exec"), qn); BRK = on_cal(qn["donchian"]("GER40", 120, "trail"))
except Exception as e:
    print("GER40 ブレイク無し:", e); BRK = legs()["mon4"] * 0
legs()["brk"] = BRK
FX = 158.0; N = 6000; BLOCK = 5; MONTHS = 36; DAYS = 21 * MONTHS; SEED = 44
def simulate(c, bestday_gate=None):
    """c: dict(eval, funded, targets, mdd, dll, trail, k, keep, pay_frac, split, balance_jpy). 戻り: dict"""
    rng = np.random.default_rng(SEED); T = len(R(legs()["mon4"])); nb = T - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); IDX = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :DAYS]
    ce = R(book(c["eval"]))[IDX]; cf = R(book(c["funded"]))[IDX]; tg = c["targets"]; mdd = c["mdd"]; dll = c["dll"]; bal = c["balance_jpy"]
    kk = c["k"]; kp = c["keep"]; pf = c["pay_frac"]; sp = c["split"]; trail = c.get("trail", False)
    e = np.ones(N); basel = np.ones(N); stage = np.zeros(N, int); funded = np.zeros(N, bool); failed = np.zeros(N, bool); hwm = np.ones(N)
    reach_day = np.full(N, 10**6); paid = np.zeros((N, MONTHS)); cum_since = np.zeros(N); best_since = np.zeros(N); gate_skips = 0
    for t in range(DAYS):
        act = ~failed
        fl = np.minimum(hwm - mdd, 1.0) if (trail and True) else basel * (1 - mdd)
        if trail: fl = np.where(funded, np.minimum(hwm - mdd, 1.0), np.minimum(hwm - mdd, 1.0))
        f = np.where(funded, np.clip(1 + kk * ((e - fl) / basel - mdd) / mdd, 1.0, 1 + kk), 1.0)
        ret = np.clip(np.where(funded, cf[:, t] * f, ce[:, t]), -dll, None)
        e_prev = e.copy(); e = np.where(act, e * (1 + ret), e); hwm = np.maximum(hwm, e); failed |= act & (e <= fl)
        d = np.where(act & funded, e - e_prev, 0.0); cum_since += d; best_since = np.maximum(best_since, d)
        for s in range(len(tg)):
            hit = act & ~failed & ~funded & (stage == s) & (e >= basel * (1 + tg[s]))
            if s == len(tg) - 1: funded |= hit; reach_day[hit] = t + 1; e[hit] = 1.0; basel[hit] = 1.0; hwm[hit] = 1.0
            else: stage[hit] = s + 1; basel[hit] = e[hit]
        if (t + 1) % 21 == 0:
            m = (t + 1) // 21 - 1; w = np.where(funded & ~failed, np.maximum(e - basel * (1 + kp), 0.0) * pf, 0.0)
            if bestday_gate is not None:
                blocked = (w > 0) & (best_since > bestday_gate * np.maximum(cum_since, 1e-9)); gate_skips += int(blocked.sum()); w = np.where(blocked, 0.0, w)
            paid[:, m] = w * bal * sp; e -= w
            pay = w > 0; cum_since[pay] = 0.0; best_since[pay] = 0.0
    reach = funded.mean(); fail = failed.mean(); fail_eval = (failed & ~funded).mean(); fail_funded = (failed & funded).mean()
    rd = reach_day[funded]; p12 = paid[:, :12].sum(1); p18 = paid[:, :18].sum(1); p36 = paid.sum(1)
    # 資金化後の定常月次(資金化 13〜24 か月目の平均出金・資金化した経路のみ・失格後は 0)
    steady = []
    for i in np.flatnonzero(funded):
        m0 = int(reach_day[i] // 21) + 12
        if m0 + 12 <= MONTHS: steady.append(paid[i, m0:m0 + 12].mean())
    steady_m = float(np.mean(steady)) / 1e4 if steady else 0.0
    return dict(reach=reach * 100, fail=fail * 100, fail_eval=fail_eval * 100, fail_funded=fail_funded * 100, reach_med_days=(float(np.median(rd)) if len(rd) else None),
                reach_p16_days=(float(np.quantile(rd, .16)) if len(rd) else None), pay12=p12.mean() / 1e4, pay18=p18.mean() / 1e4, pay36=p36.mean() / 1e4, pay36_med=float(np.median(p36)) / 1e4,
                pay36_p0=(p36 <= 0).mean() * 100, steady_m=steady_m, n_steady=len(steady), gate_skip_rate=(gate_skips / max(1, (paid > 0).sum() + gate_skips)) * 100)
CANDS = [
 ("FTMO Std 100k + EA10S ×2.0(Mon4 2.0・GER40 ブレイク 1.2・Hold XAU 0.18)", dict(eval={"mon4": 2.0, "brk": 1.2, "holdxau": 0.18}, funded={"mon4": 2.0, "brk": 1.2, "holdxau": 0.18}, targets=[0.10, 0.05], mdd=0.10, dll=0.048, trail=False, k=1.5, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=100e3 * FX), 540, 1, "FTMO 残枠 $100k。審査料は初回出金で返金(表の費用は返金前)。EA 可・週末不可(Hold XAU は平日のみの近似)"),
 ("FTMO Std 100k + EA10 ×3.3(参考・旧指定)", dict(eval={"mon4": 3.3, "brk": 2.0, "holdxau": 0.3}, funded={"mon4": 3.3, "brk": 2.0, "holdxau": 0.3}, targets=[0.10, 0.05], mdd=0.10, dll=0.04, trail=False, k=1.5, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=100e3 * FX), 540, 1, "参考(Q85 で失格 7 倍)"),
 ("FN Stellar 2-Step 25k ×3 + Mon4 ×3.3(EA3 型)", dict(eval={"mon4": 3.3}, funded={"mon4": 3.3}, targets=[0.08, 0.05], mdd=0.10, dll=0.04, trail=False, k=1.5, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=25e3 * FX), 160, 3, "FN 残枠 $80k・EA は $50k 未満のみ(docs/185 §10b)。公式ページは「EA/VPS はアドオン」表記 → 購入前に書面確認。審査料は初回出金で返金"),
 ("The5ers High Stakes 100k + A 案 ×1.5(Hold XAU + Mon GBPJPY + Mon NAS100)", dict(eval={"a9": 1.5}, funded={"a9": 1.5}, targets=[0.10, 0.05], mdd=0.10, dll=0.05, trail=False, k=1.5, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=100e3 * FX), 545, 1, "設立 2016・Trustpilot 4.7。各段「+0.5% の日 ×3」が必要(未モデル)。指標 ±2 分禁止。EA は自作ソースの書面承認"),
 ("The5ers High Stakes 100k + Mon4 ×3.3", dict(eval={"mon4": 3.3}, funded={"mon4": 3.3}, targets=[0.10, 0.05], mdd=0.10, dll=0.05, trail=False, k=1.5, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=100e3 * FX), 545, 1, "同上(Mon 族の比率は上げない方針 docs/318 §2 に注意)"),
 ("E8 One 100k DD6(目標 6%)+ Mon4 ×3.3", dict(eval={"mon4": 3.3}, funded={"mon4": 3.3}, targets=[0.06], mdd=0.06, dll=0.04, trail=True, k=1.5, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=100e3 * FX), 488, 1, "トレーリング 6%(残高 EOD・初期でロック)。本口座は最良日 ≤40% の出金関門(モデル化)・指標 ±5 分禁止。Trustpilot 停止"),
 ("E8 One 100k DD6(目標 6%)+ A 案 ×1.5", dict(eval={"a9": 1.5}, funded={"a9": 1.5}, targets=[0.06], mdd=0.06, dll=0.04, trail=True, k=1.5, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=100e3 * FX), 488, 1, "同上"),
 ("E8 One 100k DD10(目標 10%)+ A 案 ×1.5", dict(eval={"a9": 1.5}, funded={"a9": 1.5}, targets=[0.10], mdd=0.10, dll=0.04, trail=True, k=1.5, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=100e3 * FX), 560, 1, "同上(DD 10% 選択・$560)"),
 ("CTI 2-Step 100k + A 案 ×1.5", dict(eval={"a9": 1.5}, funded={"a9": 1.5}, targets=[0.10, 0.05], mdd=0.10, dll=0.05, trail=False, k=1.5, keep=0.2, pay_frac=0.5, split=0.8, balance_jpy=100e3 * FX), 549, 1, "静的 10%(残高基準・含み損を数えない → 本 MC は equity 基準で保守側)。小規模・解約報告あり"),
]
if __name__ == "__main__":
    rows = []
    for nm, c, fee_usd, n_acc, note in CANDS:
        r = simulate(c, bestday_gate=(0.40 if nm.startswith("E8") else None))
        fee = fee_usd * FX * n_acc / 1e4
        for k_ in ("pay12", "pay18", "pay36", "pay36_med", "steady_m"): r[k_] = r[k_] * n_acc
        r.update(cand=nm, fee_usd=fee_usd, n=n_acc, fee_man=fee, net36=r["pay36"] - fee, ev_per_fee=r["pay36"] / fee, annual_value=r["reach"] / 100 * r["steady_m"] * 12, note=note); rows.append(r)
        print(f"{nm[:44]:<44} 到達 {r['reach']:4.1f}% 失格 {r['fail']:4.1f}%(評価 {r['fail_eval']:.1f}/資金化後 {r['fail_funded']:.1f}) 中央 {r['reach_med_days'] or 0:4.0f} 日 | 出金 12m {r['pay12']:5.1f} 18m {r['pay18']:5.1f} 36m {r['pay36']:6.1f} 万(0 {r['pay36_p0']:.0f}%) 定常 {r['steady_m']:4.1f} 万/月 年価値 {r['annual_value']:5.1f} | 費用 {fee:4.1f} → 純 {r['net36']:6.1f}・{r['ev_per_fee']:4.1f}x 関門 {r['gate_skip_rate']:.0f}%")
    D = pd.DataFrame(rows); D.to_csv(os.path.join(ROOT, "results", "q88_purchase_mc_2026-11.csv"), index=False); print("saved results/q88_purchase_mc_2026-11.csv")
