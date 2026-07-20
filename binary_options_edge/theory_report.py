"""理論深堀りの数表を出力するレポート（python -m binary_options_edge.theory_report）。

THEORY.md の本文が引用する数値はすべてここから再現できる。
"""
from __future__ import annotations

from . import theory


def _hdr(title: str) -> None:
    print(f"\n## {title}")


def main() -> None:
    print("# IG証券バイナリー 理論深堀り 数表")

    # ------------------------------------------------------------------- #
    _hdr("1. 満期までの標準的な値動き幅 σ√T（対数リターン標準偏差, %）")
    print(f"{'年率ボラ':>8} | {'60秒':>8} {'5分':>8} {'1時間':>8} {'2時間':>8}")
    for sig in (0.08, 0.10, 0.12):
        row = [theory.horizon_sigma(sig, t) * 100
               for t in (60, 300, 3600, 7200)]
        print(f"{sig:>7.0%} | " + " ".join(f"{v:>7.3f}%" for v in row))
    print("(参考: USDJPY=150円なら 0.151% ≈ 22.7pips)")

    # ------------------------------------------------------------------- #
    _hdr("2. 構造別のボラ感応度 |∂p/∂lnσ|（相対ボラ誤差1%あたりの確率誤差pt）")
    print(f"{'規格化距離':>10} | {'ラダー':>8} {'タッチ':>8} {'対称レンジ':>10}")
    for x in (0.25, 0.5, 1.0, 1.5, 2.0):
        print(f"{x:>10.2f} | {theory.ladder_vol_sensitivity(x):>8.3f}"
              f" {theory.touch_vol_sensitivity(x):>8.3f}"
              f" {-theory.range_vol_sensitivity(x):>10.3f}")
    print("ATMラダー(d=0)の感応度は厳密に0: ボラ予測でATMラダーは絶対に取れない。")

    # ------------------------------------------------------------------- #
    _hdr("3. 必要な相対ボラ予測優位 ε*=(s/200)/(φ(d)|d|)（ラダー, %）")
    print(f"{'スプレッドs':>10} | {'d=0.5':>8} {'d=1.0':>8} {'d=1.5':>8}")
    for s in (2.0, 4.0, 6.0, 8.0):
        row = [theory.required_rel_vol_edge(s, d) * 100 for d in (0.5, 1.0, 1.5)]
        print(f"{s:>9.0f}pt | " + " ".join(f"{v:>7.1f}%" for v in row))
    print("タッチ/レンジは感応度2倍なので必要優位は半分。")

    # ------------------------------------------------------------------- #
    _hdr("4. H2境界効果: トレーリングボラMM対季節カレンダー（ラダーd=1）")
    print(f"{'直近係数':>8} {'窓係数':>8} | {'ボラ比r':>8} {'確率エッジpt':>12} {'損益分岐spread':>14}")
    for trail, win in ((0.6, 1.6), (0.8, 1.4), (1.0, 1.2), (1.6, 0.6)):
        r = theory.seasonal_boundary_misprice(1.0, trail, win)
        print(f"{trail:>8.1f} {win:>8.1f} | {r['vol_ratio']:>8.2f}"
              f" {r['edge_prob']*100:>11.1f} {r['breakeven_spread_points']:>13.1f}pt")

    # ------------------------------------------------------------------- #
    _hdr("5. H3イベントジャンプ: ラダー（σ=10%年率, T=2h, 発表が窓内）")
    print("ジャンプσ_J(対数,%) 0.1=CPI級~15pips, 0.4=NFP/中銀サプライズ級~60pips (USDJPY150想定)")
    print(f"{'σ_J':>6} | {'d(拡散基準)':>12} {'p拡散':>8} {'pジャンプ込':>10} {'エッジpt':>8} {'損益分岐s':>10}")
    spot = 150.0
    sig, ttm = 0.10, 7200.0
    st = theory.horizon_sigma(sig, ttm)
    for jstd in (0.001, 0.002, 0.004):
        for d in (1.0, 1.5, 2.0):
            strike = spot / pow(2.718281828459045, -d * st)  # ln(S/K) = -d·σ√T
            r = theory.event_ladder_edge(spot, strike, sig, ttm, jstd)
            print(f"{jstd*100:>5.1f}% | {-d:>12.1f} {r['p_diffusion']*100:>7.1f}%"
                  f" {r['p_with_jump']*100:>9.1f}% {r['edge_prob']*100:>8.1f}"
                  f" {r['breakeven_spread_points']:>9.1f}pt")

    # ------------------------------------------------------------------- #
    _hdr("6. H3イベントジャンプ: ワンタッチ（MC, バリア=+1.5σ√T, 発表は窓中央）")
    barrier = spot * pow(2.718281828459045, 1.5 * st)
    for jstd in (0.001, 0.002, 0.004):
        r = theory.event_touch_edge(spot, barrier, sig, ttm, jstd)
        print(f"σ_J={jstd*100:.1f}%: p拡散={r['p_diffusion']*100:.1f}%"
              f" pジャンプ込={r['p_with_jump']*100:.1f}%"
              f" エッジ={r['edge_prob']*100:+.1f}pt"
              f" 損益分岐spread={r['breakeven_spread_points']:.1f}pt")

    print("\n(すべて理論値。ライブでは指標前の提示停止・スプレッド拡大が反証要因)")


if __name__ == "__main__":
    main()
