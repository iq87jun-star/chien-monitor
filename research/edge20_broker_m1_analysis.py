# -*- coding: utf-8 -*-
"""
edge20_broker_m1_analysis.py — edge20(docs/108 §5改訂)の解析本体。
入力: Chien_TickExport_Edge20 が出力したブローカー実データCSV
  - TicksM1_EURJPY.csv (ティック1分集約・2.5年)   … 主データ
  - RatesM1_{EURJPY,GBPJPY,USDJPY}.csv (M1・直近3ヶ月) … 補助(3ペアの現行スプレッド)
サーバー時刻→UTC: EET(EU夏時間ルール, 夏+3/冬+2)。米指標8:30ET=サーバー15:30の
通年スパイクで実証済み(docs/109に記録)。

採点(docs/108 §2-3・§5読み替え):
  H20a: 月曜のUTC時刻別スプレッド分布
  H20b: 時刻セット3種(事前列挙)の実bid/ask執行比較 — 全期間3等分ブロック全勝でのみ変更提案
  H20c: InpMaxSpreadPips 校正(実測p95×1.2)
使い方: python3 edge20_broker_m1_analysis.py <データディレクトリ>
出力: results/edge20_broker_execution.json
"""
import os, sys, json, hashlib
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PAIRS = ["EURJPY", "GBPJPY", "USDJPY"]
HOUR_SETS = {"base_04060810": [4, 6, 8, 10],
             "alt_03050709": [3, 5, 7, 9],
             "alt_05070911": [5, 7, 9, 11]}


def eu_dst_on(ts):
    """EU夏時間(3月最終日曜〜10月最終日曜)。EETサーバー: 夏+3/冬+2"""
    y = ts.year
    mar = pd.Timestamp(y, 3, 31); mar -= pd.Timedelta(days=(mar.weekday() + 1) % 7)
    oct_ = pd.Timestamp(y, 10, 31); oct_ -= pd.Timedelta(days=(oct_.weekday() + 1) % 7)
    return mar <= ts.normalize() < oct_


def to_utc(df, col="t"):
    off = df[col].apply(lambda x: 3 if eu_dst_on(x) else 2)
    df["t_utc"] = df[col] - pd.to_timedelta(off, unit="h")
    return df


def load_ticks(path):
    df = pd.read_csv(path)
    df["t"] = pd.to_datetime(df["time_server"], format="%Y.%m.%d %H:%M")
    df = to_utc(df)
    df["mid"] = (df["bid_avg"] + df["ask_avg"]) / 2
    return df


def load_rates(path):
    df = pd.read_csv(path)
    df["t"] = pd.to_datetime(df["time_server"], format="%Y.%m.%d %H:%M")
    return to_utc(df)


def blocks3(df):
    t0, t1 = df["t_utc"].min(), df["t_utc"].max()
    edges = [t0, t0 + (t1 - t0) / 3, t0 + 2 * (t1 - t0) / 3, t1 + pd.Timedelta(minutes=1)]
    return [(f"B{i+1}", edges[i], edges[i + 1]) for i in range(3)]


def h20a(ticks, rates):
    out = {"EURJPY_ticks_2.5y": {}, "rates_3mo": {}}
    mon = ticks[ticks["t_utc"].dt.weekday == 0]
    for h in range(3, 13):
        s = mon[mon["t_utc"].dt.hour == h]
        if len(s) == 0:
            continue
        out["EURJPY_ticks_2.5y"][h] = dict(
            median=round(float(s["spread_pips_avg"].median()), 2),
            p90=round(float(s["spread_pips_avg"].quantile(.9)), 2),
            p95_avg=round(float(s["spread_pips_avg"].quantile(.95)), 2),
            p95_max=round(float(s["spread_pips_max"].quantile(.95)), 2))
    for p, df in rates.items():
        mon = df[df["t_utc"].dt.weekday == 0]
        out["rates_3mo"][p] = {
            h: dict(median=round(float(g["spread_pips_open"].median()), 2),
                    p95=round(float(g["spread_pips_open"].quantile(.95)), 2))
            for h, g in mon.groupby(mon["t_utc"].dt.hour) if 3 <= h <= 12}
    return out


