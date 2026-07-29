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

# 固定の解析窓(UTC)。再現性のため range(=実行日基準のローリング)を廃止し period1/period2 で凍結。
#   10y : 2016-01-01..2025-12-31(docs/18 のDukascopy検証窓と一致) / 730d : 2024-01-01..2025-12-31
PERIODS = {"10y": (1451606400, 1767225599), "730d": (1704067200, 1767225599)}

def fetch(sym, interval, rng):
    p1, p2 = PERIODS.get(rng, (1451606400, 1767225599))
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&period1={p1}&period2={p2}"
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
    d=json.loads(urllib.request.urlopen(req,timeout=20).read())
    r=d["chart"]["result"][0]
    ts=r["timestamp"]; q=r["indicators"]["quote"][0]
    rows=[]
    for i,t in enumerate(ts):
        o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
        if None in (o,h,l,c): continue
        rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c))
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
