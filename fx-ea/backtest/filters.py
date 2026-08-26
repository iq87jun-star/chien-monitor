#!/usr/bin/env python3
"""Test regime filters. Accept only if IS and OOS both improve on both pairs."""
import os
from sim2 import load, ema, atr_s, don, FILES, UP, stats

SPREAD={'USDJPY':0.008,'EURJPY':0.010,'GBPJPY':0.016}

def adx_series(rows,p=14):
    n=len(rows); out=[None]*n
    if n<2*p+2: return out
    tr=[0.0]*n; pdm=[0.0]*n; ndm=[0.0]*n
    for i in range(1,n):
        h,l,ph,pl,pc=rows[i][2],rows[i][3],rows[i-1][2],rows[i-1][3],rows[i-1][4]
        tr[i]=max(h-l,abs(h-pc),abs(l-pc))
        up,dn=h-ph,pl-l
        pdm[i]=up if (up>dn and up>0) else 0.0
        ndm[i]=dn if (dn>up and dn>0) else 0.0
    atr_=sum(tr[1:p+1]); ap=sum(pdm[1:p+1]); an=sum(ndm[1:p+1])
    dx=[None]*n
    for i in range(p+1,n):
        atr_=atr_-atr_/p+tr[i]; ap=ap-ap/p+pdm[i]; an=an-an/p+ndm[i]
        if atr_<=0: continue
        pdi=100*ap/atr_; ndi=100*an/atr_
        s=pdi+ndi
        dx[i]=100*abs(pdi-ndi)/s if s>0 else 0.0
    first=p+1+p
    if first>=n: return out
    vals=[d for d in dx[p+1:first] if d is not None]
    if not vals: return out
    out[first-1]=sum(vals)/len(vals)
    for i in range(first,n):
        if dx[i] is None or out[i-1] is None: continue
        out[i]=(out[i-1]*(p-1)+dx[i])/p
    return out

def run(rows, spread, cfg):
    cl=[r[4] for r in rows]
    ef=ema(cl,50); es=ema(cl,200); at=atr_s(rows,14)
    hh,ll=don(rows,20)
    adx=adx_series(rows,14) if cfg.get('adx') else None
    sep=cfg.get('sep')        # min |ef-es| as multiple of ATR
    slope=cfg.get('slope')    # min slow-EMA move over 20 bars, in ATR
    pos=None; trades=[]
    for i in range(210,len(rows)):
        t,o,h,l,c=rows[i]
        if pos:
            d=pos['dir']; ex=None
            if d>0:
                if l<=pos['sl']: ex=pos['sl']
                elif h>=pos['tp']: ex=pos['tp']
            else:
                if h+spread>=pos['sl']: ex=pos['sl']
                elif l+spread<=pos['tp']: ex=pos['tp']
            if ex is None:
                a=at[i]
                if a:
                    if d>0:
                        tr_=h-a*4.0
                        if tr_>pos['sl'] and tr_>pos['entry']: pos['sl']=tr_
                        if l<=pos['sl']: ex=pos['sl']
                    else:
                        tr_=l+spread+a*4.0
                        if tr_<pos['sl'] and tr_<pos['entry']: pos['sl']=tr_
                        if h+spread>=pos['sl']: ex=pos['sl']
            if ex is not None:
                trades.append((t,d*(ex-pos['entry'])/pos['sl0'])); pos=None
        if pos is None:
            if t.weekday()>=5: continue
            a=at[i-1]
            if None in (ef[i-1],es[i-1],a,hh[i-1]) or a<=0: continue
            if adx is not None:
                if adx[i-1] is None or adx[i-1] < cfg['adx']: continue
            if sep is not None and abs(ef[i-1]-es[i-1]) < sep*a: continue
            if slope is not None:
                if es[i-21] is None: continue
                sl_=es[i-1]-es[i-21]
            up=ef[i-1]>es[i-1]; dn=ef[i-1]<es[i-1]; pc=rows[i-1][4]
            if slope is not None:
                if up and sl_ < slope*a: continue
                if dn and sl_ > -slope*a: continue
            if up and pc>hh[i-1]:
                e=o+spread
                pos={'dir':1,'entry':e,'sl':e-a*2.0,'tp':e+a*4.0,'sl0':a*2.0}
            elif dn and pc<ll[i-1]:
                e=o
                pos={'dir':-1,'entry':e,'sl':e+a*2.0,'tp':e-a*4.0,'sl0':a*2.0}
    return trades

data={s:load(os.path.join(UP,f)) for s,f in FILES.items()}
PAIRS=['USDJPY','GBPJPY','EURJPY']

cands=[('baseline',{})]
for x in (20,25,30): cands.append((f'ADX>{x}',{'adx':x}))
for k in (0.5,1.0,2.0): cands.append((f'EMAsep>{k}ATR',{'sep':k}))
for k in (0.5,1.0): cands.append((f'EMAslope>{k}ATR/20b',{'slope':k}))
cands.append(('ADX>25 + sep>1ATR',{'adx':25,'sep':1.0}))

print(f"{'filter':<22}{'pair':<8}{'IS n/PF':<16}{'OOS n/PF':<16}{'full PF':<9}")
for name,cfg in cands:
    ok=True; rows_out=[]
    for s in PAIRS:
        tr=run(data[s],SPREAD[s],cfg)
        si=stats(tr,0.5,2016,2021); so=stats(tr,0.5,2022,2025)
        if not si or not so: ok=False; break
        rows_out.append((s,si,so,stats(tr,0.5)))
        if s in ('USDJPY','GBPJPY') and (si['pf']<1.25 or so['pf']<1.25): ok=False
    if not rows_out: continue
    mark=' <<<' if ok else ''
    for s,si,so,fu in rows_out:
        print(f"{name:<22}{s:<8}{si['n']:>4}/{si['pf']:.3f}      {so['n']:>4}/{so['pf']:.3f}      {fu['pf']:.3f}{mark}")
