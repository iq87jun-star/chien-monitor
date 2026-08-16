#!/usr/bin/env python3
"""2026年8月以降の月次収益額の推定 (フリート7口座・プロキシベース).

出力:
  1. 口座毎・フリート合計の月次リターン分布 (全期間平均 / 中央値 / P25 / P75 / σ)
  2. カレンダー月の季節性 (8月/9月/10月の歴史平均)
  3. 金額換算の月次シナリオ表 (悲観P25 / 中心 / 楽観P75 / 直近12Mペース)

実行: cd research && python3 monthly_projection.py
"""
import statistics
from collections import defaultdict

import nonfx_screen as N
from prop_fleet_portfolio import BOOKS, LO

QS = (0.25, 0.50, 0.75)


def build_series():
    data = {}
    for y in sorted({leg[0] for _, _, _, _, legs in BOOKS for leg in legs}):
        data[y] = N.fetch_daily(y, "10y")
    series = {}
    for name, cap, mult, floor, legs in BOOKS:
        port = {}
        for y, fam, arg, w in legs:
            rows = data[y]
            if fam == "DOW":
                s = N.dow_daily_returns(rows, N.DOWS.index(arg[0]), arg[1])
            elif fam == "HOLD":
                s = {k: max(v, -0.15) for k, v in N.hold_daily_returns(rows).items()}
            else:
                s = N.v4_daily_returns(rows)
            for k, v in s.items():
                port[k] = port.get(k, 0.0) + w * v * mult
        series[name] = port
    return series


def monthly(series):
    m = defaultdict(float)
    for k, v in series.items():
        if k >= LO:
            m[k[:7]] += v          # 月内単利合計(近似)
    return dict(m)


def q(xs, p):
    xs = sorted(xs)
    i = (len(xs) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def main():
    series = build_series()
    caps = {b[0]: b[1] for b in BOOKS}
    tot = sum(caps.values())

    fleet = defaultdict(float)
    permon = {}
    for n, s in series.items():
        mo = monthly(s)
        permon[n] = mo
        for k, v in mo.items():
            fleet[k] += v * caps[n] / tot
    months = sorted(fleet)
    xs = [fleet[m] for m in months]

    print(f"月数 {len(xs)} ({months[0]} .. {months[-1]})  総資本 ${tot:,}")

    print("\n=== [1] フリート合成の月次リターン分布 (資本加重・%) ===")
    print(f"  平均 {statistics.mean(xs)*100:+.2f}% / 中央値 {q(xs,.5)*100:+.2f}% / "
          f"P25 {q(xs,.25)*100:+.2f}% / P75 {q(xs,.75)*100:+.2f}% / σ {statistics.stdev(xs)*100:.2f}%")
    neg = sum(1 for v in xs if v < 0) / len(xs)
    print(f"  マイナス月の割合 {neg*100:.0f}% / 最悪月 {min(xs)*100:+.2f}% ({months[xs.index(min(xs))]}) / "
          f"最良月 {max(xs)*100:+.2f}%")
    r12 = [fleet[m] for m in months[-12:]]
    print(f"  直近12ヶ月の平均 {statistics.mean(r12)*100:+.2f}%/月")

    print("\n=== [2] カレンダー月の季節性 (歴史平均・参考) ===")
    for cm in ("08", "09", "10", "11", "12"):
        vs = [fleet[m] for m in months if m[5:] == cm]
        if vs:
            print(f"  {int(cm):2d}月: 平均 {statistics.mean(vs)*100:+.2f}% "
                  f"(中央値 {q(vs,.5)*100:+.2f}%, n={len(vs)})")

    print("\n=== [3] 口座毎の月次 (全期間, mult適用後) ===")
    print(f"{'口座':14s} {'資本$':>9s} {'平均%':>7s} {'P25%':>7s} {'P75%':>7s} | "
          f"{'平均$':>8s} {'P25$':>9s} {'P75$':>8s}")
    trow = [0.0, 0.0, 0.0]
    for name, cap, mult, floor, _ in BOOKS:
        mo = permon[name]
        vs = [mo[m] for m in sorted(mo)]
        a, p25, p75 = statistics.mean(vs), q(vs, .25), q(vs, .75)
        trow[0] += a * cap; trow[1] += p25 * cap; trow[2] += p75 * cap
        print(f"{name:14s} {cap:9,d} {a*100:+6.2f}% {p25*100:+6.2f}% {p75*100:+6.2f}% | "
              f"{a*cap:+8,.0f} {p25*cap:+9,.0f} {p75*cap:+8,.0f}")
    print(f"{'合計(独立仮定)':14s} {tot:9,d} {'':7s} {'':7s} {'':7s} | "
          f"{trow[0]:+8,.0f} {trow[1]:+9,.0f} {trow[2]:+8,.0f}")
    print("※ P25/P75の単純合算は口座間相関を無視しており幅を過大表示する。分布は[1]のフリート値を使う。")

    print("\n=== [4] 金額シナリオ (フリート合成・総資本ベース) ===")
    mean_ = statistics.mean(xs)
    for lab, v in (("悲観 (P25)", q(xs, .25)), ("中心 (全期間平均)", mean_),
                   ("楽観 (P75)", q(xs, .75)), ("直近12Mペース (選抜バイアス込み)", statistics.mean(r12))):
        print(f"  {lab:28s} {v*100:+6.2f}%/月  →  {v*tot:+10,.0f} $/月")


if __name__ == "__main__":
    main()
