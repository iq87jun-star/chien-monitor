# -*- coding: utf-8 -*-
"""docs/277 Q29a: ゴールド・銀の水曜ロール(コンタンゴ → LONG がロールで利益)。事前登録セル 2: XAUUSD Wed 20-00 LONG(実測 bid/ask・2024-01〜)/ XAGUSD Wed 20-00 LONG(仮定 5 bps・2018〜)。
対照(登録外・診断): 他曜日の同窓 LONG、XAUUSD 仮定コスト全期間。使い方: python3 queue/q29a_gold_roll.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
cum = int(sys.argv[1]); R = Runner("Q29a", cum, 2, "results/q29a_gold_roll.csv")
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]
def load_ask(sym):
    a = pd.read_csv(f"data_dukascopy/{sym}_hour_ask.csv.gz"); a["t"] = pd.to_datetime(a["timestamp"]); a = a.set_index("t").sort_index(); return a[~a.index.duplicated(keep="last")]["open"]
print("== 対照(仮定コスト・全期間・LONG 20-00 UTC) ==")
for sym in ("XAUUSD", "XAGUSD"):
    df = load(sym); o = df["open"]
    for d in range(5):
        t = o.index[(o.index.dayofweek == d) & (o.index.hour == 20)]; r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values)
        si, so, sp = st(r, IS0, IS1), st(r, OOS0, END), st(r, PRE0, IS0)
        print(f"{sym} {DOW[d]} L: IS {si['plus']}/{si['n']} {si['mean']} bps p={si['p']:.3g} | OOS {so['plus']}/{so['n']} {so['mean']} | pre {sp['plus']}/{sp['n']}")
        if d == 2 and sym == "XAGUSD": R.add("ゴールドロール", sym, "Wed 20-00 L assumed 5bps", r)
# XAUUSD 実測(2024-01〜): ask で買い bid で売る
df = load("XAUUSD"); o = df["open"]; ask = load_ask("XAUUSD"); A0 = pd.Timestamp("2024-01-01")
t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20) & (o.index >= A0)]; te = t + pd.Timedelta(hours=4)
meas = pd.Series(o.reindex(te).values / ask.reindex(t).values - 1, index=t).dropna()
mid_in = (o.reindex(t).values + ask.reindex(t).values) / 2; mid_out = (o.reindex(te).values + ask.reindex(te).values) / 2; gross = pd.Series(mid_out / mid_in - 1, index=t).dropna()
print(f"\nXAUUSD Wed L 実測(2024-01〜): 取引 {len(meas)} 粗利 {gross.mean()*1e4:.2f} bps 実測後 {meas.mean()*1e4:.2f} bps 実測往復 {(gross.mean()-meas.mean())*1e4:.2f} bps +月 {st(meas, A0, END)['plus']}/{st(meas, A0, END)['n']} p={st(meas, A0, END)['p']:.3g}")
for d, lab in ((1, "Tue"), (3, "Thu")):
    t2 = o.index[(o.index.dayofweek == d) & (o.index.hour == 20) & (o.index >= A0)]; te2 = t2 + pd.Timedelta(hours=4); m2 = pd.Series(o.reindex(te2).values / ask.reindex(t2).values - 1, index=t2).dropna()
    print(f"  対照 {lab} L 実測: {m2.mean()*1e4:.2f} bps +月 {st(m2, A0, END)['plus']}/{st(m2, A0, END)['n']}")
R.add("ゴールドロール", "XAUUSD", "Wed 20-00 L measured 2024-01〜", meas)
R.finish()
