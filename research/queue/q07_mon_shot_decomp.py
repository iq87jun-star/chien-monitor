# -*- coding: utf-8 -*-
"""docs/244 Q7: Mon 円クロスのショット分解。月曜 4/6/8/10 UTC の各ショット(LONG)× 出口 {24h, 12h, 20h} × 7 円クロス = 84 セル(改良系・診断)。
問い: 配備中の Mon 4 ショット(4/6/8/10 UTC・24h 保有)のどのショットがエッジを担っているか。出口を短くして改善するか。
H1 Dukascopy・始値→出口時刻の始値・往復 2pip(docs/216 の Mon 標準)。窓: 前窓 2016-01〜2021-09 / IS 2021-10〜2024-12 / OOS 2025-01〜末尾。
自己検証: 同一セルの LONG + SHORT = −2×コスト(docs/249)。research/ で実行。"""
import os, numpy as np, pandas as pd
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT)
SYMS = ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY", "CADJPY", "CHFJPY", "NZDJPY"]; SHOTS = (4, 6, 8, 10); EXITS = (24, 12, 20)
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31 23:00"), pd.Timestamp("2025-01-01")
def load(sym):
    df = pd.read_csv(f"data_dukascopy/{sym}_hour.csv.gz"); df["t"] = pd.to_datetime(df["timestamp"]); df = df.set_index("t").sort_index()
    return df[((df.high > df.low) | (df.volume > 0)) & (df.index >= PRE0)]
def cell(df, h0, hold, short=False):
    o = df["open"]; d = df[(df.index.dayofweek == 0) & (df.index.hour == h0)]
    oe = o.reindex(d.index + pd.Timedelta(hours=hold)); ok = ~oe.isna().values
    r = oe.values[ok] / d["open"].values[ok] - 1.0; c = 2 * 0.01 / d["open"].values[ok]
    return pd.Series((-r if short else r) - c, index=d.index[ok])
def pb(m): n = len(m); k = int((m > 0).sum()); return k, n, (sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n if n else 1.0)
def st(r, a, b):
    x = r[(r.index >= a) & (r.index <= b)]
    if len(x) == 0: return dict(n=0)
    m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); k, n, p = pb(m)
    return dict(n=n, plus=k, rate=round(k / n, 3), mean_bps=round(float(x.mean()) * 1e4, 1), p=p, sharpe=round(float(x.mean() / x.std() * np.sqrt(52)), 2) if x.std() > 0 else np.nan)
rows = []
for sym in SYMS:
    df = load(sym)
    l, s = cell(df, 4, 24, False), cell(df, 4, 24, True); z = (l + s).dropna()
    assert float(z.max()) <= 0, f"[COST SIGN] {sym}"           # docs/249 自己検証
    for h0 in SHOTS:
        for hold in EXITS:
            r = cell(df, h0, hold); sp, si, so = st(r, PRE0, IS0 - pd.Timedelta(hours=1)), st(r, IS0, IS1), st(r, OOS0, pd.Timestamp("2026-12-31"))
            rows.append(dict(symbol=sym, shot_utc=h0, hold_h=hold, pre_rate=sp.get("rate"), pre_mean=sp.get("mean_bps"), is_plus=si.get("plus"), is_n=si.get("n"), is_rate=si.get("rate"), is_mean=si.get("mean_bps"), is_sharpe=si.get("sharpe"), is_p=si.get("p"),
                             oos_plus=so.get("plus"), oos_n=so.get("n"), oos_mean=so.get("mean_bps"), oos_sharpe=so.get("sharpe")))
R = pd.DataFrame(rows); R.to_csv("results/q7_mon_shot_decomp.csv", index=False); pd.set_option("display.width", 250)
print("== 配備 4 銘柄(GBPJPY/EURJPY/AUDJPY/USDJPY)× 24h: ショット別"); print(R[(R.hold_h == 24) & R.symbol.isin(["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"])].to_string(index=False))
print("\n== ショット × 出口の平均(7 銘柄・bps/週)"); print(R.pivot_table(index="shot_utc", columns="hold_h", values=["is_mean", "oos_mean", "pre_mean"]).round(1).to_string())
print("\n== IS Sharpe 上位 10"); print(R.sort_values("is_sharpe", ascending=False).head(10).to_string(index=False))
