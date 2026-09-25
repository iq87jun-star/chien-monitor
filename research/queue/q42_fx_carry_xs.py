# -*- coding: utf-8 -*-
"""docs/293 Q42(F7): FX キャリー(フォワードプレミアム)クロスセクション。政策金利で G8 通貨をランクし上位 L / 下位 S(対 USD)、月次入替。直物ドリフト部分のみ。使い方: python3 queue/q42_fx_carry_xs.py <累積>"""
import sys, numpy as np, pandas as pd
from q_common import *
from q20_wed_swap_carry import rate_series
CCY = ["EUR", "GBP", "AUD", "NZD", "CAD", "CHF", "JPY", "USD"]; PAIR = {"EUR": ("EURUSD", 1), "GBP": ("GBPUSD", 1), "AUD": ("AUDUSD", 1), "NZD": ("NZDUSD", 1), "CAD": ("USDCAD", -1), "CHF": ("USDCHF", -1), "JPY": ("USDJPY", -1)}
opens = {}
for c, (p, sgn) in PAIR.items():
    df = load(p); selfcheck(p, df); opens[c] = (df["open"], sgn, p)
ref = opens["EUR"][0]; t00 = ref.index[(ref.index.hour == 0) & (ref.index.dayofweek < 5)]
t_reb = pd.DatetimeIndex(pd.Series(t00, index=t00).groupby(pd.PeriodIndex(t00, freq="M")).min().values)  # 各月の初営業日 00 UTC(EURUSD にバーがある日)
rates = pd.DataFrame({c: rate_series(c, t_reb - pd.Timedelta(days=1)).values for c in CCY}, index=t_reb)
def month_ret(c, t0, t1):
    """通貨 c の対 USD 月次リターン(グロス)と往復コスト。"""
    o, sgn, p = opens[c]; a = o.reindex([t0]).values[0]; b = o.reindex([t1]).values[0]
    if np.isnan(a) or np.isnan(b): return np.nan, np.nan
    return sgn * (b / a - 1.0), float(cost(p, np.array([a]))[0])
cum = int(sys.argv[1]); SPECS = [("上位1 L / 下位1 S", 1, True), ("上位2 L / 下位2 S", 2, True), ("上位3 L / 下位3 S", 3, True), ("上位2 L のみ", 2, False)]
R = Runner("Q42", cum, len(SPECS), "results/q42_fx_carry_xs.csv")
for lab, k, ls in SPECS:
    rows = []
    for i in range(len(t_reb) - 1):
        t0, t1 = t_reb[i], t_reb[i + 1]; rk = rates.iloc[i].sort_values(ascending=False); top = list(rk.index[:k]); bot = list(rk.index[-k:])
        legs = []
        for c in top:
            if c == "USD": continue
            g, k_ = month_ret(c, t0, t1); legs.append(g - k_)
        if ls:
            for c in bot:
                if c == "USD": continue
                g, k_ = month_ret(c, t0, t1); legs.append(-g - k_)
        legs = [x for x in legs if not np.isnan(x)]
        if legs: rows.append((t0, float(np.mean(legs))))
    r = pd.Series([v for _, v in rows], index=pd.DatetimeIndex([t for t, _ in rows]))
    R.add("FXキャリーXS", "G8/USD", lab + "(月次・直物のみ)", r)
R.finish()
