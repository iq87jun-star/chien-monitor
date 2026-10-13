# -*- coding: utf-8 -*-
"""Q147〜Q149(新規・結果前に固定)。窓 PRE 2016〜2021-09 / IS 2021-10〜2024 / OOS 2025〜。標準 = IS 月次二項 p < 0.05/累積・OOS > 0・PRE +月率 ≥ 50%。
Q147 農産物・エネルギー(FTMO .c / .cash): (a) Mon 効果 = 月曜の最初の足の始値 → 火曜の最初の足の始値 LONG、(b) TSMOM = 月末に 1/3/6/12 か月リターンの符号和で向きを決め翌月保有(月 5 bps)。
     Dukascopy(実行値・中値)= COCOA COFFEE COTTON OJUICE SOYBEAN SUGAR DIESEL NATGAS、Yahoo 連続先物(15 bps・限月つなぎの段差あり)= 小麦 ZW・コーン ZC。20 セル。
Q148 先物口座向け Mon 日中(13→20 UTC LONG): EURUSD(6E)・GBPUSD(6B)・AUDUSD(6A)= 外貨買い、USTBOND(ZB/ZN)= 債券買い。4 セル。
Q149 円クロス Mon4 形(月曜 4/6/8/10 UTC・24h LONG): ZARJPY・MXNJPY・TRYJPY・HKDJPY。4 セル。"""
import pandas as pd, numpy as np, sys, os
from math import comb
S = sys.argv[1]
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-01")
NCUM = 9810 + 28
def bidask(path_b, path_a):
    b = pd.read_csv(path_b, index_col=0, parse_dates=True)["open"]; a = pd.read_csv(path_a, index_col=0, parse_dates=True)["open"]
    j = b.index.intersection(a.index); b, a = b[j], a[j]; idx = pd.to_datetime(j, utc=True).tz_localize(None); b.index = idx; a.index = idx
    ok = a >= b; return b[ok], a[ok]
def st(r):
    out = {}
    for lab, lo, hi in [("PRE", PRE0, IS0), ("IS", IS0, IS1), ("OOS", OOS0, pd.Timestamp("2027-01-01"))]:
        x = r[(r.index >= lo) & (r.index < hi)]
        if len(x) < 4: out[lab] = dict(n=0, bps=np.nan, sh=np.nan, rate=np.nan, p=1.0, k=0); continue
        m = x.groupby(x.index.to_period("M")).apply(lambda q: (1 + q).prod() - 1); n = len(m); k = int((m > 0).sum())
        per = 52 if x.index.to_series().diff().dt.days.median() >= 5 else 252
        out[lab] = dict(n=n, k=k, rate=round(k / n, 3), bps=round(float(x.mean() * 1e4), 2), sh=round(float(x.mean() / x.std() * np.sqrt(per)), 2), p=sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n)
    return out
rows = []
def add(q, name, r):
    r = r.dropna().sort_index(); s = st(r)
    rows.append(dict(Q=q, cell=name, start=str(r.index.min().date()) if len(r) else "-", n=len(r),
                     PRE=f"{s['PRE']['bps']}/{s['PRE']['sh']}/{s['PRE']['rate']}", IS=f"{s['IS']['bps']}/{s['IS']['sh']}/{s['IS']['k']}of{s['IS']['n']}/p{s['IS']['p']:.3g}",
                     OOS=f"{s['OOS']['bps']}/{s['OOS']['sh']}/{s['OOS']['k']}of{s['OOS']['n']}",
                     sign3=bool(all((s[k]['bps'] > 0) for k in ("PRE", "IS", "OOS") if s[k]['n'] > 0) and s['IS']['n'] > 0 and s['OOS']['n'] > 0),
                     std=bool(s['IS']['p'] < 0.05 / NCUM and s['OOS']['bps'] > 0 and (s['PRE']['n'] == 0 or s['PRE']['rate'] >= 0.5)), r=r))
# ---- Q147 ----
def mon_first_bar(b, a):
    d = b.index.normalize(); first = pd.Series(b.index, index=b.index).groupby(d).min()
    mon = first[first.index.dayofweek == 0]; out = {}
    for day, t in mon.items():
        nxt = first[(first.index > day) & (first.index <= day + pd.Timedelta(days=4))]
        if len(nxt) == 0: continue
        t2 = nxt.iloc[0]; out[day] = b[t2] / a[t] - 1
    return pd.Series(out)
def tsmom(close, cost=5e-4):
    m = close.resample("ME").last().dropna()
    sig = sum(np.sign(m.pct_change(k)) for k in (1, 3, 6, 12)); pos = np.sign(sig).shift(1); pos.index = pos.index.to_period("M")
    d = close.pct_change().dropna(); key = d.index.to_period("M")
    r = pd.Series(d.values * pos.reindex(key).fillna(0).values, index=d.index)
    firsts = pd.Series(r.index, index=r.index).groupby(r.index.to_period("M")).min(); r.loc[r.index.isin(firsts.values)] -= cost
    return r[r.index >= m.index[12]]
