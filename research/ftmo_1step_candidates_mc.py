# -*- coding: utf-8 -*-
"""docs/300: FTMO 1-Step(+10% / EOD トレーリング 10%・+10% で初期に固定 / 日次 3%→EA 2.4% / Best Day 50%)の規則下で、
Sess 消滅後(docs/249)に残る各構成を MC 比較。research/ で実行。5 日ブロック・5,000 本・500 日。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import recentfit_screen as base, deployed_book as db
from plusmonth_portfolio import perf
rng=np.random.default_rng(31); N=5000; BLOCK=5; DAYS=500; GUARD=0.024
def comp(legs):
    parts=[(db.leg_series(f,s),w) for f,s,w in legs]
    idx=sorted(set().union(*[set(s.index) for s,_ in parts])); out=pd.Series(0.0,index=pd.DatetimeIndex(idx))
    for s,w in parts: out=out.add(s.reindex(out.index).fillna(0.0)*w,fill_value=0.0)
    out=out[out.index>=pd.Timestamp("2021-10-01")]
    return out.reindex(pd.bdate_range(out.index.min(),out.index.max())).fillna(0.0)   # Mon 系は週 1 行なので営業日に展開
def paths(c,mult,guard):
    r=np.clip(np.asarray(c.values,float)*mult,-guard,None); nb=len(r)-BLOCK+1
    st=rng.integers(0,nb,size=(N,DAYS//BLOCK+1)); return r[(st[:,:,None]+np.arange(BLOCK)[None,None,:])].reshape(N,-1)[:,:DAYS]
def one_step(p):
    eq=np.cumprod(1+p,axis=1); ok=np.zeros(N,bool); fail=np.zeros(N,bool); days=np.full(N,-1)
    for i in range(N):
        e=eq[i]; hwm=np.maximum.accumulate(np.concatenate([[1.0],e[:-1]])); floor=np.minimum(hwm,1.10)-0.10
        dq=np.where(e<=floor)[0]; prof=e-1; dr=p[i]*np.concatenate([[1.0],e[:-1]]); bestday=np.maximum.accumulate(np.maximum(dr,0))
        passd=np.where((prof>=0.10)&(bestday<=0.5*prof))[0]
        if len(dq) and (not len(passd) or dq[0]<passd[0]): fail[i]=True; continue
        if len(passd): ok[i]=True; days[i]=passd[0]+1
    return ok,fail,days
def funded_dq(p,days=250):   # 資金化後 250 日: EOD HWM −10% トレーリング(出金リセット無視=保守側)
    p=p[:,:days]; eq=np.cumprod(1+p,axis=1); hwm=np.maximum.accumulate(np.concatenate([np.ones((N,1)),eq[:,:-1]],axis=1),axis=1)
    return float((eq<=hwm-0.10).any(axis=1).mean())*100
MON4=[("Mon","GBPJPY",.260),("Mon","EURJPY",.266),("Mon","AUDJPY",.215),("Mon","USDJPY",.258)]
MON2=[("Mon","GBPJPY",.537),("Mon","AUDJPY",.463)]
C6M=[("Mon","GBPJPY",.323),("Mon","AUDJPY",.269),("v4","NZDUSD",.207),("v4","AUDUSD",.201)]
NFX=db.BOOK["FN100k_14166201"]["legs"]
G=[("Mon","GBPJPY",.537*0.8),("Mon","AUDJPY",.463*0.8),("Mon","NAS100",.1),("Mon","US500",.1)]   # Mon2×4 + 指数×1 を Σw=1 に正規化 → 倍率 5.0 が G
GAMB=[("Mon","EURJPY",.333),("Mon","USDJPY",.333),("Mon","NZDJPY",.334),("Hold","XAUUSD",.10)]     # Σw=1.1、倍率 5.0
CANDS=[("Mon4(EA3/EA8 型)",MON4,(1.5,2.0,2.5,3.3)),("Mon2(GBPJPY/AUDJPY)",MON2,(1.5,1.75,2.0,3.0,4.0)),
       ("C6m Mon2+v4 NZD/AUD",C6M,(2.5,3.0,4.0,6.0)),("非FX 4 本(#14166201 型)",NFX,(1.48,2.0,3.0)),
       ("G Mon2×4+指数×1 相当",G,(3.0,5.0)),("ギャンブル Mon3+HoldXAU",GAMB,(3.0,5.0))]
try:
    sys.path.insert(0,os.path.join(HERE,"queue")); src=open("queue/q52_donchian_vs_hold.py",encoding="utf-8").read().split("cum = int(sys.argv[1])")[0]
    ns={"__name__":"q52"}; exec(compile(src,"q52","exec"),ns); donchian=ns["donchian"]
    r=donchian("GER40",120,"trail"); brk=r.groupby(r.index.normalize()).sum(); brk=brk[brk.index>=pd.Timestamp("2021-10-01")]
    m4=comp(MON4); idx=m4.index.union(brk.index); ea8=(3.3*m4.reindex(idx).fillna(0)+2.0*brk.reindex(idx).fillna(0))/5.3
    CANDS.append(("EA8 Mon4×3.3+GER40ブレイク×2(Σ5.3)",None,(5.3,)))
except Exception as ex:
    ea8=None; print("EA8 breakout 系列なし:",ex)
END=pd.Timestamp("2026-08-31")
rows=[]
print(f"{'構成':<34}{'倍率':>5} {'年率':>6} {'最大DD':>7} {'最悪日':>7} {'最悪月':>7} | {'資金化12m':>8} {'失格':>5} {'中央日':>5} {'p90':>4} | {'資金化5y':>7} {'失格':>5} {'中央日':>5} | {'資金後250日失格':>8}")
for name,legs,mults in CANDS:
    c=ea8 if legs is None else comp(legs)
    c12=c[c.index>=END-pd.DateOffset(months=12)]
    for m in mults:
        pf=perf(c,m); yrs=(c.index[-1]-c.index[0]).days/365.25; cagr=((1+pf['total_pct']/100)**(1/yrs)-1)*100
        ok,fail,days=one_step(paths(c12,m,GUARD)); ok5,fail5,days5=one_step(paths(c,m,GUARD)); fd=funded_dq(paths(c,m,GUARD))
        md=int(np.median(days[ok])) if ok.any() else -1; p90=int(np.percentile(days[ok],90)) if ok.any() else -1; md5=int(np.median(days5[ok5])) if ok5.any() else -1
        print(f"{name:<34}{m:5.2f} {cagr:5.1f}% {pf['max_dd_pct']:7.2f} {pf['worst_day_pct']:7.2f} {pf['worst_month_pct']:7.2f} | {ok.mean()*100:8.1f} {fail.mean()*100:5.1f} {md:5d} {p90:4d} | {ok5.mean()*100:7.1f} {fail5.mean()*100:5.1f} {md5:5d} | {fd:8.1f}")
        rows.append(dict(cand=name,mult=m,cagr=round(cagr,1),max_dd=pf['max_dd_pct'],worst_day=pf['worst_day_pct'],worst_month=pf['worst_month_pct'],
                         fund12=round(ok.mean()*100,1),dq12=round(fail.mean()*100,1),med12=md,p90_12=p90,fund5y=round(ok5.mean()*100,1),dq5y=round(fail5.mean()*100,1),med5y=md5,funded_dq250=round(fd,1)))
pd.DataFrame(rows).to_csv("results/ftmo_1step_candidates_mc.csv",index=False)
