# -*- coding: utf-8 -*-
"""docs/233: 探索 第 3 段 — Dukascopy H1 の時間帯セル。曜日(月〜金)× 窓(4h × 6・8h × 3)× LONG/SHORT。
リターン = 窓始値 → 窓終値(次バー始値)。コスト = 往復 2pip(FX)/ IDX_COST。順位付け 2021-10〜2025-08(47ヶ月)→ OOS 2025-09〜2026-08(12ヶ月)。
既知(Mon 4/6/8/10 UTC 24h 系)と重なる「月曜 LONG」は除外せず表示するが known 列で区別。"""
import os, sys, glob, gzip, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]; WINS = [(h, 4) for h in (0, 4, 8, 12, 16, 20)] + [(h, 8) for h in (0, 8, 16)]
A, CUT, END = pd.Timestamp("2021-10-01"), pd.Timestamp("2025-08-31 23:59"), pd.Timestamp("2026-08-31 23:59")
IDX_COST = dict(base.IDX_COST); IDX_COST.update({"WTI": 5e-4})


def load(sym):
    df = pd.read_csv(f"data_dukascopy/{sym}_hour.csv.gz"); df["t"] = pd.to_datetime(df["timestamp"]); df = df.set_index("t").sort_index()
    df = df[(df.high > df.low) | (df.volume > 0)]                      # 休場の埋めバーを除く
    return df[(df.index >= A - pd.Timedelta(days=3)) & (df.index <= END)]


def cell(df, sym, dow, h0, span, short):
    o = df["open"]; d = df[(df.index.dayofweek == dow) & (df.index.hour == h0)]
    t_end = d.index + pd.Timedelta(hours=span)
    o_end = o.reindex(t_end); ok = ~o_end.isna().values
    r = pd.Series(o_end.values[ok] / d["open"].values[ok] - 1, index=d.index[ok])
    c = IDX_COST.get(sym) or (2 * base.pip_size(sym) / d["open"].values[ok])
    r = (-r if short else r) - c; return base.clip(r)   # 2026-09-18 修正(docs/249): 方向を先に決めてからコストを引く。旧: r-c の後に符号反転 → SHORT にコストが加算されていた


def verify_cost_sign(df, sym):
    """docs/249: 同一窓の LONG + SHORT = −2×コスト であることを検証(SHORT にコストが加算されていないか)。"""
    l = cell(df, sym, 1, 20, 4, False); s = cell(df, sym, 1, 20, 4, True); z = (l + s).dropna()
    if len(z) and float(z.max()) > 0: raise RuntimeError(f"[COST SIGN] {sym}: LONG+SHORT が正({float(z.max()):.2e})。SHORT のコスト符号を確認")


def monthly(s): m = s.groupby(pd.PeriodIndex(s.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); return m[m != 0]


def main():
    syms = sorted(os.path.basename(f).replace("_hour.csv.gz", "") for f in glob.glob("data_dukascopy/*_hour.csv.gz")); rows = []
    for sym in syms:
        df = load(sym)
        if len(df) < 1000: print("skip", sym); continue
        verify_cost_sign(df, sym)
        for dow in range(5):
            for h0, span in WINS:
                for sh in (False, True):
                    s = cell(df, sym, dow, h0, span, sh); m = monthly(s)
                    mi = m[m.index <= CUT.to_period("M")]; mo = m[m.index > CUT.to_period("M")]
                    if len(mi) < 40: continue
                    plus = int((mi > 0).sum()); p = sum(comb(len(mi), k) for k in range(plus, len(mi) + 1)) / 2 ** len(mi)
                    r_in = s[s.index <= CUT]; r_oos = s[s.index > CUT]
                    known = (dow == 0 and not sh and h0 in (4, 8) and span in (4, 8))
                    rows.append(dict(cell=f"{DOW[dow]}{'S' if sh else ''} {sym} {h0:02d}-{(h0+span)%24:02d}UTC", family=f"{DOW[dow]}{'S' if sh else ''}", symbol=sym, h0=h0, span=span, known=known,
                                     plus_in=plus, n_in=len(mi), rate_in=round(plus / len(mi) * 100), p_binom=p, mean_m_in_pct=round(float(mi.mean()) * 100, 2),
                                     cum_in_pct=round(float((1 + r_in).prod() - 1) * 100, 1), worst_m_in_pct=round(float(mi.min()) * 100, 2),
                                     plus_oos=int((mo > 0).sum()), n_oos=len(mo), cum_oos_pct=round(float((1 + r_oos).prod() - 1) * 100, 2)))
    df = pd.DataFrame(rows).sort_values(["plus_in", "rate_in", "mean_m_in_pct"], ascending=False)
    n = len(df); bonf = 0.05 / n; df["sig_bonf"] = df.p_binom < bonf; df["sig_005"] = df.p_binom < 0.05
    df.to_csv(os.path.join(HERE, "results", "plusmonth_search_h1.csv"), index=False); pd.set_option("display.width", 250)
    cols = ["cell", "known", "plus_in", "n_in", "rate_in", "p_binom", "mean_m_in_pct", "cum_in_pct", "worst_m_in_pct", "plus_oos", "n_oos", "cum_oos_pct"]
    print(f"銘柄 {len(syms)} セル数 {n}  Bonferroni p<{bonf:.1e}  通過 {int(df.sig_bonf.sum())}  p<0.05 {int(df.sig_005.sum())}(偶然期待 {n*0.05:.0f})")
    print("\n== 上位 30"); print(df[cols].head(30).to_string(index=False))
    print("\n== Bonferroni 通過"); print(df[df.sig_bonf][cols].to_string(index=False))
    g = df[df.sig_005].groupby("family"); print("\n== 族別(p<0.05): n / OOS正 / OOS平均"); print(pd.DataFrame({"n": g.size(), "oos_pos": g.apply(lambda x: int((x.cum_oos_pct > 0).sum())), "oos_mean": g.cum_oos_pct.mean().round(2)}))


if __name__ == "__main__": main()
