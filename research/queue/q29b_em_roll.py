# -*- coding: utf-8 -*-
"""docs/277 Q29b: 高金利 EM 通貨(MXN/ZAR/TRY)の水曜ロール(3 日分のフォワードポイント)。q20 と同型: 水曜 20-00 UTC・門 |carry| ≥ 1pp・方向 = −sign(carry)(carry = USD − 相手 < 0 → USDXXX を LONG = 高金利通貨を SHORT)。
3 ペア × {Wed L 実測 bid/ask(2024-01〜), Wed L 仮定 5 bps(全期間), Tue 対照 仮定} = 9 セル。
政策金利: Banxico / SARB / CBRT(1 週間レポ・2018 前半は後期流動性窓の実効値)。変更日・水準は概算で出所は各中銀の公表値の記憶に基づく(要点検)。2026 年は最終値で据置き。
使い方: python3 queue/q29b_em_roll.py <累積セル数>"""
import sys, os, numpy as np, pandas as pd
import q_common as qc
from q_common import *
from q20_wed_swap_carry import RATES, rate_series
RATES.update({
 "MXN": [("2017-12-14",7.25),("2018-02-08",7.50),("2018-06-21",7.75),("2018-11-15",8.00),("2018-12-20",8.25),("2019-08-15",8.00),("2019-09-26",7.75),("2019-11-14",7.50),("2019-12-19",7.25),("2020-02-13",7.00),("2020-03-20",6.50),("2020-04-21",6.00),("2020-05-14",5.50),("2020-06-25",5.00),("2020-08-13",4.50),("2020-09-24",4.25),("2021-02-11",4.00),("2021-06-24",4.25),("2021-08-12",4.50),("2021-09-30",4.75),("2021-11-11",5.00),("2021-12-16",5.50),("2022-02-10",6.00),("2022-03-24",6.50),("2022-05-12",7.00),("2022-06-23",7.75),("2022-08-11",8.50),("2022-09-29",9.25),("2022-11-10",10.00),("2022-12-15",10.50),("2023-02-09",11.00),("2023-03-30",11.25),("2024-03-21",11.00),("2024-08-08",10.75),("2024-09-26",10.50),("2024-11-14",10.25),("2024-12-19",10.00),("2025-02-06",9.50),("2025-03-27",9.00),("2025-05-15",8.50),("2025-06-26",8.00),("2025-08-07",7.75),("2025-09-25",7.50),("2025-11-06",7.25),("2025-12-18",7.00)],
 "ZAR": [("2017-07-20",6.75),("2018-03-28",6.50),("2018-11-22",6.75),("2019-07-18",6.50),("2020-01-16",6.25),("2020-03-19",5.25),("2020-04-14",4.25),("2020-05-21",3.75),("2020-07-23",3.50),("2021-11-18",3.75),("2022-01-27",4.00),("2022-03-24",4.25),("2022-05-19",4.75),("2022-07-21",5.50),("2022-09-22",6.25),("2022-11-24",7.00),("2023-01-26",7.25),("2023-03-30",7.75),("2023-05-25",8.25),("2024-09-19",8.00),("2024-11-21",7.75),("2025-01-30",7.50),("2025-05-29",7.25),("2025-07-31",7.00),("2025-11-20",6.75)],
 "TRY": [("2017-12-14",12.75),("2018-06-01",16.50),("2018-06-07",17.75),("2018-09-13",24.00),("2019-07-25",19.75),("2019-09-12",16.50),("2019-10-24",14.00),("2019-12-12",12.00),("2020-01-16",11.25),("2020-02-19",10.75),("2020-03-17",9.75),("2020-04-22",8.75),("2020-05-21",8.25),("2020-09-24",10.25),("2020-11-19",15.00),("2020-12-24",17.00),("2021-03-18",19.00),("2021-09-23",18.00),("2021-10-21",16.00),("2021-11-18",15.00),("2021-12-16",14.00),("2022-08-18",13.00),("2022-09-22",12.00),("2022-10-20",10.50),("2022-11-24",9.00),("2023-02-23",8.50),("2023-06-22",15.00),("2023-07-20",17.50),("2023-08-24",25.00),("2023-09-21",30.00),("2023-10-26",35.00),("2023-11-23",40.00),("2024-01-25",45.00),("2024-03-21",50.00),("2024-12-26",47.50),("2025-01-23",45.00),("2025-03-06",42.50),("2025-04-17",46.00),("2025-07-24",43.00),("2025-09-11",40.50),("2025-10-23",39.50),("2025-12-11",38.00)],
})
PAIRS = ["USDMXN", "USDZAR", "USDTRY"]; A0 = pd.Timestamp("2024-01-01")
qc.NONFX_COST.update({p: 5e-4 for p in PAIRS})   # 仮定コスト 5 bps 往復(docs/277 §2)
def load_ask(sym):
    f = f"data_dukascopy/{sym}_hour_ask.csv.gz"
    if not os.path.exists(f): return None
    a = pd.read_csv(f); a["t"] = pd.to_datetime(a["timestamp"]); a = a.set_index("t").sort_index(); return a[~a.index.duplicated(keep="last")]["open"]
