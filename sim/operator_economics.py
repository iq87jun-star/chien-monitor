#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
operator_economics.py — プロップファーム「運営側」収支モンテカルロ (docs/174)
==========================================================================

【目的】
  これまで挑戦者(利用者)側として蓄積した確率モデル(sim/montecarlo_2phase.py の
  通過率、docs/46/47 の資金化後 payout 実測アンカー)を「逆向き」に使い、
  もし自分がプロップファームを運営する側に回った場合の
    (1) 期待月次収支・累計収支
    (2) 参加費売上に対する出金(ペイアウト)比率
    (3) 初期資本ごとの 24ヶ月破綻確率(現金 < 0)
  を推計する。運営参入の採算判断・ルール設計の含意を得るのが目的。

【モデル骨子】(商品は $100k 2-step 1本に単純化。demo口座モデル=約定コストなし)
  ・毎月 SIGNUPS_M 人が参加費 FEE を払って購入。母集団は2タイプ:
      retail: 一般裁量層。通過率 7%(業界公表 5〜10% の中庸)、資金化後は
              月次 45% の確率で口座喪失(平均寿命 ~2.2ヶ月)、生存月の期待出金 $800。
      sharp : 本リポジトリの EA のような系統的トレーダー。
              通過率 90%(sim/montecarlo_2phase: win0.50 現実コストで 93.3% → 保守丸め)、
              失格 0.5%/月(docs/46/47 標準ティア fail_year 0.9%/年 → 保守に引上げ)、
              月次出金 $985(docs/46/47 標準 payout_year ¥1,856,446 ≒ $985/月・分配後)。
  ・チャレンジは購入から EVAL_MONTHS 後に合否確定。資金化時に参加費返金
    (REFUND_ON_FUND=True, FundedNext/Fintokei 型)。
  ・不合格者は翌月 rebuy_p で再購入(最大 max_buys 回)。資金化後に口座喪失した者も同様。
  ・運営コスト: 固定 OPEX_FIXED_M(テックプロバイダ+最小運営)+ 売上比 VAR_COST_PCT
    (カード決済+アフィリエイト)。
  ・月次総出金にはロット集中・相場環境による揺らぎとして lognormal 乗数(σ=0.35)。
  ・破綻判定: 初期資本 C0 + 累計収支が月末に負ならその路線は破綻。
    (実際は「累計P&Lの最小値 < −C0」で全 C0 を同一パス群から評価)

【シナリオ】
  naive   : 対策なし。sharp をそのまま受け入れる。
  defended: 運営防衛あり — スケーリング制/整合性ルール/口座数上限で sharp の
            実効月次出金を 50% に制限し、規約抵触リスクで sharp 失格 2%/月に上昇。
            (docs/170 の FN DLL失格のような「規約による排除」が現実に相当)

【何でないか】
  ・法務(金商法・賭博罪該当性・海外法人設計)・税務・決済審査は本モデルの外。
  ・EV(期待値)モデルであり保証ではない。SIGNUPS_M にほぼ線形にスケールする。
