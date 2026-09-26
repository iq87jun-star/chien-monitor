# -*- coding: utf-8 -*-
"""docs/304 Q56(F13): 参加者フィルター × Mon レグ。22 セル。Mon7 等ウェイト(AU/NZ 祝日は AUDJPY+NZDJPY 合成)× 9 条件 × {のみ(新規), 除外(改良系)} = 18、
指数 Mon NAS100/US500 × 米国(NYSE)祝日月曜 {のみ, 除外} = 4。使い方: python3 queue/q56_participant_filters.py <累積>"""
import sys, os
from q_common import *
from q_cal import *
base.DATA = os.path.join(ROOT, "data_202609")
M7 = mon7(); AN = (base.mon_cell("AUDJPY").add(base.mon_cell("NZDJPY"), fill_value=0)) / 2
FILTERS = [("米国(NYSE)祝日月曜", lambda t: t in CAL["NYSE"], M7), ("英国祝日月曜", lambda t: t in CAL["UK"], M7), ("豪NZ祝日月曜(AUDJPY+NZDJPY)", lambda t: (t in CAL["AU"]) or (t in CAL["NZ"]), AN),
           ("翌火曜が日本の祝日", lambda t: is_jp_holiday(t + pd.Timedelta(days=1)), M7), ("お盆週(8/11-16)", obon, M7), ("月末最終JP営業日の月曜", jp_month_end, M7),
           ("ゴトー日の月曜", gotobi, M7), ("月初3JP営業日の月曜", first3, M7), ("BoJ会合週の月曜", lambda t: in_week(t, BOJ), M7)]
cum = int(sys.argv[1]); R = Runner("Q56", cum, 22, "results/q56_participant_filters.csv"); imp = []
for name, f, s in FILTERS:
    sel = pd.Series([bool(f(t)) for t in s.index], index=s.index)
    R.add(f"{name} のみ", "Mon7", "該当月曜のみ o2o L", s[sel]); ex = s[~sel]
    R.add(f"{name} 除外(改良系)", "Mon7", "該当月曜を建てない", ex); imp.append(dict(filter=name, n=int(sel.sum()), n_IS=int(sel[(sel.index >= IS0) & (sel.index <= IS1)].sum()), mean_bps_sel=round(float(s[sel].mean()) * 1e4, 2), mean_bps_rest=round(float(s[~sel].mean()) * 1e4, 2), **improved(s, ex)))
for idx in ("NAS100", "US500"):
    s = base.mon_cell(idx); sel = pd.Series([t in CAL["NYSE"] for t in s.index], index=s.index)
    R.add("米国祝日月曜 のみ", idx, "NYSE 休場の月曜のみ o2o L", s[sel]); ex = s[~sel]
    R.add("米国祝日月曜 除外(改良系)", idx, "NYSE 休場の月曜を建てない", ex); imp.append(dict(filter=f"米国祝日 {idx}", n=int(sel.sum()), n_IS=int(sel[(sel.index >= IS0) & (sel.index <= IS1)].sum()), mean_bps_sel=round(float(s[sel].mean()) * 1e4, 2), mean_bps_rest=round(float(s[~sel].mean()) * 1e4, 2), **improved(s, ex)))
R.finish(); pd.set_option("display.width", 320); print("\n== Q56 改良判定(除外)==\n" + pd.DataFrame(imp).to_string(index=False))
