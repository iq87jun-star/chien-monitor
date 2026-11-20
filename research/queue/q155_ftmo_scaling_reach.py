# -*- coding: utf-8 -*-
"""docs/244 週次アイデア束 #2 Q155(診断・セル 0): FTMO スケーリング到達確率。
対象: FTMO 50k 本口座 ×2(EA8 ×6 dyn1 k1.5 / EA3 ×6 dyn1 k1.5・現残高起点)。帳簿・乱数は forward/portfolio_sim と同じ(10.6 年・5 日ブロック・6,000 本)。
スケーリング条件(FTMO 公式「Reward Growth and Scaling Plan」2026-10-29 取得・docs/385 §1 に転記): 直近 4 か月に (a) 処理済み報酬 2 回以上、(b) 4 か月の純利益 ≥ 初期残高の 10%、(c) 残高が初期以上 → 残高 +25%(名目 ×1.25)・分配 80 → 90%。
出金規則は現行(毎月 1 日・基準 ×(1+keep) 超の pay_frac)。参考として keep / pay_frac の変形も出す(セルに数えない)。
使い方: cd research && python3 queue/q155_ftmo_scaling_reach.py"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)
from forward.portfolio_sim import *
FXR = 158.0; N = 6000; BLOCK = 5; MONTHS = 24; DAYS = 21 * MONTHS; SEED = 44
def run(spec, e0, k, keep, pf, mdd=0.10, dll=0.04, scaling=True, split0=0.8, split1=0.9, bal_jpy=50e3 * FXR):
    rng = np.random.default_rng(SEED); T = len(R(legs()["mon4"])); nb = T - BLOCK + 1
    stt = rng.integers(0, nb, size=(N, DAYS // BLOCK + 1)); IDX = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :DAYS]
    cf = R(book(spec))[IDX]
    e = np.full(N, e0); basel = np.ones(N); failed = np.zeros(N, bool); scale = np.ones(N); split = np.full(N, split0)
    paid = np.zeros((N, MONTHS)); npay = np.zeros((N, MONTHS), int); bal_m = np.zeros((N, MONTHS + 1)); bal_m[:, 0] = e0
    scaled_month = np.full(N, 10**6); n_scale = np.zeros(N, int); last_scale_m = np.full(N, -1)
    for t in range(DAYS):
        act = ~failed; fl = basel * (1 - mdd)
        f = np.clip(1 + k * ((e - fl) / basel - mdd) / mdd, 1.0, 1 + k)
        ret = np.clip(cf[:, t] * f, -dll, None); e = np.where(act, e * (1 + ret), e); failed |= act & (e <= fl)
        if (t + 1) % 21 == 0:
            m = (t + 1) // 21 - 1
            w = np.where(act & ~failed, np.maximum(e - basel * (1 + keep), 0.0) * pf, 0.0); paid[:, m] = w * bal_jpy * scale * split; npay[:, m] = (w > 0); e -= w
            bal_m[:, m + 1] = e
            if scaling and m >= 3:
                win_pay = npay[:, m - 3:m + 1].sum(1); win_profit = (e - bal_m[:, m - 3]) + paid[:, m - 3:m + 1].sum(1) / (bal_jpy * scale * split)
                ok = act & ~failed & (win_pay >= 2) & (win_profit >= 0.10) & (e >= basel) & (m - last_scale_m >= 4)
                scale = np.where(ok, scale * 1.25, scale); split = np.where(ok, split1, split); n_scale += ok; last_scale_m = np.where(ok, m, last_scale_m)
                scaled_month = np.where(ok & (scaled_month == 10**6), m + 1, scaled_month)
    first_pay = np.where(npay.any(1), npay.argmax(1) + 1, 10**6)
    out = dict(fail24=failed.mean() * 100, scale12=(scaled_month <= 12).mean() * 100, scale24=(scaled_month <= 24).mean() * 100, scale_med=(float(np.median(scaled_month[scaled_month < 10**6])) if (scaled_month < 10**6).any() else None),
               n_scale_mean=float(n_scale.mean()), firstpay_med=(float(np.median(first_pay[first_pay < 10**6])) if (first_pay < 10**6).any() else None), pay12=paid[:, :12].sum(1).mean() / 1e4, pay24=paid.sum(1).mean() / 1e4, pay24_med=float(np.median(paid.sum(1))) / 1e4, pay24_p0=(paid.sum(1) <= 0).mean() * 100)
    return out
if __name__ == "__main__":
    ACC = [("FTMO 50k 521100397(EA8 Mon4 ×6 dyn1 k1.5・現 +4.4%)", {"mon4": 6.0}, 1.044), ("FTMO 50k 531407058(EA3 Mon4 ×6 dyn1 k1.5・現 +3.4%)", {"mon4": 6.0}, 1.034)]
    VARS = [("現行(残し 20%・半分出金)", 1.5, 0.2, 0.5), ("参考: 残し 10%・半分", 1.5, 0.1, 0.5), ("参考: 残し 20%・全額", 1.5, 0.2, 1.0), ("参考: 残し 10%・全額", 1.5, 0.1, 1.0), ("参考: 残し 5%・全額", 1.5, 0.05, 1.0)]
    rows = []
    for an, spec, e0 in ACC:
        for vn, k, keep, pf in VARS:
            r1 = run(spec, e0, k, keep, pf, scaling=True); r0 = run(spec, e0, k, keep, pf, scaling=False)
            rows.append(dict(account=an, variant=vn, keep=keep, pay_frac=pf, **{f"s_{a}": b for a, b in r1.items()}, pay24_noscale=r0["pay24"], pay12_noscale=r0["pay12"], gain24=r1["pay24"] - r0["pay24"]))
            print(f"{an[:22]:<22} {vn:<16} 失格24m {r1['fail24']:4.1f}% | 初回出金 中央 {r1['firstpay_med'] or 0:4.0f} か月 | スケール 12m {r1['scale12']:4.1f}% 24m {r1['scale24']:4.1f}%(中央 {r1['scale_med'] or 0:4.0f} か月・平均回数 {r1['n_scale_mean']:.2f}) | 出金 24m {r1['pay24']:6.1f} 万(無し {r0['pay24']:6.1f} → +{r1['pay24']-r0['pay24']:5.1f})12m {r1['pay12']:5.1f}(無し {r0['pay12']:5.1f}) 中央 {r1['pay24_med']:5.1f} 0 {r1['pay24_p0']:.0f}%")
    pd.DataFrame(rows).to_csv(os.path.join(ROOT, "results", "q155_ftmo_scaling_reach.csv"), index=False); print("saved results/q155_ftmo_scaling_reach.csv")
