# -*- coding: utf-8 -*-
"""docs/245: FTMO 1-Step(+10% / EOD トレーリング 10% / 日次 3% / Best Day 50%)と 2-Step(10%→5% / 静的 10% / 日次 5%)を同じ EA 構成で MC 比較。research/ で実行。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import recentfit_screen as base, deployed_book as db, plusmonth_search_h1 as H
from forward.paper_forward import refresh_live
from plusmonth_portfolio import perf
from sess_top5_portfolio import daily
import ea4_compare as E
refresh_live(); rng=np.random.default_rng(11)
WA2={("Mon","GBPJPY"):.260,("Mon","EURJPY"):.266,("Mon","AUDJPY"):.215,("Mon","USDJPY"):.258}
SA={k:db.leg_series(*k) for k in WA2}; cA=E.comp(SA,WA2)
H.A=pd.Timestamp("2021-09-25"); SB={k:daily(sym,h0,span,3) for k,sym,h0,span in E.S8}
cB5=E.comp(SB,E.invvol(SB,[k for k,*_ in E.S5])); cB8=E.comp(SB,E.invvol(SB,[k for k,*_ in E.S8]))
idx=cA.index.union(cB8.index); a,b5,b8=(x.reindex(idx).fillna(0) for x in (cA,cB5,cB8))
eas={"EA3' Mon4":a,"EA2' Mon4+Sess5":0.5*a+0.5*b5,"EA4 Sess8":b8}
N=5000; BLOCK=5; DAYS=500
def paths(c,mult,guard):
    r=np.clip(np.asarray(c.values,float)*mult,-guard,None); nb=len(r)-BLOCK+1
    st=rng.integers(0,nb,size=(N,DAYS//BLOCK+1)); return r[(st[:,:,None]+np.arange(BLOCK)[None,None,:])].reshape(N,-1)[:,:DAYS]
def two_step(p):  # FTMO 2-Step: P1 +10% / P2 +5% / static 10%
    eq=np.cumprod(1+p,axis=1); ok=np.zeros(N,bool); fail=np.zeros(N,bool); days=np.full(N,-1)
    for i in range(N):
        e=eq[i]; hit=np.where(e>=1.10)[0]; dq=np.where(e<=0.90)[0]
        if len(dq) and (not len(hit) or dq[0]<hit[0]): fail[i]=True; continue
        if not len(hit) or hit[0]>=250: continue
        b=e[hit[0]]; e2=e[hit[0]+1:]/b; h2=np.where(e2>=1.05)[0]; d2=np.where(e2<=0.90)[0]
        if len(d2) and (not len(h2) or d2[0]<h2[0]): fail[i]=True; continue
        if len(h2): ok[i]=True; days[i]=hit[0]+1+h2[0]+1
    return ok,fail,days
def one_step(p):  # FTMO 1-Step: +10% / EOD trailing 10% of highest EOD equity (locks at initial once +10%) / best day <=50% of total profit at pass
    eq=np.cumprod(1+p,axis=1); ok=np.zeros(N,bool); fail=np.zeros(N,bool); days=np.full(N,-1)
    for i in range(N):
        e=eq[i]; hwm=np.maximum.accumulate(np.concatenate([[1.0],e[:-1]]))  # EOD high-water mark before today
        floor=np.minimum(hwm,1.10)-0.10  # trailing floor, capped at initial once +10% reached
        dq=np.where(e<=floor)[0]
        prof=e-1; dr=p[i]*np.concatenate([[1.0],e[:-1]])  # $ profit per day (approx)
        bestday=np.maximum.accumulate(np.maximum(dr,0))
        passd=np.where((prof>=0.10)&(bestday<=0.5*prof))[0]
        if len(dq) and (not len(passd) or dq[0]<passd[0]): fail[i]=True; continue
        if len(passd) and passd[0]<DAYS: ok[i]=True; days[i]=passd[0]+1
    return ok,fail,days
def calib(c,guard,floor):
    c12=c[c.index>=E.END-pd.DateOffset(months=12)]
    return min(base.calibrate(c,guard,floor),base.calibrate(c12,guard,floor),6.0)
print(f"{'構成':18s} {'プラン':8s} {'倍率':>5s} {'年率':>6s} {'資金化':>6s} {'失格':>6s} {'中央日':>6s} {'p90':>5s}")
for nm,c in eas.items():
    c12=c[c.index>=E.END-pd.DateOffset(months=12)]
    for plan,guard,floor,fn in (("2-Step",0.04,0.08,two_step),("1-Step",0.024,0.08,one_step)):
        m=calib(c,guard,floor); pf=perf(c,m); cagr=((1+pf['total_pct']/100)**(1/4.25)-1)*100
        ok,fail,days=fn(paths(c12,m,guard))
        print(f"{nm:18s} {plan:8s} {m:5.2f} {cagr:5.1f}% {ok.mean()*100:5.1f}% {fail.mean()*100:5.1f}% {int(np.median(days[ok])) if ok.any() else '-':>6} {int(np.percentile(days[ok],90)) if ok.any() else '-':>5}")
    # 1-Step at the 2-Step multiplier (no re-calibration)
    m2=calib(c,0.04,0.08); ok,fail,days=one_step(paths(c12,m2,0.024))
    print(f"{'':18s} {'1-Step@2S倍率':8s} {m2:5.2f} {'':>6} {ok.mean()*100:5.1f}% {fail.mean()*100:5.1f}% {int(np.median(days[ok])) if ok.any() else '-':>6}")
