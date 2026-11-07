# -*- coding: utf-8 -*-
"""docs/290: レグ(セル)毎の 5 年成績(2021-10-01〜2026-08-31・名目比 ×1・年別)。docs/289 の各ロジックを構成する全レグ + BROAD_IV 34 の全セル + ロール 5 ペア。
系列は deployed_book / recentfit_screen(data_202609・Yahoo 日足近似)、ロールは Dukascopy H1(仮定 3 pip・2022-01〜)。日次ガード無し。実口座成績ではない。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "queue"))
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import deployed_book as db, q_common as qc
from q20_wed_swap_carry import rate_series
A, B = pd.Timestamp("2021-10-01"), pd.Timestamp("2026-08-31"); BD = pd.bdate_range(A, B)
def on_bd(x): return x.groupby(x.index.normalize()).sum().reindex(BD).fillna(0.0)
L = {}   # (family, symbol, used_in) -> series
DEP = {  # 配備・候補ロジックで使うレグ
 ("Mon","GBPJPY"):"+月5/Mon4/C案/B案/速攻/Instant/EA7/EA7g", ("Mon","EURJPY"):"+月5/Mon4/D案/EA7", ("Mon","AUDJPY"):"+月5/Mon4/C案/B案/速攻/Instant/EA7/EA7g", ("Mon","USDJPY"):"+月5/Mon4/D案/EA7",
 ("Mon","GBPUSD"):"RF5 S1", ("Mon","ETHUSD"):"非FX", ("Hold","UK100"):"+月5/非FX", ("Hold","WTI"):"非FX", ("Hold","GER40"):"D案",
 ("v4","USDJPY"):"B案/Instant", ("v4","GBPJPY"):"D案", ("v4","NZDUSD"):"C案/速攻", ("v4","AUDUSD"):"C案/速攻", ("v4nfx","BTCUSD"):"非FX",
 ("MonThuS","USDCHF"):"RF5 S3", ("RSI2a","GBPUSD"):"RF5 S4", ("RSI2b","GBPJPY"):"RF5 S5", ("Mon","GBPJPY_S2"):"RF5 S2(=Mon GBPJPY)"}
for (f, s), u in DEP.items():
    if s.endswith("_S2"): continue
    L[(f, s, u)] = on_bd(db.leg_series(f, s))
for nm in base.MON_FX + base.MON_IDX:
    if ("Mon", nm) not in DEP: L[("Mon", nm, "BROAD_IV のみ")] = on_bd(base.mon_cell(nm))
for nm in base.HOLD_SYMS:
    if ("Hold", nm) not in DEP: L[("Hold", nm, "BROAD_IV のみ")] = on_bd(base.hold_cell(nm))
for nm in base.TSMOM_SYMS: L[("TSMOM", nm, "BROAD_IV のみ")] = on_bd(base.tsmom_cell(nm))
for p in base.V4_PAIRS:
    if ("v4", p) not in DEP: L[("v4", p, "BROAD_IV のみ")] = on_bd(base.v4_cell(p))
for sym in ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]:
    df = qc.load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    r = qc.trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values); r.index = r.index.normalize()
    L[("Roll", sym, "ロール捕捉/EA7/EA7g(2022〜)")] = on_bd(r)
rows = []
for (f, s, u), x in L.items():
    x = x[(x.index >= A) & (x.index <= B)]; eq = (1 + x).cumprod(); yrs = (x.index[-1] - x.index[0]).days / 365.25
    mon = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    rec = dict(family=f, symbol=s, used_in=u)
    for y in range(2021, 2027): rec[str(y)] = round(((1 + x[x.index.year == y]).prod() - 1) * 100, 1)
    rec.update(cum5y=round((eq.iloc[-1] - 1) * 100, 1), max_dd=round((eq / eq.cummax() - 1).min() * 100, 1), worst_day=round(x.min() * 100, 2), worst_month=round(mon.min() * 100, 1),
               pos_months=f"{int((mon > 0).sum())}/{int((mon != 0).sum())}", n_active=int((x != 0).sum()), sharpe=round(x.mean() / x.std() * np.sqrt(252), 2) if x.std() > 0 else 0.0)
    rows.append(rec)
R = pd.DataFrame(rows); pd.set_option("display.width", 320); print(R.to_string(index=False)); R.to_csv(os.path.join(HERE, "results", "leg_5y_scorecard.csv"), index=False)
