#!/usr/bin/env python3
"""棄却/通過にかかわらず、数字が出た仮説を潰しにかかるための検査。

HANDOFF.md 3節のチェックリストを機械化したもの。使い方:

    python3 attack.py <hypothesis-id>

出すもの:
  1. 逆方向でも成立するか       — ロングだけ勝つなら方向性エクスポージャー
  2. フィルタなし対照との比較   — 同一銘柄・同一保有日数の常時買い持ち
  3. 年別内訳                   — 特定の1〜2年に依存していないか
  4. 日付集約後のt値            — 同じ日に複数銘柄を建てても独立な観測は1つ
  5. エピソード集約後のt値      — 連続して成立し続ける局面は1つの出来事
"""
import json, math, os, sys, statistics as st
from collections import defaultdict
import datetime as dt
import engine

HERE = os.path.dirname(os.path.abspath(__file__))


def flip(params):
    """向きを反転した params を返す。反転できなければ None。"""
    p = dict(params)
    if "direction" in p:
        p["direction"] = -p["direction"]; return p
    if p.get("mode") in ("follow", "fade"):
        p["mode"] = "fade" if p["mode"] == "follow" else "follow"; return p
    if p.get("mode") in ("break",):
        p["mode"] = "fade"; return p
    return None


def by_date(series):
    d = defaultdict(list)
    for day, r in series: d[day].append(r)
    return {k: st.mean(v) for k, v in sorted(d.items())}


def episodes(dates, gap=5):
    """連続して成立している日をひとつの局面にまとめる(gap営業日以上空いたら別局面)。"""
    out, cur, prev = [], [], None
    for d in dates:
        cd = dt.date.fromisoformat(d)
        if prev is not None and (cd - prev).days > gap:
            out.append(cur); cur = []
        cur.append(d); prev = cd
    if cur: out.append(cur)
    return out


def report(series, hold, label):
    xs = [r for _, r in series]
    if len(xs) < 5:
        print(f"  {label}: n={len(xs)} 判定不能"); return
    t = engine.tstat(xs)
    print(f"  {label}: n={len(xs):>6}  平均={st.mean(xs)*100:>8.2f}bp  "
          f"生t={t:>6.2f}  補正t={t/math.sqrt(max(1,hold)):>6.2f}")


