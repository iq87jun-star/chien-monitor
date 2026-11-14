# -*- coding: utf-8 -*-
"""docs/276 Q28: Fintokei チャレンジプラン・スイング(P1 8% / P2 6% / 全体 −10% 静的 / 日次 −5%(EA ガード −4%)/ swap-free)向けに、ロール捕捉 + Mon の構成を MC で校正。
系列: roll_overlay.py と同じ(ロール = Dukascopy H1・仮定 3pip・金利差門・5 円クロス等ウェイト・水曜 20→00 UTC・2022-01〜; Mon = recentfit_screen.mon_cell)。窓 2021-10〜2026-08。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "queue"))
import recentfit_screen as base; base.DATA = os.path.join(HERE, "data_202609")
import q_common as qc
src = open(os.path.join(HERE, "queue", "q20_wed_swap_carry.py"), encoding="utf-8").read(); ns = {}; exec("import numpy as np, pandas as pd\n" + src.split("from q_common import *")[1].split("cum = int")[0], ns)
A, B = pd.Timestamp("2021-10-01"), pd.Timestamp("2026-08-31"); BD = pd.bdate_range(A, B)
def on_bd(x): return x.groupby(x.index.normalize()).sum().reindex(BD).fillna(0.0)
per = {}
for sym in ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]:
    df = qc.load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = ns["rate_series"](sym[:3], days) - ns["rate_series"]("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    per[sym] = qc.trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values)
roll = pd.DataFrame(per).mean(axis=1).dropna(); roll.index = roll.index.normalize(); roll = on_bd(roll)
def wsum(parts):
    idx = sorted(set().union(*[set(s.index) for s, _ in parts])); c = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s, w in parts: c = c.add(s.reindex(c.index).fillna(0) * w, fill_value=0)
    return on_bd(c)
w4 = {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}; tot = sum(w4.values()); mon4 = wsum([(base.mon_cell(k), v / tot) for k, v in w4.items()])
bplan = wsum([(base.mon_cell("GBPJPY"), .374), (base.mon_cell("AUDJPY"), .322), (base.v4_cell("USDJPY"), .304)])
configs = {"Roll ×2": roll * 2, "Roll ×3": roll * 3, "Mon4 ×2.0": mon4 * 2.0, "Mon4 ×2.3": mon4 * 2.3, "Mon4 ×2.0 + Roll ×3": mon4 * 2.0 + roll * 3, "Mon4 ×2.3 + Roll ×3": mon4 * 2.3 + roll * 3, "B案(パール構成)×4.0": bplan * 4.0, "B案 ×3.0 + Roll ×3": bplan * 3.0 + roll * 3}
def perf(s):
    eq = (1 + s).cumprod(); yrs = (s.index[-1] - s.index[0]).days / 365.25
    return dict(cagr=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2), sharpe=round(s.mean() / s.std() * np.sqrt(252), 2), max_dd=round((eq / eq.cummax() - 1).min() * 100, 2), worst_day=round(s.min() * 100, 2), days_over3=int((s < -0.03).sum()))
rows = []
base.P1_TARGET, base.P2_TARGET = 0.08, 0.06
for name, s in configs.items():
    r = base.mc_challenge(s, 1.0, np.random.default_rng(7)); rows.append(dict(config=name, **perf(s), p1_pass=r["p1_pass"], funded=r["funded"], fail=r["fail"], p1_days=r["p1_days_med"], funded_days=r["funded_days_med"], funded_p90=r["funded_days_p90"]))
R = pd.DataFrame(rows); pd.set_option("display.width", 250); print(R.to_string(index=False)); R.to_csv(os.path.join(HERE, "results", "q28_fintokei_swing_mc.csv"), index=False)
