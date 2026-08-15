#!/usr/bin/env python3
"""組み換え間隔と、脱落レッグの再エントリー間隔(クールダウン)を実測する.

問い:
  Q1. 何日ごとに選抜し直すのが良いか (組み換え間隔)
  Q2. 選抜から外れたセルは、その後どうなるか (落ちたものは落ち続けるか、戻るか)
  Q3. 一度落ちたセルを再び採用するまで、どのくらい空けるべきか (クールダウン)

方法: 全期間を通したウォークフォワード。N日ごとに直近12MのtでTOP_K選抜し、
      逆ボラ加重で次のN日を保有。これを連続させた1本の系列で評価する。
      クールダウンC日 = 「選抜から外れた日からC日間は再採用しない」。

実行: cd research && python3 rebalance_policy_nonfx.py
"""
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

import nonfx_screen as N

MIN_TRADES = 30
TOP_K = 6
INTERVALS = [30, 60, 90, 180, 365]
COOLDOWNS = [0, 30, 60, 90, 180, 365]


def hr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def d(s):
    return datetime.strptime(s, "%Y-%m-%d")


def ds(x):
    return x.strftime("%Y-%m-%d")


def build_cells():
    cells = {}
    for ysym, name in N.UNIVERSE:
        try:
            rows = N.fetch_daily(ysym, "10y")
        except Exception as ex:
            print(f"  skip {name}: {ex}")
            continue
        for di, dw in enumerate(N.DOWS):
            for sgn, tag in ((+1, "L"), (-1, "S")):
                s = {}
                for i in range(len(rows) - 1):
                    if d(rows[i][0]).weekday() != di:
                        continue
                    e = rows[i][1]
                    if e > 0:
                        s[rows[i + 1][0]] = sgn * (rows[i + 1][1] - e) / e
                if len(s) > 100:
                    cells[f"{name}_{dw}_{tag}"] = s
    return cells


def win(series, lo, hi):
    return [v for k, v in series.items() if lo < k <= hi]


def tstat(xs):
    if len(xs) < 5:
        return 0.0
    sd = statistics.stdev(xs)
    return (statistics.mean(xs) / (sd / len(xs) ** 0.5)) if sd > 0 else 0.0


def comp(xs):
    e = 1.0
    for v in xs:
        e *= (1 + v)
    return e - 1


def maxdd(port):
    eq = pk = 1.0
    mdd = 0.0
    for k in sorted(port):
        eq *= (1 + port[k])
        pk = max(pk, eq)
        mdd = min(mdd, eq / pk - 1)
    return mdd


