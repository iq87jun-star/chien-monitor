import pandas as pd, numpy as np
from scipy import stats
BASE7=["USDJPY","EURJPY","GBPJPY","AUDJPY","EURUSD","GBPUSD","AUDUSD"]
NEW=["NZDJPY","CADJPY","CHFJPY","NZDUSD","USDCAD","USDCHF","EURGBP","EURAUD","GBPAUD","XAUUSD"]
D1=pd.Timestamp("2022-01-01",tz="Asia/Tokyo"); D2=pd.Timestamp("2026-05-29",tz="Asia/Tokyo")
WIN=[(7,8),(8,9),(8,10),(7,9),(9,11),(11,13),(13,15),(8,11),(7,13)]
def load(p,s=""):
    d=pd.read_csv(f"{p}_h1{s}.csv",index_col=0,parse_dates=True)
    d.index=pd.to_datetime(d.index,utc=True).tz_convert("Asia/Tokyo"); return d
def pipsz(p): return 0.1 if p=="XAUUSD" else (0.01 if p.endswith("JPY") else 1e-4)
rows=[]
for p in BASE7+NEW:
    b,a=load(p),load(p,"_ask"); j=b.index.intersection(a.index)
    mid=(b.loc[j,"open"]+a.loc[j,"open"])/2; midc=(b.loc[j,"close"]+a.loc[j,"close"])/2; sp=a.loc[j,"open"]-b.loc[j,"open"]; ps=pipsz(p)
    mons=sorted({t.normalize() for t in mid.index[mid.index.weekday==0]})
    for d0 in mons:
        t7=d0+pd.Timedelta(hours=7)
        prevc=midc[midc.index<=t7-pd.Timedelta(hours=24)]
        mon=mid[(mid.index>t7-pd.Timedelta(hours=24))&(mid.index<d0+pd.Timedelta(hours=16))]
        if prevc.empty or mon.empty: continue
        fri=prevc.iloc[-1]; first=mon.iloc[0]; gap=first-fri
        if gap==0: continue
        dst=bool(t7.tz_convert("America/New_York").dst())
        for h0,h1 in WIN:
            s,e=d0+pd.Timedelta(hours=h0),d0+pd.Timedelta(hours=h1)
            if s not in mid.index or e not in mid.index: continue
            r=mid[e]-mid[s]
            if r==0: continue
            filled=(mid[s]-first)/(fri-first)
            rows.append(dict(pair=p,new=p in NEW,t=t7,win=f"{h0:02d}→{h1:02d}",down=gap<0,ret_pips=r/ps,
                cost_pips=(sp.get(s,np.nan)+sp.get(e,np.nan))/2/ps,   # 片道 半スプレッド×2 = 往復コスト
                filled=filled,dst=dst,per="A" if t7<D1 else ("B" if t7<D2 else "C")))
X=pd.DataFrame(rows); X.to_csv("expand_rows.csv",index=False)
def wr(g):
    n=len(g); k=int((g.ret_pips>0).sum()); return f"{100*k/n:5.1f}%({n:4d})" if n else "   -       "
print("=== ① 時間帯の横展開: 下窓 → HIGH(元の 7 ペア・未埋め filled<0.5)===")
print(f"{'窓':8s} {'2016-21':>12s} {'2022-26.5':>12s} {'2026.6-10':>12s}")
for w in [f"{a:02d}→{b:02d}" for a,b in WIN]:
    g=X[(~X.new)&X.down&(X.win==w)&(X.filled<0.5)]
    if w=="05→07": g=g[g.dst]
    print(f"{w:8s} "+" ".join(f"{wr(g[g.per==per]):>12s}" for per in "ABC"))
print("\n=== ② 通貨ペアの横展開: 下窓 07→09 HIGH・未埋め(新 10 銘柄は検証に一度も使っていない)===")
for p in NEW:
    g=X[(X.pair==p)&X.down&(X.win=="07→09")&(X.filled<0.5)]
    print(f"{p:7s} "+" ".join(f"{wr(g[g.per==per]):>12s}" for per in "ABC"))
g=X[X.new&X.down&(X.win=="07→09")&(X.filled<0.5)]
print("新10合算 "+" ".join(f"{wr(g[g.per==per]):>12s}" for per in "ABC"))
print("\n=== ③ 上窓 → LOW(逆向きの対称性)元の 7 ペア 07→09・未埋め ===")
g=X[(~X.new)&(~X.down)&(X.win=="07→09")&(X.filled<0.5)]
g=g.assign(ret_pips=-g.ret_pips)
print("        "+" ".join(f"{wr(g[g.per==per]):>12s}" for per in "ABC"))
print("\n=== ④ CFD/ノックアウト向け: 下窓・未埋め の平均値幅とコスト(pips)元の 7 ペア ===")
for w in ["07→09","07→13","09→11"]:
    g=X[(~X.new)&X.down&(X.win==w)&(X.filled<0.5)]
    for per in "BC":
        h=g[g.per==per]; print(f"{w} {per}: 平均 {h.ret_pips.mean():+.2f} pips / 往復コスト {h.cost_pips.mean():.2f} pips / 差引 {h.ret_pips.mean()-h.cost_pips.mean():+.2f}  n={len(h)}")