def entry_exit(ticks, day, hour):
    """月曜UTC hourの最初の分のask → 翌日同時刻のbid(5分以内の最初の分)"""
    def first(dfday, col):
        w = dfday[dfday["t_utc"].dt.hour == hour].sort_values("t_utc")
        w = w[w["t_utc"].dt.minute <= 5]
        return float(w[col].iloc[0]) if len(w) else None
    d0 = ticks[ticks["t_utc"].dt.date == day]
    d1 = ticks[ticks["t_utc"].dt.date == day + pd.Timedelta(days=1)]
    e = first(d0, "ask_avg"); x = first(d1, "bid_avg")
    return (e, x)


def h20b(ticks):
    mon_days = sorted(set(ticks[ticks["t_utc"].dt.weekday == 0]["t_utc"].dt.date))
    res = {}
    bl = blocks3(ticks)
    for name, hours in HOUR_SETS.items():
        per = {}
        for bname, b0, b1 in bl:
            tot, n = 0.0, 0
            for d in mon_days:
                if not (b0.date() <= d < b1.date()):
                    continue
                for h in hours:
                    e, x = entry_exit(ticks, d, h)
                    if e and x and e > 0:
                        tot += x / e - 1.0; n += 1
            per[bname] = dict(net_pct=round(tot * 100, 3), shots=n)
        res[name] = per
    base = res["base_04060810"]
    winner = None
    for name in ("alt_03050709", "alt_05070911"):
        if all(res[name][b]["net_pct"] > base[b]["net_pct"] for b, _, _ in bl):
            winner = name; break
    return res, winner, [(b, str(x.date()), str(y.date())) for b, x, y in bl]


def h20c(ticks, rates):
    out = {}
    ent = HOUR_SETS["base_04060810"]
    mon = ticks[(ticks["t_utc"].dt.weekday == 0) & (ticks["t_utc"].dt.hour.isin(ent))]
    p95a = float(mon["spread_pips_avg"].quantile(.95))
    p95m = float(mon["spread_pips_max"].quantile(.95))
    out["EURJPY"] = dict(median=round(float(mon["spread_pips_avg"].median()), 2),
                         p95_avg=round(p95a, 2), p95_minute_max=round(p95m, 2),
                         proposed_MaxSpreadPips=round(p95m * 1.2, 1),
                         pct_minutes_over_3pips=round(float((mon["spread_pips_avg"] > 3).mean() * 100), 2))
    for p, df in rates.items():
        mon = df[(df["t_utc"].dt.weekday == 0) & (df["t_utc"].dt.hour.isin(ent))]
        p95 = float(mon["spread_pips_open"].quantile(.95))
        out[p + "_3mo"] = dict(median=round(float(mon["spread_pips_open"].median()), 2),
                               p95=round(p95, 2), proposed_MaxSpreadPips=round(p95 * 1.2, 1),
                               pct_minutes_over_3pips=round(float((mon["spread_pips_open"] > 3).mean() * 100), 2))
    return out


def main():
    ddir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data", "tick_edge20")
    tick_path = os.path.join(ddir, "TicksM1_EURJPY.csv")
    ticks = load_ticks(tick_path)
    rates = {p: load_rates(os.path.join(ddir, f"RatesM1_{p}.csv")) for p in PAIRS}
    hashes = {os.path.basename(f): hashlib.sha256(open(f, "rb").read()).hexdigest()[:16]
              for f in [tick_path] + [os.path.join(ddir, f"RatesM1_{p}.csv") for p in PAIRS]}
    a = h20a(ticks, rates)
    b, winner, bl = h20b(ticks)
    c = h20c(ticks, rates)
    # 実測往復コスト(=スプレッド1回分) vs 検証仮定(往復2pips)
    med_cost = a["EURJPY_ticks_2.5y"].get(6, {}).get("median")
    out = dict(prereg="docs/108(§5改訂)", input_sha256=hashes,
               server_tz="EET(夏UTC+3/冬UTC+2)・米8:30ET=サーバー15:30スパイクで実証",
               tick_window=f"{ticks['t_utc'].min()}..{ticks['t_utc'].max()}",
               blocks=bl,
               h20a=a, h20b=b, h20b_winner=(winner or "変更なし(基準セット維持)"),
               h20c=c,
               cost_note=f"EURJPY月曜エントリー時間帯の中央スプレッド≈{med_cost}pips(検証仮定=往復2pips)")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", "edge20_broker_execution.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print("保存:", path)


if __name__ == "__main__":
    main()
