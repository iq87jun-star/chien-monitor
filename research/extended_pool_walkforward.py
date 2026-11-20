# -*- coding: utf-8 -*-
"""extended_pool_walkforward.py — 拡張母集団(docs/207)。BASE 34セル vs EXT 44セル(+E5, +RSI2×9)で SEL12/CALMAR/BROAD_IV を比較。"""
import os, sys, json, collections
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import selection_value_walkforward as wf, selection_metric_walkforward as sm
import recentfit_portfolio_compare as pc
SEED = 7; ARMS = ["SEL12", "CALMAR", "BROAD_IV"]

def build(ext):
    cells = {}
    for nm in base.MON_FX + base.MON_IDX: cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    for nm in base.HOLD_SYMS: cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    for nm in base.TSMOM_SYMS: cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
    for p in base.V4_PAIRS: cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))
    if ext:
        cells["E5_BASKET"] = dict(family="E5", symbol="E5BASKET", s=base.e5_composite())
        for p in base.V4_PAIRS: cells[f"RSI2_{p}"] = dict(family="RSI2", symbol=p, s=pc.rsi2_cell(p, 30, 70, 5))
    return cells

def main():
    base.W_ALL1 = pd.Timestamp("2026-08-31")
    dates = pd.date_range(wf.WF_START, wf.WF_LAST, freq="ME")
    out = {"meta": dict(purpose="拡張母集団 docs/207", seed=SEED), "runs": {}, "tests": {}}
    daily = {}; rng = np.random.default_rng(SEED)
    for pool in ("BASE", "EXT"):
        cells = build(pool == "EXT"); base.verify_window([v["s"] for v in cells.values()])
        print(f"[{pool}] セル数 {len(cells)}", flush=True)
        for arm in ARMS:
            s, hist = sm.run(cells, arm, dates); daily[(pool, arm)] = s
            span = (s.index[-1] - s.index[0]).days; factor = span / len(s); md = int(round(365 / factor))
            rec = dict(**wf.perf(s), avg_mult=round(float(np.mean([h["mult"] for h in hist])), 2),
                       avg_turnover=round(float(np.mean([h["turnover"] for h in hist[1:]])), 3), cal_factor=round(factor, 3),
                       sharpe_cal=round(float(s.mean() / s.std() * np.sqrt(365 / factor)), 2))
            fam = collections.Counter(); newc = collections.Counter()
            for h in hist:
                for k in h["w"]:
                    fam[cells[k]["family"]] += 1
                    if cells[k]["family"] in ("E5", "RSI2"): newc[k] += 1
            rec["family_counts"] = dict(fam); rec["new_cell_counts"] = dict(newc)
            for venue, p1 in (("FTMO_10_5", 0.10), ("FN_8_5", 0.08)):
                base.P1_TARGET = p1
                r = base.mc_challenge(s, 1.0, np.random.default_rng(SEED), max_days=md)
                r["funded_days_med_cal"] = int(round(r["funded_days_med"] * factor)) if r.get("funded_days_med") else None
                rec.setdefault("mc", {})[venue] = r
            out["runs"][f"{pool}/{arm}"] = rec
            m = rec["mc"]["FTMO_10_5"]
            print(f"  {pool}/{arm:9s} cagr={rec['oos_cagr']:6.2f} SRcal={rec['sharpe_cal']:5.2f} maxDD={rec['max_dd']:7.2f} mult={rec['avg_mult']:5.2f} turn={rec['avg_turnover']:.3f} | FTMO funded={m['funded']} fail={m['fail']} med={m['funded_days_med_cal']}d | 新族採用={sum(newc.values())} 族={dict(fam)}", flush=True)
    for arm in ARMS:
        a, b = wf.monthly(daily[("EXT", arm)]), wf.monthly(daily[("BASE", arm)])
        idx = sorted(set(a.index) | set(b.index)); d = (a.reindex(idx).fillna(0) - b.reindex(idx).fillna(0)).values
        t, p = wf.ttest_paired(d); lo, hi = wf.block_boot_ci(d, rng)
        out["tests"][f"EXT-BASE/{arm}"] = dict(mean_monthly_diff_pct=round(float(np.mean(d)) * 100, 3), t=t, p=p,
                                                ci95=[round(lo * 100, 3), round(hi * 100, 3)] if lo is not None else None,
                                                significant_bonf=bool(p is not None and p < 0.05 / 3))
        print(f"  EXT−BASE {arm}: Δ={out['tests'][f'EXT-BASE/{arm}']['mean_monthly_diff_pct']:+.3f}%/月 t={t} p={p}", flush=True)
    with open(os.path.join(HERE, "results", "extended_pool_walkforward.json"), "w") as f: json.dump(out, f, ensure_ascii=False, indent=1, default=str)

if __name__ == "__main__": main()
