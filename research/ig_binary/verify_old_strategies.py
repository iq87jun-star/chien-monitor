import pandas as pd, numpy as np
from scipy import stats
BE=0.55; CUT=pd.Timestamp("2026-05-29",tz="Asia/Tokyo")
S=[("IG_S01","EURUSD",3,7,"HIGH"),("IG_S02","GBPJPY",0,7,"HIGH"),("IG_S03","USDJPY",0,7,"HIGH"),
   ("IG_S04","USDJPY",3,5,"LOW"),("IG_S05","GBPUSD",0,7,"HIGH"),("IG_A06","EURUSD",2,7,"HIGH"),
   ("IG_S07","EURUSD",1,7,"HIGH"),("IG_A10","GBPUSD",1,5,"LOW"),("IG_S09","GBPUSD",2,7,"HIGH")]
def load(p,side=""):
    d=pd.read_csv(f"{p}_h1{side}.csv",index_col=0,parse_dates=True)
    d.index=pd.to_datetime(d.index,utc=True).tz_convert("Asia/Tokyo"); return d["open"]
px={}
for p in {s[1] for s in S}:
    b=load(p); a=load(p,"_ask"); j=b.index.intersection(a.index)
    px[p]={"BID":b[j],"MID":(b[j]+a[j])/2,"SPREAD":(a[j]-b[j])}
tr=[]
for sid,p,wd,h,dr in S:
    for side in ["BID","MID"]:
        o=px[p][side]; sel=o[(o.index.weekday==wd)&(o.index.hour==h)]
        for t,v in sel.items():
            t2=t+pd.Timedelta(hours=2)
            if t2 not in o.index or o[t2]==v: continue
            win=(o[t2]>v) if dr=="HIGH" else (o[t2]<v)
            tr.append(dict(sid=sid,side=side,t=t,win=int(win),oos=t>=CUT,
                           dst=bool(pd.Timestamp(t).tz_convert("America/New_York").dst())))
T=pd.DataFrame(tr)
def s(g):
    n=len(g);w=int(g.win.sum())
    return pd.Series(dict(n=n,WR=round(100*w/n,1),p_vs55=round(stats.binomtest(w,n,BE,alternative="greater").pvalue,3)))
print("=== 2016〜2026/5/28 (検証期間) BID vs MID ===")
print(T[~T.oos].groupby(["sid","side"]).apply(s).unstack("side").to_string())
print("\n=== 2026/5/29〜10/13 (検証後・未使用データ) MID ===")
o=T[(T.oos)&(T.side=="MID")]
print(o.groupby("sid").apply(s).to_string()); print("合算:",s(o).to_dict())
print("\n=== 夏時間/冬時間別 MID (検証期間) 合算 ===")
print(T[(~T.oos)&(T.side=="MID")].groupby("dst").apply(s).to_string())
# spread at entry hours
print("\n=== 平均スプレッド(pips) 時刻別 EURUSD ===")
sp=px["EURUSD"]["SPREAD"]*1e4
print(sp.groupby(sp.index.hour).mean().round(2).loc[[4,5,6,7,8,9,10]].to_string())
# OOS pnl
o=o.copy(); o["pnl"]=np.where(o.win==1,20000*(1/BE-1),-20000)
print("\n=== OOS 月別 (MID, 20,000円/回, 勝ち=+16,364円 負け=-20,000円) ===")
print(o.groupby(o.t.dt.strftime("%Y-%m")).agg(n=("win","size"),WR=("win","mean"),pnl=("pnl","sum")).round(3).to_string())
print("OOS累計:",f"{o.pnl.sum():+,.0f}円", " 期間月数:",round((o.t.max()-o.t.min()).days/30.4,1))

print("\n=== 厳選3戦略 (S01,S02,S03) MID / 20,000円 ===")
K=T[(T.side=="MID")&(T.sid.isin(["IG_S01","IG_S02","IG_S03"]))].sort_values("t").copy()
K["pnl"]=np.where(K.win==1,20000*(1/BE-1),-20000)
for flag,lab in [(False,"検証期間2016-2026/5"),(True,"検証後2026/6-10")]:
    g=K[K.oos==flag]; m=g.groupby(g.t.dt.strftime("%Y-%m")).pnl.sum()
    eq=g.pnl.cumsum(); dd=(eq-eq.cummax()).min()
    print(f"{lab}: n={len(g)} WR={g.win.mean()*100:.1f}% 月平均 {m.mean():+,.0f}円 月中央値 {m.median():+,.0f}円 "
          f"マイナス月 {100*(m<0).mean():.0f}% 最悪月 {m.min():+,.0f}円 最大DD {dd:+,.0f}円")
    if not flag:
        y=g.groupby(g.t.dt.year).agg(n=("win","size"),WR=("win","mean"),pnl=("pnl","sum")).round(3)
        print(y.to_string())
