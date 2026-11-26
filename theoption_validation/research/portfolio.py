#!/usr/bin/env python3
"""既存の脚の 10 年の取引(data/trades_*.json)から、配分・条件を変えた場合の月平均・最大DD・最悪月を出す。
使い方: python3 portfolio.py            # 現行(v1.19: 強弱オン・月末脚込み・倍率 1.67)と基準額(1 倍・強弱オフ)を表示
取引の行 = [脚ID, 日付, 勝ち(bool), 基準の賭け金, 倍率, 条件(bool/None)]。条件 = 月曜脚: 前の金曜が下落 / 仲値脚: 09:30→09:55 に上げ / AUDJPY_02: 当日下げ / EURGBP: 当日上げ。
月末脚(trades_newlegs_10y.json の "M")の行 = [通貨, 日付, 勝ち, S&P の月間騰落]。株高の月(>0)だけ使う。新しい案を足すときは series() に日次損益を足して stats() で比べる。"""
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "data")
def load():
    rows = json.load(open(f"{D}/trades_night_10y.json")) + json.load(open(f"{D}/trades_nakane_10y.json"))
    me = [r for r in json.load(open(f"{D}/trades_newlegs_10y.json"))["M"] if r[3] > 0]
    return rows, me
def series(rows, me, sizing=True, me_stake=10000, extra=None):
    """日次損益(基準額ベース)。extra = {日付: 損益} を足せる。"""
    day = collections.defaultdict(float)
    for i, d, w, st, po, c in rows:
        k = 1.0
        if sizing and c is not None:
            if i.endswith("_N6"): k = 1.25 if c else 0.75
            if i.endswith("_NK"): k = 1.4 if c else 0.4
        s = st * k; day[d] += s * (po - 1) if w else -s
    for p, d, w, m in me:
        if me_stake: day[d] += me_stake * 0.9 if w else -me_stake
    for d, x in (extra or {}).items(): day[d] += x
    return day
def stats(day, scale=1.0, lo="2016-12", hi="2026-12"):
    cum = peak = dd = 0.0; mon = collections.defaultdict(float)
    for d in sorted(day):
        if not lo <= d < hi: continue
        x = day[d] * scale; cum += x; peak = max(peak, cum); dd = max(dd, peak - cum); mon[d[:7]] += x
    return {"月平均": round(cum / max(1, len(mon))), "最大DD": round(dd), "最悪月": round(min(mon.values())), "マイナス月": sum(v < 0 for v in mon.values()), "月数": len(mon)}
def compare(name, day, base_dd=None):
    a = stats(day); h1 = stats(day, 1, "2016-12", "2021-12"); h2 = stats(day, 1, "2021-12", "2026-12")
    line = f"{name}: {a} | 前半 月 {h1['月平均']:,} DD {h1['最大DD']:,} | 後半 月 {h2['月平均']:,} DD {h2['最大DD']:,}"
    if base_dd: sc = base_dd / a["最大DD"]; line += f" | DD を {base_dd:,} に揃えた月平均 {stats(day, sc)['月平均']:,}(×{sc:.3f})"
    print(line); return a
if __name__ == "__main__":
    rows, me = load()
    base = compare("基準額(1 倍・強弱オフ・月末脚なし)", series(rows, [], sizing=False, me_stake=0))
    cur = series(rows, me, sizing=True)
    compare("現行の形(強弱オン・月末脚込み)1 倍", cur, base["最大DD"])
    print("現行 v1.19(×1.67):", stats(cur, 1.67))
