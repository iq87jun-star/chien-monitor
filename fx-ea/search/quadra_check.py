#!/usr/bin/env python3
"""定石弐 待ち伏せ の商品概要に書いてある主張を、独立データで確認する。

主張(SALES-quadra.md):
  「条件を3つに緩めると、検出される場面は一気に増える。そして、そこから
    優位性は失われます。損切り幅と利確幅を9通りに変えて試したところ、
    4条件すべて … 9通りすべてでプラス / 3条件に緩める … 9通り全滅」

日足では損切り・利確の経路依存を正しく評価できない(HANDOFF 5節)。
そこで9通りのSL/TPの代わりに、**保有日数を5通り**に変えて同じことを見る。
「4条件は保有日数を変えてもプラス、緩めると崩れる」が成り立つかどうか。

  python3 quadra_check.py

仮説の探索ではなく、公表済みの固定ルールの確認なので
台帳(累積検定数)には加算しない。firerate.py と同じ扱い。
"""
import math, statistics as st
from collections import defaultdict
import engine

FX = ["USDJPY","EURJPY","GBPJPY","AUDJPY","NZDJPY","CADJPY","CHFJPY",
      "EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCAD","USDCHF"]
HOLDS = [1, 2, 3, 5, 10]

BUY = [{"k":"rsi","n":14,"op":"<","thr":35.0},
       {"k":"z","win":20,"op":"<","thr":-1.5},
       {"k":"streak","run":3,"dirn":-1},
       {"k":"ret","op":"<","pct":-0.5}]
SELL = [{"k":"rsi","n":14,"op":">","thr":65.0},
        {"k":"z","win":20,"op":">","thr":1.5},
        {"k":"streak","run":3,"dirn":1},
        {"k":"ret","op":">","pct":0.5}]


def run(need, hold):
    """両サイドを合成して (日付, リターン%) の列を返す。"""
    out = []
    for conds, d in ((BUY, 1), (SELL, -1)):
        out += engine.build("combo", {"symbols": FX, "conds": conds,
                                      "direction": d, "hold": hold, "need": need})
    return out


def stats(series, hold):
    if len(series) < 20:
        return None
    xs = [r for _, r in series]
    t = engine.tstat(xs)
    per = defaultdict(list)
    for d, r in series: per[d].append(r)
    td = engine.tstat([st.mean(v) for _, v in sorted(per.items())]) / math.sqrt(hold)
    s = sorted(series)
    cut = int(len(s) * 0.6)
    return {"n": len(xs), "mean": st.mean(xs) * 100, "t": t,
            "t_adj": t / math.sqrt(hold), "t_date": td,
            "pf": engine.pf(xs),
            "is": st.mean([r for _, r in s[:cut]]) * 100,
            "oos": st.mean([r for _, r in s[cut:]]) * 100}


def main():
    print("# 定石弐 の「4つすべて」という主張の確認(Yahoo日足・両サイド合成)\n")
    print("MT5実測(437取引 / PF 1.307)とは別のデータ・別の決済ルール。")
    print("日足では損切り・利確を評価できないため、保有日数を5通りに変えて代用する。\n")
    labels = {None: "4条件すべて", 3: "3条件以上", 2: "2条件以上", 1: "1条件以上"}
    rows = {}
    for need in (None, 3, 2, 1):
        print(f"\n## {labels[need]}\n")
        print("| 保有 | n | 平均bp | PF | 生t | 補正t | 日次t | IS bp | OOS bp |")
        print("|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
        plus = 0
        for h in HOLDS:
            r = stats(run(need, h), h)
            if r is None:
                print(f"| {h} | — | 取引数不足 | | | | | | |"); continue
            if r["mean"] > 0: plus += 1
            print(f"| {h} | {r['n']} | {r['mean']:+.2f} | {r['pf']:.3f} | "
                  f"{r['t']:+.2f} | {r['t_adj']:+.2f} | {r['t_date']:+.2f} | "
                  f"{r['is']:+.2f} | {r['oos']:+.2f} |")
        rows[need] = plus
        print(f"\n**プラスだった保有日数: {plus}/{len(HOLDS)}**")

    print("\n---\n\n## まとめ\n")
    print("| 条件の緩さ | プラスだった保有日数 |")
    print("|---|--:|")
    for need in (None, 3, 2, 1):
        print(f"| {labels[need]} | **{rows[need]}/{len(HOLDS)}** |")
    print()
    if rows[None] == len(HOLDS) and rows[3] < len(HOLDS):
        print("**主張どおり。** 4条件はすべての保有日数でプラス、緩めると崩れる。")
    elif rows[None] == len(HOLDS):
        print("4条件はすべての保有日数でプラス。ただし緩めても崩れきってはいない。")
    else:
        print("**主張どおりにはならなかった。** 下の注意書きを読むこと。")
    print("""
注意:
- Yahoo の日足はFXでは 00:00 UTC 区切りで、業者のMT5の日足とは別物。
- 決済が違う(こちらは固定日数、商品は損切り・利確)。
- ここでプラスにならなくても、MT5実測(437取引 / PF 1.307)を否定しない。
  逆に、ここでプラスでも商品の成績を裏付けるものでもない。
  **別データ・別決済で同じ向きが出るかどうかだけを見ている。**""")


if __name__ == "__main__":
    main()
