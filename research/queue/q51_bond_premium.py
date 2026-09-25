# -*- coding: utf-8 -*-
"""docs/295 Q51: 債券のリスクプレミアム(採用レグ Hold=ベータの抽象化を債券へ)。a) Hold LONG(日次終値・連続保有・月初 2 bps) b) TSMOM(月足 1/3/6/12 符号和・翌月保有・月初 2 bps)。BUND・USTBOND(Dukascopy H1 2018〜)。
使い方: python3 queue/q51_bond_premium.py <累積>"""
import sys
from q_common import *
SYMS = ["BUND", "USTBOND"]; cum = int(sys.argv[1]); R = Runner("Q51", cum, len(SYMS) * 2, "results/q51_bond_premium.csv")
for sym in SYMS:
    c = load(sym)["close"]; daily = c.groupby(c.index.normalize()).last(); daily = daily[daily.index.dayofweek < 5]; r = daily.pct_change().dropna()
    firsts = pd.Series(r.index, index=r.index).groupby(pd.PeriodIndex(r.index, freq="M")).min(); k = NONFX_COST[sym]
    h = r.copy(); h.loc[h.index.isin(firsts.values)] -= k; R.add("債券プレミアム", sym, "a) Hold LONG 連続保有", h)
    mclose = daily.resample("ME").last(); sig = sum(np.sign(mclose.pct_change(lb)) for lb in (1, 3, 6, 12)); pos = np.sign(sig).shift(1); pos.index = pos.index.to_period("M")
    coef = pos.reindex(pd.PeriodIndex(r.index, freq="M")).fillna(0.0).values; t = pd.Series(r.values * coef, index=r.index); t.loc[t.index.isin(firsts.values)] -= k * (coef[np.isin(r.index, firsts.values)] != 0)
    R.add("債券プレミアム", sym, "b) TSMOM 1/3/6/12 符号和・翌月保有", t)
R.finish()