for p in ["COCOA", "COFFEE", "COTTON", "OJUICE", "SOYBEAN", "SUGAR", "DIESEL", "NATGAS"]:
    f = f"{S}/agri/{p}_h1.csv"
    if not os.path.exists(f): continue
    b, a = bidask(f, f"{S}/agri/{p}_h1_ask.csv"); mid = (b + a) / 2
    add("Q147", f"Mon 効果 {p}", mon_first_bar(b, a)); add("Q147", f"TSMOM {p}", tsmom(mid.groupby(mid.index.normalize()).last()))
yf = pd.read_pickle(f"{S}/agri/yf_futures.pkl")
for t, nm in [("ZW=F", "小麦 ZW"), ("ZC=F", "コーン ZC")]:
    o = yf[t]["Open"].dropna(); c = yf[t]["Close"].dropna()
    r = (o.shift(-1) / o - 1 - 15e-4); r = r[r.index.dayofweek == 0]; r = r[r.abs() < 0.15]
    add("Q147", f"Mon 効果 {nm}", r); add("Q147", f"TSMOM {nm}", tsmom(c))
# ---- Q148 ----
def mon_intraday(b, a, h0=13, h1=20, d=1):
    t = b.index[(b.index.dayofweek == 0) & (b.index.hour == h0)]; t2 = t + pd.Timedelta(hours=h1 - h0); ok = t2.isin(b.index); t, t2 = t[ok], t2[ok]
    r = (b.reindex(t2).values / a.reindex(t).values - 1) if d > 0 else (1 - a.reindex(t2).values / b.reindex(t).values)
    return pd.Series(r, index=t.normalize())
for p, lab in [("EURUSD", "6E"), ("GBPUSD", "6B"), ("AUDUSD", "6A")]:
    b, a = bidask(f"{S}/ig/{p}_h1.csv", f"{S}/ig/{p}_h1_ask.csv"); add("Q148", f"Mon 日中 13→20 UTC {p}({lab})LONG", mon_intraday(b, a))
ub = pd.read_csv(f"{S}/agri/../old_ust.csv.gz") if os.path.exists(f"{S}/old_ust.csv.gz") else None
if ub is not None:
    ub["t"] = pd.to_datetime(ub.timestamp); o = ub.set_index("t").sort_index()["open"]; o = o[~o.index.duplicated()]
    t = o.index[(o.index.dayofweek == 0) & (o.index.hour == 13)]; t2 = t + pd.Timedelta(hours=7); ok = t2.isin(o.index)
    add("Q148", "Mon 日中 13→20 UTC USTBOND(ZB/ZN)LONG", pd.Series(o.reindex(t2[ok]).values / o.reindex(t[ok]).values - 1 - 2e-4, index=t[ok].normalize()))
# ---- Q149 ----
def mon4(b, a):
    out = []
    for h in (4, 6, 8, 10):
        t = b.index[(b.index.dayofweek == 0) & (b.index.hour == h)]; t2 = t + pd.Timedelta(hours=24); ok = t2.isin(b.index)
        out.append(pd.Series(b.reindex(t2[ok]).values / a.reindex(t[ok]).values - 1, index=t[ok].normalize()))
    return pd.concat(out, axis=1, sort=True).mean(axis=1)
for p in ["ZARJPY", "MXNJPY", "TRYJPY", "HKDJPY"]:
    f = f"{S}/agri/{p}_h1.csv"
    if os.path.exists(f): b, a = bidask(f, f"{S}/agri/{p}_h1_ask.csv"); add("Q149", f"Mon4 形 {p} LONG", mon4(b, a))
# 参照: Mon4 円クロス・Mon 指数
ref4 = pd.concat([mon4(*bidask(f"{S}/ig/{p}_h1.csv", f"{S}/ig/{p}_h1_ask.csv")) for p in ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"]], axis=1, sort=True).mean(axis=1)
w4 = ref4.groupby(ref4.index.to_period("W")).sum()
R = pd.DataFrame(rows)
def corr(r):
    w = r.groupby(r.index.to_period("W")).sum(); j = w.index.intersection(w4.index); return round(float(np.corrcoef(w[j], w4[j])[0, 1]), 2) if len(j) > 30 else np.nan
R["corr_Mon4"] = [corr(r) for r in R.r]
pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 50)
print("列: bps/Sharpe/(+月率 or +月数/p)"); print(R.drop(columns=["r"]).to_string(index=False))
R.drop(columns=["r"]).to_csv(f"{S}/q147_149.csv", index=False)
for q in ("Q147", "Q148", "Q149"):
    x = R[R.Q == q]; print(f"{q}: セル {len(x)}・3 窓正 {int(x.sign3.sum())}・標準通過 {int(x['std'].sum())}")
# TSMOM 合成(農産物)
ts = [r for c, r in zip(R.cell, R.r) if c.startswith("TSMOM")]
if ts:
    port = pd.concat(ts, axis=1, sort=True).mean(axis=1).dropna(); s = st(port)
    print("TSMOM 農産物 等ウェイト合成:", {k: (v["bps"], v["sh"]) for k, v in s.items()}, "Mon4 相関", corr(port))
