# -*- coding: utf-8 -*-
"""別ブランチ claude/zaption-check-m776m7(docs/365) の「月曜・東京オープン バスケット」(日曜 22 UTC 買い → 月曜 21 UTC 決済・GBPJPY は 1h)を
docs/244 §1 のプロトコル(探索 2021-10〜2024-12 / OOS 2025-01〜 / 前窓 2016-01〜2021-09 / 往復 3pip / 二項 p vs 0.05/累積)で再評価。
合わせて (a) 週明け 22 UTC の実スプレッド(ask−bid)、(b) 既存 Mon4(h4 UTC 24h)との週次相関を出す。"""
import sys, os, gzip, numpy as np, pandas as pd
from math import comb
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
os.chdir("/home/user/chien-monitor/research"); sys.path.insert(0, ".")
import recentfit_screen as base
PIP3 = 3  # 往復 3pip(docs/244 §1)
CUM = 9750 + 5
A, CUT, OOS0 = pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31 23:59"), pd.Timestamp("2025-01-01")
PRE0, PRE1 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-09-30 23:59")

def load(sym, ask=False):
    df = pd.read_csv(f"data_dukascopy/{sym}_hour{'_ask' if ask else ''}.csv.gz"); df["t"] = pd.to_datetime(df["timestamp"]); df = df.set_index("t").sort_index()
    return df[(df.high > df.low) | (df.volume > 0)]

def leg(df, sym, dow, h0, span, cost_pip=PIP3):
    o = df["open"]; d = df[(df.index.dayofweek == dow) & (df.index.hour == h0)]
    o_end = o.reindex(d.index + pd.Timedelta(hours=span)); ok = ~o_end.isna().values
    r = pd.Series(o_end.values[ok] / d["open"].values[ok] - 1, index=d.index[ok])
    return base.clip(r - cost_pip * base.pip_size(sym) / d["open"].values[ok])

