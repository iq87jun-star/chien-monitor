# -*- coding: utf-8 -*-
"""
portfolio_D_v4share.py — PDのv4比率(30/15/0%)の同土俵比較【事前登録 docs/136】。
ベース=PD間引き版(docs/135)。各変種を中央3ヶ月へ校正し失格%・月利・Sharpeを比較。
決定規則: v4削減の採用 = 失格%(楽観・悲観とも)改善 かつ 平均月利≥基準の90%。
出力: results/portfolio_D_v4share.json → docs/137
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import mon_daily, v4_daily, composite_daily, EMON
from policy_prune_symbols import e5_basket
from median3_calibrate_compare import month_arrays, month_stats_at, simulate, calibrate_median3
from seasonal_optimize_loyo import sha256s

SEED, N_FINAL = 7, 20000
BASE = {"v4": .30, "v7": .25, "EMon": .25, "E5": .20}


def wmap_for(x):
    k = (1.0 - x) / 0.70
    w = {"v4": x, "v7": round(.25 * k, 4), "EMon": round(.25 * k, 4), "E5": round(.20 * k, 4)}
    return {m: w for m in range(1, 13)}, w


def mstats(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    m = pd.Series({k: float((1 + s[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()
    sh = float(m.mean() / m.std() * np.sqrt(12)) if m.std() > 0 else 0.0
    return dict(mean_month=round(float(m.mean() * 100), 2), sharpe=round(sh, 2),
                worst_month=round(float(m.min() * 100), 2), worst_day=round(float(s.min() * 100), 2))


def main():
    print("[1/2] スリーブ(間引き版ベース)")
    sleeves = dict(v4=v4_daily(), v7=mon_daily(["EURJPY", "GBPJPY"]),
                   EMon=mon_daily(EMON, 3e-4), E5=e5_basket(["XAUUSD", "NAS100"]))

    print("[2/2] 校正+MC")
    out = {}
    for x in (0.30, 0.15, 0.0):
        wmap, w = wmap_for(x)
        base = composite_daily(sleeves, wmap)
        arrs = month_arrays(base)
        mult, _ = calibrate_median3(arrs, None, np.random.default_rng(SEED))
        if mult is None:
            out[f"v4_{int(x*100)}pct"] = dict(weights=w, note="中央3ヶ月に到達不可")
            continue
        st = simulate(month_stats_at(arrs, mult, None), N_FINAL, np.random.default_rng(SEED))
        rec = dict(weights=w, mult=mult, **st, **mstats(base * mult))
        out[f"v4_{int(x*100)}pct"] = rec
        print(f"  v4={int(x*100)}%: mult={mult} {st} {mstats(base*mult)}")

    b = out["v4_30pct"]
    def qualify(r):
        return (r["fail_pct_optimistic"] < b["fail_pct_optimistic"] and
                r["fail_pct_raw"] < b["fail_pct_raw"] and
                r["mean_month"] >= 0.9 * b["mean_month"])
    cands = [k for k in ("v4_15pct", "v4_0pct") if "mult" in out[k] and qualify(out[k])]
    if cands:
        pick = min(cands, key=lambda k: out[k]["fail_pct_optimistic"])
        decision = dict(adopt_candidate=pick, next_gate="Dukascopy同構成比較(docs/136 §3・必須)",
                        verdict=f"{pick} が決定規則合格(ただしYahoo判定=最終関門あり)")
    else:
        decision = dict(adopt_candidate=None, verdict="v4 30%維持(削減変種は決定規則不合格)")
    res = dict(meta=dict(prereg="docs/136", seed=SEED, n_paths=N_FINAL, base="PD間引き版(docs/135)",
                         inputs=sha256s()),
               variants=out, decision=decision)
    path = os.path.join(HERE, "results", "portfolio_D_v4share.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("判定:", decision["verdict"])
    print("保存:", path)


if __name__ == "__main__":
    main()
