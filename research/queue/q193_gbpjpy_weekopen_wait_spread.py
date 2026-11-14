# -*- coding: utf-8 -*-
"""docs/244 Q193(新規 4 セル・2026-11-13 登録「登録して実行」): 週明け開場直後の GBPJPY 買い — スプレッドが戻るまで待って建てる。
規則: 日曜 22:00〜22:45 UTC の各分足の始値で (ask − bid) ≤ cap となった最初の分に ask 始値で買い、決済時刻の分足の bid 始値で決済。
cap ∈ {3, 5} pip × 決済 ∈ {23:00, 24:00 UTC}。45 分以内に cap 以下にならない週・22:00 の足が無い週は取引なし。費用は実際の ask / bid のみ。
判定は docs/244 §1 の標準。データ = FXCM 公開ローソク足 m1(fetch_fxcm_m1_weekopen.py・各週の開場後 5 時間)。
使い方: cd research && python3 -W ignore queue/q193_gbpjpy_weekopen_wait_spread.py   出力: results/q193_gbpjpy_weekopen_wait_spread.csv・_trades.csv・_minute.csv"""
import os, sys
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
CUM = 10120; PIP = 0.01; SYM = "GBPJPY"
D = pd.read_csv(f"data_fxcm/{SYM}_m1_weekopen.csv.gz", parse_dates=["timestamp"]).set_index("timestamp").sort_index()
D["spr"] = (D.AskOpen - D.BidOpen) / PIP; D["mid"] = (D.AskOpen + D.BidOpen) / 2
def us_dst(d):
    y = d.year; m = pd.Timestamp(y, 3, 1); s = m + pd.Timedelta(days=(6 - m.weekday()) % 7 + 7); n = pd.Timestamp(y, 11, 1); e = n + pd.Timedelta(days=(6 - n.weekday()) % 7); return s <= d < e
def price_at(day, t, col):
    """t の分足の始値。無ければ直後 5 分以内の最初の足。"""
    w = day[(day.index >= t) & (day.index < t + pd.Timedelta(minutes=5))]; return (float(w[col].iloc[0]), w.index[0]) if len(w) else (np.nan, None)
