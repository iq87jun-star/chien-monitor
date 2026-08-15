#!/usr/bin/env python3
"""稼働中プロップ全口座を1つ/複数のポートフォリオと見なした場合の数値 (2026-08-15).

対象7口座 (構成は p8p06z の焼き込みEA群 + 本ブランチ NonFX2 v1.02 から抽出):
  1. FN Instant 20k #11988011   mult 4.00  Mon GBPJPY.374/AUDJPY.322 + v4 USDJPY.304
  2. Fintokei パール500万        mult 4.00  同上
  3. FTMO50k #531407058 (C6m)   mult 6.00  Mon GBPJPY.323/AUDJPY.269 + v4 NZD.207/AUD.201
  4. Fintokei 速攻プロ2000万     mult 2.50  同上 (C6m系)
  5. FTMO50k #521100397 (D3m)   mult 5.52  Mon USDJPY.374/GBPJPY.139 + v4 NZD.287/AUD.200
  6. FN100k #14166201 (NonFX)   mult 1.48  Mon ETH.145 + v4 BTC.211 + Hold UK100.491/WTI.153
  7. FN100k #14074882 (NonFX2)  mult 0.90  DOW 5レッグ (v1.02)

除外: FTMO #531343523 (RecentFit5) — nonfx_screen.py の現行ブックプロキシ(2026-08-15改訂)
      に含まれておらず、5スリーブ構造のプロキシ化も別作業のため。除外は保守側ではない。

近似の限界: Mon/DOW は o2o プロキシ (執行時刻・コスト未計上)。v4 は
v4_trades のシグナルパリティ (EA実装と完全一致ではない)。JPY口座は150円/$で換算。

実行: cd research && python3 prop_fleet_portfolio.py
"""
import math
import statistics
from datetime import datetime, timedelta, timezone

import nonfx_screen as N

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
LO = "2019-01-01"   # ETH/BTC の初期異常バー(2016-18)を除外し、全統計をこの日以降に統一
YR = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")

# (口座名, 資本USD, mult, フロア%(EA全停止線), レッグ[(yahoo, family, arg, w)])
BOOKS = [
    ("Instant20k",   20_000, 4.00, 6.0 * 0.8, [        # MLL-6% 相当
        ("GBPJPY=X", "DOW", ("Mon", +1), 0.374),
        ("AUDJPY=X", "DOW", ("Mon", +1), 0.322),
        ("USDJPY=X", "V4",  None,        0.304)]),
    ("パール500万",   33_333, 4.00, 9.0, [
        ("GBPJPY=X", "DOW", ("Mon", +1), 0.374),
        ("AUDJPY=X", "DOW", ("Mon", +1), 0.322),
        ("USDJPY=X", "V4",  None,        0.304)]),
    ("FTMO_C6m",     50_000, 6.00, 9.0, [
        ("GBPJPY=X", "DOW", ("Mon", +1), 0.323),
        ("AUDJPY=X", "DOW", ("Mon", +1), 0.269),
        ("NZDUSD=X", "V4",  None,        0.207),
        ("AUDUSD=X", "V4",  None,        0.201)]),
    ("速攻プロ2000万", 133_333, 2.50, 2.4, [
        ("GBPJPY=X", "DOW", ("Mon", +1), 0.323),
        ("AUDJPY=X", "DOW", ("Mon", +1), 0.269),
        ("NZDUSD=X", "V4",  None,        0.207),
        ("AUDUSD=X", "V4",  None,        0.201)]),
    ("FTMO_D3m",     50_000, 5.52, 9.0, [
        ("USDJPY=X", "DOW", ("Mon", +1), 0.374),
        ("GBPJPY=X", "DOW", ("Mon", +1), 0.139),
        ("NZDUSD=X", "V4",  None,        0.287),
        ("AUDUSD=X", "V4",  None,        0.200)]),
    ("FN_NonFX",    100_000, 1.48, 9.0, [
        ("ETH-USD",  "DOW", ("Mon", +1), 0.145),
        ("BTC-USD",  "V4",  None,        0.211),
        ("^FTSE",    "HOLD", None,       0.491),
        ("CL=F",     "HOLD", None,       0.153)]),
    ("FN_NonFX2",   100_000, 0.90, 8.0, [
        ("^GSPC",    "DOW", ("Tue", +1), 0.333),
        ("^HSI",     "DOW", ("Mon", +1), 0.225),
        ("^HSI",     "DOW", ("Thu", -1), 0.225),
        ("^N225",    "DOW", ("Wed", +1), 0.152),
        ("SI=F",     "DOW", ("Tue", +1), 0.065)]),
]


