#!/usr/bin/env python3
"""販売中・出品予定の商品が書いている「発火頻度」の主張を実データで確認する。

いまのところ対象は 定石弐 待ち伏せ の
「1通貨ペアあたり、シグナルが出るのは年に数回です」。

  python3 firerate.py

注意: Yahoo の日足はFXでは 00:00 UTC 区切りで、MT5のサーバー時刻区切りの日足とは
別物。件数は一致しない。桁が合っているかを見るための概算。
仮説の検定ではないので台帳(累積検定数)には加算しない。
"""
import statistics as st
from collections import defaultdict
import engine
import indicators as I

FX = ["USDJPY","EURJPY","GBPJPY","AUDJPY","NZDJPY","CADJPY","CHFJPY",
      "EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCAD","USDCHF"]


def conditions(rows):
    """MQL5/定石弐_待ち伏せ.mq5 の EvalDay を日足で再現したもの(買い側)。

    実装に合わせてある点:
      - 標準偏差は判定バーを含まない直前20本、標本標準偏差(n-1)
      - 連続本数は「終値 < 前日終値」の連続(ローソクの陰線ではない)
      - 当日変動は前日終値比
    """
    c = [r[4] for r in rows]
    rsi = I.rsi(c, 14)
    out = []
    for i in range(21, len(rows)):
        w = c[i - 20:i]                       # 判定バー自身は含めない
        m = st.mean(w)
        sd = st.stdev(w)                      # 標本標準偏差
        if sd <= 0 or c[i - 1] <= 0: continue
        f = [
            rsi[i] is not None and rsi[i] < 35,                  # 1 RSI(14) < 35
            (c[i] - m) / sd < -1.5,                              # 2 平均から1.5SD下
            all(c[i - j] < c[i - j - 1] for j in range(3)),      # 3 3本以上の連続下落
            (c[i] / c[i - 1] - 1) * 100 < -0.5,                  # 4 前日比 0.5%超の下落
        ]
        out.append((rows[i][0], f))
    return out


def main():
    print("# 定石弐 待ち伏せ — 4条件の発火頻度(Yahoo日足・買い側のみ)\n")
    print("| ペア | 年数 | 4条件 | 年あたり | 3条件のみ | 年あたり |")
    print("|---|--:|--:|--:|--:|--:|")
    tot4 = tot3 = 0.0
    per_year = defaultdict(int)
    for sym in FX:
        rows = engine.rows_of(sym)
        cond = conditions(rows)
        years = len({d[:4] for d, _ in cond})
        n4 = sum(1 for d, f in cond if all(f))
        n3 = sum(1 for d, f in cond if sum(f) == 3)
        for d, f in cond:
            if all(f): per_year[d[:4]] += 1
        tot4 += n4 / years; tot3 += n3 / years
        print(f"| {sym} | {years} | {n4} | **{n4/years:.1f}** | {n3} | {n3/years:.1f} |")
    print(f"\n13ペア平均: 4条件 **年 {tot4/len(FX):.1f} 回** / "
          f"3条件どまり 年 {tot3/len(FX):.1f} 回")
    print(f"13ペア合計では 年 {tot4:.0f} 回。\n")
    print("## 年別の発火数(13ペア合計)\n")
    for y in sorted(per_year):
        print(f"  {y}  {per_year[y]:>3} 回  {'#' * per_year[y]}")
    print("\n## 条件ごとの成立率と、3条件どまりのとき何が欠けていたか\n")
    names = ["RSI(14)<35", "平均から1.5SD下", "3本以上の連続下落", "前日比0.5%超の下落"]
    hit = [0] * 4; miss = [0] * 4; tot = 0
    for sym in FX:
        for _, f in conditions(engine.rows_of(sym)):
            tot += 1
            for k in range(4):
                if f[k]: hit[k] += 1
            if sum(f) == 3:
                miss[f.index(False)] += 1
    print("| 条件 | 単独成立率 | 3条件どまりのとき欠けていた回数 |")
    print("|---|--:|--:|")
    for k in range(4):
        print(f"| {names[k]} | {hit[k]/tot:.1%} | {miss[k]} |")
    print(f"\n全観測 {tot:,} 日分(13ペア)。")


if __name__ == "__main__":
    main()
