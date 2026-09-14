# -*- coding: utf-8 -*-
"""docs/234: 第 4 弾 — Cowork 取得の H1 8 銘柄(CADJPY CHFJPY NZDJPY EURGBP EURAUD GBPAUD NAS100 XAUUSD)。データ末尾が 2025-12 のため
順位付け窓 2021-10〜2024-12(39 ヶ月)→ OOS 2025-01〜2025-12(12 ヶ月)。探索前 2016-01〜2021-09 も別途。第 3 段と同じセル定義。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base, plusmonth_search_h1 as H
H.A = pd.Timestamp("2016-01-01"); CUT = pd.Timestamp("2024-12-31 23:59"); END = pd.Timestamp("2025-12-31 23:59"); RANK0 = pd.Period("2021-10")
SYMS = ["CADJPY", "CHFJPY", "NZDJPY", "EURGBP", "EURAUD", "GBPAUD", "NAS100", "XAUUSD"]
H.IDX_COST.update({"XAUUSD": 3e-4, "NAS100": 3e-4})


def main():
    rows = []
    for sym in SYMS:
        df = H.load(sym); df = df[df.index <= END]
        for dow in range(5):
            for h0, span in H.WINS:
                for sh in (False, True):
                    s = H.cell(df, sym, dow, h0, span, sh); m = H.monthly(s)
                    pre = m[m.index < RANK0]; mi = m[(m.index >= RANK0) & (m.index <= CUT.to_period("M"))]; mo = m[m.index > CUT.to_period("M")]
                    if len(mi) < 30: continue
                    plus = int((mi > 0).sum()); p = sum(comb(len(mi), k) for k in range(plus, len(mi) + 1)) / 2 ** len(mi)
                    pp = int((pre > 0).sum()); ppv = (sum(comb(len(pre), k) for k in range(pp, len(pre) + 1)) / 2 ** len(pre)) if len(pre) >= 20 else np.nan
                    r_oos = s[(s.index > CUT) & (s.index <= END)]
                    rows.append(dict(cell=f"{H.DOW[dow]}{'S' if sh else ''} {sym} {h0:02d}-{(h0+span)%24:02d}UTC", family=f"{H.DOW[dow]}{'S' if sh else ''}", symbol=sym, h0=h0, span=span,
                                     plus_in=plus, n_in=len(mi), rate_in=round(plus / len(mi) * 100), p_binom=p, mean_m_in_pct=round(float(mi.mean()) * 100, 2), worst_m_in_pct=round(float(mi.min()) * 100, 2),
                                     plus_pre=pp, n_pre=len(pre), p_pre=ppv, plus_oos=int((mo > 0).sum()), n_oos=len(mo), cum_oos_pct=round(float((1 + r_oos).prod() - 1) * 100, 2)))
    df = pd.DataFrame(rows).sort_values(["plus_in", "rate_in", "mean_m_in_pct"], ascending=False)
    n = len(df); bonf = 0.05 / n; df["sig_bonf"] = df.p_binom < bonf; df["sig_005"] = df.p_binom < 0.05; df["pre_sig"] = df.p_pre < 0.05
    df.to_csv(os.path.join(HERE, "results", "plusmonth_search_h1_stage4.csv"), index=False); pd.set_option("display.width", 250)
    cols = ["cell", "plus_in", "n_in", "rate_in", "p_binom", "mean_m_in_pct", "worst_m_in_pct", "plus_pre", "n_pre", "p_pre", "plus_oos", "n_oos", "cum_oos_pct"]
    print(f"銘柄 {len(SYMS)} セル数 {n}  Bonferroni p<{bonf:.1e}  通過 {int(df.sig_bonf.sum())}  p<0.05 {int(df.sig_005.sum())}(偶然期待 {n*0.05:.0f})  順位窓かつ探索前とも p<0.05: {int((df.sig_005 & df.pre_sig).sum())}")
    print("\n== 上位 30"); print(df[cols].head(30).to_string(index=False))
    print("\n== Bonferroni 通過"); print(df[df.sig_bonf][cols].to_string(index=False))
    print("\n== 順位窓 p<0.05 かつ 探索前 p<0.05 かつ OOS>0"); q = df[df.sig_005 & df.pre_sig & (df.cum_oos_pct > 0)]; print(q[cols].to_string(index=False))
    g = df[df.sig_005].groupby("symbol"); print("\n== 銘柄別(p<0.05): n / OOS 正 / 探索前も有意"); print(pd.DataFrame({"n": g.size(), "oos_pos": g.apply(lambda x: int((x.cum_oos_pct > 0).sum())), "pre_sig": g.apply(lambda x: int(x.pre_sig.sum()))}))


if __name__ == "__main__": main()
