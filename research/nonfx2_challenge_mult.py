#!/usr/bin/env python3
"""FN100k #14074882 (NonFX2) がチャレンジ段階である場合の倍率スイープ (2026-08-15).

ユーザー確認: FN はチャレンジ段階 → v1.02 の mult 0.90 (生存優先校正) は
P1 +8% にほぼ到達できない。ではどの mult なら狙えるかを測る。

規則 (FN Stellar 型・docs/178): P1 +8% / P2 +5% / 日次-5% / 静的-10%。
EA フロアは -8% (静的-10%の2%手前) = 到達で恒久停止 → 実質失格扱い。
チャレンジ自体に時間制限なし。EA の期限 (2026-10-15) は再スクリーニング規則
なので、「2ヶ月毎に構成を入れ替えつつ回し続ける」前提で 250営業日まで追う。

2系列で評価:
  楽観 = 2019年以降の全プロキシ (直近12Mの選抜窓込み = 上振れバイアスあり)
  保守 = 選抜窓 (直近12M) を除いた系列 = §7 の「残る実力」ベース

実行: cd research && python3 nonfx2_challenge_mult.py
"""
import random
import statistics
from datetime import datetime, timedelta, timezone

import nonfx_screen as N
from prop_fleet_portfolio import BOOKS, LO

random.seed(20260816)
NPATH = 20000
HORIZON = 250
YR = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")

P1, P2 = 8.0, 5.0
FLOOR = 8.0          # EAフロア(恒久停止=実質失格)
DAYFAIL = 5.0        # FN 日次-5%


def base_series():
    """NonFX2 の5レッグを mult=1.0 で合成した日次系列(日付つき)。"""
    legs = [b for b in BOOKS if b[0] == "FN_NonFX2"][0][4]
    data = {y: N.fetch_daily(y, "10y") for y in sorted({l[0] for l in legs})}
    port = {}
    for y, fam, arg, w in legs:
        s = N.dow_daily_returns(data[y], N.DOWS.index(arg[0]), arg[1])
        for k, v in s.items():
            port[k] = port.get(k, 0.0) + w * v
    return {k: v for k, v in port.items() if k >= LO}


def mc(days, mult, target):
    res = {"pass": 0, "fail": 0, "alive": 0}
    tdays = []
    for _ in range(NPATH):
        eq = 1.0
        done = None
        for d in range(HORIZON):
            r = random.choice(days) * mult
            if r <= -DAYFAIL / 100.0:
                done = "fail"; break
            eq *= (1 + r)
            if eq <= 1 - FLOOR / 100.0:
                done = "fail"; break
            if eq >= 1 + target / 100.0:
                done = "pass"; tdays.append(d + 1); break
        res[done or "alive"] += 1
    med = statistics.median(tdays) if tdays else None
    return {k: v / NPATH for k, v in res.items()}, med


def main():
    port = base_series()
    allv = list(port.values())
    consv = [v for k, v in port.items() if k < YR]
    print(f"日数: 楽観(全期間) {len(allv)} / 保守(選抜窓除外) {len(consv)}")
    print(f"素の日次: 楽観 平均{statistics.mean(allv)*1e4:.1f}bp 最悪{min(allv)*100:.2f}% / "
          f"保守 平均{statistics.mean(consv)*1e4:.1f}bp 最悪{min(consv)*100:.2f}%")

    for lab, days in (("保守 (選抜窓除外 = §7の残存実力ベース)", consv),
                      ("楽観 (直近12M込み = 選抜バイアスあり)", allv)):
        print(f"\n=== {lab} — P1 +8% (250営業日・20,000パス) ===")
        print(f"{'mult':>5s} {'P1通過':>7s} {'失格':>7s} {'未決':>7s} {'中央値':>8s} "
              f"{'歴史最悪日×mult':>13s} {'P1×P2':>7s}")
        for m in (0.90, 1.50, 2.00, 2.50, 3.00, 3.50):
            p1, med = mc(days, m, P1)
            p2, _ = mc(days, m, P2)
            worst = min(days) * m * 100
            print(f"{m:5.2f} {p1['pass']*100:6.1f}% {p1['fail']*100:6.1f}% "
                  f"{p1['alive']*100:6.1f}% {(str(round(med))+'営日' if med else '—'):>8s} "
                  f"{worst:12.2f}% {p1['pass']*p2['pass']*100:6.1f}%")
    print("\n※ 未決 = 250営業日で目標にも失格にも達しない。翌年へ持ち越し。")
    print("※ 歴史最悪日×mult が -5% に近づくと日次規則が直接の失格要因になる。")
    print("※ P1×P2 = 資金化までの合成確率 (独立近似)。")


if __name__ == "__main__":
    main()
