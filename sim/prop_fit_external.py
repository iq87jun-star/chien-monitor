#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prop_fit_external.py — 外部戦略の「プロップ規則適合性」検証 (docs/185)
====================================================================

【問い】 docs/184 で一次通過した外部戦略(ELW/PKR)を、これまで自EAに課してきた
  プロップ規則(2段階チャレンジ・日次5%・最大10%)にはめた場合、使い物になるか。

【方法 = Tier C(統計プロファイル検証)】
  ロジック非開示でも、Darwinex はリスク標準化済みのため年率μ/σが既知。
  戦略を統計過程(日次正規+テールショック混合)として近似し、
  sim/montecarlo_2phase.py と同じ規則構成で通過率・失格率・期待ペイアウトを推計する。
  レバレッジ倍率(自EAのPD倍率研究と同型)もグリッド評価する。

【規則】(FN Stellar 2-step $100k 相当・自リポの慣例に整合)
  P1 +8% / P2 +5%、日次損失5%(日初比・終値評価)、静的フロア−10%、
  各Phase 90営業日上限、最短5取引日。資金化後: 月末に利益全額出金(分配80%)、
  月内に−10%抵触で口座喪失。

【限界(正直に)】
  ・正規+テール混合の近似。実戦略の歪度/自己相関は再現しない。
  ・日次損失は終値評価(ザラ場割れを見ない)→ 失格率をやや過小評価。
  ・VaR標準化は Darwinex 口座上の姿。原戦略をプロップ口座に載せた時の
    執行・コスト差は含まない。
  → 本結果は「一次スクリーニング」。最終判定は Tier B/A(挙動再現/ロジック開示)が必要。