def attack_indicator(hid, entry, led):
    """指標トラックの検査。方向を当てにいっていないので「逆方向」は測らない。
    代わりに、合成が銘柄ごとの失敗を隠していないかを必ず見る。"""
    fam, params = entry["family"], entry["params"]
    hold = int(params.get("hold", 1))
    need = engine.required_t(led["cumulative_tests"])
    series = engine.build_forecast(fam, params)
    print(f"# 検査: {hid}  ({fam} / 指標トラック)\n\n{entry['note']}\n")

    print("## 1. 銘柄別内訳(合成が個別の失敗を隠していないか)")
    syms = params.get("symbols") or [params.get("sym")]
    bad = []
    for sym in syms:
        one = dict(params); one.pop("symbols", None); one["sym"] = sym
        r = engine.build_forecast(fam, one)
        if len(r) < 30:
            print(f"  {sym:8} 観測不足"); continue
        g = [x for _, x, _ in r]; b = [x for _, _, x in r]
        ratio = st.mean(g) / st.mean(b) if st.mean(b) else 0
        mark = " " if ratio > 0 else "  ← 悪化"
        if ratio <= 0: bad.append(sym)
        print(f"  {sym:8} n={len(r):>5}  改善率={ratio:>+6.1%}  "
              f"生t={engine.tstat(g):>7.2f}{mark}")
    print(f"  改善しない銘柄: {len(bad)}/{len(syms)}"
          + (f" — {', '.join(bad)}" if bad else ""))

    print("\n## 2. 年別")
    yr = defaultdict(list); yb = defaultdict(list)
    for d, g, b in series: yr[d[:4]].append(g); yb[d[:4]].append(b)
    for y in sorted(yr):
        ratio = st.mean(yr[y]) / st.mean(yb[y]) if st.mean(yb[y]) else 0
        print(f"  {y}  n={len(yr[y]):>5}  改善率={ratio:>+6.1%}  "
              f"{'+' if ratio > 0 else '-'}")

    print("\n## 3. 同一日を1観測に集約(銘柄間の相関を潰す)")
    dm = by_date([(d, g) for d, g, _ in series])
    xs = list(dm.values()); t = engine.tstat(xs)
    print(f"  独立な日数 n={len(xs)}  平均改善={st.mean(xs):.4f}  "
          f"生t={t:.2f}  補正t={t/math.sqrt(max(1,hold)):.2f}  (必要{need:.2f})")

    print("\n## 4. 連続する成立日を1局面に集約")
    eps = episodes(list(dm))
    ev = [st.mean([dm[d] for d in e]) for e in eps if e]
    if len(ev) >= 5:
        print(f"  局面数 n={len(ev)}  平均={st.mean(ev):.4f}  "
              f"生t={engine.tstat(ev):.2f}  勝ち局面 "
              f"{sum(1 for x in ev if x > 0)}/{len(ev)}")
    else:
        print(f"  局面数 n={len(ev)} — 連続しているため局面分割の意味がない")


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    hid = sys.argv[1]
    led = engine.load_ledger()
    entry = next((e for e in led["entries"] if e["id"] == hid), None)
    if entry is None:
        print(f"台帳に {hid} がありません"); return

    fam, params = entry["family"], entry["params"]
    hold = int(params.get("hold", 1))
    if entry.get("track") == "indicator":
        return attack_indicator(hid, entry, led)
    series = engine.build(fam, params)
    print(f"# 検査: {hid}  ({fam})\n\n{entry['note']}\n")

    print("## 1. 向き")
    report(series, hold, "そのまま")
    fp = flip(params)
    if fp is None:
        print("  逆方向: このパラメータでは反転できない")
    else:
        report(engine.build(fam, fp), hold, "逆方向  ")

    print("\n## 2. フィルタなし対照(常時買い持ち)")
    syms = params.get("symbols") or ([params["a"], params["b"]] if fam == "pairs"
                                     else [params["sym"]] if "sym" in params else None)
    if syms:
        bench = engine.benchmark_series(syms, hold)
        report([(None, r) for r in bench], hold, "常時買持")
        print(f"  超過: {(st.mean([r for _, r in series]) - st.mean(bench))*100:.2f}bp")

    print("\n## 3. 年別")
    yr = defaultdict(list)
    for d, r in series: yr[d[:4]].append(r)
    for y in sorted(yr):
        v = yr[y]
        bar = "+" if st.mean(v) > 0 else "-"
        print(f"  {y}  n={len(v):>5}  平均={st.mean(v)*100:>8.2f}bp  {bar}")
    best = max(yr, key=lambda y: st.mean(yr[y]) * len(yr[y]))
    rest = [r for y in yr if y != best for r in yr[y]]
    print(f"  最大寄与年 {best} を除くと: n={len(rest)} "
          f"平均={st.mean(rest)*100:.2f}bp 生t={engine.tstat(rest):.2f}")

    print("\n## 4. 同一日を1観測に集約(銘柄間の相関を潰す)")
    dm = by_date(series)
    xs = list(dm.values())
    t = engine.tstat(xs)
    print(f"  独立な日数 n={len(xs)}  平均={st.mean(xs)*100:.2f}bp  "
          f"生t={t:.2f}  補正t={t/math.sqrt(max(1,hold)):.2f}  "
          f"(必要{engine.required_t(led['cumulative_tests']):.2f})")

    print("\n## 5. 連続する成立日を1局面に集約")
    eps = episodes(list(dm))
    ev = [st.mean([dm[d] for d in e]) for e in eps if e]
    if len(ev) >= 5:
        print(f"  局面数 n={len(ev)}  平均={st.mean(ev)*100:.2f}bp  "
              f"生t={engine.tstat(ev):.2f}  勝ち局面 "
              f"{sum(1 for x in ev if x > 0)}/{len(ev)}")
        big = sorted(range(len(eps)), key=lambda i: -abs(ev[i]) * len(eps[i]))[:5]
        print("  寄与の大きい局面:")
        for i in big:
            print(f"    {eps[i][0]} 〜 {eps[i][-1]}  {len(eps[i])}日  "
                  f"平均={ev[i]*100:>8.2f}bp")
    else:
        print(f"  局面数 n={len(ev)} — 統計的に測れない")


if __name__ == "__main__":
    main()
