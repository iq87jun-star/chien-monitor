#!/usr/bin/env python3
"""FTMO 1ステップ (20%オフ) の評価 — 手持ち戦略はこの土俵で通るか (2026-08-17).

1ステップ規則 (スクショより):
  目標 +10% / Max Loss 10% (EODトレーリング!) / 日次 -3% /
  Best Day Rule 50% (最良日の利益が総利益の50%未満) / 期間無制限 / 分配90%
比較: 2ステップ (10%/5%, 日次-5%, 静的-10%, 分配最大90%)

要点:
  - 日次-3% は速攻プロ(-2%)に次ぐ厳しさ。FX-JPY系の現行mult では即死領域
  - EODトレーリングは「+6%到達後の-4%押し」でも死ぬ = 静的-10%より大幅に厳しい
  - Best Day Rule は週1ショット型 (利益が月曜に集中) に不利

各ブックの基底系列 (mult=1.0) に倍率を掛けてブートストラップMC。
系列は2019年以降 (FXブックは選抜が古く実運用済みのため全期間を採用。
NonFX2 のみ選抜バイアスに注意 — §7)。

実行: cd research && python3 ftmo_1step_eval.py
"""
import random
import statistics

import nonfx_screen as N
from prop_fleet_portfolio import BOOKS, LO

random.seed(20260817)
NPATH = 20000
HORIZON = 250

TARGET1 = 0.10          # 1ステップ目標
DAILY1 = -0.03          # 1ステップ日次
TRAIL = 0.10            # EODトレーリング
BESTDAY = 0.50          # Best Day Rule

CANDS = ["FTMO_C6m", "FTMO_D3m", "FN_NonFX2"]


def base_series(name):
    legs = [b for b in BOOKS if b[0] == name][0][4]
    data = {y: N.fetch_daily(y, "10y") for y in sorted({l[0] for l in legs})}
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
            port[k] = port.get(k, 0.0) + w * v
    return [v for k, v in sorted(port.items()) if k >= LO]


def mc_1step(days, mult):
    res = {"pass": 0, "fail": 0, "alive": 0}
    td = []
    for _ in range(NPATH):
        eq, peak, best = 1.0, 1.0, 0.0
        done = None
        for d in range(HORIZON):
            r = random.choice(days) * mult
            if r <= DAILY1:
                done = "fail"; break
            eq *= (1 + r)
            best = max(best, r * 1.0)          # 初期残高比の日次利益で近似
            peak = max(peak, eq)               # EODトレーリング
            if eq <= peak * (1 - TRAIL):
                done = "fail"; break
            if eq >= 1 + TARGET1 and best <= BESTDAY * (eq - 1):
                done = "pass"; td.append(d + 1); break
        res[done or "alive"] += 1
    return ({k: v / NPATH for k, v in res.items()},
            statistics.median(td) if td else None)


def mc_2step(days, mult):
    """P1 +10% → P2 +5%。日次-5%・静的-10%。合成確率(独立近似)。"""
    def phase(target):
        ok = 0
        for _ in range(NPATH // 2):
            eq = 1.0
            for d in range(HORIZON):
                r = random.choice(days) * mult
                if r <= -0.05 or eq * (1 + r) <= 0.90:
                    break
                eq *= (1 + r)
                if eq >= 1 + target:
                    ok += 1; break
        return ok / (NPATH // 2)
    return phase(0.10) * phase(0.05)


def main():
    for name in CANDS:
        days = base_series(name)
        worst = min(days)
        print(f"\n=== {name} (基底最悪日 {worst*100:.2f}% → 日次-3%に触れる倍率 {abs(0.03/worst):.1f}) ===")
        print(f"{'mult':>5s} | {'1step通過':>9s} {'失格':>7s} {'未決':>7s} {'中央値':>8s} | {'2step資金化':>10s}")
        for m in (1.0, 1.5, 2.0, 2.5, 3.0):
            p, med = mc_1step(days, m)
            p2 = mc_2step(days, m)
            print(f"{m:5.1f} | {p['pass']*100:8.1f}% {p['fail']*100:6.1f}% {p['alive']*100:6.1f}% "
                  f"{(str(round(med))+'営日' if med else '—'):>8s} | {p2*100:9.1f}%")
    print("\n※ 250営業日・20,000パス(2stepは各フェーズ10,000)。コスト未計上。")
    print("※ 1step通過は Best Day Rule 充足込み。トレーリングはEOD評価。")
    print("※ FTMO_C6m/D3m の現行稼働 mult は 6.0 / 5.52 — この表の範囲外(即死領域)。")


if __name__ == "__main__":
    main()
