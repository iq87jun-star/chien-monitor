# -*- coding: utf-8 -*-
"""fetch_intermarket.py — 第3並走ポート探索(event_intermarket_edge_10y.py)用の追加日足10年取得。
   fetch_calendar.py(指数+金+円3クロス) で足りない分を補完: WTI / ドル指数 / 主要FX(v4/リードラグ用)。
   429対策にバックオフ付き。保存: research/data/<NAME>_d.csv。研究用(本番はデモ/Dukascopyで再測)。"""
import urllib.request, json, time, os, csv, datetime as dt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)

# fetch_calendar.py が取らない分のみ(重複取得を避ける)。
ASSETS = {
    "WTI": "CL=F",            # 原油先物(oil→CAD リードラグ用)
    "DXY": "DX-Y.NYB",        # ICE ドル指数(dxy→EUR リードラグ用。取れなければ "DX=F" に変更)
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X", "NZDUSD": "NZDUSD=X",
    # 注: US500/NAS100/GER40/JP225/XAUUSD/EURJPY/GBPJPY/USDJPY は fetch_calendar.py 側で取得。
}


def fetch(sym, tries=6):
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10y"
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
            d = json.loads(urllib.request.urlopen(req, timeout=25).read())
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            rows = []
            for i, t in enumerate(ts):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                if None in (o, h, l, c):
                    continue
                rows.append((dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
            return rows
        except Exception as e:
            last = e; wait = 2 ** k
            print(f"  retry {k+1}/{tries} {sym}: {type(e).__name__} -> wait {wait}s")
            time.sleep(wait)
    raise last


def main():
    print("保存先:", OUT)
    for name, sym in ASSETS.items():
        try:
            rows = fetch(sym)
            p = os.path.join(OUT, f"{name}_d.csv")
            with open(p, "w", newline="") as f:
                w = csv.writer(f); w.writerow(["timestamp", "open", "high", "low", "close"]); w.writerows(rows)
            yrs = (dt.datetime.strptime(rows[-1][0], "%Y-%m-%d %H:%M:%S") - dt.datetime.strptime(rows[0][0], "%Y-%m-%d %H:%M:%S")).days / 365.25
            print(f"{name:7s} {len(rows)} bars {rows[0][0][:10]}..{rows[-1][0][:10]} ({yrs:.1f}y)")
        except Exception as e:
            print(f"{name} ERR {type(e).__name__} {str(e)[:80]}")
        time.sleep(3.0)


if __name__ == "__main__":
    main()
