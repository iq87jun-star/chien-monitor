# -*- coding: utf-8 -*-
"""docs/244 Q10: クロスセクション FX モメンタム。2 ユニバース(対 USD 7 ペア / 円クロス 6)× 直近 {1,2,4} 週リターンでランク → 上位 3 ロング / 下位 3 ショート × 保有 {1,2} 週 = 12 セル。
週次(月曜始値→保有週数後の月曜始値)・往復 2pip/脚。方向を先に決めてからコスト(docs/249)。
重複注記: 別 Routine 台帳 `xsect-fx-l20-h5`(FX12ペア 20 日ランク上位 2/下位 2・5 日保有)は棄却済み。本項の「4 週 × 1 週」はこれに近い。
判定: 二項 p(IS の +月数)< 0.05/(3,820+96+12)=1.27e-5、OOS 同符号、前窓 ≥ 50%。research/ で実行。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT)
import recentfit_screen as base, plusmonth_search as PS   # PS: base.YAHOO に AUDNZD 等を追加
UNIV = {"対USD 7": ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD"], "円クロス 6": ["GBPJPY", "EURJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"]}
PRE0, IS0, IS1, OOS0 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31"), pd.Timestamp("2025-01-01")
ALPHA = 0.05 / (3820 + 96 + 12)
def weekly_open(sym):
    df = base.load_daily(sym); o = df["open"]; mon = o[o.index.dayofweek == 0]; return mon
def pb(m): n = len(m); k = int((m > 0).sum()); return k, n, (sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n if n else 1.0)
def st(r, a, b):
    x = r[(r.index >= a) & (r.index <= b)]
    if len(x) == 0: return dict(n=0, plus=0, rate=np.nan, mean=np.nan, p=1.0)
    m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); k, n, p = pb(m)
    return dict(n=n, plus=k, rate=round(k / n, 3), mean=round(float(x.mean()) * 1e4, 1), p=p)
rows = []
for uname, syms in UNIV.items():
    W = pd.concat({s: weekly_open(s) for s in syms}, axis=1).dropna(how="all"); W = W[W.index >= PRE0 - pd.Timedelta(weeks=8)]
    fwd = {h: W.shift(-h) / W - 1 for h in (1, 2)}; cost = pd.DataFrame({s: 2 * base.pip_size(s) / W[s] for s in syms})
    for lb in (1, 2, 4):
        past = W / W.shift(lb) - 1
        for h in (1, 2):
            rets = []
            for t in W.index:
                p = past.loc[t].dropna(); f = fwd[h].loc[t]
                if len(p) < 6 or f.isna().any(): continue
                rk = p.sort_values(); lo, hi = rk.index[:3], rk.index[-3:]
                r = (f[hi] - cost.loc[t, hi]).mean() - (f[lo] + cost.loc[t, lo]).mean()   # 上位 3 ロング − 下位 3 ショート(各脚からコスト)
                rets.append((t, r / 2))                                                     # 総名目 1 に正規化
            r = pd.Series([v for _, v in rets], index=pd.DatetimeIndex([t for t, _ in rets]))
            if h == 2: r = r.iloc[::2]                                                       # 2 週保有は重複を避けて隔週
            sp, si, so = st(r, PRE0, IS0), st(r, IS0, IS1), st(r, OOS0, pd.Timestamp("2026-12-31"))
            passed = si["p"] < ALPHA and so["n"] > 0 and so["mean"] > 0 and sp["n"] > 0 and sp["rate"] >= 0.5
            rows.append(dict(universe=uname, lookback_w=lb, hold_w=h, is_plus=si["plus"], is_n=si["n"], is_rate=si["rate"], is_mean_bps=si["mean"], p=si["p"], oos_plus=so["plus"], oos_n=so["n"], oos_mean_bps=so["mean"], pre_rate=sp["rate"], pre_mean_bps=sp["mean"], passed=passed))
R = pd.DataFrame(rows).sort_values("p"); R.to_csv("results/q10_xs_fx_momentum.csv", index=False); pd.set_option("display.width", 220)
print(f"cells={len(R)} alpha={ALPHA:.2e} passed={int(R.passed.sum())}"); print(R.to_string(index=False))
