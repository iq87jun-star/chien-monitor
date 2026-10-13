# -*- coding: utf-8 -*-
"""Q140(新規 4 セル): 日中モメンタム(Gao, Han, Li & Zhou 2018)を先物口座向けに。前日 16:00 ET → 当日 15:00 ET の符号の向きに、15:00 → 16:00 ET の 1 時間だけ持つ(月〜金)。
US500 / NAS100 / US30 / USTBOND。コストは先物相当 1 bps/往復(保守)。窓: PRE 2016〜2021-09 / IS 2021-10〜2024 / OOS 2025〜(docs/244 と同じ)。月曜 Mon 指数(13→20 UTC)との週次相関も出す。"""
from q_common import *
CST = 1e-4
def et(df):
    x = df.copy(); x.index = x.index.tz_localize("UTC").tz_convert("America/New_York"); return x
out = {}; rows = []
for sym in ["US500", "NAS100", "US30", "USTBOND"]:
    o = et(load(sym))["open"]
    d = pd.Series(o.index.normalize().tz_localize(None), index=o.index)
    p15 = o[o.index.hour == 15]; p16 = o[o.index.hour == 16]
    p15.index = p15.index.normalize(); p16.index = p16.index.normalize()
    j = p15.index.intersection(p16.index)
    prev16 = p16.shift(1).reindex(j)
    sig = np.sign(p15[j] / prev16 - 1.0)
    r = (sig * (p16[j] / p15[j] - 1.0) - CST).dropna()
    r = r[sig.reindex(r.index) != 0]; r.index = r.index.tz_localize(None)
    out[sym] = r
    def sh(a, b):
        x = r[(r.index >= a) & (r.index <= b)]; return round(float(x.mean() / x.std() * np.sqrt(252)), 2) if len(x) > 20 else np.nan
    sp, si, so = st(r, PRE0, IS0), st(r, IS0, IS1), st(r, OOS0, END)
    rows.append(dict(cell=f"{sym} 日中モメンタム 15→16 ET", n=len(r), pre_rate=sp["rate"], pre_sharpe=sh(PRE0, IS0), is_plus=f"{si['plus']}/{si['n']}", is_bps=si["mean"], is_p=round(si["p"], 4), is_sharpe=sh(IS0, IS1),
                     oos_plus=f"{so['plus']}/{so['n']}", oos_bps=so["mean"], oos_sharpe=sh(OOS0, END), std_pass=bool(si["p"] < 0.05 / 9754 and so["mean"] > 0 and sp["rate"] >= 0.5)))
R = pd.DataFrame(rows); pd.set_option("display.width", 250); print(R.to_string(index=False)); R.to_csv("results/q140_intraday_momentum.csv", index=False)
# 月曜 Mon 指数(13→20 UTC・3 指数等ウェイト)との週次相関
mon = []
for k in ["US500", "NAS100", "US30"]:
    o = load(k)["open"]; t = o.index[(o.index.dayofweek == 0) & (o.index.hour == 13)]
    t2 = t + pd.Timedelta(hours=7); s = pd.Series(o.reindex(t2).values / o.reindex(t).values - 1, index=t.normalize()); mon.append(s)
mon = pd.concat(mon, axis=1).mean(axis=1).dropna(); mw = mon.groupby(mon.index.to_period("W")).sum()
for k, r in out.items():
    w = r.groupby(r.index.to_period("W")).sum(); j = w.index.intersection(mw.index)
    print(f"{k}: 週次相関 vs Mon 指数 = {np.corrcoef(w[j], mw[j])[0,1]:+.2f}(n={len(j)})")
