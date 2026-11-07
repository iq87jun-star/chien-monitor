# -*- coding: utf-8 -*-
"""docs/294 Q48: FX 週明けギャップの埋め(M1)。月曜 00:00 UTC の初バー始値(取得は平日ファイルのみで日曜バー無し)と金曜最終バー終値の差(ギャップ)の逆方向に、初バーで建てて 60 分 / 240 分保有。薄い流動性の窓開けは戻る、が機構。
使い方: python3 queue/q48_fx_weekend_gap_m1.py <累積> EURUSD,GBPUSD,USDJPY,AUDUSD"""
import sys
from q_m1 import *
cum = int(sys.argv[1]); syms = sys.argv[2].split(","); R = Runner("Q48", cum, len(syms) * 2, "results/q48_fx_weekend_gap_m1.csv"); J = []
for sym in syms:
    d = m1(sym); o, cl = d["open"], d["close"]; c = rt_cost(sym, 22); print(f"[{sym}] 往復コスト {c*1e4:.2f} bps")
    dates = pd.DatetimeIndex(sorted(set(o.index.normalize()))); first_t = pd.Series(o.index, index=o.index).groupby(o.index.normalize()).min(); last_c = cl.groupby(cl.index.normalize()).last()
    sun = dates[dates.dayofweek == 0]; fri = sun - pd.Timedelta(days=3)
    t_in = pd.DatetimeIndex(first_t.reindex(sun).values); gap = o.reindex(t_in).values / last_c.reindex(fri).values - 1.0; dir_ = np.where(np.isnan(gap), 0.0, -np.sign(gap))
    for lab, hold in (("ギャップ逆方向 60 分", 60), ("ギャップ逆方向 240 分", 240)):
        r = ret_series(o, t_in, dir_, t_in + pd.Timedelta(minutes=hold), c); R.add("FX週明けギャップ", sym, lab, r); judge(R, J, sym, lab, r)
    print(f"  {sym}: 週数 {int((dir_!=0).sum())}  |gap| 中央値 {np.nanmedian(np.abs(gap))*1e4:.1f} bps")
finish(R, J, "Q48")
