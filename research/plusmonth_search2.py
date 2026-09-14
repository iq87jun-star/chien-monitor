# -*- coding: utf-8 -*-
"""docs/232: 探索の第 2 段(docs/229 の拡張)。セル型を増やす: 曜日 o2o × 保有 1/2/3 日 × LONG/SHORT、月替わり(TOM: 月末 2 営業日 + 月初 3 営業日)LONG/SHORT。
同じ枠組み(順位付け 2021-10〜2025-09 の +月数 → OOS 2025-10〜2026-09・二項 p・Bonferroni)。既知セルと docs/229 候補は除外して報告。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base
from forward.paper_forward import refresh_live
from plusmonth_search import A, CUT, END, DOW, NEW
base.YAHOO.update(NEW); base.IDX_COST.update({"US30": 3e-4, "US2000": 4e-4, "HK50": 4e-4, "AUS200": 4e-4, "EUSTX50": 4e-4, "XAGUSD": 5e-4, "WTI": 5e-4})
SYMS = list(base.YAHOO.keys())
KNOWN = {("Mon", s, 1) for s in SYMS} | {("MonS", "EURGBP", 1), ("FriS", "NZDUSD", 1), ("WedS", "CADCHF", 1), ("TueS", "CADCHF", 1), ("Thu", "XAUUSD", 1), ("ThuS", "USDCHF", 1)}


def cost_of(df, nm): return base.IDX_COST.get(nm) or (2 * base.pip_size(nm) / df["open"])


def dow_hold(df, nm, dow, hold, short):
    o = df["open"]; fwd = o.shift(-hold) / o - 1                      # 当日始値 → hold 営業日後の始値
    s = (fwd[df["weekday"] == dow] - cost_of(df, nm)).dropna(); return base.clip(-s if short else s)


def tom(df, nm, short):
    o = df["open"]; idx = df.index; mk = pd.PeriodIndex(idx, freq="M")
    pos_in = pd.Series(np.arange(len(idx)), index=idx).groupby(mk).rank(method="first")            # 月内の営業日順位(1..)
    n_in = pd.Series(np.arange(len(idx)), index=idx).groupby(mk).transform("count")
    ent = (pos_in == n_in - 1)                                                                     # 月末 2 営業日目の始値で建て
    r = (o.shift(-5) / o - 1)[ent]                                                                  # 5 営業日後(月初 3 日目)の始値で決済
    s = (r - cost_of(df, nm)).dropna(); return base.clip(-s if short else s)


def monthly(s): m = s.groupby(pd.PeriodIndex(s.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); return m[m != 0]


def main():
    refresh_live(); rows = []
    for nm in SYMS:
        try: df = base.load_daily(nm)
        except Exception as e: print("skip", nm, str(e)[:50]); continue
        cells = [(f"{DOW[d]}{'S' if sh else ''}{'' if h == 1 else f'x{h}'}", (lambda d=d, h=h, sh=sh: dow_hold(df, nm, d, h, sh)), (DOW[d] + ('S' if sh else ''), nm, h))
                 for d in range(5) for h in (1, 2, 3) for sh in (False, True)]
        cells += [("TOM", lambda: tom(df, nm, False), ("TOM", nm, 5)), ("TOMS", lambda: tom(df, nm, True), ("TOMS", nm, 5))]
        for fam, fn, key in cells:
            if key in KNOWN: continue
            try: s = fn()
            except Exception: continue
            s = s[(s.index >= A) & (s.index <= END)]; m = monthly(s); mi = m[m.index <= CUT.to_period("M")]; mo = m[m.index > CUT.to_period("M")]
            if len(mi) < 40: continue
            plus = int((mi > 0).sum()); p = sum(comb(len(mi), k) for k in range(plus, len(mi) + 1)) / 2 ** len(mi)
            r_in = s[s.index <= CUT]; r_oos = s[s.index > CUT]
            rows.append(dict(cell=f"{fam} {nm}", family=fam, symbol=nm, plus_in=plus, n_in=len(mi), rate_in=round(plus / len(mi) * 100), p_binom=p,
                             mean_m_in_pct=round(float(mi.mean()) * 100, 2), cum_in_pct=round(float((1 + r_in).prod() - 1) * 100, 1), worst_m_in_pct=round(float(mi.min()) * 100, 2),
                             plus_oos=int((mo > 0).sum()), n_oos=len(mo), cum_oos_pct=round(float((1 + r_oos).prod() - 1) * 100, 2)))
    df = pd.DataFrame(rows).sort_values(["plus_in", "rate_in", "mean_m_in_pct"], ascending=False)
    n = len(df); bonf = 0.05 / n; df["sig_bonf"] = df.p_binom < bonf; df["sig_005"] = df.p_binom < 0.05
    df.to_csv(os.path.join(HERE, "results", "plusmonth_search2.csv"), index=False)
    pd.set_option("display.width", 250)
    cols = ["cell", "plus_in", "n_in", "rate_in", "p_binom", "mean_m_in_pct", "cum_in_pct", "worst_m_in_pct", "plus_oos", "n_oos", "cum_oos_pct"]
    print(f"セル数 {n}  Bonferroni p<{bonf:.1e}  通過 {int(df.sig_bonf.sum())}  p<0.05 {int(df.sig_005.sum())}(偶然期待 {n*0.05:.0f})")
    print("\n== 上位 30"); print(df[cols].head(30).to_string(index=False))
    print("\n== 族別: p<0.05 の本数 / OOS 正の本数"); g = df[df.sig_005].groupby(df.family.str.replace(r"[A-Z][a-z]{2}", "DOW", regex=True)); print(pd.DataFrame({"n": g.size(), "oos_pos": g.apply(lambda x: int((x.cum_oos_pct > 0).sum())), "oos_mean": g.cum_oos_pct.mean().round(2)}))


if __name__ == "__main__": main()
