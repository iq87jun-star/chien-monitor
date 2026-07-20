"""「ポイント(価格)だけを見てエントリーする」純粋ルールの構造的な帰結を実証するデモ。

python -m binary_options_edge.point_rule_demo

合成データ(エッジ無し・スプレッド6pt)上で:
  A. 純粋ポイントルール(「Xpt以下なら買う」「Xpt以上なら売る」)
  B. 価格帯フィルタ+確率モデル(本フレームの方式)
を比較する。Aは価格帯をどう選んでも平均−半スプレッド(−3pt)に収束するはず。
これは偶然ではなく恒等式: 買いEV = フェア − ask = −s/2(価格=損益分岐勝率のため)。
"""
from __future__ import annotations

import numpy as np

from .backtest import run_backtest, summarize
from .hypotheses import h_all, h_combine, h_point_band
from .synthetic import GBMUnderlying, make_contracts

SPREAD = 6.0


def main() -> None:
    print("# 純粋ポイントルール vs 価格帯フィルタ+モデル（合成・エッジ無し・s=6pt）")
    u = GBMUnderlying(days=30, seed=7)
    contracts = make_contracts(u, n=2000, assumed_spread=SPREAD, seed=11)
    print(f"合成提示 {len(contracts)}件\n")

    # ------------------------------------------------------------------- #
    print("## A. 純粋ポイントルール（モデルなし、価格だけでエントリー）")
    print(f"{'ルール':<24} {'n':>5} {'勝率':>7} {'損益分岐':>8} {'平均EV(pt)':>10}")
    for thr in (20.0, 35.0, 50.0, 65.0, 80.0):
        buys = [c for c in contracts if c.ask <= thr and c.settled_yes is not None]
        if buys:
            pnl = np.array([(100.0 if c.settled_yes else 0.0) - c.ask for c in buys])
            wr = float(np.mean([c.settled_yes for c in buys]))
            be = float(np.mean([c.ask for c in buys])) / 100.0
            print(f"{'買い: ask<=' + str(int(thr)) + 'pt':<24} {len(buys):>5} "
                  f"{wr:>6.1%} {be:>7.1%} {pnl.mean():>10.2f}")
        sells = [c for c in contracts if c.bid >= 100.0 - thr and c.settled_yes is not None]
        if sells:
            pnl = np.array([c.bid - (100.0 if c.settled_yes else 0.0) for c in sells])
            wr = float(np.mean([not c.settled_yes for c in sells]))
            be = float(np.mean([c.bid for c in sells])) / 100.0
            print(f"{'売り: bid>=' + str(int(100 - thr)) + 'pt':<24} {len(sells):>5} "
                  f"{wr:>6.1%} {be:>7.1%} {pnl.mean():>10.2f}")
    print("→ 勝率は常に損益分岐と同水準・平均EVは常に約−3pt(=−半スプレッド)。")
    print("  どの価格帯を選んでもこれは変わらない(価格=損益分岐勝率という恒等式)。\n")

    # ------------------------------------------------------------------- #
    print("## B. 価格帯フィルタ + 確率モデル（本フレームの方式）")
    print("正確なボラ推定(1h窓): モデル≈フェアなので取引ゼロが正解 /")
    print("ノイジーな推定(60s窓): 取引は発生するがエッジ無しなので−半スプレッドが正解\n")
    cases = (("全帯域+モデル", h_all()),
             ("7-25pt帯(+鏡像)+モデル", h_combine(h_all(), h_point_band(7, 25))),
             ("40-60pt帯(ATM)+モデル", h_combine(h_all(), h_point_band(40, 60, symmetric=False))))
    for vol_lb, tag in ((3600.0, "正確な推定"), (60.0, "ノイジー推定")):
        for label, hyp in cases:
            res = run_backtest(contracts, u, None, hyp,
                               vol_lookback_seconds=vol_lb, n_hypotheses_tried=6)
            s = summarize(res, label=label)
            ci = s["boot_ci95"]
            ci_str = (f"[{ci[0]:.2f},{ci[1]:.2f}]"
                      if isinstance(ci, tuple) and ci[0] == ci[0] else "[--]")
            print(f"  [{tag}] {label:<24} n={s['n_trades']:>4} "
                  f"平均EV={s['mean_pnl_points_after_cost']:>7.2f}pt "
                  f"CI95={ci_str} エッジ検出={s['edge_detected_after_cost']}")
    print("\n→ エッジ無しデータでは価格帯をどう組んでもエッジは出ない(正しい挙動)。")
    print("  価格帯フィルタの意味は『エッジが実在するときに、それが最も価格に出る帯")
    print("  (ボラ感応度最大の7-25pt/75-93pt)へ検証と執行を集中させる』こと。")


if __name__ == "__main__":
    main()
