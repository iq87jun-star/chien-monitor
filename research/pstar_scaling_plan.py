# -*- coding: utf-8 -*-
"""
pstar_scaling_plan.py — 「更に上のプラン」= レバでなく資金スケールで収益を伸ばす試算。

docs/57で判明: 単一口座でレバを上げる超攻めは、失格(口座喪失)込みの期待手取りが×1.5で頭打ち→逆効果。
本当に"上"を狙う正攻法は【横スケール】= 口座を増やす/大きくする/別業者で並行/複利。各々を定量化:
  (A) 資金スケール(同P★を複数口座/大口座): 収益は線形、但し同戦略=失格は相関(同時に飛ぶ)。
  (B) 別業者で並行(P★ ∥ E-Mon主軸): 収益線形 + 失格が無相関(全口座同時喪失しない)=頑健に上。
  (C) 複利: 隔週出金を再投資し口座数を増やす多年トラジェクトリ。
前提(docs/57準拠): 中庸−8% 年率13.9% / 分配95% / ¥155 / FN funded $100k当たり 年¥2,047,133・失格1.4%。
規律: 数字は盛らない。業者の最大割当/口座数の上限・実コスト/出金は別途。Yahoo近似=Drive+デモで確定。"""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
PER100K_YEAR = 2047133      # 中庸-8%・分配95%・$100k の年手取り(docs/57)
PER100K_FAIL = 0.014        # 同 年失格
CONS_YEAR = 1513308         # 保守-6% の年手取り
CONS_FAIL = 0.002


def main():
    out = {}
    print("=" * 92)
    print("『更に上』= 資金スケール案（同P★・中庸−8%・分配95%・$100k=年¥2,047,133/失格1.4%基準）")
    print("=" * 92)

    # (A) 同P★を複数口座/大口座 — 収益線形・失格は相関(全口座同時に近い)
    print("\n(A) 資金スケール（同P★を増資/複数口座）：収益は線形、ただし同戦略ゆえ失格は相関")
    print(f"{'規模':22s}{'年手取り':>14}{'月手取り':>13}{'全損確率/年(相関)':>18}")
    tiers = [("$100k ×1 (現状想定)", 1), ("$200k 相当 ×2", 2), ("$300k ×3", 3), ("$500k ×5", 5), ("$1M ×10", 10)]
    for tag, n in tiers:
        y = PER100K_YEAR * n; m = y / 12
        # 同戦略=相関≈1ゆえ全口座が同時に−10%≈単口座失格率(全部まとめて飛ぶ)
        print(f"{tag:22s}{('¥'+format(y,',')):>14}{('¥'+format(round(m),',')):>13}{f'{PER100K_FAIL*100:.1f}%':>18}")
        out[f"A_{n}x"] = dict(year=y, month=round(m), all_fail=PER100K_FAIL)

    # (B) 別業者で並行(P★ ∥ E-Mon主軸): 失格が無相関(corr~0.07)
    print("\n(B) 別業者で並行（P★口座 ∥ E-Mon主軸口座, 相関0.07・docs/52）：収益線形＋失格は無相関")
    print("    例: FN $100k(P★) + FTMO $100k(E-Mon主軸) を中庸で")
    yB = PER100K_YEAR * 2
    print(f"    年手取り ¥{yB:,} / 月 ¥{round(yB/12):,} / 同時全損確率 ≈ {PER100K_FAIL**2*100:.3f}%(=1.4%²・ほぼ0)")
    print("    → 同じ2口座でも『同P★複製(全損1.4%)』より『並行(全損0.02%)』が安全に上。")
    out["B_parallel_2firm"] = dict(year=yB, month=round(yB / 12), simul_fail=PER100K_FAIL**2)

    # (C) 複利: 出金を再投資して口座を増やす(現実版: 新口座は審査~9ヶ月を要し、年に増やせる数に上限)
    print("\n(C) 複利（出金を再投資→口座追加, 中庸。★現実制約: 新口座は審査通過に中央~9ヶ月・")
    print("    年に追加できるのは資金と「通過待ち」で律速・業者の最大割当上限あり。年+1～2口座の堅実ランプ）")
    print(f"{'年':>4}{'稼働口座':>9}{'年手取り':>14}{'累計手取り':>15}")
    accounts = 1; cum = 0.0; MAX_ADD_PER_YEAR = 2; CAP = 5
    for yr in range(1, 6):
        y = PER100K_YEAR * accounts; cum += y
        print(f"{yr:>4}{accounts:>9}{('¥'+format(y,',')):>14}{('¥'+format(round(cum),',')):>15}")
        out[f"C_year{yr}"] = dict(accounts=accounts, year=y, cum=round(cum))
        accounts = min(CAP, accounts + MAX_ADD_PER_YEAR)   # 翌年の稼働数(審査通過ラグ込みの堅実値)
    print("    ※審査費は出金から十分賄える(月¥17万/口座 ≫ 審査費¥9万)。律速は資金でなく通過時間と業者上限。")

    print("\n[結論] 『更に上』はレバでなく資金スケール:")
    print("  ・同P★を増資/複数口座 → 収益は線形(口座数倍)・失格は1.4%のまま(超攻め16-68%より遥かに安全)。")
    print("  ・別業者で並行(P★∥E-Mon) → 収益線形＋同時全損≈0.02%=最も頑健に上。")
    print("  ・複利で口座を増やす → 数年で月収が階段状に増加(上限・実コスト内で)。")
    print("  ⚠ 業者の最大資金割当/口座数・出金/審査費・実コストは別途。エッジ持続前提=デモ必須。")

    with open(os.path.join(HERE, "results", "pstar_scaling_plan.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/pstar_scaling_plan.json")


if __name__ == "__main__":
    main()
