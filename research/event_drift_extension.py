# -*- coding: utf-8 -*-
"""docs/210: イベント・ドリフト横展開(BoJ/ECB/CPI/NFP + FOMC 対照)を Dukascopy 日足で一次スクリーニング。"""
import os, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
import event_calendar as ec

HERE = os.path.dirname(os.path.abspath(__file__)); DUKA = os.path.join(HERE, "data_dukascopy")
N_PERM, SEED = 10000, 7
IS_END = pd.Timestamp("2015-12-31"); END = pd.Timestamp("2025-12-31")
COST = {"US500": 2e-4, "NAS100": 2e-4, "GER40": 2e-4, "JP225": 2e-4, "UK100": 2e-4, "XAUUSD": 2e-4,
        "USDJPY": 1e-4, "EURJPY": 1e-4, "GBPJPY": 1e-4, "EURUSD": 1e-4}
PRIMARY = [("P1", "BOJ", "JP225", "PRE"), ("P2", "ECB", "GER40", "PRE"),
           ("P3", "NFP", "US500", "EVT"), ("P4", "CPI", "US500", "EVT")]
CONTROL = [("C1", "FOMC", "US500", "PRE"), ("C2", "FOMC", "US500", "EVT")]
ALPHA = 0.05 / 4


def load(sym):
    p = os.path.join(DUKA, f"{sym}_day.csv")
    if not os.path.exists(p): return None
    d = pd.read_csv(p, parse_dates=["timestamp"])
    d = d[d.timestamp.dt.dayofweek <= 4]
    d = d[~((d.open == d.high) & (d.high == d.low) & (d.low == d.close) & (d.volume == 0))]
    s = d.set_index(d.timestamp.dt.normalize())["close"]
    return s[s.index <= END].pct_change().dropna()


def windows(ret, dates):
    idx = ret.index; pos = {d: i for i, d in enumerate(idx)}
    pre, evt, used = [], [], []
    for d in dates:
        t = pd.Timestamp(d)
        if t in pos and pos[t] >= 1 and t >= idx[0] + pd.Timedelta(days=400):
            pre.append(ret.iloc[pos[t] - 1]); evt.append(ret.iloc[pos[t]]); used.append(t)
    return pd.Series(pre, index=used), pd.Series(evt, index=used)


def perm(ret, sample, rng, one_sided):
    """曜日を揃えたランダム日(同数・復元抽出)の平均との順列検定(ベクトル化)。"""
    obs = sample.mean(); dows = sample.index.dayofweek.values; n = len(dows)
    tot = np.zeros(N_PERM)
    for k in range(5):
        c = int((dows == k).sum())
        if c: tot += rng.choice(ret[ret.index.dayofweek == k].values, size=(N_PERM, c)).sum(axis=1)
    sims = tot / n
    return float((sims >= obs).mean()) if one_sided else float((np.abs(sims) >= abs(obs)).mean())


def evaluate(ret, sample, sym, one_sided, rng):
    n = len(sample); mean = float(sample.mean())
    p = perm(ret, sample, rng, one_sided)
    yrs = sorted(set(sample.index.year)); jk = []
    for y in yrs:
        s2 = sample[sample.index.year != y]
        if len(s2) >= 10: jk.append(perm(ret, s2, np.random.default_rng(SEED), one_sided))
    is_m = float(sample[sample.index <= IS_END].mean()) if (sample.index <= IS_END).any() else float("nan")
    oos_m = float(sample[sample.index > IS_END].mean()) if (sample.index > IS_END).any() else float("nan")
    net = mean - COST[sym]
    return {"n": n, "mean_bps": round(mean * 1e4, 2), "p": p, "jk_max_p": round(max(jk), 4) if jk else None,
            "is_bps": round(is_m * 1e4, 2), "oos_bps": round(oos_m * 1e4, 2), "net_bps": round(net * 1e4, 2),
            "win": round(float((sample > 0).mean()), 3), "t": round(mean / sample.std() * np.sqrt(n), 2),
            "years": f"{yrs[0]}-{yrs[-1]}"}


def main():
    rets = {s: load(s) for s in COST}; rets = {k: v for k, v in rets.items() if v is not None}
    print("価格:", {k: f"{v.index[0].date()}..{v.index[-1].date()}" for k, v in rets.items()})
    cal = {k: fn() for k, fn in ec.ALL.items()}
    out = {"primary": {}, "control": {}, "exploratory": {}}
    for tag, ev, sym, win in PRIMARY + CONTROL:
        if sym not in rets: print(f"{tag} {ev}/{sym}: データ未取得"); continue
        pre, evt = windows(rets[sym], cal[ev]); r = evaluate(rets[sym], pre if win == "PRE" else evt, sym, True, np.random.default_rng(SEED))
        ok = r["p"] < ALPHA and (r["jk_max_p"] or 1) < 0.05 and r["is_bps"] > 0 and r["oos_bps"] > 0 and r["net_bps"] > 0
        r["verdict"] = "LEAD" if ok else ("弱い兆候" if r["p"] < 0.05 else "REJECT")
        (out["primary"] if tag.startswith("P") else out["control"])[f"{tag} {ev}/{sym}/{win}"] = r
        print(f"{tag} {ev:4s} {sym:6s} {win}: n={r['n']:3d} mean={r['mean_bps']:+6.1f}bps p={r['p']:.4f} JKmax={r['jk_max_p']} IS={r['is_bps']:+.1f} OOS={r['oos_bps']:+.1f} net={r['net_bps']:+.1f} win={r['win']:.2f} → {r['verdict']}")
    print("\n探索(両側):")
    for ev in ec.ALL:
        for sym, ret in rets.items():
            pre, evt = windows(ret, cal[ev])
            for win, smp in (("PRE", pre), ("EVT", evt)):
                r = evaluate(ret, smp, sym, False, np.random.default_rng(SEED))
                flag = "★" if r["p"] < ALPHA and (r["jk_max_p"] or 1) < 0.05 and r["is_bps"] * r["oos_bps"] > 0 else ("*" if r["p"] < 0.05 else "")
                out["exploratory"][f"{ev}/{sym}/{win}"] = dict(r, flag=flag)
                print(f"  {ev:4s} {sym:6s} {win} n={r['n']:3d} mean={r['mean_bps']:+6.1f} p2={r['p']:.4f} JK={r['jk_max_p']} IS={r['is_bps']:+.1f}/OOS={r['oos_bps']:+.1f} {flag}")
    json.dump(out, open(os.path.join(HERE, "results", "event_drift_extension.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
