# -*- coding: utf-8 -*-
"""docs/322 §5h Q122(改良系・6 セル): Mon 指数日中版の出口時刻。配備形 13→20 UTC(16:00 ET)を 18 / 19 UTC に前倒しして、US500 / NAS100 / US30 で改良系基準を満たすか。参照: 21 UTC(引け後)。
使い方: cd research && python3 queue/q122_exit_grid_intraday.py <累積セル数>"""
import sys
from q_common import *
from q114_mon_index_intraday import shot, improved
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q122", cum, 6, "results/q122_exit_grid_intraday.csv"); rows = []
    for sym in ("US500", "NAS100", "US30"):
        b = shot(sym, 13, 20)
        for h in (18, 19, 21):
            v = shot(sym, 13, h); im = improved(b, v)
            if h != 21: R.add("Mon 指数日中版 出口格子", sym, f"月曜 13 UTC → 同日 {h} UTC 決済(配備形 20 比)", v)
            rows.append(dict(symbol=sym, exit_h=h, cell=("セル" if h != 21 else "参照"), **im))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q122_exit_grid_intraday_levels.csv", index=False)
    print("\n== Q122 改良判定 ==\n" + D.to_string(index=False)); print("\n改良成立(セル):", int(D[D.cell == "セル"].ok.sum()), "/ 6")
