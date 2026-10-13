# -*- coding: utf-8 -*-
"""Q145(新規 25 セル・結果前に固定): データ未取得だった 25 銘柄に、配備中の 2 族を同形で当てる。
非指数: Mon4 形(月曜 4/6/8/10 UTC 建て・各 24h・4 ショット平均)。向き = リスクを取る側(金属・暗号資産・SGDJPY は LONG、USD/EUR 建ての北欧・東欧・CNH・SGD は SHORT = 現地通貨買い)。
指数: Mon 指数形(月曜 13 UTC 建て → 24h LONG)。参考に日中版(13→20 UTC)も出すがセルには数えない。
コスト = 実行値(LONG は ASK 買い・BID 売り、SHORT は逆)。窓 PRE 2016〜2021-09 / IS 2021-10〜2024 / OOS 2025〜。
標準 = IS 月次二項 p < 0.05/9,801・OOS 平均 > 0・PRE +月率 ≥ 50%。参照(相関用): Mon4 円クロス・Mon US500。"""
import pandas as pd, numpy as np, os, sys
from math import comb
D = sys.argv[1]; REF = sys.argv[2]
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31 23:00"), pd.Timestamp("2025-01-01")
CELLS = [("XPTUSD", 1), ("XPDUSD", 1), ("COPPER", 1), ("XRPUSD", 1), ("LTCUSD", 1), ("ADAUSD", 1), ("SGDJPY", 1),
         ("USDNOK", -1), ("USDSEK", -1), ("EURNOK", -1), ("EURSEK", -1), ("USDCNH", -1), ("USDSGD", -1), ("USDPLN", -1), ("EURPLN", -1), ("USDHUF", -1), ("USDCZK", -1)]
IDX = ["SUI20", "ESP35", "NLD25", "ITA40", "FRA40", "CHI50", "IND50", "US2000"]
def load(p, d=D):
    b = pd.read_csv(f"{d}/{p}_h1.csv", index_col=0, parse_dates=True)["open"]; a = pd.read_csv(f"{d}/{p}_h1_ask.csv", index_col=0, parse_dates=True)["open"]
    j = b.index.intersection(a.index); b, a = b[j], a[j]; idx = pd.to_datetime(j, utc=True).tz_localize(None); b.index = idx; a.index = idx
    ok = (a > b * 0.0) & (a >= b); return b[ok], a[ok]
def shot(p, hours, dur, d, src=D):
    b, a = load(p, src); out = []
    for h in hours:
        t = b.index[(b.index.dayofweek == 0) & (b.index.hour == h)]; t2 = t + pd.Timedelta(hours=dur); ok = t2.isin(b.index)
        t, t2 = t[ok], t2[ok]
        r = (b.reindex(t2).values / a.reindex(t).values - 1) if d > 0 else (1 - a.reindex(t2).values / b.reindex(t).values)
        out.append(pd.Series(r, index=t.normalize()))
    return pd.concat(out, axis=1).mean(axis=1).dropna()
def st(r, lo, hi):
    x = r[(r.index >= lo) & (r.index <= hi)]
    if len(x) < 4: return dict(n=0, k=0, rate=np.nan, bps=np.nan, p=1.0, sh=np.nan)
    m = x.groupby(x.index.to_period("M")).apply(lambda q: (1 + q).prod() - 1); n = len(m); k = int((m > 0).sum())
    return dict(n=n, k=k, rate=round(k / n, 3), bps=round(float(x.mean() * 1e4), 2), p=sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n, sh=round(float(x.mean() / x.std() * np.sqrt(52)), 2))
ref4 = pd.concat([shot(s, (4, 6, 8, 10), 24, 1, REF) for s in ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"]], axis=1).mean(axis=1)
rows = []
def add(name, r, kind):
    sp, si, so = st(r, PRE0, IS0), st(r, IS0, IS1), st(r, OOS0, pd.Timestamp("2027-01-01")); j = r.index.intersection(ref4.index)
    rows.append(dict(cell=name, kind=kind, start=str(r.index.min().date()) if len(r) else "-", n=len(r),
                     pre=f"{sp['bps']}/{sp['sh']}/{sp['rate']}", is_=f"{si['bps']}/{si['sh']}/{si['k']}of{si['n']}/p{si['p']:.3g}", oos=f"{so['bps']}/{so['sh']}/{so['k']}of{so['n']}",
                     corr_mon4=round(float(np.corrcoef(r[j], ref4[j])[0, 1]), 2) if len(j) > 20 else np.nan,
                     sign3=bool((sp["bps"] > 0 or sp["n"] == 0) and si["bps"] > 0 and so["bps"] > 0),
                     std=bool(si["p"] < 0.05 / 9801 and so["bps"] > 0 and (sp["n"] == 0 or sp["rate"] >= 0.5)), cnt=kind == "cell"))
for p, d in CELLS:
    if os.path.exists(f"{D}/{p}_h1.csv"): add(f"Mon4 形 {p} {'LONG' if d > 0 else 'SHORT'}", shot(p, (4, 6, 8, 10), 24, d), "cell")
for p in IDX:
    if os.path.exists(f"{D}/{p}_h1.csv"):
        add(f"Mon 指数形 {p} 13 UTC→24h LONG", shot(p, (13,), 24, 1), "cell")
        add(f"(参考)Mon 指数 日中 {p} 13→20 UTC", shot(p, (13,), 7, 1), "ref")
R = pd.DataFrame(rows); pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 60)
print("列: bps/Sharpe/(+月率 or +月数/p)"); print(R.drop(columns=["cnt"]).to_string(index=False)); R.to_csv("q145_new_symbols.csv", index=False)
c = R[R.cnt]; print(f"\nセル {len(c)}: 3 窓とも正 {int(c.sign3.sum())}・標準通過 {int(c['std'].sum())}")
