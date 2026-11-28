# -*- coding: utf-8 -*-
"""docs/322 §5i Q125(新規 9 セル): Mon 指数のセッション版。決済は月曜 20 UTC(16:00 ET)で固定し、建てを Globex 再開(日曜 22 UTC)/ 月曜 0 UTC / 7 UTC に広げる(13 UTC は Q114 の参照)。
US500 / NAS100 / US30 × 3 建て = 9 セル(標準基準)。先物プロップの取引日内に収まる最長形。使い方: cd research && python3 queue/q125_index_session_mon.py <累積>"""
import sys
from q_common import *
from q_session import session
from q114_mon_index_intraday import stats
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q125", cum, 9, "results/q125_index_session_mon.csv"); rows = []
    for sym in ("US500", "NAS100", "US30"):
        for h in ("open", 0, 7, 13):
            s = session(sym, 0, h)
            if h != 13: R.add("Mon 指数 セッション版", sym, f"月曜 {h} UTC 建て → 20 UTC 決済", s)
            sp, si, so = stats(s, PRE0, IS0), stats(s, IS0, IS1), stats(s, OOS0, END)
            rows.append(dict(symbol=sym, h_in=h, cell=("参照" if h == 13 else "セル"), n=len(s), pre_sharpe=sp[0], is_sharpe=si[0], is_worst=si[1], is_cum=si[2], oos_sharpe=so[0], oos_worst=so[1], oos_cum=so[2]))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q125_index_session_mon_levels.csv", index=False); print("\n" + D.to_string(index=False))
