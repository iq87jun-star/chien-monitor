# -*- coding: utf-8 -*-
"""docs/244 Q2: イベント前後ドリフト。FOMC / BoJ / 米CPI / 雇用統計 × {前日, 当日, 翌日}(24h 窓)× {L,S} × 10 銘柄 = 240 セル。
H1 Dukascopy(bid 建て・往復 3pip / XAUUSD 5bps)。窓: IS 2021-10-01〜2024-12-31 / OOS 2025-01-01〜末尾 / 前窓 2016-01〜2021-09。
判定(docs/244 §1): 二項 p(IS の +月数)< 0.05/累積セル数(3,400+240=3,640 → 1.37e-5)かつ OOS 同符号 かつ 前窓 +月率 ≥ 50%。research/ で実行。"""
import os, sys, numpy as np, pandas as pd
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
SYMS = ["EURGBP", "NZDUSD", "AUDUSD", "USDCHF", "CHFJPY", "USDJPY", "EURUSD", "GBPUSD", "XAUUSD", "EURJPY"]
EVENTS = {"FOMC": "events_fomc.csv", "BoJ": "events_boj.csv", "CPI": "events_cpi.csv", "NFP": "events_empsit.csv"}
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31 23:00"), pd.Timestamp("2025-01-01")
CUM_BEFORE, N_CELLS = 3400, 240; ALPHA = 0.05 / (CUM_BEFORE + N_CELLS)

def us_dst(d):  # 米国夏時間: 3月第2日曜〜11月第1日曜
    y = d.year; mar = pd.Timestamp(y, 3, 1); nov = pd.Timestamp(y, 11, 1)
    s = mar + pd.Timedelta(days=(6 - mar.dayofweek) % 7 + 7); e = nov + pd.Timedelta(days=(6 - nov.dayofweek) % 7)
    return s <= d < e
def announce_utc(ev, d):
    if ev == "FOMC": return d + pd.Timedelta(hours=18 if us_dst(d) else 19)
    if ev == "BoJ":  return d + pd.Timedelta(hours=3)
    return d + pd.Timedelta(hours=12 if us_dst(d) else 13)      # CPI / NFP 08:30 ET → 12:30 / 13:30 UTC(H1 バーは 12 / 13)
WINDOWS = {"前日": (-24, 0), "当日": (0, 24), "翌日": (24, 48)}

def load(sym):
    df = pd.read_csv(f"data_dukascopy/{sym}_hour.csv.gz"); df["t"] = pd.to_datetime(df["timestamp"]); df = df.set_index("t").sort_index()
    return df[(df.high > df.low) | (df.volume > 0)]
def pip(sym): return 0.01 if sym.endswith("JPY") else (0.1 if sym == "XAUUSD" else 0.0001)
def cost_frac(sym, px): return 5e-4 if sym == "XAUUSD" else 3 * pip(sym) / px

def pbinom(plus, n): return sum(comb(n, k) for k in range(plus, n + 1)) / 2 ** n if n > 0 else 1.0
def stats(r):
    if len(r) == 0: return dict(n=0, plus=0, rate=np.nan, mean=np.nan)
    mi = r.groupby(pd.PeriodIndex(r.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return dict(n=len(mi), plus=int((mi > 0).sum()), rate=float((mi > 0).mean()), mean=float(r.mean() * 1e4))

rows = []
data = {s: load(s) for s in SYMS}
for ev, fn in EVENTS.items():
    dates = pd.to_datetime(pd.read_csv(f"data_ext/{fn}")["date"]); dates = dates[(dates >= PRE0) & (dates <= pd.Timestamp("2026-08-31"))]
    for sym in SYMS:
        df = data[sym]; o = df["open"]; c = df["close"]
        for wn, (h0, h1) in WINDOWS.items():
            recs = []
            for d in dates:
                T = announce_utc(ev, d); t0 = T + pd.Timedelta(hours=h0); t1 = T + pd.Timedelta(hours=h1)
                oo = o[o.index >= t0]; cc = c[c.index < t1]
                if len(oo) == 0 or len(cc) == 0: continue
                e_t = oo.index[0]; x_t = cc.index[-1]
                if e_t >= t1 or x_t <= t0 or (x_t - e_t) < pd.Timedelta(hours=12): continue   # 休場で窓が潰れたイベントは除外
                px0 = float(oo.iloc[0]); px1 = float(cc.iloc[-1]); recs.append((e_t, px1 / px0 - 1.0, cost_frac(sym, px0)))
            if not recs: continue
            rr = pd.Series([r for _, r, _ in recs], index=pd.DatetimeIndex([t for t, _, _ in recs])); cst = pd.Series([k for _, _, k in recs], index=rr.index)
            for short in (False, True):
                r = (-rr if short else rr) - cst
                pre, is_, oos = r[r.index < IS0], r[(r.index >= IS0) & (r.index <= IS1)], r[r.index >= OOS0]
                sp, si, so = stats(pre), stats(is_), stats(oos)
                p = pbinom(si["plus"], si["n"])
                passed = (p < ALPHA) and si["n"] >= 20 and (so["n"] > 0 and so["mean"] > 0) and (sp["n"] > 0 and sp["rate"] >= 0.5)
                rows.append(dict(event=ev, symbol=sym, window=wn, side="S" if short else "L", is_n=si["n"], is_plus=si["plus"], is_rate=round(si["rate"], 3) if si["n"] else np.nan,
                                 is_mean_bps=round(si["mean"], 2) if si["n"] else np.nan, p=p, oos_n=so["n"], oos_plus=so["plus"], oos_mean_bps=round(so["mean"], 2) if so["n"] else np.nan,
                                 pre_n=sp["n"], pre_rate=round(sp["rate"], 3) if sp["n"] else np.nan, passed=passed))
R = pd.DataFrame(rows).sort_values("p"); R.to_csv("results/q2_event_drift.csv", index=False)
print(f"cells={len(R)} alpha={ALPHA:.2e} passed={int(R.passed.sum())}")
print(R.head(15).to_string(index=False))
print("\n-- passed --"); print(R[R.passed].to_string(index=False) if R.passed.any() else "(none)")
print("\n-- 事前登録の妥当性: IS の n(イベント月数)の分布 --"); print(R.groupby("event").is_n.agg(["min", "max"]).to_string())
