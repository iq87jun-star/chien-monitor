import pandas as pd, numpy as np
from scipy import stats
PAIRS=["USDJPY","EURJPY","GBPJPY","AUDJPY","EURUSD","GBPUSD","AUDUSD"]
D1=pd.Timestamp("2022-01-01",tz="Asia/Tokyo"); D2=pd.Timestamp("2026-05-29",tz="Asia/Tokyo")
def load(p,s=""):
    d=pd.read_csv(f"{p}_h1{s}.csv",index_col=0,parse_dates=True)
    d.index=pd.to_datetime(d.index,utc=True).tz_convert("Asia/Tokyo"); return d
out=[]
for p in PAIRS:
    b,a=load(p),load(p,"_ask"); j=b.index.intersection(a.index)
    m=(b.loc[j,["open","close"]]+a.loc[j,["open","close"]])/2
    mon=m[(m.index.weekday==0)&(m.index.hour==7)]
    for t,row in mon.iterrows():
        prev=m[m.index<t-pd.Timedelta(hours=24)]
        if prev.empty: continue
        fri_close=prev.close.iloc[-1]
        first=m[(m.index<=t)&(m.index>t-pd.Timedelta(hours=24))].open.iloc[0]
        t2=t+pd.Timedelta(hours=2)
        if t2 not in m.index: continue
        out.append(dict(pair=p,t=t,gap=first-fri_close,ret=m.loc[t2,"open"]-row.open,
                        per="A" if t<D1 else ("B" if t<D2 else "C")))
X=pd.DataFrame(out); X=X[X.ret!=0]
def s(g): 
    n=len(g);k=int((g.ret>0).sum()); return f"n={n} 上昇率={100*k/n:.1f}% p={stats.binomtest(k,n,.55,alternative='greater').pvalue:.3f}"
print("=== 月曜07→09 上昇率: 週末ギャップの向き別 (MID) ===")
for gs,lab in [(X.gap<0,"ギャップ下落(窓埋め上昇狙い)"),(X.gap>0,"ギャップ上昇")]:
    print(lab)
    for per,pl in [("A","2016-21"),("B","2022-26/5"),("C","2026/6-10")]:
        print(f"   {pl:10s} 全7ペア {s(X[gs&(X.per==per)])}")
print("\nペア別 (ギャップ下落時, 全期間)")
for p in PAIRS:
    print(" ",p,s(X[(X.gap<0)&(X.pair==p)]))
print("\nペア別 (無条件, 全期間)")
for p in PAIRS:
    print(" ",p,s(X[X.pair==p]))

Y=X[X.gap<0].copy().sort_values("t")
Y["dst"]=Y.t.map(lambda t:bool(t.tz_convert("America/New_York").dst()))
print("\n夏時間/冬時間 (ギャップ下落時):")
for d,lab in [(True,"夏時間(07時=開場1時間後)"),(False,"冬時間(07時=開場直後)")]: print(" ",lab,s(Y[Y.dst==d]))
Y["pnl"]=np.where(Y.ret>0,20000*(1/.55-1),-20000)
for per,lab in [("B","2022-26/5"),("C","2026/6-10")]:
    g=Y[Y.per==per]; mm=g.groupby(g.t.dt.strftime("%Y-%m")).pnl.sum(); eq=g.pnl.cumsum()
    print(f"{lab}: 月平均回数 {g.groupby(g.t.dt.strftime('%Y-%m')).size().mean():.1f} 月平均 {mm.mean():+,.0f}円 マイナス月 {100*(mm<0).mean():.0f}% 最悪月 {mm.min():+,.0f}円 最大DD {(eq-eq.cummax()).min():+,.0f}円")
