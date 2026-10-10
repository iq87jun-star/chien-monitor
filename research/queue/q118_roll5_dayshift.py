# -*- coding: utf-8 -*-
"""docs/322 §5f Q118(新規・4 セル): Roll5 の引け前シフト。配備形 Roll5 は水曜 20 UTC 建て(JPY クロス SHORT・4h)で CME の 16:10 ET 強制清算をまたぐため先物プロップで不可(docs/332)。
水曜の USDJPY SHORT を「h_in UTC 建て → 同日 20 UTC 決済」(h_in = 12 / 14 / 16 / 18)に移して符号を保つかを標準基準で見る。参照: 5 クロス等ウェイト版(各 h_in)と配備形 20→00 UTC。
使い方: cd research && python3 queue/q118_roll5_dayshift.py <累積セル数>"""
import sys
from q_common import *
from q114_mon_index_intraday import stats
CROSSES = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"]; HIN = [12, 14, 16, 18]; EXIT_H = 20
def wed_short(sym, h_in, h_out):
    o = load(sym)["open"]; t = o.index[(o.index.dayofweek == 2) & (o.index.hour == h_in)]
    t_out = pd.DatetimeIndex([x.normalize() + pd.Timedelta(hours=h_out) for x in t]) if h_out > h_in else t + pd.Timedelta(hours=(h_out + 24 - h_in))
    r = trades(sym, t, o.reindex(t).values, -np.ones(len(t)), o.reindex(t_out).values); r.index = r.index.normalize(); return r
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q118", cum, len(HIN), "results/q118_roll5_dayshift.csv"); rows = []
    for h in HIN:
        v = wed_short("USDJPY", h, EXIT_H); R.add("Roll5 引け前シフト", "USDJPY", f"水曜 {h} UTC SHORT → 同日 20 UTC 決済", v)
        five = pd.concat([wed_short(s, h, EXIT_H) for s in CROSSES], axis=1).mean(axis=1).dropna()
        for nm, s in (("USDJPY", v), ("5 クロス等ウェイト(参照)", five)):
            si, so = stats(s, IS0, IS1), stats(s, OOS0, END); sp = stats(s, PRE0, IS0)
            rows.append(dict(h_in=h, leg=nm, pre_sharpe=sp[0], is_sharpe=si[0], is_worst=si[1], is_cum=si[2], oos_sharpe=so[0], oos_worst=so[1], oos_cum=so[2]))
    base = wed_short("USDJPY", 20, 0); si, so, sp = stats(base, IS0, IS1), stats(base, OOS0, END), stats(base, PRE0, IS0)
    rows.append(dict(h_in=20, leg="配備形 20→00 UTC(参照)", pre_sharpe=sp[0], is_sharpe=si[0], is_worst=si[1], is_cum=si[2], oos_sharpe=so[0], oos_worst=so[1], oos_cum=so[2]))
    R.finish(); pd.set_option("display.width", 300); D = pd.DataFrame(rows); D.to_csv("results/q118_roll5_dayshift_levels.csv", index=False)
    print("\n== Q118 水曜 JPY SHORT の時間帯(Sharpe・最悪月 %・累積 %)==\n" + D.to_string(index=False))
