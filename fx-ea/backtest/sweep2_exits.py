#!/usr/bin/env python3
"""Sweep exit settings under BOTH an optimistic (bar-close stop updates) and a
pessimistic (intrabar stop updates) model. Keep only settings that survive both."""
import os
from sim2 import load, ema, atr_s, don, FILES, UP, stats

SPREAD={'USDJPY':0.008,'EURJPY':0.010,'GBPJPY':0.016}

def run(rows, spread, c, intrabar):
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
            if d>0:
                if l<=pos['sl']: ex=pos['sl']
                elif pos['tp'] and h>=pos['tp']: ex=pos['tp']
            else:
                if h+spread>=pos['sl']: ex=pos['sl']
                elif pos['tp'] and l+spread<=pos['tp']: ex=pos['tp']
            if ex is None:
                a=at[i]
                ref_up = h if intrabar else cc          # favorable extreme vs close
                ref_dn = l if intrabar else cc
                if a and (be_on or tr_on):
                    if d>0:
                        ns=pos['sl']
                        if be_on and ref_up-pos['entry']>=a*be_trig:
                            ns=max(ns,pos['entry']+a*be_lock)
                        if tr_on:
                            tt=ref_up-a*tr_m
                            if tt>ns and tt>pos['entry']: ns=tt
                        if ns>pos['sl'] and ns<(h if intrabar else cc): pos['sl']=ns
                        if intrabar and l<=pos['sl']: ex=pos['sl']
                    else:
                        ns=pos['sl']
                        if be_on and pos['entry']-(ref_dn+spread)>=a*be_trig:
                            ns=min(ns,pos['entry']-a*be_lock)
                        if tr_on:
                            tt=ref_dn+spread+a*tr_m
                            if tt<ns and tt<pos['entry']: ns=tt
                        if ns<pos['sl'] and ns>(l if intrabar else cc)+spread: pos['sl']=ns
                        if intrabar and h+spread>=pos['sl']: ex=pos['sl']
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

data={s:load(os.path.join(UP,f)) for s,f in FILES.items()}
PAIRS=['USDJPY','GBPJPY','EURJPY']

variants=[]
for tp in (3.0,4.0,0.0):
    for be,bt,bl in ((False,0,0),(True,1.5,0.5),(True,2.0,1.0)):
        for trail in (0.0,3.0,4.0):
            if tp==0.0 and trail==0.0: continue   # needs at least one profit exit
            variants.append(dict(fast=50,slow=200,don=20,sl=2.0,tp=tp,
                                 be=be,be_trig=bt,be_lock=bl,trail=trail,
                                 name=f"TP{tp:g}/BE{'off' if not be else f'{bt:g}+{bl:g}'}/TR{trail:g}"))

print(f"{'variant':<24}{'pair':<8}{'opt: PF/net%/DD':<26}{'pess: PF/net%/DD':<26}{'WR':>6}")
survivors=[]
for v in variants:
    worst=99; lines=[]; ok=True
    for s in PAIRS:
        to=stats(run(data[s],SPREAD[s],v,False))
        tp_=stats(run(data[s],SPREAD[s],v,True))
        if not to or not tp_: ok=False; break
        lines.append((s,to,tp_))
        worst=min(worst,to['pf'],tp_['pf'])
        if to['pf']<=1.0 or tp_['pf']<=1.0: ok=False
    if not lines: continue
    mark=' <<<' if ok else ''
    for s,to,tp_ in lines:
        print(f"{v['name']:<24}{s:<8}"
              f"{to['pf']:.2f}/{to['net']:+7.1f}%/{to['dd']:4.1f}%      "
              f"{tp_['pf']:.2f}/{tp_['net']:+7.1f}%/{tp_['dd']:4.1f}%   {tp_['wr']:5.1f}%{mark}")
    if ok: survivors.append((v['name'],worst))
print("\n--- survives BOTH models on all 3 pairs ---")
for n,w in sorted(survivors,key=lambda x:-x[1]): print(f"{n}   worstPF={w:.2f}")
if not survivors: print("(none)")
