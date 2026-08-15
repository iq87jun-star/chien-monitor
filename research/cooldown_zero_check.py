#!/usr/bin/env python3
"""クールダウン0日(即時再エントリー可)の妥当性を直接検証する.

方針決定: 機会損失を避けるため CD=0 を採る。その裏づけと代償を測る。

  Q1. CD=90 は実際どれだけの機会損失を出していたか
      (ブロックされたセルと、代わりに入ったセルの成績を直接比較)
  Q2. CD=0 の代償は何か
      (直前に脱落したセルを即座に採り直したケースの成績)
  Q3. 「落ちた直後」と「しばらく前に落ちた」で成績は違うか

実行: cd research && python3 cooldown_zero_check.py
"""
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

import nonfx_screen as N
from rebalance_policy_nonfx import build_cells, win, tstat, comp, d, ds

MIN_TRADES = 30
TOP_K = 6
INTERVAL = 30


def hr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def rank(cells, Ts, lo, exclude=()):
    out = []
    for name, s in cells.items():
        if name in exclude:
            continue
        xs = win(s, lo, Ts)
        if len(xs) >= MIN_TRADES:
            sd = statistics.stdev(xs)
            if sd > 0:
                out.append((tstat(xs), name, sd))
    out.sort(reverse=True)
    return out


def fwd(cells, name, Ts, days):
    xs = win(cells[name], Ts, ds(d(Ts) + timedelta(days=days)))
    return comp(xs) if len(xs) >= 2 else None


def main():
    cells = build_cells()
    all_d = sorted({k for s in cells.values() for k in s})
    first, last = all_d[0], all_d[-1]
    print(f"  セル数 {len(cells)}  期間 {first} .. {last}  (組み換え間隔 {INTERVAL}日)")

    # ---------------------------------------------------------------- 走査
    dropped_at = {}
    prev = set()
    reentry = defaultdict(list)     # 脱落からの経過日数バケット -> 次30日リターン
    fresh = []                      # 一度も選抜されたことがないセルの初採用
    held = []                       # 継続保有
    blocked_ev = []                 # CD=90 ならブロックされた事例 (機会損失の測定)

    T = d(first) + timedelta(days=400)
    while T < d(last) - timedelta(days=INTERVAL):
        Ts, lo = ds(T), ds(T - timedelta(days=365))
        r = rank(cells, Ts, lo)
        if len(r) < TOP_K:
            T += timedelta(days=INTERVAL)
            continue
        cur = {c[1] for c in r[:TOP_K]}

        # --- CD=90 だったらブロックされていたセルを特定し、機会損失を測る
        cd_block = {nm for nm, dd in dropped_at.items()
                    if (T - d(dd)).days < 90 and nm in cur}
        if cd_block:
            alt = [c for c in r if c[1] not in cd_block][:TOP_K]
            repl = {c[1] for c in alt} - cur
            for nm in cd_block:
                a = fwd(cells, nm, Ts, INTERVAL)
                if a is None:
                    continue
                bs = [fwd(cells, x, Ts, INTERVAL) for x in repl]
                bs = [x for x in bs if x is not None]
                if bs:
                    blocked_ev.append((a, statistics.mean(bs)))

        # --- 採用理由の分類
        for nm in cur:
            f = fwd(cells, nm, Ts, INTERVAL)
            if f is None:
                continue
            if nm in prev:
                held.append(f)
            elif nm in dropped_at:
                gap = (T - d(dropped_at[nm])).days
                b = ("即時(≤30日)" if gap <= 30 else
                     "31-60日" if gap <= 60 else
                     "61-90日" if gap <= 90 else
                     "91-180日" if gap <= 180 else "180日超")
                reentry[b].append(f)
            else:
                fresh.append(f)

        for nm in prev - cur:
            dropped_at[nm] = Ts
        prev = cur
        T += timedelta(days=INTERVAL)

    # ---------------------------------------------------------------- Q1
    hr("[1] CD=90 の機会損失 — ブロックされたセル vs 代わりに入ったセル")
    if not blocked_ev:
        print("  ブロック事例なし")
    else:
        a = [x[0] for x in blocked_ev]
        b = [x[1] for x in blocked_ev]
        yrs = (d(last) - d(first)).days / 365.25 - 1.1
        print(f"  ブロック事例 {len(blocked_ev)}件 (年 {len(blocked_ev)/yrs:.1f}件)")
        print(f"  ブロックされたセルの次30日  : {statistics.mean(a)*100:+.3f}%")
        print(f"  代わりに入ったセルの次30日  : {statistics.mean(b)*100:+.3f}%")
        print(f"  差(1件あたりの機会損失)     : {(statistics.mean(a)-statistics.mean(b))*100:+.3f}%")
        wins = sum(1 for x, y in blocked_ev if x > y) / len(blocked_ev)
        print(f"  ブロックされた側が勝った割合: {wins*100:.0f}%")
        # 構成全体(6本)への年間影響
        per_yr = len(blocked_ev) / yrs
        imp = (statistics.mean(a) - statistics.mean(b)) * per_yr / TOP_K
        print(f"\n  → 構成全体では年 {imp*100:+.2f}pt 相当。")

    # ---------------------------------------------------------------- Q2/Q3
    hr("[2] CD=0 の代償 — 採用理由別の次30日リターン")
    print(f"{'採用理由':16s} {'件数':>6s} {'平均':>9s} {'中央値':>9s} {'勝率':>7s}")

    def row(lab, xs):
        if len(xs) < 5:
            print(f"{lab:16s} {len(xs):6d} {'(件数不足)':>9s}")
            return
        wr = sum(1 for v in xs if v > 0) / len(xs)
        print(f"{lab:16s} {len(xs):6d} {statistics.mean(xs)*100:+8.3f}% "
              f"{statistics.median(xs)*100:+8.3f}% {wr*100:6.1f}%")

    row("継続保有", held)
    row("新規(初採用)", fresh)
    for b in ("即時(≤30日)", "31-60日", "61-90日", "91-180日", "180日超"):
        row("再" + b, reentry.get(b, []))

    allre = [v for b in reentry.values() for v in b]
    print()
    row("再エントリー計", allre)
    print("\n※「即時(≤30日)」= 前回の組み換えで落としたセルを、次の組み換えで採り直した")
    print("   ケース。CD=0 で初めて起きる事象であり、ここが劣後しないかが要点。")

    if len(allre) >= 5 and len(fresh) >= 5:
        m1, m2 = statistics.mean(allre), statistics.mean(fresh)
        s1 = statistics.stdev(allre) / len(allre) ** 0.5
        s2 = statistics.stdev(fresh) / len(fresh) ** 0.5
        t = (m1 - m2) / ((s1 ** 2 + s2 ** 2) ** 0.5)
        print(f"\n  再エントリー vs 新規: 差 {(m1-m2)*100:+.3f}% / t={t:+.2f}")
        print("  |t|<2 なら「再エントリーは新規と同等」= CD=0 に統計的な問題は無い。")


if __name__ == "__main__":
    main()
