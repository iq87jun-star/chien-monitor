# -*- coding: utf-8 -*-
"""docs/215: 日中 Phase 2 — docs/208 の 8 候補を Dukascopy H1(2016-01〜2026-08)で追認。"""
import os, json, math, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
import intraday_phase1 as p1
HERE = os.path.dirname(os.path.abspath(__file__)); DUKA = os.path.join(HERE, "data_dukascopy")
SYMS = ["GBPJPY", "AUDJPY", "USDJPY", "EURJPY"]; EXTRA = ["GBPUSD"]
W0, W1 = pd.Timestamp("2016-01-01"), pd.Timestamp("2026-08-31 23:00"); IS_END = pd.Timestamp("2020-12-31")


def load_h1(sym):
    d = pd.read_csv(os.path.join(DUKA, f"{sym}_hour.csv.gz"), parse_dates=["timestamp"])
    d = d[~((d.open == d.high) & (d.high == d.low) & (d.low == d.close))].set_index("timestamp").sort_index()
    return d[(d.index >= W0) & (d.index <= W1)]


def tp(t): return 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
def tstat(x): return float(x.mean() / x.std() * math.sqrt(len(x))) if len(x) > 1 and x.std() > 0 else 0.0


def main():
    dfs = {s: load_h1(s) for s in SYMS + EXTRA}
    print("H1本数:", {s: len(d) for s, d in dfs.items()})
    def basket(syms, weekday, hours, hold):
        per = [pd.concat([p1.shot_returns(dfs[s], s, h, hold, weekday) for h in hours], axis=1).mean(axis=1) for s in syms]
        return pd.concat(per, axis=1).mean(axis=1).dropna()
    out = {"meta": dict(window=[str(W0.date()), str(W1.date())], syms=SYMS, alpha=p1.ALPHA, cost_pips=p1.COST_PIPS), "candidates": {}, "gbpusd": {}}
    rows = []
    for wn, hours in p1.WINDOWS.items():
        for hold in p1.HOLDS:
            mon = basket(SYMS, 0, hours, hold); t = tstat(mon); p = tp(t)
            plc = {nm: dict(mean_bps=round(float(x.mean()) * 1e4, 2), t=round(tstat(x), 2), p=round(tp(tstat(x)), 3))
                   for wd, nm in ((1, "Tue"), (2, "Wed"), (3, "Thu"), (4, "Fri")) for x in [basket(SYMS, wd, hours, hold)]}
            i_, o_ = mon[mon.index <= IS_END], mon[mon.index > IS_END]
            rec = dict(window=wn, hours=hours, hold=hold, n=len(mon), mean_bps=round(float(mon.mean()) * 1e4, 2), cum_pct=round(float((1 + mon).prod() - 1) * 100, 2),
                       t=round(t, 2), p=round(p, 5), sig_bonf=bool(p < p1.ALPHA), win_rate=round(float((mon > 0).mean()) * 100, 1),
                       is_bps=round(float(i_.mean()) * 1e4, 2), oos_bps=round(float(o_.mean()) * 1e4, 2), is_t=round(tstat(i_), 2), oos_t=round(tstat(o_), 2),
                       maxdd_pct=round(float(((1 + mon).cumprod() / (1 + mon).cumprod().cummax() - 1).min()) * 100, 2), placebo=plc,
                       monday_only=bool(p < p1.ALPHA and all(v["p"] >= 0.05 for v in plc.values())))
            rows.append(rec); out["candidates"][f"{wn}/{hold}h"] = rec
            print(f"{wn:6s} {hold:2d}h n={rec['n']:3d} mean={rec['mean_bps']:+5.1f}bps cum={rec['cum_pct']:+6.2f}% DD={rec['maxdd_pct']:.1f} t={t:+5.2f} p={p:.5f} {'★' if rec['sig_bonf'] else ' '} IS/OOS={rec['is_bps']:+.1f}/{rec['oos_bps']:+.1f} (t {rec['is_t']:+.2f}/{rec['oos_t']:+.2f}) | 火〜金 t: " + " ".join(f"{k}={v['t']:+.2f}" for k, v in plc.items()))
    B = {h: basket(SYMS, 0, p1.WINDOWS["B_配備"], h) for h in p1.HOLDS}
    best = max(rows, key=lambda r: r["t"]); out["best"] = best["window"] + f"/{best['hold']}h"
    if best["window"] != "B_配備":
        x = basket(SYMS, 0, p1.WINDOWS[best["window"]], best["hold"]); j = pd.concat([x.rename("x"), B[best["hold"]].rename("y")], axis=1).dropna(); d = j.x - j.y
        out["best_vs_B"] = dict(diff_bps=round(float(d.mean()) * 1e4, 2), t=round(tstat(d), 2), p=round(tp(tstat(d)), 4)); print("最良 vs B(同保有):", out["best_vs_B"])
    j = pd.concat([B[12].rename("h12"), B[24].rename("h24")], axis=1).dropna(); d = j.h12 - j.h24
    out["B_12h_minus_24h"] = dict(diff_bps=round(float(d.mean()) * 1e4, 2), t=round(tstat(d), 2), p=round(tp(tstat(d)), 4), n=len(d)); print("B 12h−24h 対応差:", out["B_12h_minus_24h"])
    for hold in p1.HOLDS:
        g = basket(EXTRA, 0, p1.WINDOWS["B_配備"], hold); out["gbpusd"][f"B/{hold}h"] = dict(n=len(g), mean_bps=round(float(g.mean()) * 1e4, 2), t=round(tstat(g), 2), p=round(tp(tstat(g)), 4))
        print(f"GBPUSD B/{hold}h:", out["gbpusd"][f"B/{hold}h"])
    json.dump(out, open(os.path.join(HERE, "results", "intraday_phase2.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__": main()
