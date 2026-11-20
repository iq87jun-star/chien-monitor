# -*- coding: utf-8 -*-
"""docs/244 Q174(改良系・新規 5 セル・2026-11-08 登録「登録」→「実行」): SKEW 門の他レグへの適用。
門 = q173 の PR['SKEW'](CBOE SKEW 終値の 252 日分位)> 0.8。参照日 = 建て日 − 3 日(月曜建て)/ − 1 日(水・木曜建て)、無ければ直前(ffill)。
(a1) Mon3 円クロス(14074882 形: EURJPY .333 + USDJPY .333 + NZDJPY .334)skip  (a2) instG 円クロス(GBPJPY .537 + AUDJPY .463)skip
(b1) Roll4(account_cards.S('roll4'))門の開いた週のみ(only)  (b2) 同 門の週 ×2(size)  (c) Thu XAUUSD(paper_forward.candidate_series)門の週のみ(only)
判定 = §1 改良系(q114.improved)。only 型は累積が基準の 1/2 未満なら成立でも採用候補にしない(事前固定)。参照 = 0.9 分位・half(判定に使わない)。
使い方: cd research && python3 -W ignore queue/q174_skew_gate_other_legs.py <累積>   出力: results/q174_skew_gate_other_legs.csv・_levels.csv"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
from q_common import *
from q114_mon_index_intraday import stats, improved
from q173_skew_vvix_gate import PR
src = open(os.path.join(ROOT, "forward", "account_cards.py"), encoding="utf-8").read().split("rows_a, rows_m = [], []")[0]
ns = {"__name__": "account_cards_head", "__file__": os.path.join(ROOT, "forward", "account_cards.py")}; exec(compile(src, "account_cards_head", "exec"), ns); S = ns["S"]
import forward.paper_forward as pf
def norm(v):
    v = v.dropna(); v.index = pd.DatetimeIndex(v.index).normalize(); return v.groupby(v.index).sum()
def gate_flag(idx, lag_days, q=0.8):
    return PR["SKEW"].reindex(pd.DatetimeIndex(idx) - pd.Timedelta(days=lag_days), method="ffill").values > q
def apply(s, lag, q, mode):
    hi = gate_flag(s.index, lag, q)
    if mode == "skip": return s[~hi]
    if mode == "only": return s[hi]
    if mode == "half": return s * np.where(hi, 0.5, 1.0)
    if mode == "size": return s * np.where(hi, 2.0, 1.0)
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q174", cum, 5, "results/q174_skew_gate_other_legs.csv"); rows = []
    mon3 = (norm(base.mon_cell("EURJPY")) * 0.333 + norm(base.mon_cell("USDJPY")) * 0.333 + norm(base.mon_cell("NZDJPY")) * 0.334).dropna()
    instg = (norm(base.mon_cell("GBPJPY")) * 0.537 + norm(base.mon_cell("AUDJPY")) * 0.463).dropna()
    roll = S("roll4"); roll = roll[roll != 0]
    thu = pf.candidate_series("Thu", "XAUUSD", 3, False); thu = thu[thu != 0]
    cells = [("Mon3 円クロス(14074882 形)", mon3, 3, "skip", "a1"), ("instG 円クロス(11988011 形)", instg, 3, "skip", "a2"),
             ("Roll4", roll, 1, "only", "b1"), ("Roll4", roll, 1, "size", "b2"), ("Thu XAUUSD", thu, 1, "only", "c")]
    for nm, b, lag, mode, tag in cells:
        b = b[b.index >= PRE0]
        for q, md, is_cell in ((0.8, mode, True), (0.9, mode, False), (0.8, "half" if mode == "skip" else ("size" if mode == "only" else "only"), False)):
            v = apply(b, lag, q, md); im = improved(b, v)
            cum_ok = True
            if md == "only": cum_ok = (im["var_IS"][2] >= 0.5 * im["base_IS"][2]) and (im["var_OOS"][2] >= 0.5 * im["base_OOS"][2])
            if is_cell: R.add("SKEW 門 × 他レグ", nm, f"SKEW 252 日 {q:.0%} 超 {md}(参照日 −{lag} 日)", v)
            hi = gate_flag(b[b.index >= IS0].index, lag, q); bb = b[b.index >= IS0]
            rows.append(dict(tag=tag, series=nm, q=q, mode=md, cell="セル" if is_cell else "参照", n_IS_OOS=len(bb), n_gate_on=int(hi.sum()), on_mean_bps=round(float(bb[hi].mean()) * 1e4, 1) if hi.any() else None, off_mean_bps=round(float(bb[~hi].mean()) * 1e4, 1), **im, cum_rule_ok=bool(cum_ok), adopt=bool(im["ok"] and cum_ok)))
    R.finish(); D = pd.DataFrame(rows); D.to_csv("results/q174_skew_gate_other_legs_levels.csv", index=False); pd.set_option("display.width", 320); pd.set_option("display.max_columns", 30)
    print("\n== Q174 改良判定(base/var = (Sharpe, 最悪月%, 累積%)・on/off = 門の開閉別の平均 bps・IS+OOS) ==\n" + D.to_string(index=False))
    print("\n改良成立(セル):", int(D[D.cell == "セル"].ok.sum()), "/ 5", "| 採用候補(累積規則込み):", int(D[D.cell == "セル"].adopt.sum()))
