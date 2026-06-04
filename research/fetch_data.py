# -*- coding: utf-8 -*-
"""Yahoo Finance から FX OHLC を取得しCSVキャッシュ。
   日足10年 + 時間足~730日。研究用（実運用データはユーザーのDukascopyが正)。"""
import urllib.request, json, time, os, csv, datetime as dt

OUT = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT, exist_ok=True)

PAIRS = {
    "EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","AUDUSD":"AUDUSD=X",
    "USDCHF":"USDCHF=X","USDCAD":"USDCAD=X","NZDUSD":"NZDUSD=X",
    "EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X",
}

def fetch(sym, interval, rng):
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&range={rng}"
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
    d=json.loads(urllib.request.urlopen(req,timeout=20).read())
    r=d["chart"]["result"][0]
    ts=r["timestamp"]; q=r["indicators"]["quote"][0]
    rows=[]
    for i,t in enumerate(ts):
        o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
        if None in (o,h,l,c): continue
        rows.append((dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c))
    return rows

def save(rows, path):
    with open(path,"w",newline="") as f:
        w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"])
        w.writerows(rows)

for name,sym in PAIRS.items():
    for interval,rng,tag in [("1d","10y","d"),("1h","730d","h1")]:
        try:
            rows=fetch(sym,interval,rng)
            p=os.path.join(OUT,f"{name}_{tag}.csv"); save(rows,p)
            print(f"{name}_{tag}: {len(rows)} bars -> {p}")
        except Exception as e:
            print(f"{name}_{tag} ERR {type(e).__name__} {str(e)[:60]}")
        time.sleep(1.0)
