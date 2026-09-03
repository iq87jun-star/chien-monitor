# -*- coding: utf-8 -*-
"""
dukascopy_fetch.py — Dukascopy datafeed から日足/時間足/ティックを取得して CSV 化する(B-1・docs/84 の別ソース再現用)。
依存: Python 3 標準ライブラリのみ(urllib / lzma / struct)。Cowork(ローカルPC)で実行する想定。

使い方(リポジトリ直下で):
  python research/tools/dukascopy_fetch.py --probe                       # 疎通確認(1ファイル)
  python research/tools/dukascopy_fetch.py --tf day  --from 2003-01-01    # E5用: 金+指数3 の日足(既定セット)
  python research/tools/dukascopy_fetch.py --tf hour --from 2016-01-01 --syms GBPJPY,AUDJPY,USDJPY,EURJPY   # v7/v9 追認用 H1
  python research/tools/dukascopy_fetch.py --tf tick --from 2026-06-01 --to 2026-08-31 --syms GBPJPY        # 執行層(bid/ask)

出力: research/data_dukascopy/<SYM>_<tf>.csv  (timestamp,open,high,low,close[,volume] / tick は timestamp,bid,ask)
既存ファイルはスキップ(再開可)。Dukascopy は月=0始まりの URL 規約。
"""
import os, sys, io, lzma, struct, time, argparse, datetime as dt, urllib.request, urllib.error, csv

BASE = "https://datafeed.dukascopy.com/datafeed"
# 本プロジェクトの銘柄名 → Dukascopy インスツルメント名, 価格スケール(整数→価格)
INSTR = {
    "XAUUSD": ("XAUUSD", 1000), "XAGUSD": ("XAGUSD", 1000),
    "US500": ("USA500IDXUSD", 1000), "NAS100": ("USATECHIDXUSD", 1000), "GER40": ("DEUIDXEUR", 1000),
    "UK100": ("GBRIDXGBP", 1000), "JP225": ("JPNIDXJPY", 1000), "FR40": ("FRAIDXEUR", 1000),
    "EURUSD": ("EURUSD", 100000), "GBPUSD": ("GBPUSD", 100000), "AUDUSD": ("AUDUSD", 100000), "NZDUSD": ("NZDUSD", 100000),
    "USDCAD": ("USDCAD", 100000), "USDCHF": ("USDCHF", 100000),
    "USDJPY": ("USDJPY", 1000), "EURJPY": ("EURJPY", 1000), "GBPJPY": ("GBPJPY", 1000), "AUDJPY": ("AUDJPY", 1000),
    "NZDJPY": ("NZDJPY", 1000), "CADJPY": ("CADJPY", 1000), "CHFJPY": ("CHFJPY", 1000),
    "BTCUSD": ("BTCUSD", 10), "ETHUSD": ("ETHUSD", 10),
    "WTI": ("LIGHTCMDUSD", 1000), "BRENT": ("BRENTCMDUSD", 1000),
}
E5_DEFAULT = ["XAUUSD", "US500", "NAS100", "GER40"]
UA = {"User-Agent": "Mozilla/5.0"}
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "data_dukascopy"))


class FetchError(RuntimeError): pass

REQ_SLEEP = 2.0     # リクエスト間隔(秒)。Dukascopy は断続的に 503(レート制限)を返す

def get(url, retries=12):
    """404=データ無し(None)。503/429/接続失敗は長めのバックオフで再試行し、尽きたら FetchError(静かに欠損させない)。"""
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                data = r.read(); time.sleep(REQ_SLEEP); return data
        except urllib.error.HTTPError as e:
            if e.code == 404: time.sleep(REQ_SLEEP); return None
            last = f"HTTP {e.code}"
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:60]}"
        wait = min(10 * (i + 1), 60)
        print(f"    retry {i+1}/{retries} ({last}) {wait}s待機: {url.split('/datafeed/')[1]}", flush=True)
        time.sleep(wait)
    raise FetchError(f"取得失敗(再試行{retries}回): {url} 最終エラー={last}")


def decode_candles(raw, scale, base_time):
    """候補足: 24byte レコード = >iiiiif (time_offset_sec, open, close, low, high, volume)"""
    if not raw: return []
    data = lzma.decompress(raw); out = []
    for off in range(0, len(data) - len(data) % 24, 24):
        t, o, c, l, h, v = struct.unpack(">iiiiif", data[off:off + 24])
        out.append((base_time + dt.timedelta(seconds=t), o / scale, h / scale, l / scale, c / scale, v))
    return out


