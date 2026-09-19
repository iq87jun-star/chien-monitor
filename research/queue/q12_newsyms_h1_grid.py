# -*- coding: utf-8 -*-
"""docs/255: 新銘柄(Dukascopy 取得分・manifest で complete の bid)に第 3 段の時間帯格子(9 窓 × L/S × 月〜金 = 90 セル/銘柄)を正しい符号で適用。
コスト: FX 往復 3pip(docs/244 §1)。窓: 前窓 2016-01〜2021-09 / IS 2021-10〜2024-12 / OOS 2025-01〜末尾。判定: 二項 p(IS +月数)< 0.05/(累積+今回)、IS 月数 ≥ 24、OOS 平均 > 0、前窓 +月率 ≥ 50%。
使い方: python3 queue/q12_newsyms_h1_grid.py <累積セル数> [SYM ...](省略時は manifest の complete かつ既存 19 銘柄以外)。research/ で実行。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT)
import recentfit_screen as base
OLD = {"AUDJPY", "AUDUSD", "CADJPY", "CHFJPY", "EURAUD", "EURGBP", "EURJPY", "EURUSD", "GBPAUD", "GBPJPY", "GBPUSD", "NZDJPY", "NZDUSD", "USDCHF", "USDJPY", "XAUUSD", "GER40", "NAS100", "US500"}
cum = int(sys.argv[1]); syms = sys.argv[2:]
if not syms:
    m = json.load(open("data_dukascopy/manifest.json")); syms = sorted(k.split("|")[0] for k, v in m.items() if k.endswith("|bid") and v.get("complete") and k.split("|")[0] not in OLD)
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]; WINS = [(h, 4) for h in (0, 4, 8, 12, 16, 20)] + [(h, 8) for h in (0, 8, 16)]
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31 23:00"), pd.Timestamp("2025-01-01")
N = len(syms) * 90; ALPHA = 0.05 / (cum + N)
def load(sym):
    df = pd.read_csv(f"data_dukascopy/{sym}_hour.csv.gz"); df["t"] = pd.to_datetime(df["timestamp"]); df = df.set_index("t").sort_index()
    return df[((df.high > df.low) | (df.volume > 0)) & (df.index >= PRE0)]
def cost(sym, px): return (5e-4 if sym in ("XAUUSD", "XAGUSD") else base.IDX_COST.get(sym, None)) or 3 * base.pip_size(sym) / px
def cell(df, sym, dow, h0, span, short):
    o = df["open"]; d = df[(df.index.dayofweek == dow) & (df.index.hour == h0)]
    oe = o.reindex(d.index + pd.Timedelta(hours=span)); ok = ~oe.isna().values; px = d["open"].values[ok]
    r = oe.values[ok] / px - 1.0; c = cost(sym, px); return pd.Series((-r if short else r) - c, index=d.index[ok])
def pb(m): n = len(m); k = int((m > 0).sum()); return k, n, (sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n if n else 1.0)
def st(r, a, b):
    x = r[(r.index >= a) & (r.index <= b)]
    if len(x) == 0: return dict(n=0, plus=0, rate=np.nan, mean=np.nan, p=1.0)
    mm = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); k, n, p = pb(mm)
    return dict(n=n, plus=k, rate=round(k / n, 3), mean=round(float(x.mean()) * 1e4, 2), p=p)
rows = []
for sym in syms:
    df = load(sym)
    l, s = cell(df, sym, 1, 20, 4, False), cell(df, sym, 1, 20, 4, True); z = (l + s).dropna(); assert float(z.max()) <= 1e-12, f"[COST SIGN] {sym}"
    for dow in range(5):
        for h0, span in WINS:
            for sh in (False, True):
                r = cell(df, sym, dow, h0, span, sh); sp, si, so = st(r, PRE0, IS0), st(r, IS0, IS1), st(r, OOS0, pd.Timestamp("2026-12-31"))
                gross = float((r + cost(sym, df["open"].reindex(r.index).values))[(r.index >= IS0) & (r.index <= IS1)].mean() * 1e4) if len(r) else np.nan
                passed = si["p"] < ALPHA and si["n"] >= 24 and so["n"] > 0 and so["mean"] > 0 and sp["n"] > 0 and sp["rate"] >= 0.5
                rows.append(dict(cell=f"{DOW[dow]}{'S' if sh else ''} {sym} {h0:02d}-{(h0+span)%24:02d}UTC", symbol=sym, is_plus=si["plus"], is_n=si["n"], is_rate=si["rate"], is_gross_bps=round(gross, 2), is_net_bps=si["mean"], p=si["p"], oos_plus=so["plus"], oos_n=so["n"], oos_net_bps=so["mean"], pre_rate=sp["rate"], passed=passed))
R = pd.DataFrame(rows).sort_values("p"); R.to_csv("results/q12_newsyms_h1_grid.csv", index=False); pd.set_option("display.width", 220)
print(f"syms={syms} cells={N} cum_before={cum} alpha={ALPHA:.2e} passed={int(R.passed.sum())} p<0.05={int((R.p<0.05).sum())}(期待 {N*0.05:.0f})")
print(R.head(12).to_string(index=False)); print("\n-- passed --"); print(R[R.passed].to_string(index=False) if R.passed.any() else "(none)")
