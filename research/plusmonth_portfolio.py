# -*- coding: utf-8 -*-
"""docs/227: 「+月が多い順 上位5」ポートフォリオ(5年版 / 3年版)に標準リスク調整(逆ボラ加重 cap40% → 倍率校正 0.8×min(m*_窓, m*_12m) 上限6)
を当てた成績。窓内(サンプル内)と、順位付けを1年前で止めた walk-forward(サンプル外12ヶ月)の両方を出す。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base, deployed_book as db
from forward.paper_forward import refresh_live, universe
END = pd.Timestamp("2026-09-13"); TOP = 5


def monthly(s): return s.groupby(pd.PeriodIndex(s.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)


def rank(series, a, b):
    rows = []
    for (fam, sym), s in series.items():
        m = monthly(s[(s.index >= a) & (s.index <= b)]); m = m[m != 0]
        rows.append(dict(key=(fam, sym), plus=int((m > 0).sum()), act=int(len(m)), rate=float((m > 0).mean()) if len(m) else 0, mean=float(m.mean()) if len(m) else 0))
    rows.sort(key=lambda r: (r["plus"], r["rate"], r["mean"]), reverse=True)
    return rows[:TOP]


def build(series, picks, a, b):
    """逆ボラ加重(活動日 std・窓内)cap40% → 倍率 0.8×min(m*_窓, m*_直近12m) 上限6"""
    iv = {}
    for r in picks:
        s = series[r["key"]]; w = s[(s.index >= a) & (s.index <= b)]; act = w[w != 0]
        iv[r["key"]] = 1.0 / float(act.std())
    tot = sum(iv.values()); w = {k: v / tot for k, v in iv.items()}
    w = {k: min(v, base.W_CAP) for k, v in w.items()}; t2 = sum(w.values()); w = {k: v / t2 for k, v in w.items()}
    idx = sorted(set().union(*[set(series[k].index) for k in w]))
    comp = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, v in w.items(): comp = comp.add(series[k].reindex(comp.index).fillna(0) * v, fill_value=0)
    win = comp[(comp.index >= a) & (comp.index <= b)]
    m_win = base.calibrate(win); m_12 = base.calibrate(win[win.index >= b - pd.DateOffset(months=12)])
    mult = min(m_win, m_12, 6.0)
    return w, comp, mult, m_win, m_12


def perf(daily, mult):
    r = daily * mult; eq = (1 + r).cumprod(); dd = (eq / eq.cummax() - 1)
    mk = pd.PeriodIndex(r.index, freq="M"); mon = r.groupby(mk).apply(lambda q: (1 + q).prod() - 1)
    yr = r.groupby(r.index.year).apply(lambda q: ((1 + q).prod() - 1) * 100).round(1).to_dict()
    act = r[r != 0]
    return dict(total_pct=round(float(eq.iloc[-1] - 1) * 100, 1), by_year_pct=yr, max_dd_pct=round(float(dd.min()) * 100, 2),
                worst_day_pct=round(float(r.min()) * 100, 2), worst_month_pct=round(float(mon.min()) * 100, 2), best_month_pct=round(float(mon.max()) * 100, 2),
                plus_months=f"{int((mon > 0).sum())}/{int((mon != 0).sum())}", sharpe_act=round(float(act.mean() / act.std() * np.sqrt(252)), 2) if len(act) > 2 else None)


def main():
    refresh_live(); rng = np.random.default_rng(7)
    series = {}
    for fam, sym in universe():
        s = db.leg_series(fam, sym); series[(fam, sym)] = s[s.index <= END]
    out = {}
    for label, a in (("5y", pd.Timestamp("2021-10-01")), ("3y", pd.Timestamp("2023-10-01"))):
        # (A) サンプル内: 窓全体で順位付け → 同じ窓で校正・評価
        picks = rank(series, a, END); w, comp, mult, m_win, m_12 = build(series, picks, a, END)
        win = comp[(comp.index >= a) & (comp.index <= END)]
        mc = base.mc_challenge(win[win.index >= END - pd.DateOffset(months=12)], mult, rng)
        A = dict(picks=[dict(cell=f"{r['key'][0]} {r['key'][1]}", plus=r["plus"], act=r["act"], weight=round(w[r["key"]], 3)) for r in picks],
                 mult=mult, m_star_window=m_win, m_star_12m=m_12, perf=perf(win, mult), perf_x1=perf(win, 1.0), mc_fn_stellar=mc)
        # (B) walk-forward: 順位付け・加重・校正を 2025-09-30 で締め、2025-10〜2026-09 を評価
        cut = pd.Timestamp("2025-09-30"); picks_b = rank(series, a, cut); w_b, comp_b, mult_b, mw_b, m12_b = build(series, picks_b, a, cut)
        oos = comp_b[(comp_b.index > cut) & (comp_b.index <= END)]
        B = dict(picks=[dict(cell=f"{r['key'][0]} {r['key'][1]}", plus=r["plus"], act=r["act"], weight=round(w_b[r["key"]], 3)) for r in picks_b],
                 mult=mult_b, perf_oos=perf(oos, mult_b), perf_oos_x1=perf(oos, 1.0), mc_fn_stellar_oos=base.mc_challenge(oos, mult_b, rng))
        out[label] = dict(in_sample=A, walk_forward=B)
        print(f"\n=== {label} 上位{TOP}(サンプル内 {a.date()}〜{END.date()}) 倍率 {mult} (m*窓 {m_win} / m*12m {m_12})")
        for p in A["picks"]: print(f"   {p['cell']:16s} +{p['plus']}/{p['act']}  w={p['weight']}")
        print("   ×1  :", A["perf_x1"]); print("   ×m  :", A["perf"]); print("   MC(直近12m・FN Stellar):", mc)
        print(f"--- walk-forward: 2025-09-30 で締めて選抜/校正 → 2025-10〜2026-09 を評価  倍率 {mult_b}")
        for p in B["picks"]: print(f"   {p['cell']:16s} +{p['plus']}/{p['act']}  w={p['weight']}")
        print("   OOS ×1 :", B["perf_oos_x1"]); print("   OOS ×m :", B["perf_oos"]); print("   MC OOS :", B["mc_fn_stellar_oos"])
    json.dump(out, open(os.path.join(HERE, "results", "plusmonth_portfolio.json"), "w"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__": main()
