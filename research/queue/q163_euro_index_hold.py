# -*- coding: utf-8 -*-
"""docs/244 Q163(order 36): 欧州指数 4 本(NLD25・ESP35・FRA40・SUI20)の Hold(連続 LONG・日足終値→終値・月初 5 bps)4 セル。
Q89(docs/329)と**同一構成** `recentfit_screen.hold_cell`。データは Dukascopy 不通(2026-11-10 17:52 JST 時点 HTTP 429)のため
登録時の取り決めどおり Yahoo 日足(^AEX ^IBEX ^FCHI ^SSMI・Q89 と同じ出所・2016-01-04〜2026-07-29 の凍結窓)で代替。
判定は docs/244 §1 の標準基準(IS 二項 p < 0.05/累積・IS 月数 ≥ 24・OOS 平均 > 0・前窓 +月率 ≥ 50%)。
参考(判定に使わない): 既存 Hold UK100 / Hold XAU / Mon 指数(NAS100・US500)との日次相関。
使い方: cd research && python3 queue/q163_euro_index_hold.py <累積セル数>"""
import sys, os
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609")
NEW = {"NLD25": "^AEX", "ESP35": "^IBEX", "FRA40": "^FCHI", "SUI20": "^SSMI"}
base.YAHOO.update(NEW)
def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]
    if len(x) < 20: return (np.nan, np.nan, np.nan)
    m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    sh = round(float(x.mean() / x.std() * np.sqrt(252)), 2) if x.std() > 0 else 0.0
    return sh, round(float(m.min()) * 100, 2), round(float((1 + x).prod() - 1) * 100, 1)
cum = int(sys.argv[1]); R = Runner("Q163", cum, len(NEW), "results/q163_euro_index_hold.csv"); rows = []; S = {}
for nm, tk in NEW.items():
    s = base.hold_cell(nm); d = base.load_daily(nm); S[nm] = s
    R.add("Hold 欧州指数(連続 LONG)", nm, f"Yahoo {tk}・終値→終値・月初 5bps", s)
    pi, ii, oo = stats(s, PRE0, IS0), stats(s, IS0, IS1), stats(s, OOS0, END)
    rows.append(dict(symbol=nm, ticker=tk, first=str(d.index.min().date()), last=str(d.index.max().date()), pre_sharpe=pi[0], pre_ret=pi[2], IS_sharpe=ii[0], IS_worst_m=ii[1], IS_ret=ii[2], OOS_sharpe=oo[0], OOS_worst_m=oo[1], OOS_ret=oo[2]))
R.finish(); print("\n== 参考: Sharpe・最悪月(%)・累積(%)==\n" + pd.DataFrame(rows).to_string(index=False))
pd.DataFrame(rows).to_csv("results/q163_euro_index_hold_stats.csv", index=False)
# 参考(セルに数えない): 既存 Hold / Mon 指数との日次相関(IS0〜END)
ref = {"Hold UK100": base.hold_cell("UK100"), "Hold XAU": base.hold_cell("XAUUSD"), "Hold GER40": base.hold_cell("GER40"), "Mon NAS100": base.mon_cell("NAS100"), "Mon US500": base.mon_cell("US500")}
cr = []
for nm, s in S.items():
    x = s[(s.index >= IS0) & (s.index <= END)]
    cr.append(dict(symbol=nm, **{k: round(float(pd.concat([x, v.reindex(x.index).fillna(0.0)], axis=1).corr().iloc[0, 1]), 2) for k, v in ref.items()}))
print("\n== 参考: 日次相関(2021-10〜)==\n" + pd.DataFrame(cr).to_string(index=False)); pd.DataFrame(cr).to_csv("results/q163_euro_index_hold_corr.csv", index=False)
