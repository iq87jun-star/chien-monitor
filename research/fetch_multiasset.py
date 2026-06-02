"""
fetch_multiasset.py — edge5用の多資産 日足10年 を Yahoo から取得しCSV保存。
保存先: Colab=DRIVE_BASE/multiasset_daily/<NAME>_d.csv、ローカル=./research/data/<NAME>_d.csv。
edge5_multiasset_10y.py はこの場所を探索する。研究用データ(実運用約定はデモ/本番で別途確認)。
"""
import urllib.request, json, time, os, csv, datetime as dt

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
ASSETS = {  # 表示名: Yahooシンボル
    "XAUUSD":"GC=F",     # 金(先物近月)
    "US500":"^GSPC",     # S&P500
    "NAS100":"^IXIC",    # Nasdaq総合
    "GER40":"^GDAXI",    # DAX
    "BTCUSD":"BTC-USD",
    "ETHUSD":"ETH-USD",
}

def _out_dir():
    drive=f"{DRIVE_BASE}/multiasset_daily"
    if os.path.isdir("/content/drive/MyDrive"):
        os.makedirs(drive, exist_ok=True); return drive
    os.makedirs("./research/data", exist_ok=True); return "./research/data"

def fetch(sym):
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10y"
    req=urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
    d=json.loads(urllib.request.urlopen(req, timeout=25).read())
    r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
    rows=[]
    for i,t in enumerate(ts):
        o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
        if None in (o,h,l,c): continue
        rows.append((dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c))
    return rows

def main():
    out=_out_dir(); print("保存先:", out)
    for name,sym in ASSETS.items():
        try:
            rows=fetch(sym); p=os.path.join(out, f"{name}_d.csv")
            with open(p,"w",newline="") as f:
                w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"]); w.writerows(rows)
            yrs=(dt.datetime.strptime(rows[-1][0],"%Y-%m-%d %H:%M:%S")-dt.datetime.strptime(rows[0][0],"%Y-%m-%d %H:%M:%S")).days/365.25
            print(f"{name:7s} {len(rows)} bars {rows[0][0][:10]}..{rows[-1][0][:10]} ({yrs:.1f}y)")
        except Exception as e:
            print(f"{name} ERR {type(e).__name__} {str(e)[:60]}")
        time.sleep(1.0)

if __name__=="__main__":
    main()
