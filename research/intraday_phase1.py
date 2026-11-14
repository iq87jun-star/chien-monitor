# -*- coding: utf-8 -*-
"""intraday_phase1.py — 日中Phase 1(docs/208)。円クロス月曜4ショット窓×保有時間をYahoo H1(約2年)で検証。LEAD級。"""
import os, sys, json, math, urllib.request, datetime as dt
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data_h1"); os.makedirs(DATA, exist_ok=True)
SYMS = ["GBPJPY", "AUDJPY", "USDJPY", "EURJPY", "NZDJPY", "CADJPY", "CHFJPY"]
W0, W1 = pd.Timestamp("2024-09-01"), pd.Timestamp("2026-08-31 23:59")
WINDOWS = {"A_早朝": [0, 2, 4, 6], "B_配備": [4, 6, 8, 10], "C_欧州": [8, 10, 12, 14], "D_米国": [12, 14, 16, 18]}
HOLDS = [12, 24]; ALPHA = 0.05 / 8; COST_PIPS = 2.0

def fetch_h1(sym):
    p = os.path.join(DATA, f"{sym}_h1.csv")
    if not os.path.exists(p):
        u = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}%3DX?interval=1h&range=730d"
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
        r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
        rows = [(dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), q["open"][i], q["high"][i], q["low"][i], q["close"][i])
                for i, t in enumerate(ts) if q["open"][i] is not None and q["close"][i] is not None]
        pd.DataFrame(rows, columns=["t", "open", "high", "low", "close"]).to_csv(p, index=False)
    df = pd.read_csv(p, parse_dates=["t"]).set_index("t").sort_index()
    return df[(df.index >= W0) & (df.index <= W1)]

def shot_returns(df, sym, hour, hold, weekday):
    """weekday の hour(UTC) 始値で建て、hold時間後の始値で決済。コスト2pip往復。"""
    pip = 0.01 if sym.endswith("JPY") else 0.0001
    idx = df.index; o = df["open"]
    ent = idx[(idx.dayofweek == weekday) & (idx.hour == hour)]
    out = {}
    for t in ent:
        tx = t + pd.Timedelta(hours=hold)
        j = idx.searchsorted(tx)
        if j >= len(idx) or (idx[j] - tx) > pd.Timedelta(hours=3): continue
        out[t.normalize()] = (o.iloc[j] - o.loc[t]) / o.loc[t] - COST_PIPS * pip / o.loc[t]
    return pd.Series(out)

def main():
    dfs = {s: fetch_h1(s) for s in SYMS}
    print("H1本数:", {s: len(d) for s, d in dfs.items()})
    out = {"meta": dict(window=[str(W0.date()), str(W1.date())], syms=SYMS, windows=WINDOWS, holds=HOLDS, alpha=ALPHA, cost_pips=COST_PIPS), "candidates": {}, "range_proxy": {}}
    # 執行コスト代理: 時刻別 H1 レンジ中央値(pip)
    for s in SYMS:
        d = dfs[s]; pip = 0.01
        out["range_proxy"][s] = {int(h): round(float(((d.high - d.low) / pip)[d.index.hour == h].median()), 1) for h in range(24)}
    def basket(weekday, hours, hold):
        per = []
        for s in SYMS:
            sh = [shot_returns(dfs[s], s, h, hold, weekday) for h in hours]
            per.append(pd.concat(sh, axis=1).mean(axis=1))
        return pd.concat(per, axis=1).mean(axis=1).dropna()
    rows = []
    for wn, hours in WINDOWS.items():
        for hold in HOLDS:
            mon = basket(0, hours, hold)
            t = float(mon.mean() / mon.std() * math.sqrt(len(mon))) if mon.std() > 0 else 0.0
            p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
            plc = {}
            for wd, nm in ((1, "Tue"), (2, "Wed"), (3, "Thu"), (4, "Fri")):
                x = basket(wd, hours, hold); tt = float(x.mean() / x.std() * math.sqrt(len(x))) if x.std() > 0 else 0.0
                plc[nm] = dict(mean_bps=round(float(x.mean()) * 1e4, 2), t=round(tt, 2), p=round(2 * (1 - 0.5 * (1 + math.erf(abs(tt) / math.sqrt(2)))), 3))
            rec = dict(window=wn, hours=hours, hold=hold, n=int(len(mon)), mean_bps=round(float(mon.mean()) * 1e4, 2),
                       cum_pct=round(float((1 + mon).prod() - 1) * 100, 2), t=round(t, 2), p=round(p, 4), sig_bonf=bool(p < ALPHA),
                       win_rate=round(float((mon > 0).mean()) * 100, 1), worst_bps=round(float(mon.min()) * 1e4, 1), placebo=plc,
                       monday_only=bool(p < ALPHA and all(v["p"] >= 0.05 for v in plc.values())))
            rows.append(rec); out["candidates"][f"{wn}/{hold}h"] = rec
            print(f"{wn:6s} {hold:2d}h n={rec['n']:3d} mean={rec['mean_bps']:+6.1f}bps cum={rec['cum_pct']:+6.2f}% t={t:+5.2f} p={p:.4f} {'★' if rec['sig_bonf'] else ' '} 勝率{rec['win_rate']}% | 火〜金 t: " + " ".join(f"{k}={v['t']:+.2f}" for k, v in plc.items()))
    # B(配備) と最良窓の差の対応あり t 検定
    mon_B = {h: basket(0, WINDOWS["B_配備"], h) for h in HOLDS}
    best = max(rows, key=lambda r: r["t"]); out["best"] = best["window"] + f"/{best['hold']}h"
    if best["window"] != "B_配備":
        x = basket(0, WINDOWS[best["window"]], best["hold"]); y = mon_B[best["hold"]]
        j = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna(); d = (j.x - j.y)
        td = float(d.mean() / d.std() * math.sqrt(len(d))); pdf = 2 * (1 - 0.5 * (1 + math.erf(abs(td) / math.sqrt(2))))
        out["best_vs_B"] = dict(diff_bps=round(float(d.mean()) * 1e4, 2), t=round(td, 2), p=round(pdf, 4)); print("最良 vs B(同保有):", out["best_vs_B"])
    print("時刻別レンジ中央値(pip) GBPJPY:", out["range_proxy"]["GBPJPY"])
    json.dump(out, open(os.path.join(HERE, "results", "intraday_phase1.json"), "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__": main()
