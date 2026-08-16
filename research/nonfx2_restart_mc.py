#!/usr/bin/env python3
"""実機ログで判明した出発点 (equity 95,817 = -4.18%) からの再計算 (2026-08-16).

v1.03 の mult 2.5 は「残高100k のまっさらな口座」前提の裁定だった。
実際は季節RG3時代の損失で -4.18% から始まる:
  P1目標 108k まで +12.71% / EAフロア 92k まで 3.98% / FN静的 90k まで 6.07%
歴史最悪日×2.5 = -3.89% はフロアまでの余裕とほぼ同値 = 1日で死に得る。

mult × フロアの格子で P1到達確率を引き直す。フロアは -8%(現行) と
-9%(静的-10%の1%手前まで許容) の2水準を試す。

実行: cd research && python3 nonfx2_restart_mc.py
"""
import random
import statistics
from datetime import datetime, timedelta, timezone

import nonfx_screen as N
from prop_fleet_portfolio import BOOKS, LO

random.seed(20260817)
NPATH = 20000
HORIZON = 250
YR = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")

EQ0 = 95817.23 / 100000.0      # 実機ログ 2026-08-16
TARGET = 1.08                  # P1 = initBal +8%
DAYFAIL = 5.0                  # FN 日次-5%


def base_series():
    legs = [b for b in BOOKS if b[0] == "FN_NonFX2"][0][4]
    data = {y: N.fetch_daily(y, "10y") for y in sorted({l[0] for l in legs})}
    port = {}
    for y, fam, arg, w in legs:
        s = N.dow_daily_returns(data[y], N.DOWS.index(arg[0]), arg[1])
        for k, v in s.items():
            port[k] = port.get(k, 0.0) + w * v
    return {k: v for k, v in port.items() if k >= LO}


def mc(days, mult, floor_pct):
    floor = 1 - floor_pct / 100.0
    res = {"pass": 0, "fail": 0, "alive": 0}
    tdays = []
    for _ in range(NPATH):
        eq = EQ0
        done = None
        for d in range(HORIZON):
            r = random.choice(days) * mult
            if r <= -DAYFAIL / 100.0:
                done = "fail"; break
            eq *= (1 + r)
            if eq <= floor:
                done = "fail"; break
            if eq >= TARGET:
                done = "pass"; tdays.append(d + 1); break
        res[done or "alive"] += 1
    return ({k: v / NPATH for k, v in res.items()},
            statistics.median(tdays) if tdays else None)


def main():
    port = base_series()
    consv = [v for k, v in port.items() if k < YR]
    print(f"出発点 equity/initBal = {EQ0:.5f} (-4.18%) / 目標 {TARGET:.2f} / 保守系列 {len(consv)}日")
    print(f"参考: まっさら口座前提の旧裁定 = mult2.5で P1通過64.3%/失格26.9%\n")
    for floor in (8.0, 9.0):
        print(f"=== EAフロア -{floor:.0f}% (静的-10%の{10-floor:.0f}%手前) ===")
        print(f"{'mult':>5s} {'P1到達':>7s} {'失格':>7s} {'未決':>7s} {'中央値':>8s}")
        for m in (1.50, 2.00, 2.50, 3.00):
            p, med = mc(consv, m, floor)
            print(f"{m:5.2f} {p['pass']*100:6.1f}% {p['fail']*100:6.1f}% "
                  f"{p['alive']*100:6.1f}% {(str(round(med))+'営日' if med else '—'):>8s}")
        print()
    print("※ 保守系列(選抜窓除外)・250営業日・20,000パス。日次-5%は日次リターン近似。")


if __name__ == "__main__":
    main()
