# -*- coding: utf-8 -*-
"""直近フィット・トラック用データ取得(Yahoo)。
   凍結窓: H1/日足とも 2024-08-01 .. 2026-07-24 (UTC)。
   選定に使うのは直近12ヶ月のみだが、参考統計(正直値)用に約2年取る。
   Yahoo 1h は取得時点から遡って730日制限があるため、実行が遅れると先頭が欠ける。
   その場合は先頭欠損をそのまま記録する(結果JSONに実データ範囲を書く)。"""
import urllib.request, json, time, os, csv, datetime as dt

OUT = os.path.join(os.path.dirname(__file__), "data_recent")
os.makedirs(OUT, exist_ok=True)

PAIRS = {
    "EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","AUDUSD":"AUDUSD=X",
    "USDCHF":"USDCHF=X","USDCAD":"USDCAD=X","NZDUSD":"NZDUSD=X",
    "EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X",
}

# 2024-08-01 00:00 UTC .. 2026-07-24 23:59 UTC (金曜クローズ)
P1, P2 = 1722470400, 1784936399

def fetch(sym, interval):
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&period1={P1}&period2={P2}"
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
    d=json.loads(urllib.request.urlopen(req,timeout=30).read())
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

if __name__ == "__main__":
    for name,sym in PAIRS.items():
        for interval,tag in [("1d","d"),("1h","h1")]:
            for attempt in range(3):
                try:
                    rows=fetch(sym,interval)
                    p=os.path.join(OUT,f"{name}_{tag}.csv"); save(rows,p)
                    print(f"{name}_{tag}: {len(rows)} bars {rows[0][0]}..{rows[-1][0]} -> {p}")
                    break
                except Exception as e:
                    print(f"{name}_{tag} ERR({attempt+1}) {type(e).__name__} {str(e)[:60]}")
                    time.sleep(2*(attempt+1))
            time.sleep(1.0)
