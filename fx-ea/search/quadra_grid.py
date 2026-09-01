#!/usr/bin/env python3
"""定石弐の「3条件に緩めると9通り全滅」を、元の検証と同じルールで独立データ再現する。

元の検証(../backtest/user_v4v7.py の v4 と results.md 675行〜):
  - 7ペア、日足4条件、翌日始値エントリー、SL/TP は以後の日足高安への到達で判定
  - SL 1.0/1.5/2.0 ATR × RR 1.0/1.2/1.5 の9通り、最大8日保有、往復2pipコスト
  - 結果: 3条件 PF 0.978〜1.073(全滅)/ 4条件 1.177〜1.435(9通り全プラス)

こちらは同じロジックを Yahoo 日足(00:00 UTC区切り)で回す。
元はMT5サーバー日区切りのH1集約日足なので、バーの区切りだけが違う。
quadra_check.py(固定日数決済)では3条件が崩れなかったため、
**決済ルールまで元と揃えたときに崩れるか**を見るのが目的。

  python3 quadra_grid.py

公表済みの固定ルールの確認であり探索ではないので、台帳には加算しない。
"""
import statistics
import engine

PAIRS = ["USDCAD","GBPUSD","USDJPY","AUDUSD","GBPJPY","EURJPY","USDCHF"]
SL_MULTS = [1.0, 1.5, 2.0]
RRS = [1.0, 1.2, 1.5]


def pipsize(sym):
    return 0.01 if sym.endswith("JPY") else 0.0001


def v4(sym, need=4, sl_mult=1.5, rr=1.2, cost_pips=2.0):
    """../backtest/user_v4v7.py の v4() の忠実な移植。データだけ Yahoo 日足。"""
    rows = engine.rows_of(sym)
    o = [r[1] for r in rows]; h = [r[2] for r in rows]
    l = [r[3] for r in rows]; c = [r[4] for r in rows]

    # RSI(Wilder)と ATR(Wilder)— 元のコードと同じ組み方
    n = len(c)
    rsi = [None] * n
    g = lo = 0.0
    for i in range(1, 15):
        ch = c[i] - c[i - 1]; g += max(ch, 0); lo += max(-ch, 0)
    au, ad = g / 14, lo / 14
    rsi[14] = 100 - 100 / (1 + au / ad) if ad > 0 else 100.0
    for i in range(15, n):
        ch = c[i] - c[i - 1]
        au = (au * 13 + max(ch, 0)) / 14; ad = (ad * 13 + max(-ch, 0)) / 14
        rsi[i] = 100 - 100 / (1 + au / ad) if ad > 0 else 100.0
    atr = [None] * n
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
                          for i in range(1, n)]
    atr[0] = tr[0]
    for i in range(1, n): atr[i] = (atr[i - 1] * 13 + tr[i]) / 14

    ps = pipsize(sym); cost = cost_pips * ps
    trades = []; i = 22
    while i < n - 1:
        w = c[i - 20:i]
        m = statistics.mean(w); sd = statistics.stdev(w) if len(w) > 1 else 0
        z = (c[i] - m) / sd if sd > 0 else 0.0
        down = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
            else: break
        up = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
            else: break
        ret = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0.0
        mv = 0.005
        buy = (rsi[i] < 35) + (z < -1.5) + (down >= 3) + (ret < -mv)
        sell = (rsi[i] > 65) + (z > 1.5) + (up >= 3) + (ret > mv)
        sig = 1 if (buy >= need and buy > sell) else (-1 if (sell >= need and sell > buy) else 0)
        if sig == 0: i += 1; continue
        entry = o[i + 1]; sld = sl_mult * atr[i]; tpd = rr * sld
        if sld <= 0 or entry <= 0: i += 1; continue
        sl = entry - sig * sld; tp = entry + sig * tpd
        ex = None; j = i + 1; held = 0
        while j < n and held < 8:
            if sig > 0:
                if l[j] <= sl: ex = sl; break
                if h[j] >= tp: ex = tp; break
            else:
                if h[j] >= sl: ex = sl; break
                if l[j] <= tp: ex = tp; break
            j += 1; held += 1
        if ex is None: ex = c[min(j, n - 1)]
        r = sig * (ex / entry - 1.0) - cost / entry
        trades.append((rows[min(j, n - 1)][0], r))
        i = max(i + 1, j)
    return trades


def pf(xs):
    g = sum(x for x in xs if x > 0); lo = abs(sum(x for x in xs if x < 0))
    return g / lo if lo else 99.0


def main():
    print("# 定石弐 9通り格子の独立再現(Yahoo日足・7ペア・元と同じ決済ルール)\n")
    print("元の結果: 3条件 PF 0.978〜1.073(全滅)/ 4条件 1.177〜1.435(9通り全プラス)\n")
    summary = {}
    for need in (4, 3):
        print(f"\n## {need}条件{'すべて' if need == 4 else '以上'}\n")
        print("| SL(ATR) | RR | n | PF | 平均bp | 生t |")
        print("|--:|--:|--:|--:|--:|--:|")
        pfs = []
        for sm in SL_MULTS:
            for rr in RRS:
                xs = []
                for sym in PAIRS:
                    xs += [r for _, r in v4(sym, need=need, sl_mult=sm, rr=rr)]
                p = pf(xs); pfs.append(p)
                t = engine.tstat(xs)
                print(f"| {sm} | {rr} | {len(xs)} | **{p:.3f}** | "
                      f"{statistics.mean(xs)*1e4:+.1f} | {t:+.2f} |")
        summary[need] = pfs
        plus = sum(1 for p in pfs if p > 1.0)
        print(f"\nPF範囲 **{min(pfs):.3f} 〜 {max(pfs):.3f}** / プラス {plus}/9")

    print("\n---\n\n## まとめ\n")
    print("| | 元(MT5サーバー日) | 再現(Yahoo日足) |")
    print("|---|---|---|")
    print(f"| 4条件 | 1.177〜1.435・9/9プラス | "
          f"{min(summary[4]):.3f}〜{max(summary[4]):.3f}・"
          f"{sum(1 for p in summary[4] if p>1)}/9プラス |")
    print(f"| 3条件 | 0.978〜1.073・0/9プラス | "
          f"{min(summary[3]):.3f}〜{max(summary[3]):.3f}・"
          f"{sum(1 for p in summary[3] if p>1)}/9プラス |")
    print("""
注意: バーの区切り(Yahoo 00:00 UTC / MT5サーバー日)と価格ソースが違うため
完全一致はしない。同じ向き・同じ序列が出るかどうかだけを見る。
SLとTPが同じ日足に両方収まる場合はSL優先(元のコードと同じ悲観側の解決)。""")


if __name__ == "__main__":
    main()
