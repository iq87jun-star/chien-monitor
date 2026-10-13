# -*- coding: utf-8 -*-
"""Q150〜Q151(新規・結果前に固定)。窓 PRE 2016〜2021-09 / IS 2021-10〜2024 / OOS 2025〜。
Q150 季節性(年 1 回・決め打ちの期間): 日次リターンの和(限月つなぎの段差対策で |日次| > 10% の日は除外)、往復コスト = Dukascopy は建て・決済時の実スプレッド、Yahoo は 15 bps。
     NATGAS 9/1→10/31 LONG・NATGAS 1/15→2/28 SHORT・コーン ZC 7/1→9/30 SHORT・SOYBEAN 7/1→9/30 SHORT・小麦 ZW 5/15→7/15 SHORT。5 セル。
     年 1 回なので月次二項は使えない(IS は 3 年)。判定 = 年別で PRE・IS・OOS とも平均正、かつ全年の正の率 ≥ 70%。標準(p < 0.05/累積)は構造上通らない。
Q151 発表日:
     (a) EIA 天然ガス在庫(木曜 10:30 ET): 10:00→11:00 ET の中値の向きに 11:00 ET 建て → 14:00 ET 決済(実行値)。
     (b) 同じ向きで 14:00 ET 建て → 翌営業日 14:00 ET 決済(実行値)。
     (c) WASDE(12:00 ET): 発表日 11:00→14:00 ET の向きに 14:00 ET 建て → 5 営業日後 14:00 ET 決済。SOYBEAN(Dukascopy 実行値)。
     (d)(e) 同じ形をコーン ZC・小麦 ZW(Yahoo 日足): 発表日の終値/前日終値の向き → 終値建て 5 営業日後の終値決済(15 bps)。5 セル。
累積 9,838 → 9,848。"""
import pandas as pd, numpy as np, sys, os
from math import comb
S = sys.argv[1]
PRE0, IS0, OOS0, END = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2025-01-01"), pd.Timestamp("2027-01-01")
NCUM = 9838 + 10
WIN = [("PRE", PRE0, IS0), ("IS", IS0, OOS0), ("OOS", OOS0, END)]
def bidask(p):
    b = pd.read_csv(f"{S}/agri/{p}_h1.csv", index_col=0, parse_dates=True)["open"]; a = pd.read_csv(f"{S}/agri/{p}_h1_ask.csv", index_col=0, parse_dates=True)["open"]
    j = b.index.intersection(a.index); b, a = b[j], a[j]; ok = a >= b; b, a = b[ok], a[ok]
    et = b.index.tz_convert("America/New_York").tz_localize(None); b.index = et; a.index = et   # 以後 ET の壁時計
    return b[~b.index.duplicated()], a[~a.index.duplicated()]
def event_stats(r):
    out = {}
    for lab, lo, hi in WIN:
        x = r[(r.index >= lo) & (r.index < hi)]
        if len(x) < 4: out[lab] = dict(n=len(x), bps=np.nan, sh=np.nan, rate=np.nan, p=1.0, k=0, mn=0, mk=0); continue
        m = x.groupby(x.index.to_period("M")).sum(); n = len(m); k = int((m > 0).sum())
        out[lab] = dict(n=len(x), bps=round(float(x.mean() * 1e4), 1), sh=round(float(x.mean() / x.std() * np.sqrt(len(x) / ((hi if hi < END else x.index.max()) - lo).days * 365.25)), 2),
                        rate=round(k / n, 3), mn=n, mk=k, p=sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n)
    return out
