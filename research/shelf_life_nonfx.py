#!/usr/bin/env python3
"""各ロジック(DOWセル)の「有効期限」を実測する (2026-08-15).

EA の InpExpiry=2026-10-15 は docs/174 の運用ルール(選抜から2ヶ月)であって、
実測に基づく値ではない。本スクリプトは以下を測る:

  1. 選抜法そのものの賞味期限 — 過去の各時点で「直近12Mのtで上位6セルを選ぶ」
     という同じ手続きを実行し、その後 1/2/3/6/12ヶ月の成績を追う(ウォークフォワード)
  2. 現行5レッグ個別の持続性 — 直近12M成績と次2M成績の関係、レッグ別の減衰
  3. 半減期 — 選抜窓の優位が何ヶ月で半分になるか

実行: cd research && python3 shelf_life_nonfx.py
"""
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

import nonfx_screen as N

MIN_TRADES = 30          # 選抜に必要な最小取引数(直近12M)
TOP_K = 6                # 選抜セル数(rev5と同じ)
HORIZONS = [30, 60, 90, 180, 365]

CUR = {"US500_Tue_L", "HK50_Mon_L", "HK50_Thu_S",
       "JP225_Wed_L", "XPTUSD_Tue_L", "XAGUSD_Tue_L"}


def hr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def d(s):
    return datetime.strptime(s, "%Y-%m-%d")


def cell_series(rows, di, sgn):
    """曜日セルの o2o リターン。キー=決済日(翌営業日)。"""
    out = {}
    for i in range(len(rows) - 1):
        if d(rows[i][0]).weekday() != di:
            continue
        e = rows[i][1]
        if e <= 0:
            continue
        out[rows[i + 1][0]] = sgn * (rows[i + 1][1] - e) / e
    return out


def window(series, lo, hi):
    return [v for k, v in series.items() if lo < k <= hi]


def tstat(xs):
    if len(xs) < 5:
        return 0.0
    sd = statistics.stdev(xs)
    return (statistics.mean(xs) / (sd / len(xs) ** 0.5)) if sd > 0 else 0.0


def compound(xs):
    e = 1.0
    for v in xs:
        e *= (1 + v)
    return e - 1


