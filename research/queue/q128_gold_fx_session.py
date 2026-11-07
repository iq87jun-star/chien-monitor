# -*- coding: utf-8 -*-
"""docs/322 §5i Q128(新規 3 セル): 金と円のセッション版。XAUUSD の木曜・月曜「前日 22 UTC 建て → 20 UTC 決済」LONG(MGC 向け・2 セル)、USDJPY の月曜「日曜 22 UTC 建て → 月曜 20 UTC」LONG(6J 売り・1 セル)。参照: 各 13→20。
使い方: cd research && python3 queue/q128_gold_fx_session.py <累積>"""
import sys
from q_common import *
from q_session import session
from q114_mon_index_intraday import stats
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q128", cum, 3, "results/q128_gold_fx_session.csv"); rows = []
    for sym, d, nm in (("XAUUSD", 3, "木曜"), ("XAUUSD", 0, "月曜"), ("USDJPY", 0, "月曜")):
        s = session(sym, d, "open"); R.add("金・円 セッション版", sym, f"{nm} 前日 22 UTC 建て → 20 UTC 決済 LONG", s)
        for f, x in (("セル open→20", s), ("参照 13→20", session(sym, d, 13))):
            sp, si, so = stats(x, PRE0, IS0), stats(x, IS0, IS1), stats(x, OOS0, END)
            rows.append(dict(symbol=sym, dow=nm, form=f, n=len(x), pre_sharpe=sp[0], is_sharpe=si[0], is_worst=si[1], is_cum=si[2], oos_sharpe=so[0], oos_worst=so[1], oos_cum=so[2]))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q128_gold_fx_session_levels.csv", index=False); print("\n" + D.to_string(index=False))