cum = int(sys.argv[1]); R = Runner("Q29b", cum, 9, "results/q29b_em_roll.csv")
for pair in PAIRS:
    df = load(pair); selfcheck(pair, df); o = df["open"]; days = pd.DatetimeIndex(sorted(set(df.index.normalize())))
    carry = rate_series("USD", days) - rate_series(pair[3:], days)
    print(f"[{pair}] carry pp: min {carry.min():.2f} max {carry.max():.2f}  門 ≥1pp の日 {(carry.abs()>=1).mean()*100:.0f}%  bars {len(o)} {o.index[0].date()}〜{o.index[-1].date()}")
    for dow, dlab in ((2, "Wed"), (1, "Tue")):
        t = o.index[(o.index.dayofweek == dow) & (o.index.hour == 20)]; cy = carry.reindex(t.normalize()).values
        m = (np.abs(cy) >= 1.0) & ~np.isnan(cy); tt = t[m]; d = -np.sign(cy[m]); te = tt + pd.Timedelta(hours=4)
        r = trades(pair, tt, o.reindex(tt).values, d, o.reindex(te).values)
        R.add("EM ロール", pair, f"{dlab} 20-00UTC gate1 sign=-carry assumed 5bps", r)
        if dow == 2:
            ask = load_ask(pair)
            if ask is None: print(f"  {pair} ask ファイル無し → 実測セルは未判定"); R.add("EM ロール", pair, "Wed 20-00UTC gate1 measured 2024-01〜", pd.Series(dtype=float, index=pd.DatetimeIndex([]))); continue
            t2 = tt[tt >= A0]; te2 = t2 + pd.Timedelta(hours=4); d2 = d[tt >= A0]
            # LONG: ask で買い bid(open)で売る。SHORT: bid で売り ask で買い戻す
            pin = np.where(d2 > 0, ask.reindex(t2).values, o.reindex(t2).values); pout = np.where(d2 > 0, o.reindex(te2).values, ask.reindex(te2).values)
            meas = pd.Series(d2 * (pout / pin - 1), index=t2).dropna()
            mid_in = (o.reindex(t2).values + ask.reindex(t2).values) / 2; mid_out = (o.reindex(te2).values + ask.reindex(te2).values) / 2
            gross = pd.Series(d2 * (mid_out / mid_in - 1), index=t2).dropna()
            print(f"  {pair} Wed 実測(2024-01〜): 取引 {len(meas)} 粗利 {gross.mean()*1e4:.2f} bps 純 {meas.mean()*1e4:.2f} bps 実測往復 {(gross.mean()-meas.mean())*1e4:.2f} bps")
            R.add("EM ロール", pair, "Wed 20-00UTC gate1 measured 2024-01〜", meas)
R.finish()
