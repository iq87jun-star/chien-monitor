# -*- coding: utf-8 -*-
"""fetch_calendar.py — 新カレンダー系エッジ探索(プレ祝日/年末年始/月別)用の日足10年取得。
   指数(US500/NAS100/GER40/UK100/JP225)+金 と、相関基準用の円3クロスを Yahoo から取得。
   429対策に指数バックオフ付き。保存: research/data/<NAME>_d.csv。研究用(本番はデモ/Dukascopyで再測)。"""
import urllib.request, json, time, os, csv, datetime as dt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)

ASSETS = {
    "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI", "UK100": "^FTSE",
    "JP225": "^N225", "XAUUSD": "GC=F",
    "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X", "USDJPY": "USDJPY=X",
}


def fetch(sym, tries=6):
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&period1=1451606400&period2=1767225599"
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
                rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
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
