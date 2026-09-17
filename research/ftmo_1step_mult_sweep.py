# -*- coding: utf-8 -*-
"""docs/246: FTMO 1-Step 規則下で Sess 8 の倍率 3.3〜12 を往復 2/3/3.5pip で MC。research/ で実行。※資金化後 250 日列は集計軸の誤りで無効(docs/246 §1 参照)。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); os.chdir(HERE)
import recentfit_screen as base, plusmonth_search_h1 as H
from forward.paper_forward import refresh_live
from plusmonth_portfolio import perf
from sess_top5_portfolio import daily
import ea4_compare as E
refresh_live(); rng=np.random.default_rng(23)
N=5000; BLOCK=5; DAYS=500
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
def funded_life(p,dd=0.10,days=250):  # after funding: trailing 10% from EOD HWM (resets at payout ignored = conservative), 250 days
    p=p[:,:days]; eq=np.cumprod(1+p,axis=1); hwm=np.maximum.accumulate(np.concatenate([np.ones((N,1)),eq[:,:-1]],axis=1))
    return round(float((eq<=hwm-dd).any(axis=1).mean())*100,1)
H.A=pd.Timestamp("2021-09-25")
for cost in (2,3,3.5):
    SB={k:daily(sym,h0,span,cost) for k,sym,h0,span in E.S8}; c=E.comp(SB,E.invvol(SB,[k for k,*_ in E.S8]))
    c12=c[c.index>=E.END-pd.DateOffset(months=12)]; oos=c[c.index>pd.Timestamp("2024-12-31")]
    print(f"\n=== Sess 8 往復 {cost}pip ===  raw校正(2.4%/8%): {base.calibrate(c,0.024,0.08)/0.8:.2f}(全期間) {base.calibrate(c12,0.024,0.08)/0.8:.2f}(12m)")
    print(f"{'倍率':>5} {'年率':>6} {'最大DD':>7} {'最悪日':>7} {'最悪月':>7} | {'資金化12m':>8} {'失格':>5} {'中央日':>5} {'p90':>4} | {'資金化OOS25':>9} {'失格':>5} | {'資金化後250日失格':>8}")
    for m in (3.3,4.8,6.0,8.0,10.0,12.0):
        pf=perf(c,m); cagr=((1+pf['total_pct']/100)**(1/4.25)-1)*100
        ok,fail,days=one_step(paths(c12,m,0.024)); ok2,fail2,_=one_step(paths(oos,m,0.024)); fl=funded_life(paths(c12,m,0.024))
        print(f"{m:5.1f} {cagr:5.1f}% {pf['max_dd_pct']:7.2f} {pf['worst_day_pct']:7.2f} {pf['worst_month_pct']:7.2f} | {ok.mean()*100:8.1f} {fail.mean()*100:5.1f} {int(np.median(days[ok])):5d} {int(np.percentile(days[ok],90)):4d} | {ok2.mean()*100:9.1f} {fail2.mean()*100:5.1f} | {fl:8.1f}")
