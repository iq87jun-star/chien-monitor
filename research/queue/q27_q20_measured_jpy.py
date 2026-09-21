# -*- coding: utf-8 -*-
"""docs/272 Q27(Q20 の追試): 円クロス 6 本(USDJPY EURJPY GBPJPY AUDJPY CADJPY CHFJPY)の Wed 20-00 UTC・金利差 ≥ 1pp・高金利側 SHORT(= 円買い)を
(a) 実測 bid/ask(2024-01〜2026-08・SHORT は bid で売り ask で買い戻す)と仮定 3pip で比較(6 セル + 6 本等ウェイト合成 1 = 7)、
(b) 全期間(2016〜)の 6 本等ウェイト合成を仮定 3pip で 1 セル(事前指定の合成。前窓は門で空)。計 8 セル。
使い方: python3 queue/q27_q20_measured_jpy.py <累積セル数>"""
import sys, numpy as np, pandas as pd
from q_common import *
src = open("queue/q20_wed_swap_carry.py", encoding="utf-8").read(); exec(src.split("cum = int")[0].split("from q_common import *")[1])   # RATES, rate_series
JPY = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY"]; A0 = pd.Timestamp("2024-01-01")
cum = int(sys.argv[1]); R = Runner("Q27", cum, 8, "results/q27_q20_measured_jpy.csv")
def load_ask(sym):
    a = pd.read_csv(f"data_dukascopy/{sym}_hour_ask.csv.gz"); a["t"] = pd.to_datetime(a["timestamp"]); a = a.set_index("t").sort_index(); return a[~a.index.duplicated(keep="last")]["open"]
per_meas, per_asm, per_full = {}, {}, {}; rows = []
for sym in JPY:
    df = load(sym); o = df["open"]; ask = load_ask(sym); days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; m = (cy >= 1.0) & ~np.isnan(cy); t = t[m]; te = t + pd.Timedelta(hours=4)
    full = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(te).values); per_full[sym] = full            # 全期間・仮定 3pip
    t2 = t[t >= A0]; te2 = t2 + pd.Timedelta(hours=4)
    bid_in = o.reindex(t2).values; ask_out = ask.reindex(te2).values; mid_in = (bid_in + ask.reindex(t2).values) / 2; mid_out = (o.reindex(te2).values + ask_out) / 2
    ok = ~np.isnan(ask_out) & ~np.isnan(mid_out)
    meas = pd.Series(bid_in[ok] / ask_out[ok] - 1, index=t2[ok]); gross = pd.Series(-(mid_out[ok] / mid_in[ok] - 1), index=t2[ok]); asm = gross - cost(sym, mid_in[ok])
    per_meas[sym] = meas; per_asm[sym] = asm
    sm, sa, sg = st(meas, A0, END), st(asm, A0, END), st(gross, A0, END)
    rows.append(dict(cell=f"{sym} Wed 20-00 gate1 S", trades=len(meas), gross_bps=sg["mean"], assumed_bps=sa["mean"], measured_bps=sm["mean"], measured_cost_bps=round(sg["mean"] - sm["mean"], 2), plus_gross=f"{sg['plus']}/{sg['n']}", plus_assumed=f"{sa['plus']}/{sa['n']}", plus_measured=f"{sm['plus']}/{sm['n']}", p_measured=sm["p"]))
    R.add("Q20 追試(実測)", sym, "Wed 20-00 gate1 S measured 2024-01〜", meas)
def agg(d): X = pd.DataFrame(d); return X.mean(axis=1).dropna()
am, aa, af = agg(per_meas), agg(per_asm), agg(per_full)
sm, sa = st(am, A0, END), st(aa, A0, END)
rows.append(dict(cell="JPY6 等ウェイト合成", trades=len(am), gross_bps=round(sm["mean"] + (sa["mean"] - sm["mean"]) * 0, 2), assumed_bps=sa["mean"], measured_bps=sm["mean"], measured_cost_bps="", plus_gross="", plus_assumed=f"{sa['plus']}/{sa['n']}", plus_measured=f"{sm['plus']}/{sm['n']}", p_measured=sm["p"]))
R.add("Q20 追試(実測)", "JPY6", "等ウェイト合成 measured 2024-01〜", am)
R.add("Q20 追試(全期間)", "JPY6", "等ウェイト合成 assumed 3pip 2016〜", af)
pd.DataFrame(rows).to_csv("results/q27_q20_measured_jpy_table.csv", index=False); pd.set_option("display.width", 250)
print("== 2024-01〜2026-08 実測 vs 仮定 =="); print(pd.DataFrame(rows).to_string(index=False))
for name, a, b in (("pre", PRE0, IS0), ("IS", IS0, IS1), ("OOS", OOS0, END)):
    s = st(af, a, b); print(f"全期間合成(仮定 3pip) {name}: +月 {s['plus']}/{s['n']} 平均 {s['mean']} bps p={s['p']:.3g} 取引 {s['trades']}")
R.finish()
