# -*- coding: utf-8 -*-
"""docs/229: 「+月数 × 5年 × walk-forward」の条件で、拡張ユニバース(銘柄 40 × 曜日o2o LONG/SHORT 10 + Hold LONG)から新しい銘柄×手法を探す。
順位付け窓 2021-10〜2025-09(48ヶ月)→ サンプル外 2025-10〜2026-09(12ヶ月)。二項検定(片側・p=0.5)で有意性、Bonferroni で多重比較補正。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base, deployed_book as db
from forward.paper_forward import refresh_live, universe
A, CUT, END = pd.Timestamp("2021-10-01"), pd.Timestamp("2025-09-30"), pd.Timestamp("2026-09-13")
NEW = {"EURGBP": "EURGBP=X", "EURCHF": "EURCHF=X", "EURAUD": "EURAUD=X", "EURCAD": "EURCAD=X", "GBPAUD": "GBPAUD=X", "GBPCAD": "GBPCAD=X", "GBPCHF": "GBPCHF=X",
       "AUDNZD": "AUDNZD=X", "AUDCAD": "AUDCAD=X", "NZDCAD": "NZDCAD=X", "CADCHF": "CADCHF=X", "AUDCHF": "AUDCHF=X",
       "US30": "^DJI", "US2000": "^RUT", "HK50": "^HSI", "AUS200": "^AXJO", "EUSTX50": "^STOXX50E", "XAGUSD": "SI=F", "WTI": "CL=F"}
base.YAHOO.update(NEW); base.IDX_COST.update({"US30": 3e-4, "US2000": 4e-4, "HK50": 4e-4, "AUS200": 4e-4, "EUSTX50": 4e-4, "XAGUSD": 5e-4, "WTI": 5e-4})
SYMS = list(dict.fromkeys(list(base.YAHOO.keys())))
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def dow_cell(nm, dow, short):
    df = base.load_daily(nm); c = base.IDX_COST.get(nm) or (2 * base.pip_size(nm) / df["open"])
    s = (df[df["weekday"] == dow]["o2o"] - c).dropna(); return base.clip(-s if short else s)


def monthly(s): m = s.groupby(pd.PeriodIndex(s.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); return m[m != 0]


def main():
    refresh_live(); known = {f"{f} {s}" for f, s in universe()}; rows = []
    for nm in SYMS:
        try: base.load_daily(nm)
        except Exception as e: print("skip", nm, str(e)[:60]); continue
        cells = [(f"{DOW[d]}{'S' if sh else ''}", lambda n=nm, d=d, sh=sh: dow_cell(n, d, sh)) for d in range(5) for sh in (False, True)] + [("Hold", lambda n=nm: base.hold_cell(n))]
        for fam, fn in cells:
            try: s = fn()
            except Exception: continue
            s = s[(s.index >= A) & (s.index <= END)]; m = monthly(s)
            mi = m[m.index <= CUT.to_period("M")]; mo = m[m.index > CUT.to_period("M")]
            if len(mi) < 40: continue
            plus = int((mi > 0).sum()); p = sum(comb(len(mi), k) for k in range(plus, len(mi) + 1)) / 2 ** len(mi)
            r_in = s[s.index <= CUT]; r_oos = s[s.index > CUT]
            rows.append(dict(cell=f"{fam} {nm}", family=fam, symbol=nm, known=(f"{'Mon' if fam=='Mon' else fam} {nm}" in known),
                             plus_in=plus, n_in=len(mi), rate_in=round(plus / len(mi) * 100), p_binom=p, cum_in_pct=round(float((1 + r_in).prod() - 1) * 100, 1),
                             mean_m_in_pct=round(float(mi.mean()) * 100, 2), plus_oos=int((mo > 0).sum()), n_oos=len(mo), cum_oos_pct=round(float((1 + r_oos).prod() - 1) * 100, 2),
                             worst_m_in_pct=round(float(mi.min()) * 100, 2), maxdd_in_pct=round(float(((1 + r_in).cumprod() / (1 + r_in).cumprod().cummax() - 1).min()) * 100, 2)))
    df = pd.DataFrame(rows).sort_values(["plus_in", "rate_in", "mean_m_in_pct"], ascending=False)
    n_cells = len(df); bonf = 0.05 / n_cells
    df["sig_005"] = df.p_binom < 0.05; df["sig_bonf"] = df.p_binom < bonf
    out = os.path.join(HERE, "results", "plusmonth_search.csv"); df.to_csv(out, index=False)
    print(f"セル数 {n_cells}(銘柄 {df.symbol.nunique()})  Bonferroni 閾値 p<{bonf:.2e}  → 必要 +月 ≈ {min(df[df.sig_bonf].plus_in) if df.sig_bonf.any() else 'n/a'}/48")
    pd.set_option("display.width", 250)
    cols = ["cell", "known", "plus_in", "n_in", "rate_in", "p_binom", "mean_m_in_pct", "cum_in_pct", "worst_m_in_pct", "maxdd_in_pct", "plus_oos", "n_oos", "cum_oos_pct"]
    print("\n== 上位 25(順位付け窓 48ヶ月の +月数)"); print(df[cols].head(25).to_string(index=False))
    new = df[(~df.known) & df.sig_005]
    print(f"\n== 既知でない × p<0.05: {len(new)} 本(うち Bonferroni 通過 {int(new.sig_bonf.sum())})"); print(new[cols].head(20).to_string(index=False))
    print("\n== 既知セルの位置"); print(df[df.known][cols].head(12).to_string(index=False))


if __name__ == "__main__": main()
