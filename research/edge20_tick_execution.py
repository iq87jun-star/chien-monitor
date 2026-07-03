# -*- coding: utf-8 -*-
"""
edge20_tick_execution.py — edge20(docs/108)の解析ハーネス。colab_edge20_tick_fetch.py の
出力(1分足集約parquet)から H20a/H20b/H20c を採点する。Colab/ローカル両対応。

出力: edge20_tick_execution.json(Drive優先、なければ research/results/)→ docs/109 へ転記。
規律: 時刻セットは事前登録の3つのみ。リターン系の新パターン探索はしない。
"""
import os, json, datetime as dt
import numpy as np, pandas as pd

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
IN_DIR = (f"{DRIVE_BASE}/tick_edge20" if os.path.isdir("/content/drive/MyDrive")
          else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tick_edge20"))
OUT_PATH = (f"{DRIVE_BASE}/tick_edge20/edge20_tick_execution.json"
            if os.path.isdir("/content/drive/MyDrive")
            else os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "edge20_tick_execution.json"))
PAIRS = ["EURJPY", "GBPJPY", "USDJPY"]
PIP = 0.01
HOUR_SETS = {"base_04061810": [4, 6, 8, 10],      # 現行(基準)
             "alt_03050709": [3, 5, 7, 9],
             "alt_05070911": [5, 7, 9, 11]}
BLOCKS = [("Y1", "2023-07-01", "2024-06-30"), ("Y2", "2024-07-01", "2025-06-30"),
          ("Y3", "2025-07-01", "2026-06-30")]


def load(pair):
    df = pd.read_parquet(os.path.join(IN_DIR, f"{pair}_m1.parquet")).sort_index()
    idx = pd.to_datetime(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    df.index = idx
    df["pips"] = (df["ask"] - df["bid"]) / PIP
    return df


def h20a(dfs):
    out = {}
    for pair, df in dfs.items():
        mon = df[df.index.weekday == 0]
        byh = {}
        for h in range(3, 13):
            s = mon[mon.index.hour == h]["pips"].dropna()
            if len(s) == 0:
                continue
            byh[h] = dict(median_pips=round(float(s.median()), 2),
                          p90=round(float(s.quantile(.90)), 2),
                          p95=round(float(s.quantile(.95)), 2), n_min=int(len(s)))
        out[pair] = byh
    return out


def first_minute_price(df, day, hour, col):
    w = df[(df.index.date == day) & (df.index.hour == hour)]
    return float(w[col].iloc[0]) if len(w) else None


def h20b(dfs):
    res = {}
    for name, hours in HOUR_SETS.items():
        per_block = {}
        for bname, b0, b1 in BLOCKS:
            tot = 0.0; nshots = 0
            for pair, df in dfs.items():
                sub = df[(df.index >= pd.Timestamp(b0, tz="UTC")) & (df.index <= pd.Timestamp(b1, tz="UTC") + pd.Timedelta(days=1))]
                mondays = sorted(set(sub[sub.index.weekday == 0].index.date))
                for d in mondays:
                    d2 = d + dt.timedelta(days=1)
                    for h in hours:
                        e = first_minute_price(sub, d, h, "ask")
                        x = first_minute_price(sub, d2, h, "bid")
                        if e and x and e > 0:
                            tot += (x / e - 1.0); nshots += 1
            per_block[bname] = dict(net_pct=round(tot * 100, 3), shots=nshots)
        res[name] = per_block
    # 決定規則1: 代替が3ブロック全てで基準を上回る場合のみ提案
    base = res["base_04061810"]
    winner = None
    for name in ("alt_03050709", "alt_05070911"):
        if all(res[name][b]["net_pct"] > base[b]["net_pct"] for b, _, _ in BLOCKS):
            winner = name
            break
    return res, winner


def h20c(dfs):
    out = {}
    for pair, df in dfs.items():
        mon = df[(df.index.weekday == 0) & (df.index.hour.isin(HOUR_SETS["base_04061810"]))]
        s = mon["pips"].dropna()
        p95 = float(s.quantile(.95))
        out[pair] = dict(entry_hours_median_pips=round(float(s.median()), 2),
                         p95=round(p95, 2),
                         proposed_MaxSpreadPips=round(p95 * 1.2, 1),
                         pct_minutes_over_3pips=round(float((s > 3.0).mean() * 100), 2))
    return out


def main():
    dfs = {}
    for p in PAIRS:
        f = os.path.join(IN_DIR, f"{p}_m1.parquet")
        if not os.path.exists(f):
            print(f"⚠ {f} なし — 先に colab_edge20_tick_fetch.py を実行"); return
        dfs[p] = load(p)
        print(f"{p}: {len(dfs[p])} 分足行 {dfs[p].index.min()}..{dfs[p].index.max()}")

    a = h20a(dfs)
    b, winner = h20b(dfs)
    c = h20c(dfs)
    # 決定規則3: 実測往復コスト(スプレッド中央値×2側面≒往復) vs 検証仮定(≈2pips往復)
    med_entry = np.mean([c[p]["entry_hours_median_pips"] for p in PAIRS])
    cost_flag = bool(med_entry * 1.0 > 2.0 * 2)   # 中央スプレッド(片側)が仮定往復2pipsの2倍相当を超えるか

    out = dict(prereg="docs/108",
               h20a_spread_by_hour=a,
               h20b_hourset_compare=b,
               h20b_winner=(winner or "変更なし(基準維持)"),
               h20c_spread_cap=c,
               cost_reinterpretation_needed=cost_flag,
               note="時刻セット変更/上限変更は提案止まり。実装は承認+デモ後(docs/108 §3)")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:2000])
    print("保存:", OUT_PATH, "→ docs/109 へ転記")


if __name__ == "__main__":
    main()
