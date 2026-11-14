# -*- coding: utf-8 -*-
"""docs/211: 配備中 13 レグ・7 口座を Yahoo と Dukascopy 日足で同一式生成し、同一性を確認する。"""
import os, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
import recentfit_screen as base, deployed_book as db
from e5_replicate_dukascopy import monthly

HERE = os.path.dirname(os.path.abspath(__file__))
DUKA, RF, YAHOO = (os.path.join(HERE, d) for d in ("data_dukascopy", "data_duka_rf", "data"))
import sys
W0, W1 = pd.Timestamp(sys.argv[1] if len(sys.argv) > 2 else "2016-01-01"), pd.Timestamp(sys.argv[2] if len(sys.argv) > 2 else "2025-12-31")
SUFFIX = sys.argv[3] if len(sys.argv) > 3 else ""


def prepare(sym):
    p = os.path.join(DUKA, f"{sym}_day.csv")
    if not os.path.exists(p): return False
    d = pd.read_csv(p, parse_dates=["timestamp"])
    if sym not in base.CRYPTO: d = d[d.timestamp.dt.dayofweek <= 4]
    d = d[~((d.open == d.high) & (d.high == d.low) & (d.low == d.close) & (d.volume == 0))]
    os.makedirs(RF, exist_ok=True)
    d[["timestamp", "open", "high", "low", "close"]].assign(timestamp=d.timestamp.dt.strftime("%Y-%m-%d %H:%M:%S")) \
        .to_csv(os.path.join(RF, f"{sym}_rf.csv"), index=False)
    return True


def series_on(data_dir, fn):
    base.DATA = data_dir; base.W_ALL0, base.W_ALL1 = W0, W1
    s = fn(); return s[(s.index >= W0) & (s.index <= W1)]


def compare(y, d):
    j = pd.concat([y.rename("y"), d.rename("d")], axis=1).fillna(0.0)
    my, md = monthly(y), monthly(d); jm = pd.concat([my.rename("y"), md.rename("d")], axis=1).dropna()
    dd = lambda s: float(((1 + s).cumprod() / (1 + s).cumprod().cummax() - 1).min())
    return {"daily_rho": round(float(j.y.corr(j.d)), 3), "monthly_rho": round(float(jm.y.corr(jm.d)), 3),
            "cum_yahoo": round(float((1 + y).prod() - 1) * 100, 1), "cum_duka": round(float((1 + d).prod() - 1) * 100, 1),
            "maxdd_yahoo": round(dd(y) * 100, 1), "maxdd_duka": round(dd(d) * 100, 1),
            "active_yahoo": int((y != 0).sum()), "active_duka": int((d != 0).sum()), "months": len(jm)}


def verdict(r, acct=False):
    if acct: return "再現" if r["monthly_rho"] >= 0.85 else ("部分再現" if r["monthly_rho"] >= 0.6 else "不一致")
    same = np.sign(r["cum_yahoo"]) == np.sign(r["cum_duka"])
    if r["monthly_rho"] >= 0.80 and same: return "再現"
    if r["monthly_rho"] >= 0.60 and same: return "部分再現"
    return "不一致"


def main():
    legs = sorted({(f, s) for a in db.BOOK.values() for f, s, _ in a["legs"]})
    missing = [s for _, s in legs if not prepare(s)]
    out = {"window": f"{W0.date()}..{W1.date()}", "legs": {}, "accounts": {}, "missing": sorted(set(missing))}
    print("Dukascopy 未取得:", sorted(set(missing)))
    for f, s in legs:
        if s in missing: continue
        y = series_on(YAHOO, lambda: db.leg_series(f, s)); d = series_on(RF, lambda: db.leg_series(f, s))
        r = compare(y, d); r["verdict"] = verdict(r); out["legs"][f"{f}/{s}"] = r
        print(f"{f:7s} {s:7s} ρ日={r['daily_rho']:.3f} ρ月={r['monthly_rho']:.3f} 累積 Y={r['cum_yahoo']:+6.1f}% D={r['cum_duka']:+6.1f}% "
              f"DD Y={r['maxdd_yahoo']:.1f} D={r['maxdd_duka']:.1f} 稼働 {r['active_yahoo']}/{r['active_duka']} → {r['verdict']}")
    for k, a in db.BOOK.items():
        if any(s in missing for _, s, _ in a["legs"]): print(f"{k}: 欠損レグあり・スキップ"); continue
        y = series_on(YAHOO, lambda: db.account_composite(k)); d = series_on(RF, lambda: db.account_composite(k))
        r = compare(y, d); r["verdict"] = verdict(r, acct=True); out["accounts"][k] = r
        print(f"口座 {k:28s} ρ月={r['monthly_rho']:.3f} 累積 Y={r['cum_yahoo']:+6.1f}% D={r['cum_duka']:+6.1f}% DD Y={r['maxdd_yahoo']:.1f} D={r['maxdd_duka']:.1f} → {r['verdict']}")
    json.dump(out, open(os.path.join(HERE, "results", f"deployed_legs_dukascopy{SUFFIX}.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
