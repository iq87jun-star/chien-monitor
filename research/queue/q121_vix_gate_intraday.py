# -*- coding: utf-8 -*-
"""docs/322 §5h Q121(改良系・4 セル): VIX 門 × Mon 指数日中版。前金曜の VIX 終値が閾値(20 / 25)を超える月曜は見送る規則が、US500 / NAS100 の 13→20 UTC を
docs/244 §1 の改良系基準(IS・OOS 両方で Sharpe 改善 かつ 最悪月が悪化しない)で上回るか。参照: US30、半減版。
使い方: cd research && python3 queue/q121_vix_gate_intraday.py <累積セル数>"""
import sys
from q_common import *
from q114_mon_index_intraday import shot, stats, improved
V = pd.read_csv("data_ext/VIX_History.csv"); V["d"] = pd.to_datetime(V["DATE"]); V = V.set_index("d")["CLOSE"].sort_index()
def gate(s, thr, mode="skip"):
    prev = V.reindex(s.index - pd.Timedelta(days=3), method="ffill").values   # 前金曜(無ければ直前)の終値
    hi = prev > thr
    return s[~hi] if mode == "skip" else s * np.where(hi, 0.5, 1.0)
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q121", cum, 4, "results/q121_vix_gate_intraday.csv"); rows = []
    for sym in ("US500", "NAS100", "US30"):
        b = shot(sym, 13, 20)
        for thr in (20, 25):
            for mode in ("skip", "half"):
                v = gate(b, thr, mode); im = improved(b, v)
                if sym != "US30" and mode == "skip": R.add("VIX 門 × Mon 指数日中版", sym, f"前金曜 VIX > {thr} の月曜は見送り(13→20 UTC)", v)
                rows.append(dict(symbol=sym, thr=thr, mode=mode, cell=("セル" if (sym != "US30" and mode == "skip") else "参照"), n_skipped=int(len(b) - len(gate(b, thr, "skip"))), **im))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q121_vix_gate_intraday_levels.csv", index=False)
    print("\n== Q121 改良判定 ==\n" + D.to_string(index=False)); print("\n改良成立(セル):", int(D[D.cell == "セル"].ok.sum()), "/ 4")
