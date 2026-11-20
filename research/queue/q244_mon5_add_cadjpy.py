# -*- coding: utf-8 -*-
"""docs/244 Q244(改良系・2 セル・2026-11-16 登録): 月曜の円クロスに CADJPY を足して 5 本等分(各 0.2・合計 1.0・200 日線の下 1.0・上 0.5)にする。
K1 = 常に 24h(基準 = 配備形 Mon4・24h)。K2 = E1(前金曜の VIX > 25 の週だけ 24h・それ以外は同日 20 UTC。基準 = Mon4 + E1)。
判定 = 基準に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。期間は 5 本がそろう範囲。CADJPY は Q241 の結果を見た後の選択(事後選択)。
使い方: cd research && python3 -W ignore queue/q244_mon5_add_cadjpy.py <累積セル数>   出力: results/q244_mon5_add_cadjpy.csv・_detail.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q241_exit_switch_non_deployed_jpy_crosses import frame, hold_mask, series
MON4 = ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"]; MON5 = MON4 + ["CADJPY"]; PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
_C = {}
def frames():
    if not _C:
        P5 = frame(MON5); end = min(P5[P5.sym == s].index.max() for s in MON5); _C["P5"] = P5[P5.index <= end]; _C["P4"] = _C["P5"][_C["P5"].sym != "CADJPY"]
    return _C["P4"], _C["P5"]
def mon5(kind="E1"):
    """紙上候補用: 5 本等分。kind = base(常に 24h)/ E1。index = 月曜。"""
    return series(frames()[1], kind)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 2; P4, P5 = frames(); rows = []; det = []
    for k, nm in (("base", "K1 5 本等分・常に 24h(基準 = Mon4・24h)"), ("E1", "K2 5 本等分・E1(基準 = Mon4 + E1)")):
        b = series(P4, k); v = series(P5, k); bs = {w: stats(b, a, e) for w, a, e in WIN}; vs = {w: stats(v, a, e) for w, a, e in WIN}
        rows.append(dict(cell=nm, end=str(P5.index.max().date()), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), verdict=("成立" if all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN) else "不成立")))
        for lab, x_ in ((f"Mon4・{k}", b), (f"Mon5・{k}", v)):
            for w, a, e in ALLW:
                x = x_[(x_.index >= a) & (x_.index <= e)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
                det.append(dict(form=lab, window=w, weeks=len(x), months=len(m), sharpe=round(float(x.mean() / x.std() * np.sqrt(52)), 2), worst_month=round(float(m.min()) * 100, 2), cum=round(float((1 + x).prod() - 1) * 100, 1), plus_months=int((m > 0).sum()), week_win=round(float((x > 0).mean()) * 100, 1), week_sd_bps=round(float(x.std()) * 1e4, 1)))
    D = pd.DataFrame(rows); D.to_csv("results/q244_mon5_add_cadjpy.csv", index=False); T = pd.DataFrame(det); T.to_csv("results/q244_mon5_add_cadjpy_detail.csv", index=False)
    cad = series(P5[P5.sym == "CADJPY"], "base"); b4 = series(P4, "base"); cc = {w: round(float(np.corrcoef(cad[(cad.index >= a) & (cad.index <= e)].reindex(b4[(b4.index >= a) & (b4.index <= e)].index).fillna(0.0), b4[(b4.index >= a) & (b4.index <= e)])[0, 1]), 2) for w, a, e in ALLW}
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 60)
    print(f"Q244: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print(D.to_string(index=False)); print(); print(T.to_string(index=False)); print("\nCADJPY の月曜(24h)と Mon4(24h)の週次の相関:", cc)
