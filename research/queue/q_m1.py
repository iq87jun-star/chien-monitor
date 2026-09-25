# -*- coding: utf-8 -*-
"""docs/294 M1 家族の共通部: 終日 M1(data_dukascopy_m1/<SYM>_bid_m1_full.csv.gz)・DST・実測コスト・2024 起点の窓と判定(docs/284 §2 の代替判定)。"""
import os, numpy as np, pandas as pd
import q_common as qc
from q_common import *
qc.PRE0, qc.IS0, qc.IS1, qc.OOS0 = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31 23:59"), pd.Timestamp("2025-01-01")
def uk_bst(d):
    y = d.year; r = pd.date_range(f"{y}-03-25", f"{y}-03-31"); mar = max(r[r.dayofweek == 6]); r2 = pd.date_range(f"{y}-10-25", f"{y}-10-31"); octo = max(r2[r2.dayofweek == 6])
    return mar <= d.normalize() < octo
def us_dst(d):
    y = d.year; m = pd.date_range(f"{y}-03-08", f"{y}-03-14"); mar = m[m.dayofweek == 6][0]; n = pd.date_range(f"{y}-11-01", f"{y}-11-07"); nov = n[n.dayofweek == 6][0]
    return mar <= d.normalize() < nov
def m1(sym, full=True):
    d = pd.read_csv(f"data_dukascopy_m1/{sym}_bid_m1_{'full' if full else '1400_1730'}.csv.gz"); d["t"] = pd.to_datetime(d["timestamp"]); return d.set_index("t").sort_index()
def rt_cost(sym, hour=15):
    """H1 bid/ask の当該 UTC 時のスプレッド中央値 ×2(往復・比率)。ask 無しは q_common の 3 pip 仮定。"""
    p = f"data_dukascopy/{sym}_hour_ask.csv.gz"
    if not os.path.exists(p): return float(cost(sym, np.array([m1(sym)["open"].iloc[0]]))[0])
    b = load(sym)["open"]; a = pd.read_csv(p); a["t"] = pd.to_datetime(a["timestamp"]); a = a.set_index("t").sort_index()["open"]; a = a[~a.index.duplicated()]
    b = b[b.index >= "2024-01-01"]; a = a.reindex(b.index); sp = ((a - b) / ((a + b) / 2)); return float(sp[b.index.hour == hour].median() * 2)
def ret_series(o, t_in, dir_, t_out, c):
    """始値 o(M1)で t_in 建て・t_out 決済・方向 dir_(+1/-1/0)・往復コスト c(比率)。"""
    a = o.reindex(t_in).values; b = o.reindex(t_out).values; dir_ = np.asarray(dir_, float); ok = ~np.isnan(a) & ~np.isnan(b) & (dir_ != 0)
    return pd.Series(dir_[ok] * (b[ok] / a[ok] - 1.0) - c, index=pd.DatetimeIndex(t_in)[ok])
def judge(R, J, sym, lab, r):
    si, so = st(r, qc.IS0, qc.IS1), st(r, qc.OOS0, qc.END); ok = si["n"] >= 12 and si["plus"] >= 9 and so["n"] > 0 and so["rate"] >= 0.6 and si["p"] < R.alpha
    J.append(dict(symbol=sym, spec=lab, is_plus=si["plus"], is_n=si["n"], is_bps=si["mean"], p=si["p"], oos_plus=so["plus"], oos_n=so["n"], oos_bps=so["mean"], trades=si["trades"] + so["trades"], judged_pass=ok))
def finish(R, J, qid):
    R.finish(); print(f"\n== {qid} 判定(IS 2024 ≥9/12・OOS ≥60%・p<閾値)==\n" + pd.DataFrame(J).to_string(index=False))