def main():
    # ---------------------------------------------------------- データ
    cells = {}
    for ysym, name in N.UNIVERSE:
        try:
            rows = N.fetch_daily(ysym, "10y")
        except Exception as ex:
            print(f"  skip {name}: {ex}")
            continue
        for di, dw in enumerate(N.DOWS):
            for sgn, tag in ((+1, "L"), (-1, "S")):
                s = cell_series(rows, di, sgn)
                if len(s) > 100:
                    cells[f"{name}_{dw}_{tag}"] = s
    print(f"  セル数 {len(cells)}  ({len(N.UNIVERSE)}銘柄 x 5曜日 x 2方向)")

    all_dates = sorted({k for s in cells.values() for k in s})
    first, last = all_dates[0], all_dates[-1]

    # ------------------------------------------ 1. ウォークフォワード(選抜法)
    hr("[1] 選抜法の賞味期限 — 過去の各時点で同じ手続きを実行し、その後を追う")
    print("手続き: 直近12Mのtで上位6セル → 逆ボラ加重 → その後の成績を測る")
    print("(相関フィルタは省略。選抜窓の成績は「選んだ結果」なので比較の基準として示す)\n")

    sel_dates = []
    t0 = d(first) + timedelta(days=400)
    while t0 < d(last) - timedelta(days=60):
        sel_dates.append(t0.strftime("%Y-%m-%d"))
        t0 += timedelta(days=30)

    fwd = defaultdict(list)
    inwin = []
    for T in sel_dates:
        lo = (d(T) - timedelta(days=365)).strftime("%Y-%m-%d")
        cand = []
        for name, s in cells.items():
            xs = window(s, lo, T)
            if len(xs) >= MIN_TRADES:
                sd = statistics.stdev(xs)
                if sd > 0:
                    cand.append((tstat(xs), name, sd, compound(xs)))
        if len(cand) < TOP_K:
            continue
        cand.sort(reverse=True)
        top = cand[:TOP_K]
        iv = [1.0 / c[2] for c in top]
        tot = sum(iv)
        w = {c[1]: v / tot for c, v in zip(top, iv)}
        inwin.append(sum(w[c[1]] * c[3] for c in top))

        for h in HORIZONS:
            hi = (d(T) + timedelta(days=h)).strftime("%Y-%m-%d")
            if hi > last:
                continue
            port = defaultdict(float)
            for name, wt in w.items():
                for k, v in cells[name].items():
                    if T < k <= hi:
                        port[k] += wt * v
            if port:
                fwd[h].append(compound([port[k] for k in sorted(port)]))

    print(f"選抜回数 {len(inwin)} (2017年頃〜、30日毎)")
    print(f"選抜窓12M の平均成績: {statistics.mean(inwin)*100:+.1f}%  ← これが「選んだ」結果\n")
    print(f"{'その後':>8s} {'平均':>9s} {'中央値':>9s} {'年率換算':>9s} {'勝率':>7s} {'12M比':>7s} {'n':>5s}")
    base = statistics.mean(inwin)
    for h in HORIZONS:
        xs = fwd[h]
        if not xs:
            continue
        m = statistics.mean(xs)
        ann = (1 + m) ** (365.0 / h) - 1
        wr = sum(1 for v in xs if v > 0) / len(xs)
        # 選抜窓を同じ長さに割り戻した水準に対する比
        eq = (1 + base) ** (h / 365.0) - 1
        print(f"{h:6d}日 {m*100:+8.2f}% {statistics.median(xs)*100:+8.2f}% "
              f"{ann*100:+8.2f}% {wr*100:6.1f}% {(m/eq if eq else 0):6.2f} {len(xs):5d}")
    print("\n※「12M比」= 選抜窓のペースを同期間に割り戻した値に対する実績比。")
    print("   1.00 なら選抜窓と同じ勢いが続いた、0 なら優位が完全に消えた。")

    # ------------------------------------------ 2. 半減期
    hr("[2] 半減期 — 優位が選抜窓の半分になるまで")
    pts = []
    for h in HORIZONS:
        if not fwd[h]:
            continue
        m = statistics.mean(fwd[h])
        eq = (1 + base) ** (h / 365.0) - 1
        pts.append((h, m / eq if eq else 0))
    half = None
    for i in range(1, len(pts)):
        (h0, r0), (h1, r1) = pts[i - 1], pts[i]
        if r0 >= 0.5 > r1:
            half = h0 + (h1 - h0) * (r0 - 0.5) / (r0 - r1)
            break
    if pts and pts[0][1] < 0.5:
        print(f"  最短horizon({pts[0][0]}日)で既に比 {pts[0][1]:.2f} < 0.5")
        print("  → 半減期は 30日未満。選抜直後から優位は半分以下。")
    elif half:
        print(f"  半減期 ≈ {half:.0f}日 ({half/30:.1f}ヶ月)")
    else:
        print("  測定範囲内では半減しない(優位が持続)")
    print(f"\n  EA の InpExpiry は選抜から60日。上表の60日時点の比は "
          f"{dict(pts).get(60, float('nan')):.2f}")

    # ------------------------------------------ 3. 現行5+1レッグ個別
    hr("[3] 現行レッグ個別 — 直近12Mの強さは次の2ヶ月に続くか")
    print("各レッグについて、過去の全時点で「直近12M成績」と「次60日成績」を対にして相関を取る\n")
    print(f"{'レッグ':16s} {'直近12M':>9s} {'過去平均':>9s} {'次60日':>9s} "
          f"{'条件付':>9s} {'相関':>7s} {'n':>5s}")
    for name in sorted(CUR):
        if name not in cells:
            continue
        s = cells[name]
        pairs = []
        t0 = d(first) + timedelta(days=400)
        while t0 < d(last) - timedelta(days=60):
            T = t0.strftime("%Y-%m-%d")
            lo = (d(T) - timedelta(days=365)).strftime("%Y-%m-%d")
            hi = (d(T) + timedelta(days=60)).strftime("%Y-%m-%d")
            a, b = window(s, lo, T), window(s, T, hi)
            if len(a) >= MIN_TRADES and len(b) >= 5:
                pairs.append((compound(a), compound(b)))
            t0 += timedelta(days=30)
        if len(pairs) < 20:
            print(f"{name:16s} データ不足")
            continue
        A = [p[0] for p in pairs]
        B = [p[1] for p in pairs]
        mA, mB = statistics.mean(A), statistics.mean(B)
        sA, sB = statistics.stdev(A), statistics.stdev(B)
        cor = (sum((a - mA) * (b - mB) for a, b in pairs) / len(pairs) / (sA * sB)
               if sA > 0 and sB > 0 else 0.0)
        # 「直近12Mが上位1/3だったとき」の次60日
        thr = sorted(A)[int(len(A) * 2 / 3)]
        hot = [b for a, b in pairs if a >= thr]
        cur12 = compound(window(s, (d(last) - timedelta(days=365)).strftime("%Y-%m-%d"), last))
        print(f"{name:16s} {cur12*100:+8.1f}% {mA*100:+8.1f}% {mB*100:+8.2f}% "
              f"{statistics.mean(hot)*100:+8.2f}% {cor:+7.2f} {len(pairs):5d}")
    print("\n※ 直近12M=いま選抜に使った窓の成績 / 過去平均=同レッグの12M成績の歴史的平均")
    print("   次60日=無条件の次2ヶ月 / 条件付=直近12Mが上位1/3だったときの次2ヶ月")
    print("   相関>0 なら「強かったものは続く」、<0 なら「強かったものは反落する」。")


if __name__ == "__main__":
    main()
