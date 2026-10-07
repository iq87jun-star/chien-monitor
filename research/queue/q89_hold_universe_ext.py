# -*- coding: utf-8 -*-
"""docs/322 Q89: Hold 族(連続 LONG・日足終値→終値・月初に 5 bps のロール費)の銘柄拡張 8 セル。
配備中の Hold 6 本(US500/NAS100/GER40/JP225/XAUUSD/BTCUSD)と**同一構成** `recentfit_screen.hold_cell` を、
Fintokei / FTMO で取引できる 8 銘柄(XAGUSD / COPPER / UKOIL / NGAS / US2000 / HK50 / AUS200 / EU50)に適用する。
データは Hold 6 と同じ Yahoo 日足(`data_202609/<銘柄>_rf.csv`・2016-01-04〜2026-07-29 の凍結窓)。
判定は docs/244 §1 の標準基準(IS 二項 p < 0.05/累積・IS 月数 ≥ 24・OOS 平均 > 0・前窓 +月率 ≥ 50%)。
使い方: cd research && python3 queue/q89_hold_universe_ext.py <累積セル数>"""
import sys, os
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609")
NEW = {"XAGUSD": "SI=F", "COPPER": "HG=F", "UKOIL": "BZ=F", "NGAS": "NG=F", "US2000": "^RUT", "HK50": "^HSI", "AUS200": "^AXJO", "EU50": "^STOXX50E"}
base.YAHOO.update(NEW)
def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]
    if len(x) < 20: return (np.nan, np.nan, np.nan)
    m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    sh = round(float(x.mean() / x.std() * np.sqrt(252)), 2) if x.std() > 0 else 0.0
    return sh, round(float(m.min()) * 100, 2), round(float((1 + x).prod() - 1) * 100, 1)
cum = int(sys.argv[1]); R = Runner("Q89", cum, len(NEW), "results/q89_hold_universe_ext.csv"); rows = []
for nm, tk in NEW.items():
    s = base.hold_cell(nm); d = base.load_daily(nm)
    R.add("Hold 拡張(連続 LONG)", nm, f"Yahoo {tk}・終値→終値・月初 5bps", s)
    pi, ii, oo = stats(s, PRE0, IS0), stats(s, IS0, IS1), stats(s, OOS0, END)
    rows.append(dict(symbol=nm, ticker=tk, first=str(d.index.min().date()), last=str(d.index.max().date()), pre_sharpe=pi[0], pre_ret=pi[2], IS_sharpe=ii[0], IS_worst_m=ii[1], IS_ret=ii[2], OOS_sharpe=oo[0], OOS_worst_m=oo[1], OOS_ret=oo[2]))
R.finish(); print("\n== 参考: Sharpe・最悪月(%)・累積(%)==\n" + pd.DataFrame(rows).to_string(index=False))
# 参考(セルに数えない): 配備中 Hold 6 の同じ統計
ref = []
for nm in base.HOLD_SYMS:
    s = base.hold_cell(nm); sp, si, so = st(s, PRE0, IS0), st(s, IS0, IS1), st(s, OOS0, END); ii, oo = stats(s, IS0, IS1), stats(s, OOS0, END)
    ref.append(dict(symbol=nm, pre_rate=sp["rate"], is_plus=si["plus"], is_n=si["n"], p=f"{si['p']:.1e}", oos_plus=so["plus"], oos_n=so["n"], IS_sharpe=ii[0], OOS_sharpe=oo[0], OOS_ret=oo[2]))
print("\n== 参考: 配備中 Hold 6(セルに数えない)==\n" + pd.DataFrame(ref).to_string(index=False))