def monthly(s): m = s.groupby(pd.PeriodIndex(s.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); return m[m != 0]

def stats(s, name):
    m = monthly(s); pre = m[(m.index >= PRE0.to_period("M")) & (m.index <= PRE1.to_period("M"))]
    mi = m[(m.index >= A.to_period("M")) & (m.index <= CUT.to_period("M"))]; mo = m[m.index >= OOS0.to_period("M")]
    plus = int((mi > 0).sum()); p = sum(comb(len(mi), k) for k in range(plus, len(mi) + 1)) / 2 ** len(mi)
    si = s[(s.index >= A) & (s.index <= CUT)]; so = s[s.index >= OOS0]
    return dict(leg=name, n_trades_in=len(si), plus_in=plus, n_in=len(mi), rate_in=round(plus / len(mi) * 100), p_binom=p, bonf=p < 0.05 / CUM,
                cum_in_pct=round(float((1 + si).prod() - 1) * 100, 1), worst_m_in=round(float(mi.min()) * 100, 2),
                plus_oos=int((mo > 0).sum()), n_oos=len(mo), cum_oos_pct=round(float((1 + so).prod() - 1) * 100, 2),
                pre_rate=round(float((pre > 0).mean()) * 100) if len(pre) else None, pre_cum_pct=round(float((1 + s[(s.index >= PRE0) & (s.index <= PRE1)]).prod() - 1) * 100, 1))

rows = []; legs = {}
spec = [("EURJPY", 6, 22, 23), ("AUDJPY", 6, 22, 23), ("NZDJPY", 6, 22, 23), ("GBPJPY", 6, 22, 1), ("GBPJPY", 6, 22, 23)]
for sym, dow, h0, span in spec:
    df = load(sym); s = leg(df, sym, dow, h0, span); name = f"{sym} Sun{h0:02d}+{span}h"; legs[name] = s
    st = stats(s, name); st["mean_ret_bp_in"] = round(float(s[(s.index >= A) & (s.index <= CUT)].mean()) * 1e4, 2); rows.append(st)
    # 比較: 既存 Mon4 と同じ h4 UTC 24h(同じコスト)
    s4 = leg(df, sym, 0, 4, 24); n4 = f"{sym} Mon04+24h"; legs[n4] = s4
    st4 = stats(s4, n4); st4["mean_ret_bp_in"] = round(float(s4[(s4.index >= A) & (s4.index <= CUT)].mean()) * 1e4, 2); rows.append(st4)
out = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print("== docs/244 §1 窓・往復 3pip・Bonferroni 0.05/%d = %.2e" % (CUM, 0.05 / CUM)); print(out.to_string(index=False))

print("\n== コスト感度(往復 pip)と出口変形: 探索窓の 1 取引平均 pip・+月率・OOS 累積")
for sym, dow, h0, span in spec:
    df = load(sym)
    for cost in (3, 10):
        for (hh, sp, tag) in ((h0, span, "原案"), (23, span - 1, "23UTC 建て"), (h0, (20 - h0) % 24 if span > 1 else span, "20UTC 決済")):
            if span == 1 and tag != "原案": continue
            s_ = leg(df, sym, dow, hh, sp, cost); si = s_[(s_.index >= A) & (s_.index <= CUT)]; so = s_[s_.index >= OOS0]
            d = df[(df.index.dayofweek == dow) & (df.index.hour == hh)]; px = float(d["open"].median())
            m = monthly(s_); mi = m[(m.index >= A.to_period("M")) & (m.index <= CUT.to_period("M"))]
            print(f"  {sym} {tag:9s} Sun{hh:02d}+{sp:2d}h cost{cost:2d}: 平均 {float(si.mean())*px/base.pip_size(sym):6.1f} pip/回  +月率 {int((mi>0).sum())}/{len(mi)}  OOS 累積 {float((1+so).prod()-1)*100:6.2f}%")
print("\n== 週明け 22 UTC の実スプレッド(ask open − bid open・2024-01〜2026-08・pip)")
for sym in ("EURJPY", "AUDJPY", "NZDJPY", "GBPJPY"):
    b = load(sym); a = load(sym, ask=True); j = pd.concat([b["open"].rename("bid"), a["open"].rename("ask")], axis=1).dropna()
    j = j[j.index >= "2024-01-01"]; sp = (j.ask - j.bid) / base.pip_size(sym)
    sun22 = sp[(j.index.dayofweek == 6) & (j.index.hour == 22)]; sun23 = sp[(j.index.dayofweek == 6) & (j.index.hour == 23)]
    mon04 = sp[(j.index.dayofweek == 0) & (j.index.hour == 4)]; mon21 = sp[(j.index.dayofweek == 0) & (j.index.hour == 21)]
    print(f"  {sym}: Sun22 中央 {sun22.median():.1f} 平均 {sun22.mean():.1f} 90% {sun22.quantile(.9):.1f} | Sun23 中央 {sun23.median():.1f} | Mon04 中央 {mon04.median():.1f} | Mon21(決済) 中央 {mon21.median():.1f}  n={len(sun22)}")

print("\n== 既存 Mon4(h4 24h)との週次相関(探索+OOS・同じ週)")
for sym in ("EURJPY", "AUDJPY", "NZDJPY", "GBPJPY"):
    a_ = legs[f"{sym} Sun22+23h" if sym != "GBPJPY" else "GBPJPY Sun22+1h"]; b_ = legs[f"{sym} Mon04+24h"]
    wa = a_.groupby(a_.index.to_period("W-SAT")).sum(); wb = b_.groupby(b_.index.to_period("W-SAT")).sum(); j = pd.concat([wa, wb], axis=1).dropna(); j = j[j.index >= A.to_period("W-SAT")]
    print(f"  {sym}: corr={j.iloc[:,0].corr(j.iloc[:,1]):.2f} n_weeks={len(j)}")
# 週次に揃えたバスケット比較(改良系基準: IS・OOS の Sharpe と最悪月・docs/244 §1)
def wk(s_): return s_.groupby(s_.index.to_period("W-SAT")).sum()
def mo(s_): return s_.groupby(s_.index.to_period("M")).sum()
for cost in (3, 10):
    L = {}
    for sym in ("EURJPY", "AUDJPY", "NZDJPY", "GBPJPY"):
        df = load(sym); L[f"n{sym}"] = wk(leg(df, sym, 6, 22, 23, cost)); L[f"n20{sym}"] = wk(leg(df, sym, 6, 22, 22, cost)); L[f"b{sym}"] = wk(leg(df, sym, 0, 4, 24, cost)); L[f"g1"] = wk(leg(load("GBPJPY"), "GBPJPY", 6, 22, 1, cost))
    W = pd.concat(L, axis=1).fillna(0.0)
    new = (W.nEURJPY + W.nAUDJPY + W.nNZDJPY + W.g1) / 4; new20 = (W.n20EURJPY + W.n20AUDJPY + W.n20NZDJPY + W.n20GBPJPY) / 4
    basel = (W.bEURJPY + W.bAUDJPY + W.bNZDJPY + W.bGBPJPY) / 4; both = (new20 + basel) / 2
    print(f"\n== 週次バスケット比較(往復 {cost} pip)")
    for nm, x in (("原案 4 本(EURJPY/AUDJPY/NZDJPY 23h + GBPJPY 1h)", new), ("変形 4 本(20UTC 決済・GBPJPY も 22h)", new20), ("既存 Mon4 相当(h4 24h・4 本)", basel), ("既存 + 変形を半分ずつ", both)):
        xi = x[(x.index >= A.to_period("W-SAT")) & (x.index <= CUT.to_period("W-SAT"))]; xo = x[x.index >= OOS0.to_period("W-SAT")]
        sh = lambda q: float(q.mean() / q.std() * np.sqrt(52)) if q.std() > 0 else float("nan")
        mi = xi.to_timestamp().groupby(pd.Grouper(freq="ME")).sum()
        mo_ = xo.to_timestamp().groupby(pd.Grouper(freq="ME")).sum()
        print(f"  {nm:40s}: IS Sharpe {sh(xi):.2f} 累積 {xi.sum()*100:5.1f}% 最悪月 {mi.min()*100:5.2f}% | OOS Sharpe {sh(xo):.2f} 累積 {xo.sum()*100:5.1f}% 最悪月 {mo_.min()*100:5.2f}%")
    print(f"  原案 vs 既存 の週次相関 {new.corr(basel):.2f} / 変形 vs 既存 {new20.corr(basel):.2f}")
