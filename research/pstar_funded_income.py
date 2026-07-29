# -*- coding: utf-8 -*-
"""
pstar_funded_income.py — 推奨P★を【本番(資金化)後】に各サイズで回した時の収益試算。

前段(pstar_challenge_mc)が「審査通過月数」。本書は通過後=funded口座での年収を、各サイズで出す。
funded口座 = FundedNext Stellar 2-step funded $100,000(目標なし・静的−10%で口座喪失)。
各サイズ(保守-6%/中庸-8%/攻め-10%/超攻め×1.5/×2/×3)について:
  - 年率%(scaled P★の幾何年率) / 年失格%(12ヶ月で−10%抵触する確率, block BS) /
  - 手取り(生存時) = 口座 × 年率 × 分配率 × 為替 / 月割り /
  - 期待手取り(失格で口座喪失を考慮) ≈ 手取り × (1 − 年失格)。
規律: 数字は盛らない。Yahoo近似・月次解像度(年失格は楽観側=月内/日次−5%で実際は高い)。為替/分配率は可変。
   絶対値はDrive+デモで確定。本番後は生存優先で保守推奨(docs/36)。"""
import os, sys, json, numpy as np, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pstar_challenge_mc import pstar_monthly, find_scale, block_paths, p95_annual_maxdd

HERE = os.path.dirname(os.path.abspath(__file__))

ACCOUNT_USD = 100000.0      # FN Stellar funded $100k
SPLIT = 0.95                # 分配率(FN base 80% + アドオン15% = 95%。ユーザー保有アドオン反映)
FX = 155.0                  # ¥/$ (可変)


def ann_return(series, scale):
    s = series.values * scale
    # 幾何年率(月次→年率): (Π(1+r))^(12/n) − 1
    g = np.prod(1 + s) ** (12 / len(s)) - 1
    return float(g)


def annual_fail(series, scale, n_paths=20000, max_loss=0.10, seed=5):
    """12ヶ月パスで、年初来ピークからの最大DDが−10%に達する確率(年失格)。"""
    P = block_paths(series.values * scale, n_paths, 12, seed=seed)
    fail = 0
    for i in range(n_paths):
        eq = np.cumprod(1 + P[i]); dd = (eq - np.maximum.accumulate(eq)) / np.maximum.accumulate(eq)
        if dd.min() <= -max_loss:
            fail += 1
    return fail / n_paths


def main():
    s = pstar_monthly()
    S10 = find_scale(s, -10.0)     # 攻め=p95年DD−10%の基準スケール
    levels = [("保守 (−6%)", find_scale(s, -6.0)),
              ("中庸 (−8%)", find_scale(s, -8.0)),
              ("攻め (−10%)", S10),
              ("超攻め ×1.5", S10 * 1.5),
              ("超攻め ×2.0", S10 * 2.0),
              ("超攻め ×3.0", S10 * 3.0)]

    print("=" * 104)
    print(f"P★ 本番(funded)後 収益試算  口座=${ACCOUNT_USD:,.0f} / 分配{SPLIT*100:.0f}% / 為替¥{FX}/$  (FN Stellar funded)")
    print("=" * 104)
    print(f"{'サイズ':14s}{'年率%':>8}{'年失格%':>9}{'手取り/月':>13}{'手取り/年':>13}{'期待手取り/年':>15}")
    out = {}
    for tag, S in levels:
        ar = ann_return(s, S)
        af = annual_fail(s, S)
        gross_y = ACCOUNT_USD * ar * SPLIT * FX
        gross_m = gross_y / 12
        exp_y = gross_y * (1 - af)        # 失格で口座喪失を粗く考慮
        out[tag] = dict(scale=round(S, 3), ann_return_pct=round(ar * 100, 1),
                        annual_fail_pct=round(af * 100, 1),
                        net_month_jpy=round(gross_m), net_year_jpy=round(gross_y),
                        exp_year_jpy=round(exp_y))
        print(f"{tag:14s}{ar*100:>8.1f}{af*100:>9.1f}{('¥'+format(round(gross_m),',')):>13}"
              f"{('¥'+format(round(gross_y),',')):>13}{('¥'+format(round(exp_y),',')):>15}")

    print("\n[読み方] 手取り/年=生存時(口座×年率×分配×為替)。期待手取り=失格で口座喪失を考慮(×(1−年失格))。")
    print("  ⚠ 年失格は月次解像度ゆえ楽観(日次−5%/月内で実際は高い)＝超攻めの期待値は表より低い。")
    print("  本番後は『生存優先で保守』が定石(docs/36)。超攻めは口座喪失・再挑戦前提の戦法。")
    print(f"\n  ※前提: 分配{SPLIT*100:.0f}%(base80%+アドオン15%)・為替¥{FX}(変動)・$100k口座。base80%なら×{0.80/SPLIT:.3f}・$50k口座は概ね半額。")

    with open(os.path.join(HERE, "results", "pstar_funded_income.json"), "w") as fp:
        json.dump(dict(account_usd=ACCOUNT_USD, split=SPLIT, fx=FX, levels=out),
                  fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/pstar_funded_income.json")


if __name__ == "__main__":
    main()
