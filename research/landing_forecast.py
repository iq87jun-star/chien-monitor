# -*- coding: utf-8 -*-
"""
landing_forecast.py — 月初の着地予測(4口座体制・docs/180 §3.5用)
====================================================================
月次採点(docs/180 §3)とセットで月初に実行する。入力は「現在地」だけ。
データ再取得なしで動く簡易版(docs/179の照合先の数字のみを使用)。

方法と限界(正直な注記):
  - Fintokei B案: docs/175B §2の月次系列×5/6(4.0x換算)を月単位ブートストラップし、
    期限(2026-10-31)までにステップ目標へ届く確率と着地分布を出す。
    月末判定の近似(月中ロック7.9到達を拾わない)=やや保守的。12点のみの系列で
    選定窓そのもの=楽観バイアス込み、という両方向の限界がある。額面で信じない。
  - FTMO A案: MC由来の中央ペース(hist_ann +25%/年 @1.25% ≈ 月+1.9%)での幾何外挿ETA。
    分布幅は出さない(正式にはrecentfit_mc.pyを現在残高で回す=要Yahoo再取得, docs/180 §3.5)。
  - FN 2口座: 研究値ペース(季節+18.6%/Instant +5.1%)との乖離チェックのみ。
  - 本予測は**情報提供のみ**。停止判断はdocs/180 §2の連続カウントで機械的に行い、
    予測を倍率・配置の変更根拠にしない(docs/179 §4)。

使い方例(2026-09月初、Fintokei進捗+2.3%・FTMOエクイティ$97,200):
  python landing_forecast.py --fintokei-progress 2.3 --months-to-expiry 2 \
      --ftmo-equity 97200 --fn100k-月利 1.2 --instant-月利 0.4
"""
import argparse
import numpy as np

# docs/175B §2の月次系列(4.8x)→ 4.0x換算(×5/6)。docs/180 §1の表と同一。
B_MONTHLY_48 = [1.9, 1.9, 11.5, 2.5, -1.5, 3.9, 6.8, -1.0, 10.4, 6.8, 3.0, -2.7]
B_MONTHLY_40 = [x * 5.0 / 6.0 for x in B_MONTHLY_48]

FTMO_BASELINE = 100_000.0
FTMO_TARGET_PCT = 10.0      # 利益目標$10,000(docs/178 §3で確定)
FTMO_FLOOR = 92_000.0       # EAフロア−8%
FTMO_MONTHLY_MEDIAN = 1.9   # hist_ann +25% @1.25% の月次換算(docs/175A §2)

N_PATH = 20_000
SEED = 20260731


def fintokei_landing(progress_pct: float, target_pct: float, months: int):
    """現在進捗%から、months ヶ月以内に累積 target_pct 到達する確率と着地分布。"""
    rng = np.random.default_rng(SEED)
    series = np.array(B_MONTHLY_40)
    draws = series[rng.integers(0, len(series), size=(N_PATH, months))]
    # 進捗は初期残高比%で管理(ロック判定と同じ基準)。複利で近似。
    eq = (1 + progress_pct / 100.0) * np.cumprod(1 + draws / 100.0, axis=1)
    prog = (eq - 1.0) * 100.0
    hit = (prog >= target_pct).any(axis=1)
    final = prog[:, -1]
    return {
        "p_hit%": round(float(hit.mean() * 100), 1),
        "final_median%": round(float(np.median(final)), 1),
        "final_p5%": round(float(np.percentile(final, 5)), 1),
        "final_p95%": round(float(np.percentile(final, 95)), 1),
    }


def ftmo_eta(equity: float):
    """中央ペース幾何外挿での目標到達ETA(月)とフロアまでの余白。"""
    target = FTMO_BASELINE * (1 + FTMO_TARGET_PCT / 100.0)
    gap_pct = (target / equity - 1.0) * 100.0
    eta = float(np.log(target / equity) / np.log(1 + FTMO_MONTHLY_MEDIAN / 100.0))
    floor_margin_pct = (equity / FTMO_FLOOR - 1.0) * 100.0
    return {"残り%": round(gap_pct, 2), "中央ペースETAヶ月": round(eta, 1),
            "フロア余白%": round(floor_margin_pct, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fintokei-progress", type=float, default=None,
                    help="Fintokei現在進捗%%(初期残高比。例 2.3)")
    ap.add_argument("--fintokei-target", type=float, default=8.0,
                    help="現ステップ目標%%(S1=8 / S2=6)")
    ap.add_argument("--months-to-expiry", type=int, default=None,
                    help="B案期限2026-10-31までの残り月数")
    ap.add_argument("--ftmo-equity", type=float, default=None,
                    help="FTMO現在エクイティ$(例 96580)")
    ap.add_argument("--fn100k-月利", type=float, default=None, dest="fn100k",
                    help="FN100k 前月実測月利%%")
    ap.add_argument("--instant-月利", type=float, default=None, dest="instant",
                    help="FN Instant 前月実測月利%%")
    a = ap.parse_args()

    print("=== 着地予測(簡易・情報提供のみ。停止判断はdocs/180 §2の連続カウントで) ===")
    if a.fintokei_progress is not None and a.months_to_expiry is not None:
        r = fintokei_landing(a.fintokei_progress, a.fintokei_target, a.months_to_expiry)
        print(f"[Fintokei B案] 進捗{a.fintokei_progress:+.1f}% → 期限まで{a.months_to_expiry}ヶ月で "
              f"目標+{a.fintokei_target}%到達確率 {r['p_hit%']}% / "
              f"期限時点の着地 中央{r['final_median%']:+.1f}% (5-95%: "
              f"{r['final_p5%']:+.1f}〜{r['final_p95%']:+.1f}%)")
        print("  ⚠ 12点系列ブートストラップ(選定窓=楽観込み・月末判定=保守)。額面で信じない。")
    if a.ftmo_equity is not None:
        r = ftmo_eta(a.ftmo_equity)
        print(f"[FTMO A案] equity ${a.ftmo_equity:,.0f} → 目標$110,000まで残り{r['残り%']}% / "
              f"中央ペース(月+{FTMO_MONTHLY_MEDIAN}%)ETA {r['中央ペースETAヶ月']}ヶ月 / "
              f"フロア$92kまで余白{r['フロア余白%']}%")
        print("  ※分布付きの正式版はrecentfit_mc.pyを現在残高で再実行(要データ再取得)。")
    if a.fn100k is not None:
        print(f"[FN100k 季節1.0x] 実測{a.fn100k:+.1f}%/月 vs 研究値ペース+1.4%/月(年+18.6%・LOYO正直値≈2/3)")
    if a.instant is not None:
        print(f"[FN Instant PD1.0x] 実測{a.instant:+.1f}%/月 vs 研究値ペース+0.4%/月(年+5.1%・昇格中央19ヶ月)")


if __name__ == "__main__":
    main()
