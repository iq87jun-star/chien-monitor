# -*- coding: utf-8 -*-
"""
pstar_challenge_mc.py — 推奨P★(v4:35/v7:25/E-Mon:25/E5:15)でプロップ審査を回した時の通過月数MC。

手法(docs/24・p2_challenge_mc 同思想):
  - P★の月次リターン系列を再構築(リスク加重・等ボラ標準化)。
  - サイズS を「12ヶ月ブロックブートストラップの p95 年次maxDD」が目標(-6/-8/-10%)になるよう調整(=−10%枠適合)。
  - Phase1: 初期残高比 +8% 到達で通過 / 静的 −10% 抵触で失格(FundedNext Stellar 2-step・時間無制限)。
  - Phase2: +5% 到達で通過 / 同 −10%。
  - ブロックブートストラップ(block=3ヶ月)で月次パスを多数生成し、通過月数の分布・通過/失格率を出す。
規律: 数字は盛らない。月次解像度=月内スパイクは過小評価(EAの−9%フロア/日次ガードで実DQは別途低減)。
   Yahoo日足10年・近似。最終はDrive+デモで確定。"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from portfolio_optimize import aligned, znorm

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ["v7", "v4", "E5", "E-Mon"]
W = {"v4": .35, "v7": .25, "E-Mon": .25, "E5": .15}
RNG = np.random.default_rng(20260608)


def pstar_monthly():
    Z = znorm(aligned(NAMES))
    w = np.array([W[n] for n in NAMES])
    return (Z * w).sum(axis=1).dropna()


def block_paths(series, n_paths, horizon, block=3, seed=11):
    w = np.asarray(series, float); n = len(w)
    rng = np.random.default_rng(seed); P = np.empty((n_paths, horizon))
    for p in range(n_paths):
        seq = []
        while len(seq) < horizon:
            st = rng.integers(0, n)
            seq.extend(w[(st + k) % n] for k in range(block))
        P[p] = seq[:horizon]
    return P


def p95_annual_maxdd(series, scale, n_paths=4000):
    P = block_paths(series.values * scale, n_paths, 12, seed=3)
    dds = []
    for i in range(n_paths):
        eq = np.cumprod(1 + P[i]); dd = ((eq - np.maximum.accumulate(eq)) / np.maximum.accumulate(eq)).min()
        dds.append(dd)
    return float(np.percentile(dds, 5) * 100)


def find_scale(series, target_dd, lo=0.05, hi=6.0):
    for _ in range(40):
        mid = (lo + hi) / 2
        if p95_annual_maxdd(series, mid) <= target_dd:   # より悪い(負が大きい)
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def simulate(series, scale, target_gain, max_loss=0.10, n_paths=20000, cap_m=72, block=3, seed=7):
    """月次パスで +target_gain 到達(通過) vs −max_loss 抵触(失格)。通過月数分布を返す。"""
    P = block_paths(series.values * scale, n_paths, cap_m, block=block, seed=seed)
    months = []; passed = 0; failed = 0; timeout = 0
    for i in range(n_paths):
        eq = 1.0; done = False
        for m in range(cap_m):
            eq *= (1 + P[i, m])
            if eq <= 1.0 - max_loss:
                failed += 1; done = True; break
            if eq >= 1.0 + target_gain:
                passed += 1; months.append(m + 1); done = True; break
        if not done:
            timeout += 1
    months = np.array(months) if months else np.array([cap_m])
    return dict(pass_pct=round(passed / n_paths * 100, 1), fail_pct=round(failed / n_paths * 100, 1),
                timeout_pct=round(timeout / n_paths * 100, 1),
                med_month=int(np.median(months)), p25=int(np.percentile(months, 25)),
                p75=int(np.percentile(months, 75)), p90=int(np.percentile(months, 90)))


def main():
    s = pstar_monthly()
    ann = (1 + s).prod() ** (12 / len(s)) - 1
    print(f"P★ 月次系列: n={len(s)}  年率(素スケール)≈{ann*100:.1f}%  月次σ={s.std()*100:.2f}%")

    out = {}
    print("\n" + "=" * 92)
    print("P★ プロップ審査 通過月数MC（FundedNext Stellar 2-step・時間無制限・ブロックBS 2万パス）")
    print("=" * 92)
    print(f"{'サイズ(目標p95年DD)':22s}{'P1通過%':>8}{'P1失格%':>8}{'P1中央月':>9}{'P1 25-75%':>11}{'2段通過%':>9}{'2段中央月':>9}")
    for tag, tdd in [("保守 (−6%)", -6.0), ("中庸 (−8%)", -8.0), ("攻め (−10%)", -10.0)]:
        S = find_scale(s, tdd)
        p1 = simulate(s, S, 0.08)                      # Phase1 +8%
        p2 = simulate(s, S, 0.05, seed=23)             # Phase2 +5%(独立近似)
        # 2段通過率と合計中央月(P1通過かつP2通過の近似: 率は積, 月は中央の和)
        both_pct = round(p1["pass_pct"] / 100 * p2["pass_pct"] / 100 * 100, 1)
        both_med = p1["med_month"] + p2["med_month"]
        realized_dd = p95_annual_maxdd(s, S)
        out[tag] = dict(scale=round(S, 3), p95_annual_maxDD=round(realized_dd, 1), P1=p1, P2=p2,
                        both_pass_pct=both_pct, both_med_month=both_med)
        print(f"{tag:22s}{p1['pass_pct']:>8}{p1['fail_pct']:>8}{p1['med_month']:>9}"
              f"{str(p1['p25'])+'-'+str(p1['p75']):>11}{both_pct:>9}{both_med:>9}")

    print("\n[読み方] P1=Phase1(+8%) / 2段=Phase1→Phase2(+5%)通過。月=到達までの月数。")
    print("  時間無制限ゆえ『失格しなければいずれ通過』。保守ほど失格↓だが到達は遅い。")
    with open(os.path.join(HERE, "results", "pstar_challenge_mc.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/pstar_challenge_mc.json")


if __name__ == "__main__":
    main()
