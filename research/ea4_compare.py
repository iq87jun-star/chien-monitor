# -*- coding: utf-8 -*-
"""docs/238: 4 本の EA 候補を同じ枠組みで比較。2021-10〜2025-12(共通末尾)・Sess 往復 2pip/3pip・逆ボラ加重・倍率校正 0.8×min(m*窓,m*12m)上限6・MC(FN Stellar)。
EA1 Sess 上位5 ×4.8(v1.11) / EA2 A+B 50/50 ×3.3(docs/237) / EA3 A 5年版 ×3.3(docs/228) / EA4 Sess 8本(S1〜S8)×校正。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base, deployed_book as db, plusmonth_search_h1 as H
from forward.paper_forward import refresh_live
from plusmonth_portfolio import perf
from sess_top5_portfolio import daily
A0, CUT, END = pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31"), pd.Timestamp("2025-12-31")
S5 = [("EURGBP 20-00S", "EURGBP", 20, 4), ("NZDUSD 20-00S", "NZDUSD", 20, 4), ("AUDUSD 20-00S", "AUDUSD", 20, 4), ("EURGBP 16-20S", "EURGBP", 16, 4), ("USDCHF 00-04S", "USDCHF", 0, 4)]
S8 = S5 + [("USDCHF 16-20S", "USDCHF", 16, 4), ("NZDUSD 16-20S", "NZDUSD", 16, 4), ("CHFJPY 20-00S", "CHFJPY", 20, 4)]
WA = {("Mon", "GBPJPY"): 0.222, ("Mon", "EURJPY"): 0.231, ("Mon", "AUDJPY"): 0.186, ("Mon", "USDJPY"): 0.223, ("Hold", "UK100"): 0.138}


def comp(S, w):
    idx = sorted(set().union(*[set(S[k].index) for k in w])); c = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, v in w.items(): c = c.add(S[k].reindex(c.index).fillna(0) * v, fill_value=0)
    return c[(c.index >= A0) & (c.index <= END)]


def invvol(S, keys):
    iv = {k: 1 / S[k][(S[k].index >= A0) & (S[k].index <= END)].std() for k in keys}; t = sum(iv.values()); w = {k: v / t for k, v in iv.items()}
    w = {k: min(v, base.W_CAP) for k, v in w.items()}; t2 = sum(w.values()); return {k: v / t2 for k, v in w.items()}


def calib(c): return min(base.calibrate(c), base.calibrate(c[c.index >= c.index.max() - pd.DateOffset(months=12)]), 6.0)


def main():
    refresh_live(); rng = np.random.default_rng(7); SA = {k: db.leg_series(*k) for k in WA}; cA = comp(SA, WA); out = {}; tracks = {}
    for cost in (3, 2):
        H.A = pd.Timestamp("2021-09-25"); SB = {k: daily(sym, h0, span, cost) for k, sym, h0, span in S8}
        cB5 = comp(SB, invvol(SB, [k for k, *_ in S5])); cB8 = comp(SB, invvol(SB, [k for k, *_ in S8]))
        idx = cA.index.union(cB5.index).union(cB8.index); a, b5, b8 = (x.reindex(idx).fillna(0) for x in (cA, cB5, cB8))
        eas = {"EA1 Sess上位5 ×4.8": (b5, 4.8), "EA2 A+B 50/50 ×3.3": (0.5 * a + 0.5 * b5, 3.3), "EA3 A 5年版 ×3.3": (a, 3.3), "EA4 Sess 8本 ×校正": (b8, None)}
        print(f"\n=== Sess コスト {cost}pip ===")
        for name, (c, m) in eas.items():
            mult = m if m else calib(c); p = perf(c, mult); mc = base.mc_challenge(c[c.index >= END - pd.DateOffset(months=12)], mult, rng)
            win = c[c.index <= CUT]; mb = min(base.calibrate(win), base.calibrate(win[win.index >= CUT - pd.DateOffset(months=12)]), 6.0) if m is None else m
            oos = c[c.index > CUT]; po = perf(oos, mb); mco = base.mc_challenge(oos, mb, rng)
            cagr = ((1 + p["total_pct"] / 100) ** (1 / 4.25) - 1) * 100
            out[f"{name}|{cost}pip"] = dict(mult=mult, cagr=round(cagr, 1), **{k: v for k, v in p.items() if k != "by_year_pct"}, by_year=p["by_year_pct"], mc=mc, wf=dict(mult=mb, **{k: v for k, v in po.items() if k != "by_year_pct"}, mc=mco))
            print(f"  {name:22s} ×{mult:<4} 年率 {cagr:+5.1f}% 年別 {p['by_year_pct']} 最大DD {p['max_dd_pct']:6.2f} 最悪日 {p['worst_day_pct']:6.2f} 最悪月 {p['worst_month_pct']:6.2f} +月 {p['plus_months']} Sharpe {p['sharpe_act']:4.2f} | MC12m {mc['funded']}%/{mc['fail']}% | WF2025 ×{mb} {po['total_pct']:+5.1f}% DD {po['max_dd_pct']:5.2f} +月 {po['plus_months']} MC {mco['funded']}%/{mco['fail']}%")
            if cost == 3:
                r = c * mult; mon = r.groupby(pd.PeriodIndex(r.index, freq="M")).apply(lambda q: (1 + q).prod() - 1) * 100
                tracks[name] = mon
        if cost == 3:
            T = pd.DataFrame(tracks).round(2); T.index = T.index.astype(str); T.to_csv(os.path.join(HERE, "results", "ea4_compare_monthly_3pip.csv"))
            Y = pd.DataFrame({n: {y: round(((1 + t[t.index.year == y] / 100).prod() - 1) * 100, 1) for y in range(2021, 2026)} for n, t in tracks.items()}); print("\n年別(3pip・%):\n", Y.to_string())
    json.dump(out, open(os.path.join(HERE, "results", "ea4_compare.json"), "w"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__": main()
