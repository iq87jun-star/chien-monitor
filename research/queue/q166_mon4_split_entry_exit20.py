# -*- coding: utf-8 -*-
"""docs/244 Q166(改良系・新規 1 セル・2026-11-08 登録/同日実行 ユーザー「Q166 もこのまま検証してください」):
Mon4 の分割建て + 出口 20 UTC = GBPJPY・EURJPY・AUDJPY・USDJPY 等ウェイト、月曜 4/6/8/10 UTC 建て → 同日 20 UTC 決済 LONG(4 ショット平均・往復 3pip)。
比較対象 = 配備形 Mon4(base.mon_cell × 0.25・各ショット 24h)。参考 = Q165 セッション形(日曜 22 UTC 一括 → 月曜 20 UTC)。
判定 = 改良系(q114.improved): IS・OOS とも Sharpe が配備形を上回り、最悪月が悪化しない。
使い方: cd research && python3 queue/q166_mon4_split_entry_exit20.py <累積>   出力: results/q166_mon4_split_entry_exit20.csv・_levels.csv"""
import sys
from q_common import *
from q_session import session
from q114_mon_index_intraday import shot, stats, improved
SYMS = ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY"); HOURS = (4, 6, 8, 10)
def norm(v, shift=0):
    v = v.dropna(); v.index = pd.DatetimeIndex(v.index).normalize() + pd.Timedelta(days=shift); return v.groupby(v.index).sum()
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q166", cum, 1, "results/q166_mon4_split_entry_exit20.csv")
    shots = {(s, h): norm(shot(s, h, 20)) for s in SYMS for h in HOURS}
    per_sym = {s: sum(shots[(s, h)] for h in HOURS) / len(HOURS) for s in SYMS}
    V = sum(per_sym[s] * 0.25 for s in SYMS).dropna()
    dep = {s: norm(base.mon_cell(s)) for s in SYMS}; D = sum(dep[s] * 0.25 for s in SYMS).dropna()
    S = sum(norm(session(s, 0, "open"), 1) * 0.25 for s in SYMS).dropna()   # Q165 セッション形(参考・月曜日付に揃える)
    R.add("Mon4 分割建て+出口20", "Mon4", "月曜 4/6/8/10 UTC 建て → 同日 20 UTC 決済 LONG・4 ショット平均・4 通貨 0.25", V); R.finish()
    imp = improved(D, V); print("\n改良系判定(配備形 Mon4 24h → 分割建て+出口 20 UTC):", imp)
    rows = []
    series = [("分割建て+出口20 Mon4", V), ("配備形 Mon4 24h", D), ("参考 セッション形 Mon4(Q165)", S)] + [(f"出口20 {s}", per_sym[s]) for s in SYMS] + [(f"配備形 {s}", dep[s]) for s in SYMS] + [(f"出口20 Mon4 h{h}", sum(shots[(s, h)] for s in SYMS) * 0.25) for h in HOURS]
    for nm, x in series:
        for w, lo, hi in (("前窓", PRE0, IS0), ("IS", IS0, IS1), ("OOS", OOS0, END)):
            q = st(x, lo, hi); sh, worst, cumr = stats(x, lo, hi)
            rows.append(dict(系列=nm, 窓=w, 月数=q["n"], プラス月=q["plus"], 勝率=q["rate"], 平均bps=q["mean"], Sharpe=sh, 最悪月pct=worst, 累積pct=cumr, p=q["p"]))
    T = pd.DataFrame(rows); pd.set_option("display.width", 250); print("\n" + T.to_string(index=False)); T.to_csv("results/q166_mon4_split_entry_exit20_levels.csv", index=False)
    j = V.index.intersection(D.index); print(f"\n配備形との週次相関: {np.corrcoef(V[j], D[j])[0,1]:.2f} (n={len(j)})"); k = V.index.intersection(S.index); print(f"セッション形との週次相関: {np.corrcoef(V[k], S[k])[0,1]:.2f}")
    m = lambda x, lo, hi: x[(x.index >= lo) & (x.index <= hi)].groupby(pd.PeriodIndex(x[(x.index >= lo) & (x.index <= hi)].index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    for nm, x in (("分割+出口20", V), ("配備形", D), ("セッション形", S)): print(f"IS 最悪 3 か月 {nm}:", (m(x, IS0, IS1).sort_values().head(3) * 100).round(2).to_dict())
    y = pd.DataFrame({"分割+出口20": V, "配備形": D}).dropna(); y["年"] = y.index.year
    print("\n年別 平均 bps/週:"); print(y.groupby("年").agg(分割出口20=("分割+出口20", lambda v: round(v.mean() * 1e4, 1)), 配備形=("配備形", lambda v: round(v.mean() * 1e4, 1)), 週=("配備形", "size")).to_string())