"""

import json
import math
import os
import random

SEED    = 20260730
N_SIMS  = 20_000
USDJPY  = 157.0

# --- 規則 ---
ACCT        = 100_000.0
P1_TARGET   = 0.08
P2_TARGET   = 0.05
DAILY_LOSS  = 0.05
MAX_LOSS    = 0.10
MAX_DAYS    = 90
MIN_DAYS    = 5
SPLIT       = 0.80
FUNDED_MONTHS = 12          # 資金化後の評価地平
DPM         = 21            # 営業日/月

# --- テールショック(保守化): 2%の日に損失3倍 ---
P_TAIL    = 0.02
TAIL_MULT = 3.0

# --- 候補(docs/184 通過組) + 自EAアンカー ---
SIGMA_A = 0.065 / 1.645 * math.sqrt(12.0)   # Darwinex VaR標準化 ≈ 13.7%
CANDIDATES = [
    dict(name="ELW",  ann_ret=0.1562, sigma_a=SIGMA_A),
    dict(name="PKR",  ann_ret=0.1008, sigma_a=SIGMA_A),
]
MULTS = [1.0, 1.5, 2.0, 3.0]

RNG = random.Random(SEED)


def day_ret(mu_d, sg_d, rng):
    r = rng.gauss(mu_d, sg_d)
    if r < 0 and rng.random() < P_TAIL:
        r *= TAIL_MULT
    return r


def run_phase(target, mu_d, sg_d, rng):
    """1 Phase を回し (結果, 日数) を返す。結果: pass/dd/daily/timeout"""
    eq = 1.0
    for day in range(1, MAX_DAYS + 1):
        r = day_ret(mu_d, sg_d, rng)
        if r <= -DAILY_LOSS:
            return "daily", day
        eq *= (1.0 + r)
        if eq <= 1.0 - MAX_LOSS:
            return "dd", day
        if eq >= 1.0 + target and day >= MIN_DAYS:
            return "pass", day
    return "timeout", MAX_DAYS


def run_funded(mu_d, sg_d, rng, months=FUNDED_MONTHS):
    """資金化後: 月次出金・-10%で喪失。(総出金[口座比], 生存月数, 喪失有無)"""
    total = 0.0
    for m in range(months):
        eq = 1.0
        for _ in range(DPM):
            r = day_ret(mu_d, sg_d, rng)
            if r <= -DAILY_LOSS:
                return total, m, True
            eq *= (1.0 + r)
            if eq <= 1.0 - MAX_LOSS:
                return total, m, True
        if eq > 1.0:
            total += (eq - 1.0) * SPLIT
    return total, months, False


def evaluate(name, ann_ret, sigma_a, mult):
    mu_d = ann_ret * mult / 252.0
    sg_d = sigma_a * mult / math.sqrt(252.0)
    rng = random.Random(SEED + hash_stable(name) + int(mult * 10))

    seq_pass = fail_dd = fail_daily = timeout = 0
    days_sum = 0
    payouts = []
    lost_funded = 0
    for _ in range(N_SIMS):
        r1, d1 = run_phase(P1_TARGET, mu_d, sg_d, rng)
        if r1 == "pass":
            r2, d2 = run_phase(P2_TARGET, mu_d, sg_d, rng)
        else:
            r2, d2 = r1, 0
        if r1 == "pass" and r2 == "pass":
            seq_pass += 1
            days_sum += d1 + d2
            pay, _, lost = run_funded(mu_d, sg_d, rng)
            payouts.append(pay)
            lost_funded += int(lost)
        else:
            key = r2 if r1 == "pass" else r1
            if key == "dd":
                fail_dd += 1
            elif key == "daily":
                fail_daily += 1
            else:
                timeout += 1

    n = N_SIMS
    pass_pct = seq_pass / n * 100
    avg_pay = (sum(payouts) / len(payouts)) if payouts else 0.0
    return dict(
        name=name, mult=mult,
        seq_pass_pct=pass_pct,
        fail_dd_pct=fail_dd / n * 100,
        fail_daily_pct=fail_daily / n * 100,
        timeout_pct=timeout / n * 100,
        avg_days_pass=(days_sum / seq_pass) if seq_pass else None,
        funded_loss_12m_pct=(lost_funded / seq_pass * 100) if seq_pass else None,
        payout_12m_jpy=avg_pay * ACCT * USDJPY,
        ev_12m_jpy=pass_pct / 100 * avg_pay * ACCT * USDJPY,
    )


def hash_stable(s):
    return sum(ord(c) * (i + 1) for i, c in enumerate(s))


def main():
    print("=" * 100)
    print("外部戦略のプロップ規則適合性 (docs/185) — Tier C: 統計プロファイル検証 / "
          f"FN 2-step型 / {N_SIMS}パス")
    print("=" * 100)
    print("\n  規則: P1+8%/P2+5%・日次5%・静的-10%・90日/Phase。資金化後12ヶ月・月次全額出金(80%)")
    print(f"  {'戦略':<6} {'倍率':>4} | {'通過率':>7} | {'DD失格':>7} {'日次失格':>7} {'期限切れ':>7} | "
          f"{'平均日数':>7} | {'資金化後12M喪失':>12} | {'12M期待出金(通過時)':>16} | {'無条件EV/12M':>12}")

    results = []
    for c in CANDIDATES:
        for mult in MULTS:
            r = evaluate(c["name"], c["ann_ret"], c["sigma_a"], mult)
            results.append(r)
            print(f"  {r['name']:<6} {r['mult']:>3.1f}x | {r['seq_pass_pct']:>6.1f}% | "
                  f"{r['fail_dd_pct']:>6.1f}% {r['fail_daily_pct']:>6.1f}% {r['timeout_pct']:>6.1f}% | "
                  f"{(r['avg_days_pass'] or 0):>6.0f}日 | "
                  f"{(r['funded_loss_12m_pct'] or 0):>11.1f}% | "
                  f"¥{r['payout_12m_jpy']:>14,.0f} | ¥{r['ev_12m_jpy']:>10,.0f}")
        print()

    print("  [参考アンカー] 自EA(docs/46/47 標準): 通過~93%・年間ペイアウト¥1,856,446・年失格0.9%")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "prop_fit_external.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"config": dict(SEED=SEED, N_SIMS=N_SIMS, rules=dict(
            P1=P1_TARGET, P2=P2_TARGET, daily=DAILY_LOSS, maxloss=MAX_LOSS,
            max_days=MAX_DAYS, split=SPLIT, tail=dict(p=P_TAIL, mult=TAIL_MULT)),
            sigma_a=SIGMA_A, USDJPY=USDJPY),
            "grid": results}, f, ensure_ascii=False, indent=2)
    print(f"\n結果JSON: {out}")


if __name__ == "__main__":
    main()
