# -*- coding: utf-8 -*-
"""docs/244 Q165(改良系・新規 1 セル・2026-11-07 登録/同日実行 ユーザー「セッション形はこのまま検証してください」):
Mon4 のセッション形 = GBPJPY・EURJPY・AUDJPY・USDJPY 等ウェイト、日曜 22 UTC 寄り建て → 月曜 20 UTC 決済 LONG(q_session.session と同じ実装・往復 3pip)。
比較対象 = 配備形 Mon4(base.mon_cell × 0.25・4/6/8/10 UTC 建て各 24h)。
判定 = 改良系(q114.improved): IS・OOS とも Sharpe が配備形を上回り、最悪月が悪化しない。参考: 前窓 +月率・相関・通貨別寄与。
使い方: cd research && python3 queue/q165_mon4_session_exit20.py <累積>   出力: results/q165_mon4_session_exit20.csv"""
import sys
from q_common import *
from q_session import session
from q114_mon_index_intraday import stats, improved
SYMS = ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY")
def norm(v):
    v = v.dropna(); v.index = pd.DatetimeIndex(v.index).normalize(); return v.groupby(v.index).sum()
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q165", cum, 1, "results/q165_mon4_session_exit20.csv")
    ses = {s: norm(session(s, 0, "open")) for s in SYMS}; dep = {s: norm(base.mon_cell(s)) for s in SYMS}
    S = sum(ses[s] * 0.25 for s in SYMS).dropna(); D = sum(dep[s] * 0.25 for s in SYMS).dropna()
    R.add("Mon4 セッション形", "Mon4", "日曜 22 UTC 寄り建て → 月曜 20 UTC 決済 LONG・4 通貨 0.25", S); R.finish()
    imp = improved(D, S); print("\n改良系判定(配備形 Mon4 24h → セッション形):", imp)
    rows = []
    for nm, x in (("セッション形 Mon4", S), ("配備形 Mon4 24h", D), *[(f"セッション {s}", ses[s]) for s in SYMS], *[(f"配備形 {s}", dep[s]) for s in SYMS]):
        for w, lo, hi in (("前窓", PRE0, IS0), ("IS", IS0, IS1), ("OOS", OOS0, END)):
            q = st(x, lo, hi); sh, worst, cumr = stats(x, lo, hi)
            rows.append(dict(系列=nm, 窓=w, 月数=q["n"], プラス月=q["plus"], 勝率=q["rate"], 平均bps=q["mean"], Sharpe=sh, 最悪月pct=worst, 累積pct=cumr, p=q["p"]))
    T = pd.DataFrame(rows); pd.set_option("display.width", 250); print("\n" + T.to_string(index=False)); T.to_csv("results/q165_mon4_session_exit20_levels.csv", index=False)
    j = S.index.intersection(D.index); print(f"\n配備形との週次相関: {np.corrcoef(S[j], D[j])[0,1]:.2f}  (n={len(j)})")
    y = pd.DataFrame({"セッション": S, "配備形": D}).dropna(); y["年"] = y.index.year
    g = y.groupby("年").agg(セッション_bps=("セッション", lambda v: round(v.mean() * 1e4, 1)), 配備形_bps=("配備形", lambda v: round(v.mean() * 1e4, 1)), 週=("セッション", "size"))
    print("\n年別 平均 bps/週:"); print(g.to_string())
