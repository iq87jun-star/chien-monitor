# -*- coding: utf-8 -*-
"""
colab_edge20_tick_fetch.py — edge20(docs/108): Dukascopyティック取得(ユーザーColab用)。

使い方(Colab):
  1) ランタイム接続 → 新しいセルに:
       from google.colab import drive; drive.mount('/content/drive')
       !python colab_edge20_tick_fetch.py
     (本ファイルをアップロードするか、リポジトリをcloneして research/ から実行)
  2) 出力: {DRIVE_BASE}/tick_edge20/{PAIR}_m1.parquet (1分足集約・約20-30MB)
  3) 続けて edge20_tick_execution.py を実行

仕様(docs/108 §1固定):
  EURJPY/GBPJPY/USDJPY × 月曜・火曜 × 03-12時UTC × 2023-07-01..2026-06-30
  bi5(LZMA)→ティック→1分足(bid/ask中央値・スプレッド中央値bps・ティック数)に集約。
  再開可能(取得済み日はスキップ)。ネットワークエラーはリトライ後スキップ(ログに記録)。
"""
import os, io, lzma, struct, time, datetime as dt, urllib.request
import pandas as pd, numpy as np

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
OUT_DIR = (f"{DRIVE_BASE}/tick_edge20" if os.path.isdir("/content/drive/MyDrive")
           else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tick_edge20"))
PAIRS = {"EURJPY": 0.001, "GBPJPY": 0.001, "USDJPY": 0.001}   # Dukascopy point
START, END = dt.date(2023, 7, 1), dt.date(2026, 6, 30)
HOURS = range(3, 13)          # 03..12 UTC
WEEKDAYS = (0, 1)             # 月曜・火曜


def fetch_hour(pair, day, hour, point, retries=3):
    # Dukascopy URLの月は0始まり
    url = (f"https://datafeed.dukascopy.com/datafeed/{pair}/{day.year}/"
           f"{day.month-1:02d}/{day.day:02d}/{hour:02d}h_ticks.bi5")
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=30).read()
            if len(raw) == 0:
                return []
            d = lzma.decompress(raw)
            base = dt.datetime.combine(day, dt.time(hour), tzinfo=dt.timezone.utc)
            out = []
            for i in range(0, len(d) - 19, 20):
                ms, ask, bid, _, _ = struct.unpack(">IIIff", d[i:i+20])
                out.append((base + dt.timedelta(milliseconds=ms), ask * point, bid * point))
            return out
        except Exception as e:
            if a == retries - 1:
                print(f"  SKIP {pair} {day} {hour:02d}h: {type(e).__name__}")
                return None
            time.sleep(2 * (a + 1))


def to_m1(ticks):
    df = pd.DataFrame(ticks, columns=["t", "ask", "bid"])
    df["spread_bps"] = (df["ask"] - df["bid"]) / ((df["ask"] + df["bid"]) / 2) * 1e4
    df = df.set_index("t")
    g = df.resample("1min")
    m1 = pd.DataFrame(dict(bid=g["bid"].median(), ask=g["ask"].median(),
                           spread_bps=g["spread_bps"].median(), n_ticks=g["bid"].count()))
    return m1.dropna(subset=["bid"])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for pair, point in PAIRS.items():
        path = os.path.join(OUT_DIR, f"{pair}_m1.parquet")
        done_days = set()
        acc = []
        if os.path.exists(path):
            prev = pd.read_parquet(path)
            acc = [prev]
            done_days = set(pd.to_datetime(prev.index.date).date if hasattr(pd.to_datetime(prev.index), 'date')
                            else prev.index.normalize().unique().date)
            done_days = set(pd.Series(prev.index.date).unique())
            print(f"{pair}: 既存 {len(prev)} 行 / {len(done_days)} 日 → 続きから")
        day = START
        buf = []
        n_new = 0
        while day <= END:
            if day.weekday() in WEEKDAYS and day not in done_days:
                day_ticks = []
                for h in HOURS:
                    t = fetch_hour(pair, day, h, point)
                    if t:
                        day_ticks.extend(t)
                    time.sleep(0.12)
                if day_ticks:
                    buf.append(to_m1(day_ticks)); n_new += 1
                if n_new and n_new % 20 == 0:
                    pd.concat(acc + buf).sort_index().to_parquet(path)
                    print(f"{pair}: {day} まで保存({n_new}日追加)")
            day += dt.timedelta(days=1)
        if buf or acc:
            pd.concat(acc + buf).sort_index().to_parquet(path)
        print(f"{pair}: 完了 → {path}")


if __name__ == "__main__":
    main()
