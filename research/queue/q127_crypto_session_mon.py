# -*- coding: utf-8 -*-
"""docs/322 §5i Q127(新規 4 セル): 暗号資産の月曜セッション版(CME ミクロ MBT / MET 向け)。ETHUSD / BTCUSD × {日曜 22 UTC 建て → 月曜 20 UTC, 月曜 13 → 20 UTC}(標準基準)。参照: 配備形 Mon ETH 4 ショット(4/6/8/10 UTC → 24h)。
使い方: cd research && python3 queue/q127_crypto_session_mon.py <累積>"""
import sys
from q_common import *
from q_session import session
from q114_mon_index_intraday import stats, shot
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q127", cum, 4, "results/q127_crypto_session_mon.csv"); rows = []
    for sym in ("ETHUSD", "BTCUSD"):
        for nm, s in (("open→20", session(sym, 0, "open")), ("13→20", session(sym, 0, 13))):
            R.add("暗号資産 月曜セッション版(MBT/MET)", sym, f"月曜 {nm} UTC", s)
            sp, si, so = stats(s, PRE0, IS0), stats(s, IS0, IS1), stats(s, OOS0, END)
            rows.append(dict(symbol=sym, form=nm, cell="セル", n=len(s), pre_sharpe=sp[0], is_sharpe=si[0], is_worst=si[1], is_cum=si[2], oos_sharpe=so[0], oos_worst=so[1], oos_cum=so[2]))
        ref = pd.concat([shot(sym, h, None) for h in (4, 6, 8, 10)], axis=1).mean(axis=1).dropna(); sp, si, so = stats(ref, PRE0, IS0), stats(ref, IS0, IS1), stats(ref, OOS0, END)
        rows.append(dict(symbol=sym, form="4 ショット 24h(参照・配備形)", cell="参照", n=len(ref), pre_sharpe=sp[0], is_sharpe=si[0], is_worst=si[1], is_cum=si[2], oos_sharpe=so[0], oos_worst=so[1], oos_cum=so[2]))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q127_crypto_session_mon_levels.csv", index=False); print("\n" + D.to_string(index=False))
