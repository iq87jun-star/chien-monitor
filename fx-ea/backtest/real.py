#!/usr/bin/env python3
"""Loader + engine for MT5-exported bar data with per-bar recorded spread."""
from datetime import datetime

UP='/root/.claude/uploads/a60920ff-b5f1-54fc-b986-4629d305c95d'
REAL={'USDJPY':'197eb218-USDJPY_H1_201601040000_202608260600.csv',
      'GBPJPY':'d4fd87a5-GBPJPY_H1_201601040000_202608260600.csv'}
POINT=0.001  # 3-digit JPY pairs

def load_real(sym):
    rows=[]
    with open(f"{UP}/{REAL[sym]}") as f:
        next(f)
        for line in f:
            c=line.strip().split('\t')
            if len(c)<9: continue
            t=datetime.strptime(c[0]+' '+c[1],'%Y.%m.%d %H:%M:%S')
            rows.append((t,float(c[2]),float(c[3]),float(c[4]),float(c[5]),int(c[8])))
    return rows  # (time, o, h, l, c, spread_points)

def ema(vals,p):
    out=[None]*len(vals); k=2.0/(p+1)
    if len(vals)<p: return out
    out[p-1]=sum(vals[:p])/p
    for i in range(p,len(vals)): out[i]=vals[i]*k+out[i-1]*(1-k)
    return out

def atr_s(rows,p):
    n=len(rows); out=[None]*n; tr=[None]*n
    for i in range(1,n):
        h,l,pc=rows[i][2],rows[i][3],rows[i-1][4]
        tr[i]=max(h-l,abs(h-pc),abs(l-pc))
    if n<=p: return out
    out[p]=sum(tr[1:p+1])/p
    for i in range(p+1,n): out[i]=(out[i-1]*(p-1)+tr[i])/p
    return out

def stats(trades,risk=0.5,y0=1900,y1=3000):
    tr=[(t,r) for t,r in trades if y0<=t.year<=y1]
    n=len(tr)
    if n==0: return None
    bal=100.0;peak=100.0;dd=0.0;gp=gl=0.0;w=0
    for _,r in tr:
        p=risk*r
        if p>0: gp+=p; w+=1
        else: gl+=-p
        bal*=(1+p/100); peak=max(peak,bal); dd=max(dd,(peak-bal)/peak*100)
    return dict(n=n,pf=(gp/gl if gl>0 else 99),net=bal-100,dd=dd,wr=w/n*100)

def run_donchian(rows, max_spread_pts=30):
    """v1.30 logic on real data: per-bar spread, spread filter, pessimistic intrabar."""
    cl=[r[4] for r in rows]
    ef=ema(cl,50); es=ema(cl,200); at=atr_s(rows,14)
    n=len(rows); pos=None; trades=[]
    # precompute rolling donchian over bars [i-21..i-2]
    from collections import deque
    for i in range(210,n):
        t,o,h,l,c,sp=rows[i]
        spread=sp*POINT
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
            if max_spread_pts>0 and sp>max_spread_pts: continue
            a=at[i-1]
            if None in (ef[i-1],es[i-1],a) or a<=0: continue
            hh=max(rows[j][2] for j in range(i-21,i-1))
            ll=min(rows[j][3] for j in range(i-21,i-1))
            pc=rows[i-1][4]
            if ef[i-1]>es[i-1] and pc>hh:
                e=o+spread
                pos={'dir':1,'entry':e,'sl':e-a*2.0,'tp':e+a*4.0,'sl0':a*2.0}
            elif ef[i-1]<es[i-1] and pc<ll:
                e=o
                pos={'dir':-1,'entry':e,'sl':e+a*2.0,'tp':e-a*4.0,'sl0':a*2.0}
    return trades

if __name__=='__main__':
    print("=== calibration: v1.30 logic on REAL exported data vs MT5 measured ===\n")
    target={'USDJPY':(1542,38.3,1.082,21.2),'GBPJPY':(1232,37.3,1.021,15.6)}
    for s in ('USDJPY','GBPJPY'):
        rows=load_real(s)
        sps=[r[5] for r in rows]
        print(f"{s}: {len(rows)} bars {rows[0][0]}..{rows[-1][0]}  median spread={sorted(sps)[len(sps)//2]} pts")
        tr=run_donchian(rows)
        st=stats(tr)
        tn,tw,tp_,td=target[s]
        print(f"  sim : n={st['n']}  WR={st['wr']:.1f}%  PF={st['pf']:.3f}  net={st['net']:+.1f}%  DD={st['dd']:.1f}%")
        print(f"  MT5 : n={tn}  WR={tw}%  PF={tp_}  DD={td}%\n")
