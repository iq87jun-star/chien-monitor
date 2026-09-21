# -*- coding: utf-8 -*-
"""docs/272: Q20 追試の「監視」(候補ではない)。円クロス 6 本の Wed 20-00 UTC・金利差 ≥ 1pp・SHORT(円買い)を、月ごとに Dukascopy の bid/ask で実測評価し results/q20_monitor.csv に追記する。
毎月 1 日に `cd research && python3 forward/q20_monitor.py` を実行(前月分と当月の途中経過)。データは forward/q20_monitor_data/ に月単位で保存(本体の data_dukascopy には混ぜない)。
判定(事前指定・2026-09 から): 12 ヶ月で JPY6 等ウェイトの +月 ≥ 8/12 かつ 平均 > 0 なら Q28 として正式登録(候補入りの検討)。それ未満なら監視終了。"""
import os, sys, time, json, datetime as dt, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools")); sys.path.insert(0, os.path.join(ROOT, "queue"))
import dukascopy_fetch as dk
src = open("queue/q20_wed_swap_carry.py", encoding="utf-8").read(); ns = {}; exec("import numpy as np, pandas as pd\n" + src.split("from q_common import *")[1].split("cum = int")[0], ns); RATES, rate_series = ns["RATES"], ns["rate_series"]
JPY = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY"]; DATA = "forward/q20_monitor_data"; os.makedirs(DATA, exist_ok=True)
def month_df(sym, side, y, m):
    f = f"{DATA}/{sym}_{y}-{m:02d}_{side}.csv"
    if os.path.exists(f) and (y, m) < (dt.date.today().year, dt.date.today().month): return pd.read_csv(f, parse_dates=["t"]).set_index("t")
    st, data = dk.fetch(f"https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m-1:02d}/{side.upper()}_candles_hour_1.bi5"); time.sleep(dk.GAP)
    if st != 200 or not data: return None
    rows = dk.decode(data, sym, y, m); df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume"]).set_index("t"); df.to_csv(f); return df
months = [(a.year, a.month) for a in pd.period_range(sys.argv[1] if len(sys.argv) > 1 else "2026-09", dt.date.today().strftime("%Y-%m"), freq="M")]
out = []
for (y, m) in months:
    per = {}
    for sym in JPY:
        b = month_df(sym, "bid", y, m); a = month_df(sym, "ask", y, m)
        if b is None or a is None: print(f"[{sym}] {y}-{m:02d} 取得不可"); continue
        b = b[(b.high > b.low) | (b.volume > 0)]; t = b.index[(b.index.dayofweek == 2) & (b.index.hour == 20)]
        days = pd.DatetimeIndex(sorted(set(b.index.normalize()))); cy = (rate_series(sym[:3], days) - rate_series("JPY", days)).reindex(t.normalize()).values
        t = t[(cy >= 1.0) & ~np.isnan(cy)]; te = t + pd.Timedelta(hours=4)
        r = pd.Series(b["open"].reindex(t).values / a["open"].reindex(te).values - 1, index=t).dropna(); per[sym] = r
        for tt, rr in r.items(): out.append(dict(month=f"{y}-{m:02d}", symbol=sym, entry=tt, ret_bps=round(rr * 1e4, 2)))
    if per:
        X = pd.DataFrame(per); port = X.mean(axis=1).dropna()
        out.append(dict(month=f"{y}-{m:02d}", symbol="JPY6", entry="", ret_bps=round(float(((1 + port).prod() - 1) * 1e4), 2), n_wed=len(port)))
O = pd.DataFrame(out, columns=["month", "symbol", "entry", "ret_bps", "n_wed"]); f = "results/q20_monitor.csv"
if len(O) == 0: print("取得できた月なし(Dukascopy 503 の可能性・後で再実行)"); sys.exit(1)
if os.path.exists(f): old = pd.read_csv(f); O = pd.concat([old[~old.month.isin(O.month.unique())], O])
O.to_csv(f, index=False); print(O[O.symbol == "JPY6"].to_string(index=False)); print(O[O.symbol != "JPY6"].groupby("month").ret_bps.agg(["count", "mean"]).round(2).to_string())
