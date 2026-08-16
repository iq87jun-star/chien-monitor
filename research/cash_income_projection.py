#!/usr/bin/env python3
"""現金収入ベースの月次予測 — 収益化済みは Instant20k のみという現実を反映 (2026-08-15).

フリート合算の +$2,900/月 は「口座内損益」であり、チャレンジ中の口座は
通過するまで現金を生まない。本スクリプトは:

  1. 現金収入の現状 = Instant20k 単独の月次分布
  2. 各チャレンジ口座の S1 通過確率・所要月数 (日次ブートストラップMC)
  3. それを織り込んだ「現金収入の時間プロファイル」

ステップ規則の仮定 (docs/174,178 と各EAフロアから。※要実規約確認):
  パール500万   : 目標+8% / 失格-9%(EAフロア) / 日次-5%
  速攻プロ2000万 : 目標+8% / 失格-2.4%(EAフロア,規約-3%) / 日次-2% / 60日枠
  FTMO C6m/D3m : 目標+10% / 失格-9% / 日次-5%
  FN NonFX     : 目標+8% / 失格-9% / 日次-5%
  FN NonFX2    : 目標+8% / 失格-8% / 日次-5% / 期限2026-10-15(約60日)

実行: cd research && python3 cash_income_projection.py
"""
import random
import statistics

import nonfx_screen as N
from prop_fleet_portfolio import BOOKS, LO

random.seed(20260815)
NPATH = 20000

# (口座, 目標%, 失格%(静的), 日次失格%, 日数上限(営業日; Noneは無制限→250日で打ち切り)
CHALLENGES = {
    "パール500万":    (8.0,  9.0, 5.0, None),
    "速攻プロ2000万": (8.0,  2.4, 2.0, 42),
    "FTMO_C6m":       (10.0, 9.0, 5.0, None),
    "FTMO_D3m":       (10.0, 9.0, 5.0, None),
    "FN_NonFX":       (8.0,  9.0, 5.0, None),
    "FN_NonFX2":      (8.0,  8.0, 5.0, 42),
}


def build_series():
    data = {}
    for y in sorted({leg[0] for _, _, _, _, legs in BOOKS for leg in legs}):
        data[y] = N.fetch_daily(y, "10y")
    out = {}
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
        out[name] = [v for k, v in sorted(port.items()) if k >= LO]
    return out


def mc(days, target, ruin, dayfail, limit):
    horizon = limit or 250
    res = {"pass": 0, "fail": 0, "expire": 0}
    tdays = []
    for _ in range(NPATH):
        eq, pk = 1.0, 1.0
        done = None
        for d in range(horizon):
            r = random.choice(days)
            if r <= -dayfail / 100.0:
                done = "fail"; break
            eq *= (1 + r)
            if eq <= 1 - ruin / 100.0:
                done = "fail"; break
            if eq >= 1 + target / 100.0:
                done = "pass"; tdays.append(d + 1); break
        res[done or "expire"] += 1
    med = statistics.median(tdays) if tdays else None
    return {k: v / NPATH for k, v in res.items()}, med


def main():
    series = build_series()
    caps = {b[0]: b[1] for b in BOOKS}

    print("=== [1] 現金収入の現状 = Instant20k のみ ===")
    inst = series["Instant20k"]
    mavg = statistics.mean(inst) * 21 * caps["Instant20k"]
    print(f"  月次中心 {statistics.mean(inst)*21*100:+.2f}% × $20,000 = {mavg:+,.0f} $/月 (コスト前・分配前)")
    print("  ペイアウト分配(仮に80%)後: {:+,.0f} $/月".format(mavg * 0.8))

    print("\n=== [2] チャレンジ口座の S1 通過確率 (日次ブートストラップ, 20,000パス) ===")
    print(f"{'口座':14s} {'目標':>5s} {'失格線':>6s} {'枠':>6s} | {'通過':>6s} {'失格':>6s} {'期限切れ':>7s} {'中央値':>8s}")
    results = {}
    for name, (tgt, ruin, dayfail, limit) in CHALLENGES.items():
        probs, med = mc(series[name], tgt, ruin, dayfail, limit)
        results[name] = (probs, med)
        lim = f"{limit}営" if limit else "無制限"
        print(f"{name:14s} {tgt:4.0f}% {-ruin:5.1f}% {lim:>6s} | {probs['pass']*100:5.1f}% "
              f"{probs['fail']*100:5.1f}% {probs['expire']*100:6.1f}% "
              f"{(str(round(med))+'営日' if med else '—'):>8s}")
    print("※ 250営業日で打ち切り。日次失格は日次リターン近似(口座内の時刻構造は無視)。")
    print("※ S1通過後に S2 が続く2ステップ口座は、資金化までさらに同程度の関門がある。")

    print("\n=== [3] 現金収入の時間プロファイル (概算) ===")
    print("  資金化後の各口座の月次中心 ($, 口座内損益ベース):")
    monthly = {n: statistics.mean(series[n]) * 21 * caps[n] for n in series}
    for n, v in sorted(monthly.items(), key=lambda x: -x[1]):
        tag = "収益化済み" if n == "Instant20k" else "チャレンジ中"
        print(f"    {n:14s} {v:+8,.0f} $/月  ({tag})")
    exp_add = 0.0
    for n, (probs, med) in results.items():
        p2 = probs["pass"] ** 2 if n in ("パール500万", "速攻プロ2000万", "FTMO_C6m", "FTMO_D3m",
                                          "FN_NonFX", "FN_NonFX2") else probs["pass"]
        exp_add += monthly[n] * p2
    print(f"\n  期待値ベース: 全チャレンジの資金化後追加収入 × 通過確率(2ステップ=P²近似)")
    print(f"    = {exp_add:+,.0f} $/月 (実現には最短でも数ヶ月〜半年のラグ)")


if __name__ == "__main__":
    main()
