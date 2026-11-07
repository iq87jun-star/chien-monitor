# -*- coding: utf-8 -*-
"""docs/322 §5i Q126(新規 12 セル): 指数セッション版の曜日格子。火〜金の「前日 22 UTC(Globex 再開)建て → 当日 20 UTC 決済」を US500 / NAS100 / US30 で(標準基準)。参照: 同日 13→20 UTC。
使い方: cd research && python3 queue/q126_index_session_weekdays.py <累積>"""
import sys
from q_common import *
from q_session import session
from q114_mon_index_intraday import stats
DOW = ["月", "火", "水", "木", "金"]
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q126", cum, 12, "results/q126_index_session_weekdays.csv"); rows = []
    for sym in ("US500", "NAS100", "US30"):
        for d in (1, 2, 3, 4):
            s = session(sym, d, "open"); R.add("指数 セッション版 曜日格子", sym, f"{DOW[d]}曜 前日 22 UTC 建て → 20 UTC 決済", s)
            for nm, x in (("セル open→20", s), ("参照 13→20", session(sym, d, 13))):
                sp, si, so = stats(x, PRE0, IS0), stats(x, IS0, IS1), stats(x, OOS0, END)
                rows.append(dict(symbol=sym, dow=DOW[d], form=nm, n=len(x), pre_sharpe=sp[0], is_sharpe=si[0], is_worst=si[1], is_cum=si[2], oos_sharpe=so[0], oos_worst=so[1], oos_cum=so[2]))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q126_index_session_weekdays_levels.csv", index=False); print("\n" + D.to_string(index=False))
