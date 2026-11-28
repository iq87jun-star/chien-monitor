# -*- coding: utf-8 -*-
"""docs/289: 稼働中・候補の各ロジックの 5 年成績(2021-10-01〜2026-08-31・年別・配備倍率)。
系列は deployed_book / recentfit_screen(data_202609・Yahoo 日足近似)、BROAD_IV は selection_metric_walkforward、ロールは Dukascopy H1(仮定 3pip・2022-01〜)。
日次 −4% ガードは掛けない(生の系列)。実口座成績ではない。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "queue"))
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import deployed_book as db, selection_value_walkforward as wf, selection_metric_walkforward as sm, q_common as qc
A, B = pd.Timestamp("2021-10-01"), pd.Timestamp("2026-08-31"); BD = pd.bdate_range(A, B)
def on_bd(x): return x.groupby(x.index.normalize()).sum().reindex(BD).fillna(0.0)
def wsum(parts):
    idx = sorted(set().union(*[set(s.index) for s, _ in parts])); c = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s, w in parts: c = c.add(s.reindex(c.index).fillna(0) * w, fill_value=0)
    return c
# --- ロール(docs/275 と同じ) ---
from q20_wed_swap_carry import rate_series; ns = {"rate_series": rate_series}
per = {}
for sym in ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]:
    df = qc.load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = ns["rate_series"](sym[:3], days) - ns["rate_series"]("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    per[sym] = qc.trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values)
roll = pd.DataFrame(per).mean(axis=1).dropna(); roll.index = roll.index.normalize(); roll = on_bd(roll)
# --- ロジック ---
L = {}
w4 = {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}; tot = sum(w4.values()); mon4 = on_bd(wsum([(base.mon_cell(k), v / tot) for k, v in w4.items()]))
w5 = {("Mon", "GBPJPY"): .222, ("Mon", "EURJPY"): .231, ("Mon", "AUDJPY"): .186, ("Mon", "USDJPY"): .223, ("Hold", "UK100"): .138}
L["+月5本 ×2.36(docs/228・未配備)"] = on_bd(wsum([(db.leg_series(f, s), w) for (f, s), w in w5.items()])) * 2.36
L["RF5 A案 5スリーブ ×4.8(FTMO100k #531343523)"] = on_bd(db.account_composite("FTMO100k_531343523")) * 4.8
L["Mon4 ×2.5(EA3・FTMO50k #531407058)"] = mon4 * 2.5
L["Mon4 ×3.3(EA2 Mon側・FTMO50k #521100397)"] = mon4 * 3.3
L["C案 C6m ×6.0(FTMO50k #531407058)"] = on_bd(db.account_composite("FTMO50k_531407058")) * 6.0
L["D案 v2 ×5.24(FTMO50k #521100397)"] = on_bd(db.account_composite("FTMO50k_521100397")) * 5.24
L["B案 RecentFit ×4.0(Fintokei パール)"] = on_bd(db.account_composite("Fintokei_Pearl500")) * 4.0
L["速攻プロ C6m系 ×2.5(#6078225)"] = on_bd(db.account_composite("Fintokei_Sokkou2000_6078225")) * 2.5
L["Instant ×4.0(FN #11988011)"] = on_bd(db.account_composite("FN_Instant20k_11988011")) * 4.0
L["非FX ×1.48(FN #14166201)"] = on_bd(db.account_composite("FN100k_14166201")) * 1.48
base.W_ALL1 = B; dates = pd.date_range(wf.WF_START, wf.WF_LAST, freq="ME")
def build(inc):
    cells = {}
    if "Mon" in inc:
        for nm in base.MON_FX + base.MON_IDX: cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    if "Hold" in inc:
        for nm in base.HOLD_SYMS: cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    if "TSMOM" in inc:
        for nm in base.TSMOM_SYMS: cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
    if "v4" in inc:
        for p in base.V4_PAIRS: cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))
    return cells
s34, _ = sm.run(build(("Mon", "Hold", "TSMOM", "v4")), "BROAD_IV", dates); s34 = on_bd(s34)
L["BROAD_IV 34 ×4.3(候補・EA 未完成)"] = s34
L["BROAD_IV 34 ×0.6(長寿命 2.6)"] = s34 * 0.6
s6, _ = sm.run(build(("TSMOM",)), "BROAD_IV", dates); L["TSMOM6 単独(校正 0.82)"] = on_bd(s6)
L["ロール捕捉 ×3(swap-free・2022-01〜)"] = roll * 3
L["ロール捕捉 ×5"] = roll * 5
L["EA7 Mon4 ×2.0 + ロール ×3(Fintokei スイング候補)"] = mon4 * 2.0 + roll * 3
L["EA7g Mon2 ×10 + ロール ×20(速攻プロ ギャンブル)"] = on_bd(wsum([(base.mon_cell("GBPJPY"), .5), (base.mon_cell("AUDJPY"), .5)])) * 10 + roll * 20
# --- 評価 ---
rows = []
for name, s in L.items():
    s = s[(s.index >= A) & (s.index <= B)]; eq = (1 + s).cumprod(); yrs = (s.index[-1] - s.index[0]).days / 365.25
    mon = s.groupby(pd.PeriodIndex(s.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    rec = dict(logic=name)
    for y in range(2021, 2027): rec[str(y)] = round(((1 + s[s.index.year == y]).prod() - 1) * 100, 1)
    rec.update(cum5y=round((eq.iloc[-1] - 1) * 100, 1), cagr=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1), max_dd=round((eq / eq.cummax() - 1).min() * 100, 1),
               worst_day=round(s.min() * 100, 2), worst_month=round(mon.min() * 100, 1), pos_months=f"{int((mon > 0).sum())}/{len(mon)}", sharpe=round(s.mean() / s.std() * np.sqrt(252), 2))
    rows.append(rec)
R = pd.DataFrame(rows); pd.set_option("display.width", 300); print(R.to_string(index=False)); R.to_csv(os.path.join(HERE, "results", "logic_5y_scorecard.csv"), index=False)
