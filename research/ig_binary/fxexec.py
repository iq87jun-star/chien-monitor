import pandas as pd, numpy as np, glob, os
D1=pd.Timestamp("2022-01-01",tz="Asia/Tokyo"); D2=pd.Timestamp("2026-05-29",tz="Asia/Tokyo")
PAIRS=["USDJPY","EURJPY","GBPJPY","AUDJPY","NZDJPY","EURUSD","GBPUSD","AUDUSD"]
def hc(p):
    b=pd.read_csv(f"{p}_h1.csv",index_col=0,parse_dates=True); a=pd.read_csv(f"{p}_h1_ask.csv",index_col=0,parse_dates=True)
    j=b.index.intersection(a.index); c=(b.loc[j,"close"]+a.loc[j,"close"])/2; c.index=pd.to_datetime(c.index,utc=True).tz_convert("Asia/Tokyo"); return c
R=[]
for p in PAIRS:
    H=hc(p); pip=0.01 if p.endswith("JPY") else 1e-4
    for fb in sorted(glob.glob(f"m1/{p}_BID_*.csv")):
        b=pd.read_csv(fb,index_col=0,parse_dates=True)["open"]; a=pd.read_csv(fb.replace("_BID_","_ASK_"),index_col=0,parse_dates=True)["open"]
        j=b.index.intersection(a.index); b,a=b[j],a[j]
        if len(j)<60: continue
        idx=pd.to_datetime(j,utc=True).tz_convert("Asia/Tokyo"); b.index=idx; a.index=idx
        m=(b+a)/2; t0=idx[0]; mon=(t0+pd.Timedelta(hours=12)).normalize()
        if mon.weekday()!=0: continue
        prev=H[H.index<t0-pd.Timedelta(hours=12)]
        if prev.empty or m.iloc[0]>=prev.iloc[-1]: continue
        fri=prev.iloc[-1]; first=m.iloc[0]; per="A" if mon<D1 else ("B" if mon<D2 else "C")
        off=((idx-t0).total_seconds()//60).astype(int)          # 開場からの分
        B=pd.Series(b.values,index=off); A=pd.Series(a.values,index=off); M=pd.Series(m.values,index=off)
        B=B[~B.index.duplicated()]; A=A[~A.index.duplicated()]; M=M[~M.index.duplicated()]
        for e in (0,5,10,20,30,60):
            if e not in A.index or (M[e]-first)/(fri-first)>=0.5: continue
            for d in (60,120):
                if e+d not in B.index: continue
                R.append(dict(per=per,e=e,d=d,gross=(M[e+d]-M[e])/pip,net=(B[e+d]-A[e])/pip,spread_in=(A[e]-B[e])/pip))
X=pd.DataFrame(R)
print("FX/CFD 実行値(ASK で買い・BID で売り)開場から e 分後に買い d 分保有。平均 pips [2016-21 / 2022-26.5 / 2026.6-10]")
for (e,d),g in X.groupby(["e","d"]):
    s=lambda c:"/".join(f"{g[g.per==q][c].mean():+.1f}" for q in "ABC")
    w=lambda: "/".join(f"{100*(g[g.per==q].net>0).mean():.0f}%" for q in "ABC")
    print(f" 開場+{e:2d}分 保有{d:3d}分: 中値 {s('gross'):>17s}  実行(コスト込) {s('net'):>17s}  勝ち {w()}  入りスプレッド {g.spread_in.median():.1f}")
