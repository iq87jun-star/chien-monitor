# -*- coding: utf-8 -*-
"""
selection_metric_walkforward.py — 【実験】選抜指標の比較(docs/206の実装)。
docs/186の枠組み(母集団・フィルタ・制約・加重・倍率・月次入替)を固定し、スコア関数だけを差し替える。
出力: results/selection_metric_walkforward.json → docs/206 §7
"""
import os, sys, json, math
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import selection_value_walkforward as wf

SEED = 7
ARMS = ["SEL12", "RET", "CALMAR", "WORSTDAY", "LEVRET", "CONSIST", "DIVERSE", "BROAD_IV"]
R = wf.SEL_RULES["SEL12"]


def cell_stats_ext(s, t):
    st = wf.cell_window_stats(s, t, R["sel_m"], R["conf_kind"], R["conf_n"])
    sel0 = t - pd.DateOffset(months=R["sel_m"]) + pd.Timedelta(days=1)
    ss = wf.wnd(s, sel0, t)
    if len(ss) == 0:
        st.update(worst=0.0, dd=0.0, pos_month=0.0); return st
    wd, wdd = base.worst_stats(ss)
    mk = pd.PeriodIndex(ss.index, freq="M")
    mret = pd.Series({k: float((1 + ss[mk == k]).prod() - 1) for k in mk.unique()})
    st.update(worst=float(wd), dd=float(wdd), pos_month=float((mret > 0).mean()) if len(mret) else 0.0)
    return st


def score(arm, st):
    cum = st["cum_sel"]; wd = abs(st["worst"]); dd = abs(st["dd"])
    if arm == "SEL12" or arm == "DIVERSE": return st["score"]
    if arm == "RET": return cum
    if arm == "CALMAR": return cum / dd if dd > 0 else -1e9
    if arm == "WORSTDAY": return cum / wd if wd > 0 else -1e9
    if arm == "LEVRET":
        m = 0.8 * min(0.04 / wd if wd > 0 else 12.0, 0.08 / dd if dd > 0 else 12.0); return cum * min(m, 6.0)
    if arm == "CONSIST": return st["pos_month"] + cum * 1e-3
    return st["score"]


def select_arm(arm, cells, table, t):
    ok = [(k, v) for k, v in table.items()
          if v["st"]["score"] is not None and v["st"]["n_active"] >= R["min_active"]
          and v["st"]["cum_sel"] > 0 and v["st"]["cum_conf"] > 0
          and np.isfinite(v["st"]["std_active"]) and v["st"]["std_active"] > 0]
    sel0 = t - pd.DateOffset(months=12) + pd.Timedelta(days=1)
    scored = sorted([(k, v, score(arm, v["st"])) for k, v in ok], key=lambda x: -x[2])
    picked, fam_ct, sym_used = [], {}, set()
    if arm == "DIVERSE":
        remaining = list(scored)
        while remaining and len(picked) < 4:
            best = None
            for k, v, sc in remaining:
                if v["symbol"] in sym_used or fam_ct.get(v["family"], 0) >= 2: continue
                pen = 0.0
                for p in picked:
                    j = pd.concat([wf.wnd(cells[k]["s"], sel0, t).rename("a"), wf.wnd(cells[p]["s"], sel0, t).rename("b")], axis=1).dropna()
                    if len(j) > 20 and j.a.std() > 0 and j.b.std() > 0: pen = max(pen, float(j.a.corr(j.b)))
                adj = sc * (1 - 1.0 * max(0.0, pen))
                if best is None or adj > best[2]: best = (k, v, adj)
            if best is None: break
            picked.append(best[0]); sym_used.add(best[1]["symbol"]); fam_ct[best[1]["family"]] = fam_ct.get(best[1]["family"], 0) + 1
            remaining = [x for x in remaining if x[0] != best[0]]
    else:
        for k, v, _ in scored:
            if v["symbol"] in sym_used or fam_ct.get(v["family"], 0) >= 2: continue
            picked.append(k); sym_used.add(v["symbol"]); fam_ct[v["family"]] = fam_ct.get(v["family"], 0) + 1
            if len(picked) == 4: break
    return wf.cap_normalize({k: 1.0 / table[k]["st"]["std_active"] for k in picked})


