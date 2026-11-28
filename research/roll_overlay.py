# -*- coding: utf-8 -*-
"""docs/275: ロール捕捉(水曜 20-00 UTC・5 円クロス等ウェイト SHORT・金利差門・swap-free 前提)を既存ロジックに名目 3 倍で上乗せした場合の成績(2021-10〜2026-08・日次)。
既存ロジックの日次系列は recentfit_screen のセル(data_202609)で再構成。ロール系列は Dukascopy H1(仮定 3pip・2022-01〜)。MC は base.mc_challenge(FTMO 10/5・FN 8/5)。"""
import os, sys, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "queue"))
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import selection_value_walkforward as wf, selection_metric_walkforward as sm
A, B = pd.Timestamp("2021-10-01"), pd.Timestamp("2026-08-31"); ROLL_M = 3.0
# --- ロール系列 ---
import q_common as qc
src = open(os.path.join(HERE, "queue", "q20_wed_swap_carry.py"), encoding="utf-8").read(); ns = {}; exec("import numpy as np, pandas as pd\n" + src.split("from q_common import *")[1].split("cum = int")[0], ns)
per = {}
for sym in ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]:
    df = qc.load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = ns["rate_series"](sym[:3], days) - ns["rate_series"]("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    r = qc.trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values); per[sym] = r
roll = pd.DataFrame(per).mean(axis=1).dropna(); roll.index = roll.index.normalize()   # 水曜の日付に載せる(1× 名目)
# --- 既存ロジック ---
def wsum(parts):
    idx = sorted(set().union(*[set(s.index) for s, _ in parts])); c = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s, w in parts: c = c.add(s.reindex(c.index).fillna(0) * w, fill_value=0)
    return c
logics = {}
w4 = {"GBPJPY": .260, "EURJPY": .266, "AUDJPY": .215, "USDJPY": .258}; tot = sum(w4.values())
logics["Mon4 ×2.5(EA3・#531407058)"] = wsum([(base.mon_cell(k), v / tot) for k, v in w4.items()]) * 2.5
try:
    parts = [(base.hold_cell("UK100"), .491), (base.hold_cell("WTI"), .153), (base.mon_cell("ETHUSD"), .145)]
    try: parts.append((base.v4_cell("BTCUSD"), .211))
    except Exception as e: print("v4 BTCUSD 除外:", e)
    logics["NonFX ×1.48(FN #14166201・swap-free)"] = wsum(parts) * 1.48
except Exception as e: print("NonFX 構成不可:", e)
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
s34, _ = sm.run(build(("Mon", "Hold", "TSMOM", "v4")), "BROAD_IV", dates); logics["BROAD_IV 34(校正倍率 4.3)"] = s34
logics["BROAD_IV 34 ×0.6(長寿命・実効 2.6)"] = s34 * 0.6
# --- 評価 ---
def perf(s):
    s = s[(s.index >= A) & (s.index <= B)]; eq = (1 + s).cumprod(); yrs = (s.index[-1] - s.index[0]).days / 365.25
    return dict(cagr=round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2), vol=round(s.std() * np.sqrt(252) * 100, 2), sharpe=round(s.mean() / s.std() * np.sqrt(252), 2), max_dd=round((eq / eq.cummax() - 1).min() * 100, 2), worst_day=round(s.min() * 100, 2))
BD = pd.bdate_range(A, B)
def on_bd(x): return x.groupby(x.index.normalize()).sum().reindex(BD).fillna(0.0)   # 営業日カレンダーに載せる(月曜だけの系列も日次に)
roll = on_bd(roll); rows = []
for name, s in logics.items():
    s = on_bd(s); comb = s + roll * ROLL_M
    for lab, x in (("単独", s), (f"+ロール×{ROLL_M:.0f}", comb)):
        p = perf(x); rec = dict(logic=name, arm=lab, **p)
        for venue, p1 in (("FTMO", 0.10), ("FN", 0.08)):
            base.P1_TARGET = p1; r = base.mc_challenge(x, 1.0, np.random.default_rng(7)); rec[f"{venue}_funded"] = r.get("funded"); rec[f"{venue}_fail"] = r.get("fail")
        rows.append(rec)
R = pd.DataFrame(rows); pd.set_option("display.width", 250); print(R.to_string(index=False))
pr = perf(on_bd(roll * ROLL_M)); print("ロール単独 ×3(2021-10〜・2022 以前は 0):", pr)
R.to_csv(os.path.join(HERE, "results", "roll_overlay.csv"), index=False)