def simulate(cells, first, last, interval, cooldown, track=None):
    """N日ごとに選抜し直し、連続保有した系列を返す。"""
    port = {}
    dropped_at = {}                      # cell -> 最後に選抜から外れた日
    prev = set()
    turnover = []
    T = d(first) + timedelta(days=400)
    while T < d(last) - timedelta(days=interval // 2):
        Ts, lo = ds(T), ds(T - timedelta(days=365))
        cand = []
        for name, s in cells.items():
            if cooldown and name in dropped_at:
                if (T - d(dropped_at[name])).days < cooldown:
                    continue                       # クールダウン中は再採用しない
            xs = win(s, lo, Ts)
            if len(xs) >= MIN_TRADES:
                sd = statistics.stdev(xs)
                if sd > 0:
                    cand.append((tstat(xs), name, sd))
        if len(cand) >= TOP_K:
            cand.sort(reverse=True)
            top = cand[:TOP_K]
            iv = [1.0 / c[2] for c in top]
            tot = sum(iv)
            w = {c[1]: v / tot for c, v in zip(top, iv)}
            cur = set(w)
            for nm in prev - cur:
                dropped_at[nm] = Ts
            if prev:
                turnover.append(len(cur - prev) / TOP_K)
            if track is not None and prev:
                track.append((Ts, prev - cur, cur - prev, cur))
            prev = cur
            hi = ds(T + timedelta(days=interval))
            for name, wt in w.items():
                for k, v in cells[name].items():
                    if Ts < k <= hi:
                        port[k] = port.get(k, 0.0) + wt * v
        T += timedelta(days=interval)
    return port, (statistics.mean(turnover) if turnover else 0.0)


def summarize(port):
    if not port:
        return None
    ks = sorted(port)
    yrs = (d(ks[-1]) - d(ks[0])).days / 365.25
    tot = comp([port[k] for k in ks])
    ann = (1 + tot) ** (1 / yrs) - 1
    xs = [port[k] for k in ks]
    return dict(ann=ann, mdd=maxdd(port), t=tstat(xs), n=len(xs))


def main():
    cells = build_cells()
    all_d = sorted({k for s in cells.values() for k in s})
    first, last = all_d[0], all_d[-1]
    print(f"  セル数 {len(cells)}  期間 {first} .. {last}")

    # ------------------------------------------------ Q1. 組み換え間隔
    hr("[1] 組み換え間隔 — 何日ごとに選抜し直すか (クールダウン無し)")
    print(f"{'間隔':>8s} {'年率':>8s} {'maxDD':>8s} {'t':>6s} {'入替率':>8s} {'年間の組換回数':>12s}")
    base = {}
    for iv in INTERVALS:
        port, to = simulate(cells, first, last, iv, 0)
        r = summarize(port)
        base[iv] = r
        print(f"{iv:6d}日 {r['ann']*100:+7.2f}% {r['mdd']*100:7.2f}% {r['t']:6.2f} "
              f"{to*100:7.1f}% {365/iv:11.1f}回")
    print("\n※ 入替率=1回の組み換えで6本中何%が入れ替わるか。")
    print("   このロジックは建玉が24時間で完結するため、レッグを入れ替えても")
    print("   建玉の乗り換えコストは発生しない(入替率が高くても直接コストは増えない)。")

    # ------------------------------------------------ Q2. 脱落セルのその後
    hr("[2] 脱落したセルはその後どうなるか")
    track = []
    simulate(cells, first, last, 30, 0, track=track)
    fwd = defaultdict(list)
    stay = defaultdict(list)
    back = []
    for idx, (Ts, out, inn, cur) in enumerate(track):
        for nm in out:
            for h in (30, 60, 90, 180, 365):
                hi = ds(d(Ts) + timedelta(days=h))
                xs = win(cells[nm], Ts, hi)
                if len(xs) >= 3:
                    fwd[h].append(comp(xs))
            # 何日後に選抜へ戻ったか
            for j in range(idx + 1, len(track)):
                if nm in track[j][3]:
                    back.append((d(track[j][0]) - d(Ts)).days)
                    break
        for nm in cur - inn:                 # 残留したセル
            for h in (30, 60, 90, 180, 365):
                hi = ds(d(Ts) + timedelta(days=h))
                xs = win(cells[nm], Ts, hi)
                if len(xs) >= 3:
                    stay[h].append(comp(xs))
    print(f"{'脱落後':>8s} {'脱落セル':>10s} {'残留セル':>10s} {'差':>9s} {'n':>6s}")
    for h in (30, 60, 90, 180, 365):
        if not fwd[h]:
            continue
        a, b = statistics.mean(fwd[h]), statistics.mean(stay[h])
        print(f"{h:6d}日 {a*100:+9.2f}% {b*100:+9.2f}% {(a-b)*100:+8.2f}% {len(fwd[h]):6d}")
    if back:
        back.sort()
        print(f"\n脱落セルが再び選抜に戻るまで: 中央値 {statistics.median(back):.0f}日 / "
              f"平均 {statistics.mean(back):.0f}日 / 30日以内に復帰 "
              f"{sum(1 for x in back if x <= 30)/len(back)*100:.0f}%")
        print(f"  ({len(back)}件が復帰。復帰しなかったものは除く)")

    # ------------------------------------------------ Q3. クールダウン
    hr("[3] 再エントリー間隔(クールダウン) — 脱落後C日は再採用しない")
    print(f"{'':>8s}" + "".join(f"{c:>10d}日" for c in COOLDOWNS))
    for iv in [30, 60, 90]:
        row = f"{iv:6d}日 "
        for c in COOLDOWNS:
            port, _ = simulate(cells, first, last, iv, c)
            r = summarize(port)
            row += f"{r['ann']*100:+9.2f}% " if r else f"{'--':>10s} "
        print(row)
    print("\n(縦=組み換え間隔 / 横=クールダウン日数 / 数値=年率。コスト未計上)")

    # 統計的な有意性の目安
    hr("[4] 差は有意か — 標準誤差の目安")
    port, _ = simulate(cells, first, last, 30, 0)
    r = summarize(port)
    # 系列のtは尺度に依らないので、年率の標準誤差は 年率/t で近似できる
    se_ann = abs(r['ann'] * 100) / r['t'] if r['t'] else float('nan')
    print(f"  30日組み換えの年率 {r['ann']*100:+.2f}% / t={r['t']:.2f}")
    print(f"  年率の標準誤差はおよそ ±{se_ann:.1f}pt (= 年率/t)。")
    print("  → 上表の格子で数十bp〜1pt程度の差は、ノイズと区別できない。")
    print("     方針は「最も高い枡を選ぶ」ではなく「明確に劣る枡を避ける」で決めること。")


if __name__ == "__main__":
    main()
