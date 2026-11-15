# -*- coding: utf-8 -*-
"""docs/244 Q243(改良系・3 セル・2026-11-16 登録): 通貨別で成立した AUDJPY と CADJPY を 0.5 ずつ束ねた月曜の買い(200 日線の下 1.0・上 0.5)に、決済の切り替え(E1・G1・G3)を当てた成績。
判定 = 束の「常に 24h」に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。期間は 2 本がそろう範囲。通貨別の結果を見た後で選んだ組み合わせ(事後選択)。
使い方: cd research && python3 -W ignore queue/q243_audjpy_cadjpy_bundle_exit_switch.py <累積セル数>   出力: results/q243_audjpy_cadjpy_bundle_exit_switch.csv・_detail.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q241_exit_switch_non_deployed_jpy_crosses import frame, hold_mask, series
PAIR = ["AUDJPY", "CADJPY"]; PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),)
def pair_frame():
    P = frame(PAIR); end = min(P[P.sym == s].index.max() for s in PAIR); return P[P.index <= end]
def aud_cad(kind="E1"):
    """紙上候補用: AUDJPY・CADJPY 等分の束。index = 月曜。"""
    return series(pair_frame(), kind)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 3; P = pair_frame(); b = series(P, "base"); bs = {w: stats(b, a, e) for w, a, e in WIN}; rows = []; det = []
    for k, nm in (("E1", "E1 VIX > 25 の週だけ 24h"), ("G1", "G1 週末に安く始まった通貨だけ 24h"), ("G3", "G3 VIX > 25 または G1")):
        v = series(P, k); vs = {w: stats(v, a, e) for w, a, e in WIN}
        rows.append(dict(cell=nm, end=str(P.index.max().date()), share=round(float(hold_mask(P, k).mean()), 3), base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), verdict=("成立" if all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN) else "不成立")))
    for k in ("base", "E1", "G1", "G3"):
        v = series(P, k); h = pd.Series(hold_mask(P, k), index=P.index)
        for w, a, e in ALLW:
            x = v[(v.index >= a) & (v.index <= e)]; hh = h[(h.index >= a) & (h.index <= e)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
            det.append(dict(form=k, window=w, weeks=len(x), months=len(m), pair_weeks=len(hh), hold24=int(hh.sum()), weeks_with_hold=int(hh.groupby(level=0).any().sum()), sharpe=round(float(x.mean() / x.std() * np.sqrt(52)), 2), worst_month=round(float(m.min()) * 100, 2), cum=round(float((1 + x).prod() - 1) * 100, 1), plus_months=int((m > 0).sum()), week_win=round(float((x > 0).mean()) * 100, 1)))
    D = pd.DataFrame(rows); D.to_csv("results/q243_audjpy_cadjpy_bundle_exit_switch.csv", index=False); T = pd.DataFrame(det); T.to_csv("results/q243_audjpy_cadjpy_bundle_exit_switch_detail.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 60)
    print(f"Q243: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print(D.to_string(index=False)); print(); print(T.to_string(index=False))
