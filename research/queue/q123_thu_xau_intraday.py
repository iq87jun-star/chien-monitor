# -*- coding: utf-8 -*-
"""docs/322 §5h Q123(新規・1 セル + 参照): 木曜 XAUUSD の日中版。紙上候補「Thu XAUUSD」を先物口座(MGC)向けに木曜 13 UTC 建て → 同日 20 UTC 決済に移す。参照: 24h 版、h14 建て。
使い方: cd research && python3 queue/q123_thu_xau_intraday.py <累積セル数>"""
import sys
from q_common import *
from q114_mon_index_intraday import stats
def thu(sym, h_in, h_out):
    o = load(sym)["open"]; t = o.index[(o.index.dayofweek == 3) & (o.index.hour == h_in)]
    t_out = (t + pd.Timedelta(hours=24)) if h_out is None else pd.DatetimeIndex([x.normalize() + pd.Timedelta(hours=h_out) for x in t])
    r = trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t_out).values); r.index = r.index.normalize(); return r
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q123", cum, 1, "results/q123_thu_xau_intraday.csv"); rows = []
    for h_in, h_out, cell in ((13, 20, "セル"), (13, None, "参照 24h"), (14, 20, "参照 h14")):
        s = thu("XAUUSD", h_in, h_out)
        if cell == "セル": R.add("木曜 XAU 日中版(MGC)", "XAUUSD", "木曜 13 UTC LONG → 同日 20 UTC 決済", s)
        sp, si, so = stats(s, PRE0, IS0), stats(s, IS0, IS1), stats(s, OOS0, END)
        rows.append(dict(cell=cell, h_in=h_in, h_out=h_out or "+24h", pre_sharpe=sp[0], is_sharpe=si[0], is_worst=si[1], is_cum=si[2], oos_sharpe=so[0], oos_worst=so[1], oos_cum=so[2]))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q123_thu_xau_intraday_levels.csv", index=False); print("\n" + D.to_string(index=False))
