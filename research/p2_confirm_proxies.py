# -*- coding: utf-8 -*-
"""
p2_confirm_proxies.py — P2「株価指数 月曜LONG」エッジの独立インストゥルメント追認。

目的: ユーザーのDrive実データに直接アクセスできない環境での追認として、同じ指数を
  【別インストゥルメント=ETF・先物】で取得し、月曜エッジが「Yahoo現物指数データ固有の
  クセ」ではなく、現物/ETF/先物を通じて再現する本物の現象かを交差確認する。
  CFDは先物/現物に連動するため、ETF・先物での再現は実運用妥当性の追認にもなる。

確認対象(全てYahoo・10年日足だが、現物とは別系列のインストゥルメント):
  US株: 現物^GSPC / ETF SPY / 先物 ES=F   ・ Nasdaq: 現物^IXIC / ETF QQQ / 先物 NQ=F
  独株: 現物^GDAXI / ETF EWG(独株ETF)
判定: 各々で「月曜LONGのperm_p」と「火-金プラセボ」を出し、月曜のみ有意が再現するか。
注: ETF/先物は配当・限月・乖離があり現物と完全一致しない＝独立性の担保。最終確証はユーザー実CFDデモで。
"""
import os, json, urllib.request, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

try:
    HERE=os.path.dirname(os.path.abspath(__file__))   # スクリプト実行時
except NameError:
    HERE=os.getcwd()                                   # ノートブックcell実行時(__file__無し)
BPS=5.0
GROUPS={
 "US500":  [("現物 ^GSPC","^GSPC"),("ETF SPY","SPY"),("先物 ES=F","ES=F")],
 "NAS100": [("現物 ^IXIC","^IXIC"),("ETF QQQ","QQQ"),("先物 NQ=F","NQ=F")],
 "GER40":  [("現物 ^GDAXI","^GDAXI"),("ETF EWG","EWG")],
}

def yahoo(sym):
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10y"
    req=urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
    d=json.loads(urllib.request.urlopen(req, timeout=25).read())
    r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
    rows=[(dt.datetime.utcfromtimestamp(t), q["open"][i],q["close"][i])
          for i,t in enumerate(ts) if None not in (q["open"][i],q["close"][i])]
    df=pd.DataFrame(rows,columns=["t","open","close"])
    df["t"]=pd.to_datetime(df["t"],utc=True)
    df["trade_date"]=(df["t"]+pd.Timedelta(hours=2)).dt.floor("D")
    df=df.groupby("trade_date").last(); df["weekday"]=df.index.dayofweek
    df=df[df["weekday"]<=4]; df["o2o"]=df["open"].shift(-1)/df["open"]-1.0
    return df.dropna(subset=["o2o"])

def perm_p(x,n=5000,seed=11):
    x=np.asarray(x,float)
    if len(x)<10: return 1.0
    rng=np.random.default_rng(seed); real=x.sum(); a=np.abs(x).astype(np.float32)
    return float(((rng.choice(np.array([-1,1],np.float32),size=(n,len(a)))*a).sum(axis=1)>=real).mean())

def net(x):
    x=pd.Series(x).dropna(); return round(((1+x).cumprod().iloc[-1]-1)*100,1) if len(x) else 0.0

def mon_other(df):
    mon=df[df["weekday"]==0]["o2o"]-BPS/1e4
    oth=df[df["weekday"].isin([1,2,3,4])]["o2o"]-BPS/1e4
    return (net(mon.values),perm_p(mon.values),len(mon)),(net(oth.values),perm_p(oth.values))

def main():
    print("="*74); print("P2 月曜エッジ 独立インストゥルメント追認（現物 / ETF / 先物）"); print("="*74)
    out={}; n_mon_sig=0; n_total=0
    for grp,members in GROUPS.items():
        print(f"\n[{grp}]")
        out[grp]={}
        for label,sym in members:
            try:
                df=yahoo(sym); (mn,mp,nn),(on,op)=mon_other(df)
                span=f"{df.index.min().date()}..{df.index.max().date()}"
                sig = mp<=0.05; plac_ok = op>0.05
                verdict = "✅月曜のみ有意" if (sig and plac_ok) else ("△月曜有意/プラセボも" if sig else "✗月曜非有意")
                print(f"  {label:11s} 月曜 net{mn:6.1f}% p={mp:.4f} (n{nn}) | 火-金 net{on:6.1f}% p={op:.3f} → {verdict}  [{span}]")
                out[grp][sym]=dict(mon_net=mn,mon_p=round(mp,4),mon_n=nn,other_net=on,other_p=round(op,3),span=span)
                n_total+=1; n_mon_sig+= 1 if sig else 0
            except Exception as e:
                print(f"  {label:11s} ERR {type(e).__name__} {str(e)[:50]}")
    print(f"\n=== 追認サマリ: 月曜LONGが p<=0.05 で再現したインストゥルメント = {n_mon_sig}/{n_total} ===")
    print("→ 現物だけでなくETF/先物でも月曜効果が再現すれば『Yahoo現物固有のクセ』ではない＝本物の現象の傍証。")
    print("  (絶対値はインストゥルメントで異なる＝配当/限月/乖離。最終確証はユーザー実CFDデモで)")
    os.makedirs(os.path.join(HERE,"results"),exist_ok=True)
    with open(os.path.join(HERE,"results","p2_confirm_proxies.json"),"w") as f:
        json.dump(dict(summary=f"{n_mon_sig}/{n_total}",groups=out),f,ensure_ascii=False,indent=2)
    print("\n保存: results/p2_confirm_proxies.json")

if __name__=="__main__":
    main()
