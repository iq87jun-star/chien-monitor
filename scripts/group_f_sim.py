#!/usr/bin/env python3
"""
2026 W杯 グループF 予想シミュレーター
手法: Eloレーティング -> ポアソン得点モデル -> モンテカルロ
チーム強度はEloを基に、Optaの突破確率(NED88/JPN76/SWE63/TUN43)へ較正。
"""
import math
import random
from itertools import combinations
from collections import defaultdict, Counter

random.seed(42)

# ---- チーム強度(Elo概値, 2026年) ----
ELO = {
    "オランダ": 2010,
    "日本":     1915,
    "スウェーデン": 1800,
    "チュニジア": 1680,
}

# ---- ポアソン得点モデルのパラメータ ----
TOTAL_GOALS = 2.65      # 1試合あたり期待総得点(W杯平均的)
SUP_PER_100 = 0.45      # Elo100差あたりの期待得点差
N_SIM = 300_000

def expected_goals(a, b):
    dr = ELO[a] - ELO[b]              # ニュートラル開催のためホームアドバンテージ無し
    sup = dr / 100.0 * SUP_PER_100
    la = max(0.15, (TOTAL_GOALS + sup) / 2.0)
    lb = max(0.15, (TOTAL_GOALS - sup) / 2.0)
    return la, lb

def poisson(lam):
    # Knuth法
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1

FIXTURES = list(combinations(ELO.keys(), 2))

# ---- 試合ごとの結果分布(勝/分/負, 期待得点, 最頻スコア) ----
def analyze_matches():
    print("=" * 64)
    print("【1試合ごとの予想】(ニュートラル開催)")
    print("=" * 64)
    for a, b in FIXTURES:
        la, lb = expected_goals(a, b)
        wa = wb = dr = 0
        scores = Counter()
        M = 100_000
        for _ in range(M):
            ga, gb = poisson(la), poisson(lb)
            scores[(ga, gb)] += 1
            if ga > gb: wa += 1
            elif gb > ga: wb += 1
            else: dr += 1
        top = scores.most_common(1)[0]
        print(f"\n{a} vs {b}")
        print(f"  期待得点 {la:.2f} - {lb:.2f}")
        print(f"  {a}勝ち {wa/M*100:4.1f}% / 引分 {dr/M*100:4.1f}% / {b}勝ち {wb/M*100:4.1f}%")
        print(f"  最頻スコア {top[0][0]}-{top[0][1]} ({top[1]/M*100:.1f}%)")

# ---- グループ総当たりのモンテカルロ ----
def simulate_group():
    place_count = {t: [0, 0, 0, 0] for t in ELO}   # 1位,2位,3位,4位
    pts_sum = defaultdict(float)
    qualify = defaultdict(int)

    def third_advance_prob(points):
        # 3位チームが8枠のベスト3位に入る確率(近似)
        return {0:0.0,1:0.02,2:0.10,3:0.45,4:0.82,5:0.95,6:0.99,7:1.0,9:1.0}.get(points, 1.0)

    for _ in range(N_SIM):
        pts = defaultdict(int); gf = defaultdict(int); ga = defaultdict(int)
        for a, b in FIXTURES:
            la, lb = expected_goals(a, b)
            x, y = poisson(la), poisson(lb)
            gf[a]+=x; ga[a]+=y; gf[b]+=y; ga[b]+=x
            if x>y: pts[a]+=3
            elif y>x: pts[b]+=3
            else: pts[a]+=1; pts[b]+=1
        # 順位付け: 勝点 -> 得失点差 -> 総得点 -> 乱数
        table = sorted(ELO, key=lambda t:(pts[t], gf[t]-ga[t], gf[t], random.random()), reverse=True)
        for rank, t in enumerate(table):
            place_count[t][rank]+=1
            pts_sum[t]+=pts[t]
        # 突破判定: 1,2位は自動。3位は枠次第。
        for rank, t in enumerate(table):
            if rank<2: qualify[t]+=1
            elif rank==2 and random.random()<third_advance_prob(pts[t]): qualify[t]+=1

    print("\n" + "=" * 64)
    print(f"【グループ最終順位の確率】({N_SIM:,}回シミュレーション)")
    print("=" * 64)
    print(f"{'チーム':<10}{'平均勝点':>8}{'1位':>8}{'2位':>8}{'3位':>8}{'4位':>8}{'突破':>8}")
    for t in sorted(ELO, key=lambda t:qualify[t], reverse=True):
        pc=place_count[t]
        print(f"{t:<10}{pts_sum[t]/N_SIM:>8.2f}"
              f"{pc[0]/N_SIM*100:>7.1f}%{pc[1]/N_SIM*100:>7.1f}%"
              f"{pc[2]/N_SIM*100:>7.1f}%{pc[3]/N_SIM*100:>7.1f}%"
              f"{qualify[t]/N_SIM*100:>7.1f}%")

if __name__ == "__main__":
    analyze_matches()
    simulate_group()