def run(cells, arm, dates):
    pieces, hist, prev = [], [], {}
    for t in dates:
        table = {k: dict(family=v["family"], symbol=v["symbol"], st=cell_stats_ext(v["s"], t)) for k, v in cells.items()}
        w = wf.weights_broad(table, "IV", R["min_active"]) if arm == "BROAD_IV" else select_arm(arm, cells, table, t)
        mult = wf.mult_at(cells, w, t, 12)
        end = min(t + pd.DateOffset(months=1), wf.W_END); s0 = t + pd.Timedelta(days=1)
        seg = wf.composite(cells, w, s0, end) * mult if w else pd.Series(0.0, index=pd.date_range(s0, end, freq="B"))
        if len(seg) == 0: seg = pd.Series(0.0, index=pd.date_range(s0, end, freq="B"))
        pieces.append(seg); hist.append(dict(t=str(t.date()), mult=mult, turnover=round(wf.turnover(prev, w), 3), w=sorted(w))); prev = w
    s = pd.concat(pieces).sort_index(); s = s[~s.index.duplicated(keep="first")]
    return s, hist


def main():
    base.W_ALL1 = pd.Timestamp("2026-08-31")
    for nm in base.YAHOO:
        try: base.fetch(nm)
        except Exception: pass
    cells = {}
    for nm in base.MON_FX + base.MON_IDX: cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    for nm in base.HOLD_SYMS: cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    for nm in base.TSMOM_SYMS: cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
    for p in base.V4_PAIRS: cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))
    base.verify_window([v["s"] for v in cells.values()])
    dates = pd.date_range(wf.WF_START, wf.WF_LAST, freq="ME")
    out = {"meta": dict(purpose="選抜指標の比較 docs/206", seed=SEED, arms=ARMS), "arms": {}, "tests": {}}
    daily = {}; rng = np.random.default_rng(SEED)
    for arm in ARMS:
        s, hist = run(cells, arm, dates); daily[arm] = s
        span = (s.index[-1] - s.index[0]).days; factor = span / len(s); md = int(round(365 / factor))
        rec = dict(**wf.perf(s), avg_mult=round(float(np.mean([h["mult"] for h in hist])), 2),
                   avg_turnover=round(float(np.mean([h["turnover"] for h in hist[1:]])), 3),
                   cal_factor=round(factor, 3), sharpe_cal=round(float(s.mean() / s.std() * np.sqrt(365 / factor)), 2))
        for venue, p1 in (("FTMO_10_5", 0.10), ("FN_8_5", 0.08)):
            base.P1_TARGET = p1
            r = base.mc_challenge(s, 1.0, np.random.default_rng(SEED), max_days=md)
            r["funded_days_med_cal"] = int(round(r["funded_days_med"] * factor)) if r.get("funded_days_med") else None
            rec.setdefault("mc", {})[venue] = r
        out["arms"][arm] = rec
        print(f"{arm:9s} cagr={rec['oos_cagr']:6.2f} SRcal={rec['sharpe_cal']:5.2f} maxDD={rec['max_dd']:7.2f} mult={rec['avg_mult']:5.2f} turn={rec['avg_turnover']:.3f} | "
              f"FTMO funded={rec['mc']['FTMO_10_5']['funded']} fail={rec['mc']['FTMO_10_5']['fail']} med={rec['mc']['FTMO_10_5']['funded_days_med_cal']}d | FN funded={rec['mc']['FN_8_5']['funded']} fail={rec['mc']['FN_8_5']['fail']}", flush=True)
    mons = {a: wf.monthly(daily[a]) for a in ARMS}
    idx = sorted(set().union(*[set(m.index) for m in mons.values()]))
    M = pd.DataFrame({a: mons[a].reindex(idx).fillna(0.0) for a in ARMS})
    for a in ARMS:
        if a == "SEL12": continue
        d = (M[a] - M["SEL12"]).values; t, p = wf.ttest_paired(d); lo, hi = wf.block_boot_ci(d, rng)
        out["tests"][f"{a}-SEL12"] = dict(mean_monthly_diff_pct=round(float(np.mean(d)) * 100, 3), t=t, p=p,
                                          ci95=[round(lo * 100, 3), round(hi * 100, 3)] if lo is not None else None,
                                          significant_bonf=bool(p is not None and p < 0.05 / 6))
        print(f"  {a}-SEL12: Δ={out['tests'][f'{a}-SEL12']['mean_monthly_diff_pct']:+.3f}%/月 t={t} p={p}", flush=True)
    with open(os.path.join(HERE, "results", "selection_metric_walkforward.json"), "w") as f: json.dump(out, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