def hr(t):
    print(f"\n{'=' * 84}\n{t}\n{'=' * 84}")


def maxdd(series):
    eq = pk = 1.0
    mdd = 0.0
    for k in sorted(series):
        eq *= (1 + series[k])
        pk = max(pk, eq)
        mdd = min(mdd, eq / pk - 1)
    return mdd


def stats(series, lo=None, hi="9999"):
    lo = lo or LO
    s = {k: v for k, v in series.items() if lo <= k < hi}
    if len(s) < 30:
        return None
    ks = sorted(s)
    yrs = (datetime.strptime(ks[-1], "%Y-%m-%d")
           - datetime.strptime(ks[0], "%Y-%m-%d")).days / 365.25
    eq = 1.0
    for k in ks:
        eq *= (1 + s[k])
    xs = [s[k] for k in ks]
    sd = statistics.stdev(xs)
    t = statistics.mean(xs) / (sd / math.sqrt(len(xs))) if sd > 0 else 0.0
    return dict(ann=(eq ** (1 / yrs) - 1) if yrs > 0.5 else eq - 1,
                mdd=maxdd(s), worst=min(xs), t=t, n=len(xs))


def main():
    data = {}
    for y in sorted({leg[0] for _, _, _, _, legs in BOOKS for leg in legs}):
        data[y] = N.fetch_daily(y, "10y")
        print(f"  {y:10s} {len(data[y])} bars")

    # ---------------------------------------------------------- 口座系列
    series = {}
    for name, cap, mult, floor, legs in BOOKS:
        port = {}
        for y, fam, arg, w in legs:
            rows = data[y]
            if fam == "DOW":
                s = N.dow_daily_returns(rows, N.DOWS.index(arg[0]), arg[1])
            elif fam == "HOLD":
                # EA の Hold 災害SL (InpHoldCatSLPct=15%) を日次で近似。
                # これが無いと 2020-04 の WTI マイナス価格 (-306%/日) が素通りする。
                s = {k: max(v, -0.15) for k, v in N.hold_daily_returns(rows).items()}
            else:
                s = N.v4_daily_returns(rows)
            for k, v in s.items():
                port[k] = port.get(k, 0.0) + w * v * mult
        series[name] = port

    hr("[1] 口座単体 (mult適用後・口座内%・コスト未計上)")
    print(f"{'口座':14s} {'資本$':>9s} {'mult':>5s} | {'年率(全)':>9s} {'年率(12M)':>9s} "
          f"{'maxDD':>8s} {'最悪日':>8s} | {'フロア':>6s} {'余裕':>7s}")
    for name, cap, mult, floor, _ in BOOKS:
        a = stats(series[name])
        i = stats(series[name], YR)
        gap = floor - abs(a['mdd'] * 100)
        print(f"{name:14s} {cap:9,d} {mult:5.2f} | {a['ann']*100:+8.1f}% "
              f"{(i['ann']*100 if i else float('nan')):+8.1f}% {a['mdd']*100:7.2f}% "
              f"{a['worst']*100:7.2f}% | {-floor:5.1f}% {gap:+6.2f}pt")
    print("\n※「余裕」= EA全停止線に対する歴史的maxDDの残り幅。負=歴史再演で停止する。")

    # ---------------------------------------------------------- 相関行列
    hr("[2] 口座間の相関 (日次・共通日)")
    names = [b[0] for b in BOOKS]
    alld = sorted(set().union(*[set(series[n]) for n in names]))
    alld = [d for d in alld if d >= LO]
    M = {n: [series[n].get(d, 0.0) for d in alld] for n in names}

    def corr(a, b):
        ma, mb = statistics.mean(a), statistics.mean(b)
        sa, sb = statistics.stdev(a), statistics.stdev(b)
        if sa <= 0 or sb <= 0:
            return 0.0
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (len(a) - 1) / (sa * sb)

    print(f"{'':14s}" + "".join(f"{n[:9]:>10s}" for n in names))
    for i, ni in enumerate(names):
        row = f"{ni:14s}"
        for j, nj in enumerate(names):
            c = corr(M[ni], M[nj])
            row += f"{c:10.2f}"
        print(row)

    # ---------------------------------------------------------- 合成
    hr("[3] 全口座を1つのポートフォリオとみなす (資本加重・$486,666)")
    caps = {b[0]: b[1] for b in BOOKS}
    tot = sum(caps.values())
    comb = {}
    for n in names:
        for k, v in series[n].items():
            comb[k] = comb.get(k, 0.0) + v * caps[n] / tot
    a = stats(comb)
    i = stats(comb, YR)
    wavg_mdd = sum(abs(stats(series[n])['mdd']) * caps[n] for n in names) / tot
    print(f"  年率(全期間)  : {a['ann']*100:+7.2f}%   (12M: {i['ann']*100:+.2f}%)")
    print(f"  maxDD         : {a['mdd']*100:7.2f}%   最悪日 {a['worst']*100:.2f}%   t={a['t']:.2f}")
    print(f"  金額換算      : 年 {a['ann']*tot:+,.0f}$ / maxDD {a['mdd']*tot:,.0f}$ / 最悪日 {a['worst']*tot:,.0f}$")
    print(f"  分散効果      : 口座DDの加重平均 {wavg_mdd*100:.2f}% → 合成 {abs(a['mdd'])*100:.2f}% "
          f"(比 {abs(a['mdd'])/wavg_mdd:.2f})")

    # ---------------------------------------------------------- グループ
    hr("[4] 2ポートフォリオに分けた場合 (FX-JPY系 5口座 / 非FX 2口座)")
    grp = {"FX-JPY系(1-5)": names[:5], "非FX(6-7)": names[5:]}
    gser = {}
    for g, ns in grp.items():
        gtot = sum(caps[n] for n in ns)
        s = {}
        for n in ns:
            for k, v in series[n].items():
                s[k] = s.get(k, 0.0) + v * caps[n] / gtot
        gser[g] = s
        a = stats(s)
        i = stats(s, YR)
        print(f"  {g:14s} 資本 {gtot:8,d}$ | 年率 {a['ann']*100:+6.2f}% (12M {i['ann']*100:+6.2f}%) "
              f"maxDD {a['mdd']*100:6.2f}% 最悪日 {a['worst']*100:5.2f}% t={a['t']:.2f}")
    ga, gb = gser["FX-JPY系(1-5)"], gser["非FX(6-7)"]
    days = [d for d in alld]
    c = corr([ga.get(d, 0.0) for d in days], [gb.get(d, 0.0) for d in days])
    print(f"\n  グループ間相関: {c:+.2f}")

    # ---------------------------------------------------------- 集中度
    hr("[5] 銘柄集中 (合成ポートフォリオの実効ウェイト = w×mult×資本/総資本)")
    expo = {}
    for name, cap, mult, floor, legs in BOOKS:
        for y, fam, arg, w in legs:
            key = y
            expo[key] = expo.get(key, 0.0) + w * mult * cap / tot
    for k, v in sorted(expo.items(), key=lambda x: -x[1]):
        print(f"  {k:10s} {v*100:6.1f}%")
    print(f"  {'合計(グロス)':10s} {sum(expo.values())*100:6.1f}%")


if __name__ == "__main__":
    main()
