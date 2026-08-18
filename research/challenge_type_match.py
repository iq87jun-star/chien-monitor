#!/usr/bin/env python3
"""チャレンジ規則タイプ別の適合度 — 手持ち手法はどの型で最も通るか (2026-08-17).

手持ち手法の特性 (共通):
  - 週次ショット型 (曜日レッグ+v4)。ドリフト小・分散頼み → 通過は時間がかかる
  - 基底最悪日 -0.9〜-1.6% → 日次ラインに合わせて倍率を畳める
  - 24h保有必須 (o2o)。週末エクスポージャはほぼゼロ

規則アーキタイプ (100k想定・すべて近似):
  A. 1step無制限     : 目標+10 / 日次-3 / EODトレーリング-10 (FTMO 1step)
  B. 2step無制限FTMO : 10→5 / 日次-5 / 静的-10
  C. 2step無制限FN   : 8→5  / 日次-5 / 静的-10 (Stellar)
  D. 時間制限型      : 目標+8 / 総損失-3 / 日次-2 / 60営業日 (速攻プロ型)
  E. Instant型       : 関門なし。初回出金ライン+5% / トレーリング-6 に
                       「先に到達する」確率を測る (FN Instant近似)

ブックは D3m型 (基底最悪日が最小=土俵適合が最良) で統一し、
各型について mult を掃引して最良点を取る。

実行: cd research && python3 challenge_type_match.py
"""
import random
import statistics

import nonfx_screen as N
from prop_fleet_portfolio import BOOKS, LO

random.seed(20260818)
NPATH = 10000
HORIZON = 250
MULTS = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5)


def base_series(name="FTMO_D3m"):
    legs = [b for b in BOOKS if b[0] == name][0][4]
    data = {y: N.fetch_daily(y, "10y") for y in sorted({l[0] for l in legs})}
    port = {}
    for y, fam, arg, w in legs:
        rows = data[y]
        s = (N.dow_daily_returns(rows, N.DOWS.index(arg[0]), arg[1]) if fam == "DOW"
             else N.v4_daily_returns(rows))
        for k, v in s.items():
            port[k] = port.get(k, 0.0) + w * v
    return [v for k, v in sorted(port.items()) if k >= LO]


def run(days, mult, target, daily, static=None, trail=None, limit=None,
        stage2=None):
    horizon = limit or HORIZON
    ok = fail = 0
    td = []
    for _ in range(NPATH):
        eq, peak = 1.0, 1.0
        done = None
        for d in range(horizon):
            r = random.choice(days) * mult
            if r <= -daily / 100.0:
                done = "fail"; break
            eq *= (1 + r)
            peak = max(peak, eq)
            if static and eq <= 1 - static / 100.0:
                done = "fail"; break
            if trail and eq <= peak * (1 - trail / 100.0):
                done = "fail"; break
            if eq >= 1 + target / 100.0:
                done = "pass"; td.append(d + 1); break
        if done == "pass":
            ok += 1
        elif done == "fail":
            fail += 1
    p1 = ok / NPATH
    f1 = fail / NPATH
    m1 = statistics.median(td) if td else None
    if stage2 is None:
        return p1, f1, m1
    p2, _, m2 = run(days, mult, stage2, daily, static=static, trail=trail)
    return p1 * p2, f1, (m1 + m2 if m1 and m2 else None)


ARCHETYPES = [
    ("A. 1step無制限 (FTMO 1step)",
     dict(target=10, daily=3, trail=10)),
    ("B. 2step無制限 (FTMO)",
     dict(target=10, daily=5, static=10, stage2=5)),
    ("C. 2step無制限 (FN Stellar)",
     dict(target=8, daily=5, static=10, stage2=5)),
    ("D. 時間制限型 (速攻プロ型60営)",
     dict(target=8, daily=2, static=3, limit=60)),
    ("E. Instant型 (+5%出金 vs -6%トレール)",
     dict(target=5, daily=100, trail=6)),
]


def main():
    days = base_series()
    print(f"ブック: D3m型 (基底最悪日 {min(days)*100:.2f}%)・250営業日・{NPATH:,}パス\n")
    print(f"{'アーキタイプ':34s} {'最良mult':>8s} {'資金化/到達':>10s} {'失格':>7s} {'中央値':>9s}")
    for lab, kw in ARCHETYPES:
        best = None
        for m in MULTS:
            p, f, med = run(days, m, **kw)
            if best is None or p > best[1]:
                best = (m, p, f, med)
        m, p, f, med = best
        print(f"{lab:34s} {m:8.1f} {p*100:9.1f}% {f*100:6.1f}% "
              f"{(str(round(med))+'営日' if med else '—'):>9s}")
    print("\n※ すべて同一ブック・同一系列。差は規則構造の差そのもの。")
    print("※ E は「初回出金に先に届く確率」。Instant は失格しても口座代のみの損失で、")
    print("   資金化確率は定義上100% (買った瞬間から本番)。")


if __name__ == "__main__":
    main()
