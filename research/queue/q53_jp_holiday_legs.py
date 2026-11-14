# -*- coding: utf-8 -*-
"""docs/303 Q53(F10): 日本の祝日 × 採用レグ。38 セル。
 a) Mon 円クロス 7 本 × {祝日月曜のみ(新規), 祝日月曜を除外(改良系)} = 14
 b) ロール 5 本 × {祝日水曜のみ(新規), 祝日水曜を除外(改良系)} = 10
 c) 祝日翌営業日の円クロス o2o × {L, S} × 7 = 14(新規)
使い方: python3 queue/q53_jp_holiday_legs.py <累積>"""
import sys, os
from q_common import *
from q_jp import *
base.DATA = os.path.join(ROOT, "data_202609")
from q20_wed_swap_carry import rate_series
PAIRS = base.MON_FX; ROLL = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]
def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return (round(float(x.mean() / x.std() * np.sqrt(252)), 2) if x.std() > 0 else 0.0), round(float(m.min()) * 100, 2)
def improved(basis, var):
    bi, bo, gi, go = stats(basis, IS0, IS1), stats(basis, OOS0, END), stats(var, IS0, IS1), stats(var, OOS0, END)
    return dict(base_IS=bi, var_IS=gi, base_OOS=bo, var_OOS=go, ok=bool(gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]))
def roll_series(sym):
    df = load(sym); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
    t = o.index[(o.index.dayofweek == 2) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values; t = t[(cy >= 1.0) & ~np.isnan(cy)]
    return trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t + pd.Timedelta(hours=4)).values)
cum = int(sys.argv[1]); R = Runner("Q53", cum, 38, "results/q53_jp_holiday_legs.csv"); imp = []
for p in PAIRS:
    m = base.mon_cell(p); hol = pd.Series([is_jp_holiday(t) for t in m.index], index=m.index)
    R.add("Mon 祝日月曜のみ", p, "月曜が日本の祝日の週だけ o2o L", m[hol])
    ex = m[~hol]; R.add("Mon 祝日月曜除外(改良系)", p, "祝日月曜を建てない", ex); imp.append(dict(cell=f"Mon {p} 祝日除外", n_hol=int(hol.sum()), **improved(m, ex)))
for s in ROLL:
    r = roll_series(s); hol = pd.Series([is_jp_holiday(t) for t in r.index], index=r.index)
    R.add("Roll 祝日水曜のみ", s, "水曜が日本の祝日のときだけ 20-00 S", r[hol])
    ex = r[~hol]; R.add("Roll 祝日水曜除外(改良系)", s, "祝日水曜を建てない", ex); imp.append(dict(cell=f"Roll {s} 祝日除外", n_hol=int(hol.sum()), **improved(r, ex)))
for p in PAIRS:
    d = base.load_daily(p); c = 3 * base.pip_size(p) / d["open"]; days = pd.DatetimeIndex(d.index)
    after = set(next_jp_bday(h) for h in H if h.dayofweek < 5 and PRE0 <= h <= END)   # 平日の祝日の翌 JP 営業日
    sel = d.index.isin(list(after)); o2o = d["o2o"][sel]; cc = c[sel]
    R.add("祝日翌営業日 L", p, "祝日翌営業日の o2o LONG", base.clip((o2o - cc).dropna()))
    R.add("祝日翌営業日 S", p, "祝日翌営業日の o2o SHORT", base.clip((-o2o - cc).dropna()))
R.finish(); pd.set_option("display.width", 300); print("\n== Q53 改良判定(祝日除外)==\n" + pd.DataFrame(imp).to_string(index=False))
