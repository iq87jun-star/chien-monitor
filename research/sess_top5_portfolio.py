# -*- coding: utf-8 -*-
"""docs/235: 5年勝率上位5(全て時間帯セル)をポートフォリオにした場合。逆ボラ加重 cap40%・倍率校正 0.8×min(m*窓,m*12m)・MC(FN Stellar)。
コスト往復 2pip / 3pip。スワップ未反映(EURGBP は受取・NZD/AUD ≈ 0 なので保守側)。データ共通末尾 2025-12-31。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base, plusmonth_search_h1 as H
from plusmonth_portfolio import perf
H.A = pd.Timestamp("2021-09-25"); A = pd.Timestamp("2021-10-01"); CUT = pd.Timestamp("2024-12-31 23:59"); END = pd.Timestamp("2025-12-31 23:59")
TOP5 = [("EURGBP 20-00S", "EURGBP", 20, 4), ("NZDUSD 20-00S", "NZDUSD", 20, 4), ("AUDUSD 20-00S", "AUDUSD", 20, 4), ("EURGBP 16-20S", "EURGBP", 16, 4), ("USDCHF 00-04S", "USDCHF", 0, 4)]


def daily(sym, h0, span, cost):
    df = H.load(sym); df = df[df.index <= END]; pip = base.pip_size(sym); parts = []
    for d in range(4):
        r = H.cell(df, sym, d, h0, span, True); r = r - (cost - 2) * pip / df["open"].reindex(r.index).values; parts.append(r)
    s = pd.concat(parts).sort_index(); s.index = s.index.normalize(); return s.groupby(level=0).sum()


def build(S, keys, a, b):
    iv = {k: 1.0 / float(S[k][(S[k].index >= a) & (S[k].index <= b)].std()) for k in keys}; t = sum(iv.values()); w = {k: v / t for k, v in iv.items()}
    w = {k: min(v, base.W_CAP) for k, v in w.items()}; t2 = sum(w.values()); w = {k: v / t2 for k, v in w.items()}
    idx = sorted(set().union(*[set(S[k].index) for k in keys])); comp = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, v in w.items(): comp = comp.add(S[k].reindex(comp.index).fillna(0) * v, fill_value=0)
    win = comp[(comp.index >= a) & (comp.index <= b)]; m_win = base.calibrate(win); m_12 = base.calibrate(win[win.index >= b - pd.DateOffset(months=12)])
    return w, comp, min(m_win, m_12, 6.0), m_win, m_12


def main():
    rng = np.random.default_rng(7); out = {}
    for cost in (2, 3):
        S = {k: daily(sym, h0, span, cost) for k, sym, h0, span in TOP5}
        M = pd.DataFrame({k: S[k].groupby(pd.PeriodIndex(S[k].index, freq="M")).apply(lambda q: (1 + q).prod() - 1) for k in S}).fillna(0)
        if cost == 2: print("月次相関:\n", M.corr().round(2).to_string())
        w, comp, mult, mw, m12 = build(S, list(S), A, END); win = comp[(comp.index >= A) & (comp.index <= END)]
        print(f"\n=== 往復 {cost}pip: 加重 {[(k, round(v, 3)) for k, v in w.items()]}  校正倍率 {mult} (m*窓 {mw} / m*12m {m12})")
        res = {}
        for m in (1.0, mult, 3.3, 4.8):
            p = perf(win, m); mc = base.mc_challenge(win[win.index >= END - pd.DateOffset(months=12)], m, rng)
            res[m] = dict(**p, mc=mc); print(f"  ×{m:<4}: 累積 {p['total_pct']:+6.1f}% 年率 {((1+p['total_pct']/100)**(1/4.25)-1)*100:+5.1f}% 年別 {p['by_year_pct']} 最大DD {p['max_dd_pct']} 最悪日 {p['worst_day_pct']} 最悪月 {p['worst_month_pct']} +月 {p['plus_months']} Sharpe {p['sharpe_act']} | MC12m 資金化 {mc['funded']}% 失格 {mc['fail']}%")
        # walk-forward: 2024-12 で加重・校正 → 2025
        wb, cb, mb, _, _ = build(S, list(S), A, CUT); oos = cb[(cb.index > CUT) & (cb.index <= END)]; po = perf(oos, mb); mco = base.mc_challenge(oos, mb, rng)
        print(f"  walk-forward(2024-12 締め・倍率 {mb}): OOS 2025 {po['total_pct']:+.2f}% 最大DD {po['max_dd_pct']} 最悪月 {po['worst_month_pct']} +月 {po['plus_months']} Sharpe {po['sharpe_act']} | MC 資金化 {mco['funded']}% 失格 {mco['fail']}%")
        out[f"cost{cost}"] = dict(weights=w, mult=mult, in_sample={str(k): v for k, v in res.items()}, walk_forward=dict(mult=mb, perf=po, mc=mco))
        if cost == 2:
            r = win * mult; mon = r.groupby(pd.PeriodIndex(r.index, freq="M")).apply(lambda q: (1 + q).prod() - 1) * 100
            g = pd.DataFrame({"year": [p.year for p in mon.index], "month": [p.month for p in mon.index], "ret": mon.values}).pivot(index="year", columns="month", values="ret").round(2)
            g["年間"] = [round(((1 + r[r.index.year == y]).prod() - 1) * 100, 2) for y in g.index]; g.to_csv(os.path.join(HERE, "results", "sess_top5_track.csv")); print("\n月次(×校正倍率):\n", g.to_string())
    json.dump(out, open(os.path.join(HERE, "results", "sess_top5_portfolio.json"), "w"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__": main()