"""

import json
import math
import os
import random

SEED       = 20260729
N_PATHS    = 4000
HORIZON_M  = 24

# --- 商品 ---
FEE            = 500.0     # $100k 2-step 参加費 (FTMO €540 / FundedNext $549 / Fintokei ¥89,800 の丸め)
REFUND_ON_FUND = True      # 資金化時に参加費返金 (FN/Fintokei 型)
EVAL_MONTHS    = 2         # 購入→合否確定までの月数 (Phase1+2)

# --- 母集団 ---
TRADER = {
    "retail": dict(p_pass=0.07, payout_m=800.0, hazard_m=0.45,  rebuy_p=0.35, max_buys=3),
    "sharp":  dict(p_pass=0.90, payout_m=985.0, hazard_m=0.005, rebuy_p=0.90, max_buys=3),
}

# --- 運営 ---
SIGNUPS_M     = 300        # 新規購入者/月 (小規模ファーム定常。成長なし)
OPEX_FIXED_M  = 12_000.0   # テックプロバイダ+最小人件費/月
VAR_COST_PCT  = 0.15       # 決済手数料+アフィリエイト (参加費売上比)
PAYOUT_SIGMA  = 0.35       # 月次総出金の lognormal ゆらぎ

SHARP_SHARES  = [0.00, 0.01, 0.02, 0.03, 0.05, 0.10]
CAPITALS      = [50_000, 150_000, 300_000]

SCENARIOS = {
    "naive":    dict(sharp_payout_mult=1.0, sharp_hazard=0.005),
    "defended": dict(sharp_payout_mult=0.5, sharp_hazard=0.02),
}


# ----------------------------------------------------------------------------
# 乱数ヘルパ (stdlib のみ)
# ----------------------------------------------------------------------------
def _poisson(lam, rng):
    if lam <= 0:
        return 0
    if lam > 30:  # 正規近似
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def _binom(n, p, rng):
    if n <= 0 or p <= 0:
        return 0
    if p >= 1:
        return n
    var = n * p * (1 - p)
    if var > 9:                      # 正規近似
        return max(0, min(n, round(rng.gauss(n * p, math.sqrt(var)))))
    if p < 0.1 and n >= 25:          # ポアソン近似
        return min(n, _poisson(n * p, rng))
    return sum(1 for _ in range(n) if rng.random() < p)


def _lognorm_mult(sigma, rng):
    return math.exp(rng.gauss(-0.5 * sigma * sigma, sigma))


# ----------------------------------------------------------------------------
# 1タイプあたりの単体経済性 (決定論的な期待値再帰・24ヶ月地平)
# ----------------------------------------------------------------------------
def unit_economics(cfg, payout_mult=1.0, hazard=None):
    """初期顧客1人(初回購入者)あたりの、24ヶ月地平での運営側期待損益を返す。"""
    hz = cfg["hazard_m"] if hazard is None else hazard
    buyers  = {0: 1.0}    # 購入した月 -> 期待人数
    attempts = {0: 1}     # その購入が何回目か
    funded  = []          # (資金化月, 期待人数)
    fee_rev = 0.0
    refunds = 0.0
    payouts = 0.0
    n_buys  = 0.0

    pending = [(0, 1.0, 1)]  # (購入月, 人数, 購入回数)
    while pending:
        month, n, attempt = pending.pop()
        if month >= HORIZON_M:
            continue
        fee_rev += n * FEE
        n_buys  += n
        decide = month + EVAL_MONTHS
        if decide >= HORIZON_M:
            continue
        n_pass = n * cfg["p_pass"]
        n_fail = n - n_pass
        if REFUND_ON_FUND:
            refunds += n_pass * FEE
        # 資金化: decide 月から地平まで、生存期待値で出金
        alive = n_pass
        for m in range(decide, HORIZON_M):
            payouts += alive * cfg["payout_m"] * payout_mult
            dead = alive * hz
            alive -= dead
            # 口座喪失者の再購入
            if attempt < cfg["max_buys"] and m + 1 < HORIZON_M:
                pending.append((m + 1, dead * cfg["rebuy_p"], attempt + 1))
        # 不合格者の再購入
        if attempt < cfg["max_buys"] and decide + 1 < HORIZON_M:
            pending.append((decide + 1, n_fail * cfg["rebuy_p"], attempt + 1))

    margin = fee_rev * (1 - VAR_COST_PCT) - refunds - payouts
    return dict(fee_gross=fee_rev, refunds=refunds, payouts=payouts,
                buys=n_buys, margin=margin)


# ----------------------------------------------------------------------------
# 運営キャッシュフロー・モンテカルロ
# ----------------------------------------------------------------------------
def simulate_paths(sharp_share, scen, n_paths=N_PATHS, seed=SEED):
    rng = random.Random(seed + int(sharp_share * 1000) + hash(scen) % 1000)
    sc = SCENARIOS[scen]
    hazard = {"retail": TRADER["retail"]["hazard_m"], "sharp": sc["sharp_hazard"]}
    pmult  = {"retail": 1.0, "sharp": sc["sharp_payout_mult"]}

    min_pnl_dist, final_pnl_dist, payout_ratio_dist = [], [], []
    for _ in range(n_paths):
        funded = {"retail": 0, "sharp": 0}
        # eval_due[month] -> {type: (人数, 購入回数別リスト)} を単純化: (type, n, attempt)
        eval_due = {}
        rebuy_next = []           # (type, n, attempt) 翌月購入
        cum = 0.0
        min_cum = 0.0
        tot_fees, tot_payouts = 0.0, 0.0

        for m in range(HORIZON_M):
            # --- 購入 (新規 + 再購入) ---
            n_new = _poisson(SIGNUPS_M, rng)
            n_sharp = _binom(n_new, sharp_share, rng)
            buys = [("sharp", n_sharp, 1), ("retail", n_new - n_sharp, 1)] + rebuy_next
            rebuy_next = []
            for ttype, n, attempt in buys:
                if n <= 0:
                    continue
                cum += n * FEE * (1 - VAR_COST_PCT)
                tot_fees += n * FEE
                eval_due.setdefault(m + EVAL_MONTHS, []).append((ttype, n, attempt))

            # --- 合否確定 ---
            for ttype, n, attempt in eval_due.pop(m, []):
                n_pass = _binom(n, TRADER[ttype]["p_pass"], rng)
                n_fail = n - n_pass
                funded[ttype] += n_pass
                if REFUND_ON_FUND:
                    cum -= n_pass * FEE
                if attempt < TRADER[ttype]["max_buys"] and n_fail > 0:
                    nr = _binom(n_fail, TRADER[ttype]["rebuy_p"], rng)
                    if nr > 0:
                        rebuy_next.append((ttype, nr, attempt + 1))

            # --- 出金と口座喪失 ---
            for ttype in ("retail", "sharp"):
                alive = funded[ttype]
                if alive <= 0:
                    continue
                pay = alive * TRADER[ttype]["payout_m"] * pmult[ttype] \
                      * _lognorm_mult(PAYOUT_SIGMA, rng)
                cum -= pay
                tot_payouts += pay
                dead = _binom(alive, hazard[ttype], rng)
                funded[ttype] -= dead
                if dead > 0:
                    nr = _binom(dead, TRADER[ttype]["rebuy_p"], rng)
                    if nr > 0:
                        rebuy_next.append((ttype, nr, 2))  # 再購入(回数は概算)

            cum -= OPEX_FIXED_M
            min_cum = min(min_cum, cum)

        min_pnl_dist.append(min_cum)
        final_pnl_dist.append(cum)
        payout_ratio_dist.append(tot_payouts / tot_fees if tot_fees > 0 else 0.0)

    final_pnl_dist.sort()
    n = len(final_pnl_dist)

    def pct(dist, q):
        return dist[min(n - 1, int(q * n))]

    ruin = {str(c): sum(1 for v in min_pnl_dist if v < -c) / n for c in CAPITALS}
    # 破綻確率 1% に必要な初期資本 = −min_cum の 99パーセンタイル
    neg_min = sorted(-v for v in min_pnl_dist)
    cap_req_1pct = max(0.0, neg_min[min(n - 1, int(0.99 * n))])

    return dict(
        sharp_share=sharp_share,
        mean_final_pnl_24m=sum(final_pnl_dist) / n,
        p05_final_pnl_24m=pct(final_pnl_dist, 0.05),
        p50_final_pnl_24m=pct(final_pnl_dist, 0.50),
        mean_monthly_pnl=sum(final_pnl_dist) / n / HORIZON_M,
        payout_ratio=sum(payout_ratio_dist) / n,
        ruin_prob=ruin,
        capital_for_ruin_1pct=cap_req_1pct,
    )


def main():
    print("=" * 88)
    print("プロップファーム運営側 収支モンテカルロ (docs/174) — "
          f"参加費${FEE:.0f} / {SIGNUPS_M}人/月 / 地平{HORIZON_M}ヶ月 / {N_PATHS}パス")
    print("=" * 88)

    # --- 単体経済性と損益分岐 sharp 比率 ---
    print("\n[1] 初期顧客1人あたりの運営側期待損益 (24ヶ月地平・決定論EV)")
    unit = {}
    for scen, sc in SCENARIOS.items():
        u_r = unit_economics(TRADER["retail"])
        u_s = unit_economics(TRADER["sharp"],
                             payout_mult=sc["sharp_payout_mult"],
                             hazard=sc["sharp_hazard"])
        m_r, m_s = u_r["margin"], u_s["margin"]
        s_star = m_r / (m_r - m_s) if m_s < 0 else 1.0
        unit[scen] = dict(retail=u_r, sharp=u_s, breakeven_sharp_share=s_star)
        print(f"\n  ◆ シナリオ: {scen}")
        print(f"    {'タイプ':<8} {'購入回数':>8} {'参加費計':>10} {'返金':>10} "
              f"{'出金計':>12} {'運営マージン':>12}")
        for name, u in (("retail", u_r), ("sharp", u_s)):
            print(f"    {name:<8} {u['buys']:>8.2f} ${u['fee_gross']:>9,.0f} "
                  f"${u['refunds']:>9,.0f} ${u['payouts']:>11,.0f} ${u['margin']:>11,.0f}")
        print(f"    → 損益分岐 sharp 比率 s* = {s_star * 100:.2f}%  "
              f"(顧客の s* 超が sharp なら期待値ベースで赤字)")

    # --- 運営キャッシュフローMC ---
    results = {"config": dict(
        SEED=SEED, N_PATHS=N_PATHS, HORIZON_M=HORIZON_M, FEE=FEE,
        REFUND_ON_FUND=REFUND_ON_FUND, EVAL_MONTHS=EVAL_MONTHS,
        SIGNUPS_M=SIGNUPS_M, OPEX_FIXED_M=OPEX_FIXED_M,
        VAR_COST_PCT=VAR_COST_PCT, PAYOUT_SIGMA=PAYOUT_SIGMA,
        TRADER=TRADER, SCENARIOS=SCENARIOS, CAPITALS=CAPITALS),
        "unit_economics": unit, "grid": {}}

    for scen in SCENARIOS:
        print(f"\n[2] 運営キャッシュフローMC — シナリオ: {scen}")
        header = (f"  {'sharp比率':>8} | {'期待月次損益':>12} | {'24M累計(中央値)':>14} | "
                  f"{'24M累計(5%tile)':>14} | {'出金/売上':>8} | "
                  + " | ".join(f"破綻P(C0=${c/1000:.0f}k)" for c in CAPITALS)
                  + f" | {'破綻1%必要資本':>12}")
        print(header)
        rows = []
        for s in SHARP_SHARES:
            r = simulate_paths(s, scen)
            rows.append(r)
            ruins = " | ".join(f"{r['ruin_prob'][str(c)] * 100:>13.1f}%" for c in CAPITALS)
            print(f"  {s * 100:>7.0f}% | ${r['mean_monthly_pnl']:>11,.0f} | "
                  f"${r['p50_final_pnl_24m']:>13,.0f} | ${r['p05_final_pnl_24m']:>13,.0f} | "
                  f"{r['payout_ratio'] * 100:>7.1f}% | {ruins} | "
                  f"${r['capital_for_ruin_1pct']:>11,.0f}")
        results["grid"][scen] = rows

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "results", "operator_economics_results.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n結果JSON: {out}")


if __name__ == "__main__":
    main()