rows = []
def add_event(q, name, r):
    r = r.dropna().sort_index(); s = event_stats(r)
    rows.append(dict(Q=q, cell=name, n=len(r), PRE=f"{s['PRE']['bps']}bps/{s['PRE']['sh']}/{s['PRE']['rate']}", IS=f"{s['IS']['bps']}bps/{s['IS']['sh']}/{s['IS']['mk']}of{s['IS']['mn']}/p{s['IS']['p']:.3g}",
                     OOS=f"{s['OOS']['bps']}bps/{s['OOS']['sh']}/{s['OOS']['mk']}of{s['OOS']['mn']}",
                     pass_=bool(s['IS']['p'] < 0.05 / NCUM and s['OOS']['bps'] > 0 and s['PRE']['rate'] >= 0.5),
                     sign3=bool(all(s[k]['bps'] > 0 for k, _, _ in WIN))))
def add_season(q, name, yr):
    yr = yr.dropna()
    g = {"PRE": yr[yr.index <= 2021], "IS": yr[(yr.index >= 2022) & (yr.index <= 2024)], "OOS": yr[yr.index >= 2025]}
    f = lambda x: f"{x.mean()*100:+.1f}%({int((x>0).sum())}/{len(x)})" if len(x) else "-"
    rows.append(dict(Q=q, cell=name, n=len(yr), PRE=f(g["PRE"]), IS=f(g["IS"]), OOS=f(g["OOS"]),
                     pass_=bool(all(len(v) and v.mean() > 0 for v in g.values()) and (yr > 0).mean() >= 0.7),
                     sign3=bool(all(len(v) and v.mean() > 0 for v in g.values())), years=" ".join(f"{y}:{v*100:+.0f}" for y, v in yr.items())))
# ---------- Q150 季節性 ----------
def season_duka(p, m0, d0, m1, d1, side):
    b, a = bidask(p); mid = (b + a) / 2; day = mid.groupby(mid.index.normalize()).last(); dr = day.pct_change(); dr[dr.abs() > 0.10] = 0
    out = {}
    for y in range(2016, 2027):
        lo, hi = pd.Timestamp(y, m0, d0), pd.Timestamp(y, m1, d1)
        x = dr[(dr.index > lo) & (dr.index <= hi)]
        if hi > b.index.max() or len(x) < 10: continue
        t0 = b.index[b.index >= lo][0]; t1 = b.index[b.index <= hi + pd.Timedelta(hours=23)][-1]
        cost = (a[t0] - b[t0]) / mid[t0] / 2 + (a[t1] - b[t1]) / mid[t1] / 2
        out[y] = side * ((1 + x).prod() - 1) - cost
    return pd.Series(out)
yf = pd.read_pickle(f"{S}/agri/yf_futures.pkl")
def season_yf(t, m0, d0, m1, d1, side):
    c = yf[t]["Close"].dropna(); dr = c.pct_change(); dr[dr.abs() > 0.10] = 0; out = {}
    for y in range(2016, 2027):
        lo, hi = pd.Timestamp(y, m0, d0), pd.Timestamp(y, m1, d1)
        if hi > c.index.max(): continue
        x = dr[(dr.index > lo) & (dr.index <= hi)]; out[y] = side * ((1 + x).prod() - 1) - 15e-4
    return pd.Series(out)
add_season("Q150", "NATGAS 9/1→10/31 LONG", season_duka("NATGAS", 9, 1, 10, 31, 1))
add_season("Q150", "NATGAS 1/15→2/28 SHORT", season_duka("NATGAS", 1, 15, 2, 28, -1))
add_season("Q150", "コーン ZC 7/1→9/30 SHORT", season_yf("ZC=F", 7, 1, 9, 30, -1))
add_season("Q150", "SOYBEAN 7/1→9/30 SHORT", season_duka("SOYBEAN", 7, 1, 9, 30, -1))
add_season("Q150", "小麦 ZW 5/15→7/15 SHORT", season_yf("ZW=F", 5, 15, 7, 15, -1))
# ---------- Q151 発表日 ----------
def at(s, t): return s.get(t, np.nan)
b, a = bidask("NATGAS"); mid = (b + a) / 2
thu = sorted(set(mid.index[(mid.index.dayofweek == 3)].normalize()))
ra, rb = {}, {}
for d in thu:
    t10, t11, t14 = d + pd.Timedelta(hours=10), d + pd.Timedelta(hours=11), d + pd.Timedelta(hours=14)
    s = np.sign(at(mid, t11) - at(mid, t10))
    if not s or np.isnan(s): continue
    ra[d] = (at(b, t14) / at(a, t11) - 1) if s > 0 else (1 - at(a, t14) / at(b, t11))
    nx = [x for x in (d + pd.Timedelta(days=1, hours=14), d + pd.Timedelta(days=4, hours=14)) if x in b.index]
    if nx and t14 in b.index: rb[d] = (b[nx[0]] / a[t14] - 1) if s > 0 else (1 - a[nx[0]] / b[t14])
