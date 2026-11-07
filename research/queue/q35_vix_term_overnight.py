# -*- coding: utf-8 -*-
"""docs/284 §1 Q35: VIX/VIX3M の期間構造を状態にした指数オーバーナイト LONG。使い方: python3 queue/q35_vix_term_overnight.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
def cboe(n):
    d = pd.read_csv(f"data_ext/{n}_History.csv"); d["d"] = pd.to_datetime(d["DATE"]); return d.set_index("d")["CLOSE"]
s = (cboe("VIX") / cboe("VIX3M")).dropna(); H_ON = int(sys.argv[2]) if len(sys.argv) > 2 else 21   # 修正: 米指数 CFD は 21 UTC バーが欠けるため 20 UTC 始値で再実行(docs/286)
cum = int(sys.argv[1]); R = Runner("Q35", cum, 9, "results/q35_vix_term_overnight.csv")
for sym in ("US500", "US30", "NAS100"):
    df = load(sym); selfcheck(sym, df); o = df["open"]
    t21 = o.index[(o.index.hour == H_ON) & (o.index.dayofweek < 5)]; sig = s.reindex(t21.normalize()).values
    def overnight(mask, lab):
        t = t21[mask]; te = t + pd.Timedelta(hours=38 - H_ON)
        return trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(te).values)
    ok = ~np.isnan(sig)
    r_all = overnight(ok, "all"); print(f"  {sym} 無条件 O/N: IS {st(r_all, IS0, IS1)['mean']} bps  OOS {st(r_all, OOS0, END)['mean']}  (n={len(r_all)})")
    R.add("VIX 期間構造", sym, f"a) contango(s<1) O/N {H_ON}→14 L", overnight(ok & (sig < 1), "c"))
    R.add("VIX 期間構造", sym, f"b) backwardation(s>1) O/N {H_ON}→14 L", overnight(ok & (sig > 1), "b"))
    t14 = o.index[(o.index.hour == 14) & (o.index.dayofweek < 5)]; days14 = pd.Series(t14, index=t14.normalize())
    bd = pd.DatetimeIndex(sorted(set(t14.normalize()))); sig_d = s.reindex(bd)
    t_in, t_out = [], []
    for i in range(len(bd) - 6):
        if sig_d.iloc[i] > 1: t_in.append(days14[bd[i + 1]]); t_out.append(days14[bd[i + 6]])
    m = dict(zip(t_in, t_out)); tk = nonoverlap(pd.DatetimeIndex(t_in), lambda t: m[t]); to = pd.DatetimeIndex([m[t] for t in tk])
    R.add("VIX 期間構造", sym, "c) after backwardation 5bd L (nonoverlap)", trades(sym, tk, o.reindex(tk).values, np.ones(len(tk)), o.reindex(to).values))
R.finish()
