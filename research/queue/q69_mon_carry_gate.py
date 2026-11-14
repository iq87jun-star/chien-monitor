# -*- coding: utf-8 -*-
"""docs/311 Q69(F26): Mon 円クロスのキャリー門。7 ペア × {金利差 ≥1pp のみ, <1pp のみ} = 14 セル(新規)。金利差は q20 の rate_series(政策金利)。"""
import sys, os
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609")
from q20_wed_swap_carry import rate_series
cum = int(sys.argv[1]); R = Runner("Q69", cum, 14, "results/q69_mon_carry_gate.csv"); diag = []
for p in base.MON_FX:
    m = base.mon_cell(p); days = pd.DatetimeIndex(m.index); carry = rate_series(p[:3], days) - rate_series("JPY", days); carry = carry.reindex(days)
    hi = m[(carry >= 1.0).values]; lo = m[(carry < 1.0).values]
    R.add("Mon キャリー≥1pp のみ", p, "政策金利差 ≥1pp の月曜 o2o L", hi); R.add("Mon キャリー<1pp のみ", p, "政策金利差 <1pp の月曜 o2o L", lo)
    diag.append(dict(pair=p, carry_from=str(carry.dropna().index.min().date()) if carry.notna().any() else None, hi_n=len(hi), hi_bps=round(float(hi.mean()) * 1e4, 2) if len(hi) else None, lo_n=len(lo), lo_bps=round(float(lo.mean()) * 1e4, 2) if len(lo) else None))
R.finish(); pd.set_option("display.width", 300); print("\n== Q69 診断 ==\n" + pd.DataFrame(diag).to_string(index=False))
