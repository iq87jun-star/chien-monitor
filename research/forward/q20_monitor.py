# -*- coding: utf-8 -*-
"""docs/272: Q20 追試の「監視」(候補ではない)。円クロス 6 本の Wed 20-00 UTC・金利差 ≥ 1pp・SHORT(円買い)を、月ごとに Dukascopy の bid/ask で実測評価し results/q20_monitor.csv に追記する。
毎月 1 日に `cd research && python3 forward/q20_monitor.py` を実行(前月分と当月の途中経過)。データは forward/q20_monitor_data/ に月単位で保存(本体の data_dukascopy には混ぜない)。
判定(事前指定・2026-09 から): 12 ヶ月で JPY6 等ウェイトの +月 ≥ 8/12 かつ 平均 > 0 なら Q28 として正式登録(候補入りの検討)。それ未満なら監視終了。"""
import os, sys, time, json, datetime as dt, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools")); sys.path.insert(0, os.path.join(ROOT, "queue"))
import dukascopy_fetch as dk
from q20_wed_swap_carry import RATES, rate_series
JPY = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY"]; DATA = "forward/q20_monitor_data"; os.makedirs(DATA, exist_ok=True)
# docs/279 追加: 判定線 JPY6(門あり・Wed)は不変。診断線として CHFJPY(門なし)・JPY6 の Tue/Thu 対照・非 JPY 対照 EURUSD(USD SHORT 側 = LONG・Wed/Tue/Thu)を併記し「JPY 固有の水曜要因」が続いているかを見る。
CTRL = "EURUSD"
def month_df(sym, side, y, m):
    f = f"{DATA}/{sym}_{y}-{m:02d}_{side}.csv"
    if os.path.exists(f) and (y, m) < (dt.date.today().year, dt.date.today().month): return pd.read_csv(f, parse_dates=["t"]).set_index("t")
    main = f"data_dukascopy/{sym}_hour{'' if side == 'bid' else '_ask'}.csv.gz"     # 本体データに月が揃っていればそれを使う(取得しない)
    if os.path.exists(main):
        d = pd.read_csv(main); d["t"] = pd.to_datetime(d["timestamp"]); d = d.set_index("t").sort_index(); d = d[~d.index.duplicated(keep="last")]
        d = d[(d.index.year == y) & (d.index.month == m)]
        if len(d) > 300 and d.index[-1].day >= 25: return d[["open", "high", "low", "close", "volume"]]
    st, data = dk.fetch(f"https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m-1:02d}/{side.upper()}_candles_hour_1.bi5"); time.sleep(dk.GAP)
    if st != 200 or not data: return None
    rows = dk.decode(data, sym, y, m); df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume"]).set_index("t"); df.to_csv(f); return df
months = [(a.year, a.month) for a in pd.period_range(sys.argv[1] if len(sys.argv) > 1 else "2026-09", sys.argv[2] if len(sys.argv) > 2 else dt.date.today().strftime("%Y-%m"), freq="M")]   # 第 2 引数 = 終了月(テスト用)
out = []
for (y, m) in months:
    per = {}; ctrl = {}
    for sym in JPY:
        b = month_df(sym, "bid", y, m); a = month_df(sym, "ask", y, m)
        if b is None or a is None: print(f"[{sym}] {y}-{m:02d} 取得不可"); continue
        b = b[(b.high > b.low) | (b.volume > 0)]
        days = pd.DatetimeIndex(sorted(set(b.index.normalize()))); carry = rate_series(sym[:3], days) - rate_series("JPY", days)
        for dow, lab in ((2, ""), (1, "_Tue"), (3, "_Thu")):
            t = b.index[(b.index.dayofweek == dow) & (b.index.hour == 20)]; cy = carry.reindex(t.normalize()).values
            tg = t[(cy >= 1.0) & ~np.isnan(cy)]
            for gate, tt in (("", tg), ("_nogate", t)):
                if gate == "_nogate" and (sym != "CHFJPY" or lab != ""): continue
                te = tt + pd.Timedelta(hours=4); r = pd.Series(b["open"].reindex(tt).values / a["open"].reindex(te).values - 1, index=tt).dropna()
                if lab == "" and gate == "": per[sym] = r
                elif lab != "" and gate == "": ctrl.setdefault(lab, {})[sym] = r
                for t1, rr in r.items(): out.append(dict(month=f"{y}-{m:02d}", symbol=sym + lab + gate, entry=t1, ret_bps=round(rr * 1e4, 2)))
    # 非 JPY 対照: EURUSD LONG(USD SHORT 側)20-00 UTC・Wed/Tue/Thu・実測(ask で買い bid で売り)
    b = month_df(CTRL, "bid", y, m); a = month_df(CTRL, "ask", y, m)
    if b is not None and a is not None:
        b = b[(b.high > b.low) | (b.volume > 0)]
        for dow, lab in ((2, "_Wed"), (1, "_Tue"), (3, "_Thu")):
            t = b.index[(b.index.dayofweek == dow) & (b.index.hour == 20)]; te = t + pd.Timedelta(hours=4)
            r = pd.Series(b["open"].reindex(te).values / a["open"].reindex(t).values - 1, index=t).dropna()
            out.append(dict(month=f"{y}-{m:02d}", symbol=CTRL + lab, entry="", ret_bps=round(float(((1 + r).prod() - 1) * 1e4), 2), n_wed=len(r)))
    if per:
        X = pd.DataFrame(per); port = X.mean(axis=1).dropna()
        out.append(dict(month=f"{y}-{m:02d}", symbol="JPY6", entry="", ret_bps=round(float(((1 + port).prod() - 1) * 1e4), 2), n_wed=len(port)))
        for lab, d in ctrl.items():
            Xc = pd.DataFrame(d); pc_ = Xc.mean(axis=1).dropna()
            out.append(dict(month=f"{y}-{m:02d}", symbol="JPY6" + lab, entry="", ret_bps=round(float(((1 + pc_).prod() - 1) * 1e4), 2), n_wed=len(pc_)))
O = pd.DataFrame(out, columns=["month", "symbol", "entry", "ret_bps", "n_wed"]); f = "results/q20_monitor.csv"
if len(O) == 0: print("取得できた月なし(Dukascopy 503 の可能性・後で再実行)"); sys.exit(1)
if os.path.exists(f): old = pd.read_csv(f); O = pd.concat([old[~old.month.isin(O.month.unique())], O])
O.to_csv(f, index=False); S = O[O.symbol.isin(["JPY6", "JPY6_Tue", "JPY6_Thu", CTRL + "_Wed", CTRL + "_Tue", CTRL + "_Thu"])]
print("== 月次(bps・合成は月内複利)==\n" + S.pivot_table(index="month", columns="symbol", values="ret_bps").round(1).to_string())
print("== 判定線 JPY6(門あり・Wed)==\n" + O[O.symbol == "JPY6"].to_string(index=False))
print("== 銘柄別(Wed・門あり + CHFJPY_nogate)==\n" + O[O.symbol.isin(JPY + ["CHFJPY_nogate"])].groupby(["month", "symbol"]).ret_bps.agg(["count", "mean"]).round(2).to_string())
