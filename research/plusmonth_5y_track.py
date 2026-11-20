# -*- coding: utf-8 -*-
"""docs/228: 5年版「+月上位5」ポートフォリオの倍率スイープと、5年分の月次成績表(年×月グリッド)。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base, deployed_book as db
from forward.paper_forward import refresh_live, universe
from plusmonth_portfolio import rank, build, perf, END
A = pd.Timestamp("2021-10-01"); MULTS = [1.0, 2.36, 2.6, 2.95, 3.3, 3.6, 4.0, 4.5, 5.0]


def mc_full(daily, mult, rng):
    """静的DD−10%・日次−4%クリップで、5年系列そのものを流した場合の失格(=どこかで−10%到達)と最大DD。ブートストラップは mc_challenge。"""
    r = np.clip(daily.values * mult, -base.DAY_GUARD, None); eq = np.cumprod(1 + r); dd = eq / np.maximum.accumulate(eq) - 1
    return dict(hist_max_dd_pct=round(float(dd.min()) * 100, 2), hist_breach_10=bool(dd.min() <= -0.10), hist_worst_month_pct=round(float(pd.Series(r, index=daily.index).groupby(pd.PeriodIndex(daily.index, freq="M")).apply(lambda q: (1 + q).prod() - 1).min()) * 100, 2),
                **{f"mc_{k}": v for k, v in base.mc_challenge(daily, mult, rng).items() if k in ("p1_pass", "funded", "fail", "funded_days_med")})


def main():
    refresh_live(); rng = np.random.default_rng(7)
    series = {}
    for fam, sym in universe():
        s = db.leg_series(fam, sym); series[(fam, sym)] = s[s.index <= END]
    picks = rank(series, A, END); w, comp, mult, m_win, m_12 = build(series, picks, A, END)
    win = comp[(comp.index >= A) & (comp.index <= END)]; last12 = win[win.index >= END - pd.DateOffset(months=12)]
    print(f"構成: " + ", ".join(f"{k[0]} {k[1]} w={v:.3f}" for k, v in w.items()) + f"  校正倍率 {mult} (m*窓 {m_win} / m*12m {m_12})")
    print(f"×1 の最悪日 {win.min()*100:.2f}% / 最悪月 {perf(win,1)['worst_month_pct']}% / 最大DD {perf(win,1)['max_dd_pct']}%  → 日次−4%ガードに当たる倍率 = {0.04/abs(win.min()):.2f}")
    sweep = []
    for m in MULTS:
        full = mc_full(win, m, rng); l12 = base.mc_challenge(last12, m, rng)
        sweep.append(dict(mult=m, cagr_pct=round(((1 + perf(win, m)["total_pct"] / 100) ** (1 / 4.95) - 1) * 100, 1), **full, mc12_funded=l12["funded"], mc12_fail=l12["fail"], mc12_days=l12["funded_days_med"]))
        s = sweep[-1]; print(f"  ×{m:<4}: 年率 {s['cagr_pct']:+5.1f}%  5年最大DD {s['hist_max_dd_pct']:6.2f}%  最悪月 {s['hist_worst_month_pct']:6.2f}%  −10%到達 {s['hist_breach_10']}  MC5y 資金化 {s['mc_funded']}% 失格 {s['mc_fail']}%  MC12m 資金化 {s['mc12_funded']}% 失格 {s['mc12_fail']}%")
    # 月次グリッド
    grids = {}
    for m in (1.0, mult, 3.3):
        r = win * m; mon = r.groupby(pd.PeriodIndex(r.index, freq="M")).apply(lambda q: (1 + q).prod() - 1) * 100
        g = pd.DataFrame({"year": [p.year for p in mon.index], "month": [p.month for p in mon.index], "ret": mon.values}).pivot(index="year", columns="month", values="ret").round(2)
        g["年間"] = [round(((1 + r[r.index.year == y]).prod() - 1) * 100, 2) for y in g.index]
        eqy = (1 + r).cumprod(); g["年内最大DD"] = [round(float(((eqy[eqy.index.year == y] / eqy[eqy.index.year == y].cummax()) - 1).min()) * 100, 2) for y in g.index]
        grids[m] = g; g.to_csv(os.path.join(HERE, "results", f"plusmonth5y_track_x{m}.csv"))
        print(f"\n--- 月次(×{m}) ---"); print(g.to_string())
    json.dump(dict(weights={f"{k[0]} {k[1]}": round(v, 3) for k, v in w.items()}, mult_calibrated=mult, sweep=sweep), open(os.path.join(HERE, "results", "plusmonth5y_sweep.json"), "w"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__": main()