def decode_ticks(raw, scale, base_time):
    """ティック: 20byte = >iiiff (ms_offset, ask, bid, askvol, bidvol)"""
    if not raw: return []
    data = lzma.decompress(raw); out = []
    for off in range(0, len(data) - len(data) % 20, 20):
        ms, ask, bid, av, bv = struct.unpack(">iiiff", data[off:off + 20])
        out.append((base_time + dt.timedelta(milliseconds=ms), bid / scale, ask / scale))
    return out


def fetch_symbol(sym, tf, d0, d1, force=False):
    inst, scale = INSTR[sym]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{sym}_{tf}.csv")
    if os.path.exists(path) and not force:
        print(f"  skip(exists) {path}"); return path
    rows = []
    if tf == "day":                      # 年ファイル
        for y in range(d0.year, d1.year + 1):
            raw = get(f"{BASE}/{inst}/{y}/BID_candles_day_1.bi5")
            rows += decode_candles(raw, scale, dt.datetime(y, 1, 1))
            print(f"  {sym} {y}: {len(rows)} 本", flush=True)
    elif tf == "hour":                   # 月ファイル(URLの月は0始まり)
        y, m = d0.year, d0.month
        while (y, m) <= (d1.year, d1.month):
            raw = get(f"{BASE}/{inst}/{y}/{m - 1:02d}/BID_candles_hour_1.bi5")
            rows += decode_candles(raw, scale, dt.datetime(y, m, 1))
            m += 1
            if m > 12: y, m = y + 1, 1
            if m == 1: print(f"  {sym} {y - 1}: 累計 {len(rows)} 本", flush=True)
    elif tf == "tick":                   # 時間ファイル(1日24本)
        d = d0
        while d <= d1:
            for h in range(24):
                raw = get(f"{BASE}/{inst}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{h:02d}h_ticks.bi5")
                rows += decode_ticks(raw, scale, dt.datetime(d.year, d.month, d.day, h))
            print(f"  {sym} {d}: 累計 {len(rows)} tick", flush=True)
            d += dt.timedelta(days=1)
    rows = [r for r in rows if d0 <= r[0].date() <= d1]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        if tf == "tick":
            w.writerow(["timestamp", "bid", "ask"])
            for t, b, a in rows: w.writerow([t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], b, a])
        else:
            w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            for t, o, h, l, c, v in rows: w.writerow([t.strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c, v])
    print(f"  saved {path} ({len(rows)} rows)  先頭: {rows[0] if rows else '-'}")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", choices=["day", "hour", "tick"], default="day")
    ap.add_argument("--syms", default=",".join(E5_DEFAULT))
    ap.add_argument("--from", dest="d0", default="2003-01-01"); ap.add_argument("--to", dest="d1", default=dt.date.today().isoformat())
    ap.add_argument("--probe", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.probe:
        url = f"{BASE}/EURUSD/2025/00/06/08h_ticks.bi5"
        raw = get(url); print("probe:", url, "->", ("OK %d bytes, %d ticks" % (len(raw), len(decode_ticks(raw, 100000, dt.datetime(2025, 1, 6, 8)))) if raw else "取得不可(None)"))
        raw = get(f"{BASE}/XAUUSD/2024/BID_candles_day_1.bi5"); c = decode_candles(raw, 1000, dt.datetime(2024, 1, 1)) if raw else []
        print("probe day XAUUSD 2024:", len(c), "本", c[:1]); return
    d0, d1 = dt.date.fromisoformat(a.d0), dt.date.fromisoformat(a.d1)
    for s in a.syms.split(","):
        s = s.strip()
        if s not in INSTR: print(f"  未登録の銘柄: {s}(INSTR に追加してください)"); continue
        print(f"== {s} ({INSTR[s][0]}) {a.tf} {d0}..{d1}")
        try:
            fetch_symbol(s, a.tf, d0, d1, a.force)
        except FetchError as e:
            print(f"  !! {s}: {e}\n  !! 部分保存はしない。後で再実行すると未取得分から再開する。", flush=True)
        except Exception as e:
            import traceback; print(f"  !! {s}: 予期しない例外 {type(e).__name__}: {e}", flush=True); traceback.print_exc()
    print("\n完了。取得した CSV を git add してこのブランチへ push すると、E5 再現(docs/84 条件(a))に進めます。")


if __name__ == "__main__":
    main()
