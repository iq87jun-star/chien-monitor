# -*- coding: utf-8 -*-
"""docs/244 Q8: 祝日・月末・SQ。{米祝日の前営業日, 米祝日の翌営業日, 月末最終営業日, 第 3 金曜(SQ)} × {L,S} × 12 銘柄 = 96 セル。
日足 o2o(Yahoo・base.load_daily)・往復 2pip(指数は IDX_COST)。方向を先に決めてからコスト(docs/249)。
窓: 前窓 2016-01〜2021-09 / IS 2021-10〜2024-12 / OOS 2025-01〜末尾。判定: 二項 p(IS の +月数)< 0.05/(3,820+96)=1.28e-5、OOS 同符号、前窓 ≥ 50%。
別 Routine 台帳との重複: 月末効果(fx-ea/multi RESULTS §5「月末1営業日前寄り→翌月3営業日目寄り」29 銘柄・不成立)とは窓が異なる(最終営業日 1 日のみ)。research/ で実行。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from math import comb
from pandas.tseries.holiday import USFederalHolidayCalendar
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT)
import recentfit_screen as base
SYMS = ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY", "CADJPY", "CHFJPY", "NZDJPY", "EURUSD", "GBPUSD", "AUDUSD", "US500", "NAS100"]
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31"), pd.Timestamp("2025-01-01")
ALPHA = 0.05 / (3820 + 96)
hol = USFederalHolidayCalendar().holidays(start="2015-12-01", end="2026-12-31")
def event_days(idx):
    bd = pd.DatetimeIndex(sorted(idx)); pos = {d: i for i, d in enumerate(bd)}
    pre = set(); post = set()
    for h in hol:
        i = bd.searchsorted(h)
        if i < len(bd) and i > 0 and bd[i] != h: pre.add(bd[i - 1]); post.add(bd[i])       # 祝日が営業日でない場合のみ(週末重複を除く)
        elif i < len(bd) and bd[i] == h: pass
    me = set(pd.Series(bd, index=bd).groupby(bd.to_period("M")).max().values)
    sq = set(d for d in bd if d.weekday() == 4 and 15 <= d.day <= 21)
    return {"祝日前営業日": pre, "祝日翌営業日": post, "月末最終営業日": me, "第3金曜": sq}
def pb(m): n = len(m); k = int((m > 0).sum()); return k, n, (sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n if n else 1.0)
def st(r, a, b):
    x = r[(r.index >= a) & (r.index <= b)]
    if len(x) == 0: return dict(n=0, plus=0, rate=np.nan, mean=np.nan, p=1.0)
    m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); k, n, p = pb(m)
    return dict(n=n, plus=k, rate=round(k / n, 3), mean=round(float(x.mean()) * 1e4, 1), p=p)
rows = []
for sym in SYMS:
    df = base.load_daily(sym); c = base.IDX_COST.get(sym) or (2 * base.pip_size(sym) / df["open"]); ev = event_days(df.index)
    for en, days in ev.items():
        for short in (False, True):
            s = df["o2o"]; r = base.clip(((-s if short else s) - c)).dropna(); r = r[r.index.isin(days)]
            sp, si, so = st(r, PRE0, IS0), st(r, IS0, IS1), st(r, OOS0, pd.Timestamp("2026-12-31"))
            passed = si["p"] < ALPHA and si["n"] >= 20 and so["n"] > 0 and so["mean"] > 0 and sp["n"] > 0 and sp["rate"] >= 0.5
            rows.append(dict(event=en, symbol=sym, side="S" if short else "L", is_plus=si["plus"], is_n=si["n"], is_rate=si["rate"], is_mean_bps=si["mean"], p=si["p"], oos_plus=so["plus"], oos_n=so["n"], oos_mean_bps=so["mean"], pre_n=sp["n"], pre_rate=sp["rate"], passed=passed))
R = pd.DataFrame(rows).sort_values("p"); R.to_csv("results/q8_holiday_sq.csv", index=False); pd.set_option("display.width", 220)
print(f"cells={len(R)} alpha={ALPHA:.2e} passed={int(R.passed.sum())}"); print(R.head(12).to_string(index=False))
print("\n-- passed --"); print(R[R.passed].to_string(index=False) if R.passed.any() else "(none)")
print("\n-- イベント別: 良い側の IS +月率 中央値 --"); g = R.copy(); g["best"] = g.groupby(["event", "symbol"]).is_rate.transform("max"); print(g[g.is_rate == g.best].groupby("event").is_rate.median().round(3).to_string())
