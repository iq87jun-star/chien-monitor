"""実証検証レポート（python -m binary_options_edge.empirical_report）。

Yahoo公開データのみで検証A/B/Cを実行し、THEORY.mdの仮定を実測値で更新する。
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from . import empirical, theory


def main() -> None:
    print("# 実証検証レポート（原資産データのみ・IG気配不要）")
    sym = "JPY=X"  # USDJPY

    print("\nデータ取得中(Yahoo 60m×730d, 5m×60d)...")
    df60 = empirical.fetch_yahoo(sym, "730d", "60m")
    df5 = empirical.fetch_yahoo(sym, "60d", "5m")
    r60 = empirical.log_returns(df60, interval_seconds=3600.0)
    r5 = empirical.log_returns(df5, interval_seconds=300.0)
    print(f"USDJPY 60分足 {len(r60)}リターン ({df60.index.min():%Y-%m-%d}..{df60.index.max():%Y-%m-%d})")
    print(f"USDJPY 5分足  {len(r5)}リターン ({df5.index.min():%Y-%m-%d}..{df5.index.max():%Y-%m-%d})")

    # ------------------------------------------------------------------- #
    print("\n## 検証A: 日内ボラ季節性の実測（UTC時間帯別・全体平均比）")
    prof = empirical.seasonality_profile(r60)
    for _, row in prof.iterrows():
        bar = "#" * int(round(row["vol_factor"] * 20))
        print(f"  UTC{int(row['utc_hour']):>2} (JST{int(row['jst_hour']):>2}) "
              f"factor={row['vol_factor']:.2f} n={int(row['n']):>4} {bar}")
    key = {4: "東京昼(JST13)", 7: "ロンドン序盤(JST16)", 12: "NY朝/指標(JST21)",
           18: "NY午後(JST27=3)"}
    print("  主要時点: " + ", ".join(
        f"{v}={prof[prof['utc_hour'] == k]['vol_factor'].iloc[0]:.2f}"
        for k, v in key.items() if (prof['utc_hour'] == k).any()))
    lo = prof.loc[prof["vol_factor"].idxmin()]
    hi = prof.loc[prof["vol_factor"].idxmax()]
    ratio = hi["vol_factor"] / lo["vol_factor"]
    print(f"  最小 UTC{int(lo['utc_hour'])}={lo['vol_factor']:.2f} / "
          f"最大 UTC{int(hi['utc_hour'])}={hi['vol_factor']:.2f} → 最大比 {ratio:.2f}x")

    # ------------------------------------------------------------------- #
    print("\n## 検証B: ボラ予測可能性（H1必要条件テスト, 5分足60日）")
    ds = empirical.build_vol_dataset(r5, prof)
    fc = empirical.forecastability(ds)
    print(f"  標本: 学習{fc['n_train']} / 検証{fc['n_test']}時点")
    print(f"  OOS RMSE(logボラ): ナイーブ(trail1h)={fc['rmse_log_naive']:.3f}"
          f" 季節調整={fc['rmse_log_seasonal']:.3f} HAR+季節={fc['rmse_log_har']:.3f}")
    print(f"  ナイーブとの中央値乖離(実現/trail1h-1): {fc['median_abs_mismatch_naive']*100:.1f}%")
    print(f"  モデル対ナイーブの予測乖離 中央値: {fc['disagree_vs_naive_median']*100:.1f}%")
    print(f"    >6.2%(タッチs=6の必要優位)の頻度: {fc['disagree_gt_6.2%']*100:.0f}%")
    print(f"    >12.4%(ラダーs=6の必要優位)の頻度: {fc['disagree_gt_12.4%']*100:.0f}%")
    print(f"  モデル自身の残存誤差 中央値: {fc['model_residual_median']*100:.1f}%")
    print("  読み方: IGがナイーブなトレーリング価格付けなら、乖離頻度の分だけ機会がある。")
    print("  IGがHAR+季節相当なら、残る優位は「残存誤差の差」でありほぼゼロと考えるべき。")

    # ------------------------------------------------------------------- #
    print("\n## 検証C: イベントジャンプσ_Jの実測（60分足×2年）")
    cal = empirical.build_event_calendar(df60.index.min().date(),
                                        df60.index.max().date())
    ej = empirical.event_jump_hourly(r60, cal)
    spot = float(df60["close"].iloc[-1])
    for _, row in ej.iterrows():
        sj = row["sigma_j_log"]
        pips = sj * spot * 100  # 対数≈率, 1pip=0.01円
        # 実測σ_Jでの理論エッジ(2時間物, d=1.5, σ=年率実測を使用)
        sig_ann = float(np.sqrt(np.mean(r60**2)) * np.sqrt(365 * 24 * 3600 / 3600))
        st = theory.horizon_sigma(sig_ann, 7200.0)
        strike = spot * float(np.exp(1.5 * st))
        edge = theory.event_ladder_edge(spot, strike, sig_ann, 7200.0, sj)
        print(f"  {row['event']:>5}: n={int(row['n_events'])} "
              f"イベント時ボラ={row['vol_event_hour']*100:.3f}% "
              f"平常時={row['vol_base_hour']*100:.3f}% "
              f"→ σ_J={sj*100:.3f}% (≈{pips:.0f}pips)")
        print(f"         最大変動={row['max_abs_move']*100:.2f}% | "
              f"理論エッジ(2h物,d=1.5ラダー)={edge['edge_prob']*100:+.1f}pt "
              f"損益分岐spread={edge['breakeven_spread_points']:.1f}pt")

    print("\n## 検証C': 直近60日のイベント個別実測（発表後10分の変動, 5分足）")
    ej5 = empirical.event_jump_5m(r5, cal)
    for _, row in ej5.iterrows():
        print(f"  {row['event']:>5} {row['date']}: 10分変動={row['move_10min_log']*100:.2f}%"
              f" (≈{row['move_10min_log']*spot*100:.0f}pips)")

    print("\n(注: NFP/CPI日付は確度の高いもののみ。2025年10-12月は政府閉鎖の影響で除外。"
          "\n 日付誤りが混入した場合はσ_Jを過小評価する方向に働く=保守的)")


if __name__ == "__main__":
    main()