add_event("Q151", "EIA 木曜 NATGAS 11→14 ET 追随", pd.Series(ra)); add_event("Q151", "EIA 木曜 NATGAS 14 ET→翌日 追随", pd.Series(rb))
# 参照(セル外): 同じ形を木曜以外の平日で
ref = {}
for d in sorted(set(mid.index[mid.index.dayofweek.isin([0, 1, 2, 4])].normalize())):
    t10, t11, t14 = d + pd.Timedelta(hours=10), d + pd.Timedelta(hours=11), d + pd.Timedelta(hours=14); s = np.sign(at(mid, t11) - at(mid, t10))
    if s and not np.isnan(s): ref[d] = (at(b, t14) / at(a, t11) - 1) if s > 0 else (1 - at(a, t14) / at(b, t11))
ref = pd.Series(ref).dropna()
wd = pd.to_datetime(open(f"{S}/agri/wasde_dates.txt").read().split()); wd = wd[wd >= "2016-01-01"]
b, a = bidask("SOYBEAN"); mid = (b + a) / 2; days = sorted(set(b.index.normalize())); rc = {}
for d in wd:
    if d not in days: continue
    i = days.index(d)
    if i + 5 >= len(days): continue
    t11, t14, tx = d + pd.Timedelta(hours=11), d + pd.Timedelta(hours=14), days[i + 5] + pd.Timedelta(hours=14)
    s = np.sign(at(mid, t14) - at(mid, t11))
    if not s or np.isnan(s) or tx not in b.index: continue
    rc[d] = (b[tx] / a[t14] - 1) if s > 0 else (1 - a[tx] / b[t14])
add_event("Q151", "WASDE SOYBEAN 発表日の向き→5 営業日", pd.Series(rc))
for t, nm in [("ZC=F", "コーン ZC"), ("ZW=F", "小麦 ZW")]:
    c = yf[t]["Close"].dropna(); r = {}
    for d in wd:
        if d not in c.index: continue
        i = c.index.get_loc(d)
        if i < 1 or i + 5 >= len(c): continue
        s = np.sign(c.iloc[i] / c.iloc[i - 1] - 1); x = s * (c.iloc[i + 5] / c.iloc[i] - 1) - 15e-4
        if s and abs(x) < 0.15: r[d] = x
    add_event("Q151", f"WASDE {nm} 発表日の向き→5 営業日", pd.Series(r))
R = pd.DataFrame(rows); pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 120)
print("Q150 列: 年平均(正の年/年数)。Q151 列: 1 回平均 bps / 年率 Sharpe / +月率 or +月数・p"); print(R.drop(columns=["years"], errors="ignore").to_string(index=False))
for _, x in R[R.Q == "Q150"].iterrows(): print(x.cell, "|", x.years)
s = event_stats(ref); print("参照 木曜以外 NATGAS 11→14 ET 追随:", {k: (v['bps'], v['sh']) for k, v in s.items()})
R.to_csv(f"{S}/q150_151.csv", index=False)
for q in ("Q150", "Q151"): x = R[R.Q == q]; print(f"{q}: セル {len(x)}・3 窓正 {int(x.sign3.sum())}・判定通過 {int(x.pass_.sum())}")
