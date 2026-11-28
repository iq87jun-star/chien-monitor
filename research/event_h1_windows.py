# -*- coding: utf-8 -*-
"""docs/214: G3 型 24h 窓(H1)— ECB/GER40, FOMC/EURUSD(一次), FOMC/US500(対照), POST6 副次。"""
import os, json, datetime as dt, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
import event_calendar as ec
HERE = os.path.dirname(os.path.abspath(__file__)); DUKA = os.path.join(HERE, "data_dukascopy")
N_PERM, SEED = 10000, 7; COST = {"GER40": 2e-4, "US500": 2e-4, "EURUSD": 1e-4}
PRIMARY = [("P1", "ECB", "GER40"), ("P2", "FOMC", "EURUSD")]; CONTROL = [("C", "FOMC", "US500")]
SECOND = [("S1", "FOMC", "GER40"), ("S2", "ECB", "EURUSD")]; ALPHA = 0.025


def load_h1(sym):
    d = pd.read_csv(os.path.join(DUKA, f"{sym}_hour.csv.gz"), parse_dates=["timestamp"])
    d = d[~((d.open == d.high) & (d.high == d.low) & (d.low == d.close))]
    return d.set_index("timestamp").sort_index()


def _nth_sunday(y, m, n): 
    d = dt.date(y, m, 1); d += dt.timedelta(days=(6 - d.weekday()) % 7); return d + dt.timedelta(days=7 * (n - 1))
def _last_sunday(y, m):
    d = dt.date(y, m + 1, 1) - dt.timedelta(days=1) if m < 12 else dt.date(y, 12, 31); return d - dt.timedelta(days=(d.weekday() + 1) % 7)
def us_dst(d): return _nth_sunday(d.year, 3, 2) <= d < _nth_sunday(d.year, 11, 1)
def eu_dst(d): return _last_sunday(d.year, 3) <= d < _last_sunday(d.year, 10)
def ann_hour(ev, d):
    if ev == "FOMC": return 18 if us_dst(d) else 19
    if d < dt.date(2022, 7, 21): return 11 if eu_dst(d) else 12
    return 12 if eu_dst(d) else 13


def win_ret(df, ev, d, kind):
    ha = ann_hour(ev, d); tx = pd.Timestamp(d) + pd.Timedelta(hours=ha)
    try:
        if kind == "PRE24":
            t0 = tx - pd.Timedelta(hours=24); return float(df.at[tx - pd.Timedelta(hours=1), "close"] / df.at[t0, "open"] - 1)
        return float(df.at[tx + pd.Timedelta(hours=5), "close"] / df.at[tx, "open"] - 1)
    except KeyError: return np.nan


def evaluate(df, ev, dates, sym, kind, one_sided, rng):
    dates = [d for d in dates if d.weekday() < 5]
    r = pd.Series({pd.Timestamp(d): win_ret(df, ev, d, kind) for d in dates}).dropna()
    if len(r) < 10: return None
    # 同曜日の非事象日プール(同じ窓)
    evset = set(dates); days = sorted(set(df.index.normalize().date)); days = [x for x in days if x.weekday() < 5 and x not in evset and r.index[0].date() <= x <= r.index[-1].date()]
    pool = pd.Series({pd.Timestamp(x): win_ret(df, ev, x, kind) for x in days}).dropna()
    by_dow = {k: pool[pool.index.dayofweek == k].values for k in range(5)}
    dows = r.index.dayofweek.values; tot = np.zeros(N_PERM)
    for k in range(5):
        c = int((dows == k).sum())
        if c and len(by_dow[k]): tot += rng.choice(by_dow[k], size=(N_PERM, c)).sum(axis=1)
    sims = tot / len(r); obs = r.mean()
    p = float((sims >= obs).mean()) if one_sided else float((np.abs(sims) >= abs(obs)).mean())
    def perm_sub(s):
        d2 = s.index.dayofweek.values; t2 = np.zeros(N_PERM); rg = np.random.default_rng(SEED)
        for k in range(5):
            c = int((d2 == k).sum())
            if c and len(by_dow[k]): t2 += rg.choice(by_dow[k], size=(N_PERM, c)).sum(axis=1)
        sm = t2 / len(s); return float((sm >= s.mean()).mean()) if one_sided else float((np.abs(sm) >= abs(s.mean())).mean())
    jk = [perm_sub(r[r.index.year != y]) for y in sorted(set(r.index.year)) if len(r[r.index.year != y]) >= 10]
    mid = r.index[len(r) // 2]; is_m, oos_m = float(r[r.index < mid].mean()), float(r[r.index >= mid].mean())
    return dict(n=len(r), mean_bps=round(obs * 1e4, 2), p=p, jk_max_p=round(max(jk), 4), is_bps=round(is_m * 1e4, 2), oos_bps=round(oos_m * 1e4, 2),
                net_bps=round((obs - COST[sym]) * 1e4, 2), win=round(float((r > 0).mean()), 3), t=round(float(obs / r.std() * np.sqrt(len(r))), 2),
                years=f"{r.index[0].year}-{r.index[-1].year}", pool_mean_bps=round(float(pool.mean()) * 1e4, 2))


def main():
    dfs = {s: load_h1(s) for s in COST}; cal = {k: fn() for k, fn in ec.ALL.items() if k in ("FOMC", "ECB")}
    print("H1:", {s: f"{d.index[0].date()}..{d.index[-1].date()} ({len(d)})" for s, d in dfs.items()})
    out = {}
    for tag, ev, sym in PRIMARY + CONTROL + SECOND:
        for kind in ("PRE24", "POST6"):
            one = (tag[0] in "PC") and kind == "PRE24"
            r = evaluate(dfs[sym], ev, cal[ev], sym, kind, one, np.random.default_rng(SEED))
            if r is None: continue
            if one:
                ok = r["p"] < ALPHA and r["jk_max_p"] < 0.05 and r["is_bps"] > 0 and r["oos_bps"] > 0 and r["net_bps"] > 0
                r["verdict"] = "LEAD" if ok else ("弱い兆候" if r["p"] < 0.05 else "REJECT")
            else: r["verdict"] = "(副次)" + ("*" if r["p"] < 0.05 else "")
            out[f"{tag} {ev}/{sym}/{kind}"] = r
            print(f"{tag:2s} {ev:4s} {sym:6s} {kind:5s} n={r['n']:3d} mean={r['mean_bps']:+6.1f}bps p={r['p']:.4f} JK={r['jk_max_p']} IS={r['is_bps']:+.1f}/OOS={r['oos_bps']:+.1f} net={r['net_bps']:+.1f} win={r['win']:.2f} pool={r['pool_mean_bps']:+.1f} → {r['verdict']}")
    json.dump(out, open(os.path.join(HERE, "results", "event_h1_windows.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__": main()