suns = sorted({t.normalize() for t in D.index if t.weekday() == 6}); trades = []; minute = []; info = []
for s in suns:
    t0 = s + pd.Timedelta(hours=22); day = D[(D.index >= s) & (D.index < s + pd.Timedelta(hours=27))]
    if t0 not in day.index: info.append(dict(sunday=s, has22=False)); continue
    first = day.index[0]; win = day[(day.index >= t0) & (day.index <= t0 + pd.Timedelta(minutes=45))]; m0 = float(day.mid[t0])
    for k in (0, 1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 120):
        v, _ = price_at(day, t0 + pd.Timedelta(minutes=k), "mid"); sp, _ = price_at(day, t0 + pd.Timedelta(minutes=k), "spr")
        minute.append(dict(sunday=s, dst=us_dst(s), k=k, spr=sp, mid_chg_pip=(v - m0) / PIP if v == v else np.nan))
    row = dict(sunday=s, has22=True, dst=us_dst(s), open_min=int((t0 - first).total_seconds() // 60), spr22=float(day.spr[t0]))
    for cap in (3, 5):
        ok = win[win.spr <= cap + 1e-9]; row[f"wait_cap{cap}"] = (int((ok.index[0] - t0).total_seconds() // 60) if len(ok) else np.nan)
        for ex in (23, 24):
            if not len(ok): continue
            te = s + pd.Timedelta(hours=ex); px, _ = price_at(day, te, "BidOpen"); pa = float(ok.AskOpen.iloc[0])
            if px != px: continue
            mx, _ = price_at(day, te, "mid")
            trades.append(dict(cell=f"cap{cap}_exit{ex}", cap=cap, exit=ex, sunday=s, month=(s + pd.Timedelta(days=1)).strftime("%Y-%m"), wait=row[f"wait_cap{cap}"], entry=pa, exitpx=px, pip=(px - pa) / PIP, ret=(px / pa - 1) * 100,
                               spr_entry=float(ok.spr.iloc[0]), mid_pip=(mx - float(ok.mid.iloc[0])) / PIP))
    info.append(row)
T = pd.DataFrame(trades); I = pd.DataFrame(info); M = pd.DataFrame(minute); T.to_csv("results/q193_gbpjpy_weekopen_wait_spread_trades.csv", index=False)
def binom_p(k, n): return sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n
def seg(x, a, b): return x[(x.month >= a) & (x.month <= b)]
rows = []
for cell, g in T.groupby("cell", sort=False):
    out = dict(cell=cell, trades=len(g), weeks=int(I.has22.sum()), traded_share=round(len(g) / I.has22.sum(), 3), wait_med=float(g.wait.median()), mean_pip=round(g.pip.mean(), 2), median_pip=round(g.pip.median(), 2), win=round((g.pip > 0).mean() * 100, 1), mid_mean_pip=round(g.mid_pip.mean(), 2), spr_entry=round(g.spr_entry.mean(), 2))
    for nm, a, b in (("pre", "2016-01", "2021-09"), ("is", "2021-10", "2024-12"), ("oos", "2025-01", "2099-12")):
        x = seg(g, a, b); m = x.groupby("month").ret.sum(); k = int((m > 0).sum()); n = len(m)
        out.update({f"{nm}_n": len(x), f"{nm}_months": n, f"{nm}_plus": k, f"{nm}_plus_rate": round(k / n * 100, 1) if n else np.nan, f"{nm}_cum_pct": round(m.sum(), 2), f"{nm}_mean_pip": round(x.pip.mean(), 2) if len(x) else np.nan, f"{nm}_worst_month": round(m.min(), 2) if n else np.nan})
        if nm == "is": out["is_p"] = binom_p(k, n) if n else np.nan
    out["bonf"] = bool(out["is_p"] < 0.05 / CUM); out["same_sign"] = bool(out["is_cum_pct"] > 0 and out["oos_cum_pct"] > 0); out["pre_ok"] = bool(out["pre_plus_rate"] >= 50)
    out["verdict"] = "通過" if (out["bonf"] and out["same_sign"] and out["pre_ok"]) else "棄却"; rows.append(out)
R = pd.DataFrame(rows); R.to_csv("results/q193_gbpjpy_weekopen_wait_spread.csv", index=False)
Mg = M.groupby("k").agg(n=("spr", "count"), spr_med=("spr", "median"), spr_mean=("spr", "mean"), spr_p90=("spr", lambda x: x.quantile(0.9)), mid_mean=("mid_chg_pip", "mean"), mid_med=("mid_chg_pip", "median"), mid_up=("mid_chg_pip", lambda x: (x > 0).mean() * 100)).round(2).reset_index()
Mg.to_csv("results/q193_gbpjpy_weekopen_wait_spread_minute.csv", index=False)
pd.set_option("display.width", 320); pd.set_option("display.max_columns", 50)
print("weeks with data", len(I), "has 22:00 bar", int(I.has22.sum()), "| threshold", 0.05 / CUM)
print(R[["cell", "trades", "traded_share", "wait_med", "spr_entry", "mean_pip", "median_pip", "win", "mid_mean_pip", "pre_plus", "pre_months", "pre_plus_rate", "is_plus", "is_months", "is_p", "is_cum_pct", "is_mean_pip", "is_worst_month", "oos_plus", "oos_months", "oos_cum_pct", "oos_mean_pip", "verdict"]].to_string(index=False)); print()
print(Mg.to_string(index=False)); print()
J = I[I.has22]
print("open offset (min before 22:00) by dst:\n", J.groupby("dst").open_min.describe()[["count", "50%", "min", "max"]])
print("spr at 22:00 by dst:\n", J.groupby("dst").spr22.describe()[["count", "50%", "mean"]].round(2), "\n p90", J.groupby("dst").spr22.quantile(0.9).round(1).to_dict())
for cap in (3, 5): print(f"wait cap{cap}: never {J[f'wait_cap{cap}'].isna().mean()*100:.1f}% | 0 min {(J[f'wait_cap{cap}']==0).mean()*100:.1f}% | med {J[f'wait_cap{cap}'].median()} | by dst", J.groupby('dst')[f'wait_cap{cap}'].agg(lambda x: f"never {x.isna().mean()*100:.0f}% med {x.median()}").to_dict())
print("mid 22:00→23:00 by dst:\n", M[M.k == 60].groupby("dst").mid_chg_pip.agg(["count", "mean", "median", lambda x: (x > 0).mean() * 100]).round(2))
for (c, d), g in T.assign(dst=T.sunday.map(us_dst)).groupby(["cell", "dst"]): print(c, "dst" if d else "std", len(g), "mean_pip", round(g.pip.mean(), 2), "win", round((g.pip > 0).mean() * 100, 1))
since = M[(M.sunday >= "2024-01-01")]; print("2024〜 spr at 22:00 median/mean/p90:", since[since.k == 0].spr.median().round(1), since[since.k == 0].spr.mean().round(1), since[since.k == 0].spr.quantile(0.9).round(1), "| 23:00:", since[since.k == 60].spr.median().round(1))

# ---- 実行後の追加(登録外・参考・判定なし): 22:00 ちょうどの足が無い週(冬時間に多い)も、22:00〜22:15 の最初の足を起点にして含める ----
ref = []
for s_ in suns:
    t0 = s_ + pd.Timedelta(hours=22); day = D[(D.index >= s_) & (D.index < s_ + pd.Timedelta(hours=27))]; w0 = day[(day.index >= t0) & (day.index <= t0 + pd.Timedelta(minutes=15))]
    if not len(w0): continue
    ts = w0.index[0]; win = day[(day.index >= ts) & (day.index <= ts + pd.Timedelta(minutes=45))]
    for cap in (3, 5):
        ok = win[win.spr <= cap + 1e-9]
        if not len(ok): continue
        for ex in (23, 24):
            px, _ = price_at(day, s_ + pd.Timedelta(hours=ex), "BidOpen")
            if px != px or ok.index[0] >= s_ + pd.Timedelta(hours=ex): continue
            pa = float(ok.AskOpen.iloc[0]); ref.append(dict(cell=f"cap{cap}_exit{ex}", sunday=s_, month=(s_ + pd.Timedelta(days=1)).strftime("%Y-%m"), pip=(px - pa) / PIP, ret=(px / pa - 1) * 100, dst=us_dst(s_)))
RF = pd.DataFrame(ref); rr = []
for cell, g in RF.groupby("cell", sort=False):
    o = dict(cell=cell, trades=len(g), mean_pip=round(g.pip.mean(), 2), win=round((g.pip > 0).mean() * 100, 1), std_n=int((~g.dst).sum()), std_mean_pip=round(g[~g.dst].pip.mean(), 2))
    for nm, a, b in (("pre", "2016-01", "2021-09"), ("is", "2021-10", "2024-12"), ("oos", "2025-01", "2099-12")):
        x = seg(g, a, b); m = x.groupby("month").ret.sum(); o.update({f"{nm}_plus": int((m > 0).sum()), f"{nm}_months": len(m), f"{nm}_cum_pct": round(m.sum(), 2)})
    o["is_p"] = binom_p(o["is_plus"], o["is_months"]); rr.append(o)
RR = pd.DataFrame(rr); RR.to_csv("results/q193_gbpjpy_weekopen_wait_spread_ref.csv", index=False); print(); print("参考(登録外): 22:00〜22:15 の最初の足を起点"); print(RR.to_string(index=False))
