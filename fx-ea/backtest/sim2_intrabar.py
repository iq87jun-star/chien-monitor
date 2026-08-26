#!/usr/bin/env python3
"""Intrabar-aware simulation: stops are moved using the bar's favorable extreme,
then re-checked against the same bar's adverse extreme (approximates tick-level
trailing, which the bar-close model underestimated)."""
import csv, os
from datetime import datetime

UP = '/root/.claude/uploads/a60920ff-b5f1-54fc-b986-4629d305c95d'
FILES = {'USDJPY': '4fc0bf86-USDJPY_h1.csv',
         'EURJPY': '0fb4ac0c-EURJPY_h1.csv',
         'GBPJPY': 'ad848be3-GBPJPY_h1.csv'}

def load(path):
    rows = []
    with open(path) as f:
        r = csv.reader(f); next(r)
        for l in r:
            rows.append((datetime.strptime(l[0], '%Y-%m-%d %H:%M:%S'),
                         float(l[1]), float(l[2]), float(l[3]), float(l[4])))
    return rows

def ema(cl, p):
    out=[None]*len(cl); k=2.0/(p+1)
    out[p-1]=sum(cl[:p])/p
    for i in range(p,len(cl)): out[i]=cl[i]*k+out[i-1]*(1-k)
    return out

def atr_s(rows,p):
    n=len(rows); out=[None]*n; tr=[None]*n
    for i in range(1,n):
        h,l,pc=rows[i][2],rows[i][3],rows[i-1][4]
        tr[i]=max(h-l,abs(h-pc),abs(l-pc))
    out[p]=sum(tr[1:p+1])/p
    for i in range(p+1,n): out[i]=(out[i-1]*(p-1)+tr[i])/p
    return out

def don(rows,p):
    n=len(rows); hh=[None]*n; ll=[None]*n
    import collections
    for i in range(p,n):
        hh[i]=max(rows[j][2] for j in range(i-p,i))
        ll[i]=min(rows[j][3] for j in range(i-p,i))
    return hh,ll

def run(rows, spread, c):
    cl=[r[4] for r in rows]
    ef=ema(cl,c['fast']); es=ema(cl,c['slow']); at=atr_s(rows,14)
    hh,ll=don(rows,c['don'])
    sl_m,tp_m=c['sl'],c['tp']
    be_on,be_trig,be_lock=c['be'],c['be_trig'],c['be_lock']
    tr_on,tr_m=c['trail']>0,c['trail']
    pos=None; trades=[]
    for i in range(c['slow']+5,len(rows)):
        t,o,h,l,cc=rows[i]
        if pos:
            d=pos['dir']; ex=None
            # 1) exits against the stop/TP as they stand at bar open
            if d>0:
                if l<=pos['sl']: ex=pos['sl']
                elif pos['tp'] and h>=pos['tp']: ex=pos['tp']
            else:
                if h+spread>=pos['sl']: ex=pos['sl']
                elif pos['tp'] and l+spread<=pos['tp']: ex=pos['tp']
            if ex is None:
                # 2) move stop using the bar's favorable extreme (tick-like)
                a=at[i]
                if a and (be_on or tr_on):
                    if d>0:
                        ns=pos['sl']
                        if be_on and h-pos['entry']>=a*be_trig:
                            ns=max(ns,pos['entry']+a*be_lock)
                        if tr_on:
                            tt=h-a*tr_m
                            if tt>ns and tt>pos['entry']: ns=tt
                        if ns>pos['sl']: pos['sl']=ns
                        # 3) the same bar can then retrace into the new stop
                        if l<=pos['sl']: ex=pos['sl']
                    else:
                        ns=pos['sl']
                        if be_on and pos['entry']-(l+spread)>=a*be_trig:
                            ns=min(ns,pos['entry']-a*be_lock)
                        if tr_on:
                            tt=l+spread+a*tr_m
                            if tt<ns and tt<pos['entry']: ns=tt
                        if ns<pos['sl']: pos['sl']=ns
                        if h+spread>=pos['sl']: ex=pos['sl']
            if ex is not None:
                trades.append((t,d*(ex-pos['entry'])/pos['sl0'])); pos=None
        if pos is None:
            if t.weekday()>=5: continue
            a=at[i-1]
            if None in (ef[i-1],es[i-1],a,hh[i-1]) or a<=0: continue
            up=ef[i-1]>es[i-1]; dn=ef[i-1]<es[i-1]; pc=rows[i-1][4]
            if up and pc>hh[i-1]:
                e=o+spread
                pos={'dir':1,'entry':e,'sl':e-a*sl_m,'tp':e+a*tp_m if tp_m>0 else None,'sl0':a*sl_m}
            elif dn and pc<ll[i-1]:
                e=o
                pos={'dir':-1,'entry':e,'sl':e+a*sl_m,'tp':e-a*tp_m if tp_m>0 else None,'sl0':a*sl_m}
    return trades

def stats(tr,risk=1.0,y0=1900,y1=3000):
    tr=[(t,r) for t,r in tr if y0<=t.year<=y1]
    n=len(tr)
    if not n: return None
    bal=100.0;peak=100.0;dd=0.0;gp=gl=0.0;w=0
    for _,r in tr:
        p=risk*r
        if p>0: gp+=p; w+=1
        else: gl+=-p
        bal*=(1+p/100); peak=max(peak,bal); dd=max(dd,(peak-bal)/peak*100)
    return dict(n=n,pf=gp/gl if gl else 99,net=bal-100,dd=dd,wr=w/n*100,
                aw=gp/w if w else 0, al=gl/(n-w) if n-w else 0)

if __name__=='__main__':
    data={s:load(os.path.join(UP,f)) for s,f in FILES.items()}
    base=dict(fast=50,slow=200,don=20,sl=2.0,tp=3.0,be=True,be_trig=1.0,be_lock=0.1,trail=2.0)
    print("=== validation: default params vs MT5 actual (USDJPY PF 1.085 / WR 66.3%) ===")
    for sp in (0.006,0.010,0.015):
        st=stats(run(data['USDJPY'],sp,base))
        print(f"spread={sp}: n={st['n']} WR={st['wr']:.1f}% PF={st['pf']:.3f} "
              f"net={st['net']:+.1f}% DD={st['dd']:.1f}% avgW/avgL={st['aw']/st['al']:.2f}")
