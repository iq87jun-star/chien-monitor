#!/usr/bin/env python3
"""公開ソースから10年データを取得し research/data（または CHIEN_DATA_DIR）に保存する。

出典（docs/26 の方法論と整合）:
  - 日足/多資産: Yahoo Finance（yfinance）。SPX=^GSPC, VIX=^VIX, XAUUSD=GC=F,
    USDJPY=JPY=X, EURJPY=EURJPY=X, GBPJPY=GBPJPY=X。
  - 米2年金利 US2Y: FRED 系列 DGS2（CSV 直 DL、APIキー不要）。
  - 円クロス H1: Dukascopy（dukascopy-python、ベストエフォート）。失敗時は v7 相関を
    日足プロキシで代替（lib/v7_reference）。

使い方（Colab 推奨。ネットワーク必要）:
    export CHIEN_DATA_DIR=/content/drive/MyDrive/chien-monitor/data
    python3 research/fetch_data.py            # 全部
    python3 research/fetch_data.py --no-h1    # 日足のみ（速い）
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import data as _data  # noqa: E402

START, END = "2016-01-01", "2025-12-31"

YF_DAILY = {           # 保存名: Yahoo ティッカー
    "SPX": "^GSPC",
    "VIX": "^VIX",
    "XAUUSD": "GC=F",
    "USDJPY": "JPY=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
}
H1_PAIRS = ["EURJPY", "GBPJPY", "USDJPY"]


def _out_dir() -> str:
    d = os.environ.get("CHIEN_DATA_DIR") or _data.LOCAL_DEFAULT
    os.makedirs(d, exist_ok=True)
    return d


def _save(df: pd.DataFrame, path: str, label: str):
    df.to_csv(path, index=False)
    print(f"  [OK] {label}: {len(df)} 行 -> {path}  ({df['time'].min().date()}..{df['time'].max().date()})")


# ----------------------------------------------------------------- Yahoo daily
def fetch_yf_daily(out: str):
    import yfinance as yf
    print("== Yahoo 日足 ==")
    for name, tkr in YF_DAILY.items():
        try:
            df = yf.download(tkr, start=START, end=END, interval="1d",
                             auto_adjust=False, progress=False)
            if df is None or len(df) == 0:
                print(f"  [WARN] {name} ({tkr}) 空")
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            df = df.rename(columns={df.columns[0]: "time"})
            df.columns = [str(c).lower() for c in df.columns]
            o = df[["time", "open", "high", "low", "close"]].dropna()
            o["time"] = pd.to_datetime(o["time"], utc=True)
            _save(o, os.path.join(out, f"{name}_d.csv"), name)
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR] {name} ({tkr}): {type(e).__name__}: {e}")


# ----------------------------------------------------------------- FRED US2Y
def fetch_fred_us2y(out: str):
    fetch_fred_series(out, "DGS2", "US2Y")


def fetch_fred_series(out: str, series_id: str, name: str):
    # 全期間一括は 504 になりやすいので年次チャンクで取得して結合。
    import io
    import time
    import urllib.request
    print(f"== FRED {name} ({series_id}) ==")
    frames = []
    for y in range(int(START[:4]), int(END[:4]) + 1):
        url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
               f"&cosd={y}-01-01&coed={y}-12-31")
        raw = None
        for i in range(4):
            try:
                raw = urllib.request.urlopen(url, timeout=20).read()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1.5 * (i + 1))
        if raw is None:
            print(f"  [WARN] {name} {y} 取得失敗")
            continue
        frames.append(pd.read_csv(io.BytesIO(raw)))
    if not frames:
        print(f"  [ERR] {name} 全滅")
        return
    d = pd.concat(frames, ignore_index=True)
    d.columns = ["time", "v"]
    d["time"] = pd.to_datetime(d["time"], utc=True)
    d["v"] = pd.to_numeric(d["v"].replace(".", np.nan), errors="coerce")
    d = d.dropna(subset=["v"]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    out_df = pd.DataFrame({"time": d["time"], "open": d["v"], "high": d["v"],
                           "low": d["v"], "close": d["v"]})
    _save(out_df, os.path.join(out, f"{name}_d.csv"), name)


# ----------------------------------------------------------------- Dukascopy H1
def _duka_const(mod, *needles):
    for name in dir(mod):
        up = name.upper()
        if all(n in up for n in needles):
            return getattr(mod, name)
    return None


def fetch_dukascopy_h1(out: str):
    print("== Dukascopy 円クロス H1（ベストエフォート）==")
    try:
        import dukascopy_python
        from dukascopy_python import instruments as inst
    except Exception as e:  # noqa: BLE001
        print(f"  [SKIP] dukascopy-python 未導入: {e}")
        print("        -> pip install dukascopy-python  で導入可。")
        print("        未取得でも v7 相関は日足プロキシで代替されます。")
        return
    interval = _duka_const(dukascopy_python, "HOUR_1") or _duka_const(dukascopy_python, "HOUR")
    side = _duka_const(dukascopy_python, "OFFER_SIDE_BID") or _duka_const(dukascopy_python, "BID")
    needle = {"EURJPY": ("EUR", "JPY"), "GBPJPY": ("GBP", "JPY"), "USDJPY": ("USD", "JPY")}
    start = pd.Timestamp(START, tz="UTC")
    end = pd.Timestamp(END, tz="UTC")
    for name in H1_PAIRS:
        instr = _duka_const(inst, *needle[name])
        if instr is None or interval is None or side is None:
            print(f"  [WARN] {name}: 定数解決できず（API差異）。スキップ。")
            continue
        try:
            df = dukascopy_python.fetch(instr, interval, side, start, end)
            if df is None or len(df) == 0:
                print(f"  [WARN] {name} 空")
                continue
            df = df.reset_index()
            df.columns = [str(c).lower() for c in df.columns]
            df = df.rename(columns={df.columns[0]: "time"})
            o = df[["time", "open", "high", "low", "close"]].dropna()
            o["time"] = pd.to_datetime(o["time"], utc=True)
            _save(o, os.path.join(out, f"{name}_h1.csv"), f"{name} H1")
        except Exception as e:  # noqa: BLE001
            print(f"  [ERR] {name} H1: {type(e).__name__}: {e}")


def fetch_fomc_events(out: str):
    """E5 用イベント日: FOMC 声明発表日を federalreserve.gov 公式から抽出（捏造なし）。
    声明 URL `monetaryYYYYMMDD*.htm` のリンクを各カレンダー/historical ページから拾う。
    BOJ は機械可読な一次ソースが乏しく未対応（必要なら手動で行追加）。
    """
    import re
    import urllib.request
    print("== FOMC イベント日 (federalreserve.gov) ==")
    pages = ["https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"]
    for y in range(int(START[:4]), 2021):
        pages.append(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm")
    dates = set()
    for u in pages:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            h = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] {u.split('/')[-1]}: {e}")
            continue
        dates.update(re.findall(r"monetary(\d{8})[a-z]?\d?\.htm", h))
    dts = sorted(d for d in dates if START[:4] <= d[:4] <= END[:4])
    if not dts:
        print("  [WARN] FOMC 日が取れず（E5 は SKIP）")
        return
    df = pd.DataFrame({"time": pd.to_datetime(dts, format="%Y%m%d", utc=True), "kind": "FOMC"})
    df = df.drop_duplicates("time").sort_values("time")
    path = os.path.join(out, "events_cb_d.csv")
    # 既存に手動の BOJ 行などがあれば残してマージ
    if os.path.exists(path):
        old = pd.read_csv(path)
        old["time"] = pd.to_datetime(old["time"], utc=True)
        df = pd.concat([old[old["kind"] != "FOMC"], df]).drop_duplicates("time").sort_values("time")
    df.to_csv(path, index=False)
    print(f"  [OK] FOMC {len(dts)} 日 -> {path}")


def fetch_boj_events(out: str):
    """E5 用イベント日: BOJ 金融政策決定会合(MPM)の決定日を boj.or.jp 議事要旨から網羅取得。
    `mpmsche_minu/minu_{year}/index.htm` の全会合を拾い、決定日=会合2日目に補正
    （月跨ぎ "October 31 and November 1" 対応）。既存 events に BOJ 行をマージ。
    """
    import re
    import urllib.request
    print("== BOJ イベント日 (boj.or.jp 議事要旨) ==")
    mon = {m: i + 1 for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"])}
    days = set()
    for y in range(int(START[:4]), int(END[:4]) + 1):
        u = f"https://www.boj.or.jp/en/mopo/mpmsche_minu/minu_{y}/index.htm"
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            h = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] BOJ {y}: {e}")
            continue
        for m1, d1, m2, d2, yr in re.findall(r"([A-Z][a-z]+) (\d{1,2}) and ([A-Z][a-z]+) (\d{1,2}), (\d{4})", h):
            days.add(f"{yr}-{mon[m2]:02d}-{int(d2):02d}")
        for m, d1, d2, yr in re.findall(r"([A-Z][a-z]+) (\d{1,2}) and (\d{1,2}), (\d{4})", h):
            days.add(f"{yr}-{mon[m]:02d}-{int(d2):02d}")
        for m, d, yr in re.findall(r"Meeting on ([A-Z][a-z]+) (\d{1,2}), (\d{4})", h):
            days.add(f"{yr}-{mon[m]:02d}-{int(d):02d}")
    days = sorted(d for d in days if START[:4] <= d[:4] <= END[:4])
    if not days:
        print("  [WARN] BOJ 日が取れず")
        return
    df = pd.DataFrame({"time": pd.to_datetime(days, utc=True), "kind": "BOJ"})
    path = os.path.join(out, "events_cb_d.csv")
    if os.path.exists(path):
        old = pd.read_csv(path)
        old["time"] = pd.to_datetime(old["time"], utc=True)
        df = pd.concat([old[old["kind"] != "BOJ"], df]).drop_duplicates("time").sort_values("time")
    df.to_csv(path, index=False)
    print(f"  [OK] BOJ {len(days)} 日 -> {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-h1", action="store_true", help="円クロス H1（Dukascopy）を取得しない")
    args = ap.parse_args()
    out = _out_dir()
    print(f"保存先: {out}\n期間: {START}..{END}\n")
    try:
        import yfinance  # noqa: F401
    except Exception:
        print("[setup] pip install yfinance ...")
        os.system(f"{sys.executable} -m pip -q install yfinance")
    fetch_yf_daily(out)
    fetch_fred_series(out, "DGS2", "US2Y")
    fetch_fred_series(out, "DGS10", "US10Y")
    fetch_fomc_events(out)
    fetch_boj_events(out)
    if not args.no_h1:
        fetch_dukascopy_h1(out)
    print("\n完了。次: python3 research/run_all.py")


if __name__ == "__main__":
    main()
