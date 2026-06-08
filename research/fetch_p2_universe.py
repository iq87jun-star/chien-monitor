# -*- coding: utf-8 -*-
"""
fetch_p2_universe.py — 第2ポートフォリオ(P2)用「商品ユニバース拡張」データ取得。

目的: 既存P1(v7 円月曜 / v4 合議FX / E5 多資産モメンタム)と【低相関な別ポートフォリオ】を
      組むため、既存9ペアに無い土俵=追加FXクロス + 金属 + 株価指数 + 暗号 を日足10年で取得。
      機構は E5(モメンタム)と被らない曜日/月末/短期平均回帰で検定する(p2_edge_search.py)。

保存先: research/data/<NAME>_d.csv (research_backtester / edge_search と同じ置き場)。
データ源: Yahoo Finance(研究用)。最終確認はユーザーのDukascopy/Colabで(P1と同じ規律)。
"""
import urllib.request, json, time, os, csv, datetime as dt

OUT = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT, exist_ok=True)

# 表示名 : Yahooシンボル。既存P1で取得済み(EURUSD等9ペア/E5の金・指数・暗号)と重複する分も
# 再取得して同じ置き場・同じ列形式に揃える(取りこぼし回避)。
ASSETS = {
    # --- 追加FXクロス(既存9ペアに無い) ---
    "EURGBP":"EURGBP=X", "AUDJPY":"AUDJPY=X", "NZDJPY":"NZDJPY=X", "CADJPY":"CADJPY=X",
    "CHFJPY":"CHFJPY=X", "EURAUD":"EURAUD=X", "AUDNZD":"AUDNZD=X", "EURCHF":"EURCHF=X",
    "GBPCHF":"GBPCHF=X", "GBPAUD":"GBPAUD=X",
    # --- 金属 ---
    "XAUUSD":"GC=F", "XAGUSD":"SI=F",
    # --- 株価指数(price index, 配当抜き) ---
    "US500":"^GSPC", "NAS100":"^IXIC", "GER40":"^GDAXI", "JP225":"^N225", "UK100":"^FTSE",
    # --- 暗号 ---
    "BTCUSD":"BTC-USD", "ETHUSD":"ETH-USD",
}

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
    print("保存先:", OUT)
    ok=0
    for name,sym in ASSETS.items():
        for attempt in range(3):
            try:
                rows=fetch(sym)
                p=os.path.join(OUT, f"{name}_d.csv")
                with open(p,"w",newline="") as f:
                    w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"]); w.writerows(rows)
                yrs=(dt.datetime.strptime(rows[-1][0],"%Y-%m-%d %H:%M:%S")
                     -dt.datetime.strptime(rows[0][0],"%Y-%m-%d %H:%M:%S")).days/365.25
                print(f"{name:7s} {len(rows):5d} bars {rows[0][0][:10]}..{rows[-1][0][:10]} ({yrs:.1f}y)")
                ok+=1; break
            except Exception as e:
                if attempt==2:
                    print(f"{name:7s} ERR {type(e).__name__} {str(e)[:60]}")
                else:
                    time.sleep(2.0*(attempt+1))
        time.sleep(0.8)
    print(f"\n取得成功 {ok}/{len(ASSETS)}")

if __name__=="__main__":
    main()
