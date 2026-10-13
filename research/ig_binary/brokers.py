import pandas as pd, numpy as np, glob, os
from scipy import stats
D1=pd.Timestamp("2022-01-01",tz="Asia/Tokyo"); D2=pd.Timestamp("2026-05-29",tz="Asia/Tokyo")
PAIRS=["USDJPY","EURJPY","GBPJPY","AUDJPY","NZDJPY","EURUSD","GBPUSD","AUDUSD"]
# (名前, 対象ペア, 冬時間 開始/判定, 夏時間 開始/判定) JST "HH:MM"
B=[("GMO外貨 オプトレ!(2h)",PAIRS,("07:25","09:25"),("07:25","09:25")),
   ("みんなのオプション(3h)",["USDJPY","EURJPY","GBPJPY","AUDJPY","EURUSD"],("08:10","11:10"),("07:10","10:10")),
   ("IG証券(2h・月曜初回)",["USDJPY","EURJPY","GBPJPY","AUDJPY","EURUSD","GBPUSD","AUDUSD"],("09:00","11:00"),("08:00","10:00")),
   ("GMOクリック 外為オプション(3h)",["USDJPY","EURJPY","GBPJPY","AUDJPY","EURUSD"],("08:00","11:00"),("08:00","11:00")),
   ("外為どっとコム ネクストバイナリー(2h)",["USDJPY","EURJPY","GBPJPY","AUDJPY","EURUSD","GBPUSD","AUDUSD"],("08:20","10:20"),("08:20","10:20")),
   ("(参考)理想 07:00→09:00",PAIRS,("07:00","09:00"),("07:00","09:00"))]
def hourly_close(p):
    b=pd.read_csv(f"{p}_h1.csv",index_col=0,parse_dates=True); a=pd.read_csv(f"{p}_h1_ask.csv",index_col=0,parse_dates=True)
    j=b.index.intersection(a.index); c=(b.loc[j,"close"]+a.loc[j,"close"])/2; c.index=pd.to_datetime(c.index,utc=True).tz_convert("Asia/Tokyo"); return c
rows=[]
for p in PAIRS:
    hc=hourly_close(p)
    for fb in sorted(glob.glob(f"m1/{p}_BID_*.csv")):
        fa=fb.replace("_BID_","_ASK_")
        if not os.path.exists(fa): continue
        b=pd.read_csv(fb,index_col=0,parse_dates=True)["open"]; a=pd.read_csv(fa,index_col=0,parse_dates=True)["open"]
        m=((b+a)/2).dropna()
        if m.empty: continue
        m.index=pd.to_datetime(m.index,utc=True).tz_convert("Asia/Tokyo")
        first_t=m.index[0]; first=m.iloc[0]
        mon=(first_t+pd.Timedelta(hours=12)).normalize()
        if mon.weekday()!=0: continue
        prev=hc[hc.index<first_t-pd.Timedelta(hours=12)]
        if prev.empty: continue
        fri=prev.iloc[-1]
        if first>=fri: continue                       # 下窓のみ
        dst=bool((mon+pd.Timedelta(hours=7)).tz_convert("America/New_York").dst())
        def px(hhmm):
            t=mon+pd.Timedelta(hours=int(hhmm[:2]),minutes=int(hhmm[3:]))
            s=m[(m.index>=t)&(m.index<t+pd.Timedelta(minutes=5))]
            return s.iloc[0] if len(s) else None
        for name,pairs,win,summ in B:
            if p not in pairs: continue
            s,e=summ if dst else win
            ps,pe=px(s),px(e)
            if ps is None or pe is None or ps==pe: continue
            filled=(ps-first)/(fri-first)
            rows.append(dict(broker=name,pair=p,mon=mon,win=int(pe>ps),filled=filled,dst=dst,
                             per="A" if mon<D1 else ("B" if mon<D2 else "C")))
X=pd.DataFrame(rows); X.to_csv("brokers_rows.csv",index=False)
def f(g):
    n=len(g); k=int(g.win.sum()); return f"{100*k/n:5.1f}%({n:4d})" if n else "     -     "
print(f"{'業者(下窓・開始時点で未埋め<50%)':40s} {'2016-21':>12s} {'2022-26.5':>12s} {'2026.6-10':>12s}  月あたり回数")
for name,*_ in B:
    g=X[(X.broker==name)&(X.filled<0.5)]
    months=X.mon.dt.strftime("%Y-%m").nunique()
    print(f"{name:40s} "+" ".join(f"{f(g[g.per==per]):>12s}" for per in "ABC")+f"  {len(g)/months:.1f}")
print("\n夏/冬 内訳(全期間)")
for name,*_ in B[:2]:
    for d,l in [(True,"夏"),(False,"冬")]:
        g=X[(X.broker==name)&(X.filled<0.5)&(X.dst==d)]; print(f"  {name} {l}: {f(g)}")

# ---- 時間帯マップ: 入る時刻 × 判定までの時間(下窓・入る時点で未埋め<50%)----
print("\n=== 時間帯マップ(全 8 ペア・下窓・入る時点で未埋め)勝率% [2016-21 / 2022-26.5 / 2026.6-10] ===")
ent=[f"{h:02d}:{m:02d}" for h in (6,7,8,9) for m in (0,10,20,30,40,50)]
ent=[e for e in ent if "06:00"<=e<="09:00"]
DUR=[60,120,180]
mm={}
for p in PAIRS:
    hc=hourly_close(p)
    for fb in sorted(glob.glob(f"m1/{p}_BID_*.csv")):
        fa=fb.replace("_BID_","_ASK_")
        if not os.path.exists(fa): continue
        b=pd.read_csv(fb,index_col=0,parse_dates=True)["open"]; a=pd.read_csv(fa,index_col=0,parse_dates=True)["open"]
        m=((b+a)/2).dropna()
        if m.empty: continue
        m.index=pd.to_datetime(m.index,utc=True).tz_convert("Asia/Tokyo")
        first_t=m.index[0]; first=m.iloc[0]; mon=(first_t+pd.Timedelta(hours=12)).normalize()
        if mon.weekday()!=0: continue
        prev=hc[hc.index<first_t-pd.Timedelta(hours=12)]
        if prev.empty or first>=prev.iloc[-1]: continue
        fri=prev.iloc[-1]; per="A" if mon<D1 else ("B" if mon<D2 else "C")
        dst=bool((mon+pd.Timedelta(hours=7)).tz_convert("America/New_York").dst())
        mi=m.copy(); mi.index=((mi.index-mon).total_seconds()//60).astype(int); mi=mi[~mi.index.duplicated()]
        for e in ent:
            t0=int(e[:2])*60+int(e[3:])
            if t0 not in mi.index: continue
            ps=mi[t0]
            if (ps-first)/(fri-first)>=0.5: continue
            for d in DUR:
                if t0+d in mi.index and mi[t0+d]!=ps:
                    mm.setdefault((e,d,per,dst),[]).append(int(mi[t0+d]>ps))
for season,dl in [("夏時間(開場 06:00)",True),("冬時間(開場 07:00)",False)]:
    print(f"\n[{season}]  入る時刻 | 1時間後 | 2時間後 | 3時間後")
    for e in ent:
        cells=[]
        for d in DUR:
            v=[mm.get((e,d,per,dl),[]) for per in "ABC"]
            cells.append("/".join(f"{100*np.mean(x):.0f}" if len(x)>=20 else "-" for x in v))
        if any(c!="-/-/-" for c in cells): print(f"  {e} | "+" | ".join(f"{c:>11s}" for c in cells))
