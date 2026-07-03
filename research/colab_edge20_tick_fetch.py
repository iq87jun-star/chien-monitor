# -*- coding: utf-8 -*-
"""
colab_edge20_tick_fetch.py — edge20(docs/108): Dukascopyティック取得(ユーザーColab用)。
v2: 並列ダウンロード(16スレッド)で約5〜10分に高速化。再開可能(取得済み日はスキップ)。

使い方(Colab):
  from google.colab import drive; drive.mount('/content/drive')
  !python colab_edge20_tick_fetch.py
出力: {DRIVE_BASE}/tick_edge20/{PAIR}_m1.parquet (1分足集約・約20-30MB)
仕様(docs/108 §1固定): EURJPY/GBPJPY/USDJPY × 月・火曜 × 03-12時UTC × 2023-07-01..2026-06-30
"""
import os, lzma, struct, time, datetime as dt, urllib.request
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
OUT_DIR = (f"{DRIVE_BASE}/tick_edge20" if os.path.isdir("/content/drive/MyDrive")
           else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tick_edge20"))
PAIRS = {"EURJPY": 0.001, "GBPJPY": 0.001, "USDJPY": 0.001}   # Dukascopy point
START, END = dt.date(2023, 7, 1), dt.date(2026, 6, 30)
HOURS = list(range(3, 13))    # 03..12 UTC
WEEKDAYS = (0, 1)             # 月曜・火曜
WORKERS = 16
CHECKPOINT_DAYS = 60


def fetch_hour(pair, day, hour, point, retries=3):
    url = (f"https://datafeed.dukascopy.com/datafeed/{pair}/{day.year}/"
           f"{day.month-1:02d}/{day.day:02d}/{hour:02d}h_ticks.bi5")   # 月は0始まり
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=30).read()
            if len(raw) == 0:
                return day, hour, []
            d = lzma.decompress(raw)
            base = dt.datetime.combine(day, dt.time(hour), tzinfo=dt.timezone.utc)
            out = [(base + dt.timedelta(milliseconds=struct.unpack(">I", d[i:i+4])[0]),
                    struct.unpack(">I", d[i+4:i+8])[0] * point,
                    struct.unpack(">I", d[i+8:i+12])[0] * point)
                   for i in range(0, len(d) - 19, 20)]
            return day, hour, out
        except Exception as e:
            if a == retries - 1:
                print(f"  SKIP {pair} {day} {hour:02d}h: {type(e).__name__}")
                return day, hour, None
            time.sleep(1.5 * (a + 1))


def to_m1(ticks):
    df = pd.DataFrame(ticks, columns=["t", "ask", "bid"])
    df["spread_bps"] = (df["ask"] - df["bid"]) / ((df["ask"] + df["bid"]) / 2) * 1e4
    df = df.set_index("t")
    g = df.resample("1min")
    m1 = pd.DataFrame(dict(bid=g["bid"].median(), ask=g["ask"].median(),
                           spread_bps=g["spread_bps"].median(), n_ticks=g["bid"].count()))
    return m1.dropna(subset=["bid"])


def target_days():
    d, out = START, []
    while d <= END:
        if d.weekday() in WEEKDAYS:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for pair, point in PAIRS.items():
        t0 = time.time()
        path = os.path.join(OUT_DIR, f"{pair}_m1.parquet")
        acc, done_days = [], set()
        if os.path.exists(path):
            prev = pd.read_parquet(path)
            acc = [prev]
            done_days = set(pd.Series(prev.index.date).unique())
            print(f"{pair}: 既存 {len(prev)} 行 / {len(done_days)} 日 → 続きから")
        days = [d for d in target_days() if d not in done_days]
        if not days:
            print(f"{pair}: 取得済み"); continue
        print(f"{pair}: {len(days)}日 × {len(HOURS)}時間 を{WORKERS}並列で取得")
        buf, day_ticks = [], {}
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            for i0 in range(0, len(days), CHECKPOINT_DAYS):
                chunk = days[i0:i0 + CHECKPOINT_DAYS]
                futs = [ex.submit(fetch_hour, pair, d, h, point) for d in chunk for h in HOURS]
                day_ticks = {d: [] for d in chunk}
                for f in futs:
                    d, h, ticks = f.result()
                    if ticks:
                        day_ticks[d].extend(ticks)
                for d in chunk:
                    if day_ticks[d]:
                        buf.append(to_m1(sorted(day_ticks[d])))
                pd.concat(acc + buf).sort_index().to_parquet(path)
                print(f"  {pair}: {chunk[-1]} まで保存 ({i0+len(chunk)}/{len(days)}日, {time.time()-t0:.0f}s)")
        print(f"{pair}: 完了 {time.time()-t0:.0f}s → {path}")


if __name__ == "__main__":
    main()
