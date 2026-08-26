#!/usr/bin/env python3
"""Broad intraday sweep, 2021-08..2026-08, 7 pairs, real spreads.
Intraday only (hold < 1 day) => zero swap. Entry hours restricted to 2..20
to avoid the rollover-spread artifact. Time-based exits => no path dependency."""
from datetime import datetime, date
import statistics, math
from portfolio import Pair, FILES

START=date(2021,8,1)

class P2:
    def __init__(self,p):
        self.sym=p.sym; self.point=p.point
        self.bars=[]   # (t,o,h,l,c,sp)
        for (d,hh),v in sorted(p.hbar.items()):
            if d<START: continue
            self.bars.append((datetime.combine(d,datetime.min.time()).replace(hour=hh),)+v)
        self.idx={(b[0].date(),b[0].hour):i for i,b in enumerate(self.bars)}
        # daily context
        self.day={}
        for b in self.bars:
            d=b[0].date()
            if d not in self.day: self.day[d]=[b[1],b[2],b[3],b[4]]
            else:
                x=self.day[d]; x[1]=max(x[1],b[2]); x[2]=min(x[2],b[3]); x[3]=b[4]
        self.days=sorted(self.day)
        self.dpos={d:i for i,d in enumerate(self.days)}
        # daily ATR20
        self.atr={}
        trs=[]; prev=None
        for d in self.days:
            o,h,l,c=self.day[d]
            tr=h-l if prev is None else max(h-l,abs(h-prev),abs(l-prev))
            trs.append(tr); prev=c
            if len(trs)>=20: self.atr[d]=sum(trs[-20:])/20

def bt(p2, sig, hold, sl_atr=1.5, max_sp_x=3.0):
    """sig(p2,i)->+1/-1/0 using bars up to i-1; enter at bar i open."""
    meds=statistics.median([b[5] for b in p2.bars])
    cap=meds*max_sp_x
    trades=[]; n=len(p2.bars)
    i=0
    while i<n:
        b=p2.bars[i]; t,o,h,l,c,sp=b
        if sp>cap or t.hour<2 or t.hour>20: i+=1; continue
        a=p2.atr.get(t.date())
        if not a: i+=1; continue
        s=sig(p2,i)
        if s==0: i+=1; continue
        spread=sp*p2.point
        entry=o+spread if s>0 else o
        risk=a*sl_atr
        sl=entry-risk if s>0 else entry+risk
        r=None
        for j in range(i,min(i+hold,n)):
            bj=p2.bars[j]
            if bj[0].date()!=t.date() and (bj[0]-t).total_seconds()>hold*3600: break
            spj=bj[5]*p2.point
            if s>0 and bj[3]<=sl: r=-1.0; i=j; break
            if s<0 and bj[2]+spj>=sl: r=-1.0; i=j; break
        if r is None:
            j=min(i+hold,n-1)
            bj=p2.bars[j]
            ex=bj[1] if s>0 else bj[1]+bj[5]*p2.point
            r=s*(ex-entry)/risk
            i=j
        trades.append((p2.bars[i][0],r))
        i+=1
    return trades

def stat(tr,y0=1900,y1=3000):
    s=[(t,r) for t,r in tr if y0<=t.year<=y1]
    if len(s)<30: return None
    w=[r for _,r in s if r>0]; l=[-r for _,r in s if r<0]
    gp,gl=sum(w),sum(l)
    m=statistics.mean(r for _,r in s)
    sd=statistics.stdev([r for _,r in s]) if len(s)>2 else 1
    return dict(n=len(s),pf=gp/gl if gl else 99,wr=100*len(w)/len(s),
                mean=m,t=m/(sd/math.sqrt(len(s))) if sd>0 else 0)

# ---- signal library ----
def sig_hour(hr,dirn):
    def f(p,i):
        return dirn if p.bars[i][0].hour==hr else 0
    return f
def sig_prevbar_mom(hr,k):
    def f(p,i):
        t=p.bars[i][0]
        if t.hour!=hr or i<2: return 0
        prev=p.bars[i-1]
        rng=prev[2]-prev[3]
        if rng<=0: return 0
        body=prev[4]-prev[1]
        if abs(body)<k*rng: return 0
        return 1 if body>0 else -1
    return f
def sig_prevbar_fade(hr,k):
    g=sig_prevbar_mom(hr,k)
    return lambda p,i: -g(p,i)
def sig_dayopen_break(hr,k):
    def f(p,i):
        t=p.bars[i][0]
        if t.hour!=hr: return 0
        a=p.atr.get(t.date())
        if not a: return 0
        d0=p.idx.get((t.date(),2))
        if d0 is None or d0>=i: return 0
        op=p.bars[d0][1]
        c=p.bars[i-1][4]
        if c>op+k*a: return 1
        if c<op-k*a: return -1
        return 0
    return f
def sig_dayopen_fade(hr,k):
    g=sig_dayopen_break(hr,k)
    return lambda p,i: -g(p,i)
def sig_dow(dow,hr,dirn):
    def f(p,i):
        t=p.bars[i][0]
        return dirn if (t.hour==hr and t.weekday()==dow) else 0
    return f

if __name__=='__main__':
    pairs={s:P2(Pair(s)) for s in FILES}
    print(f"window: {list(pairs.values())[0].bars[0][0]} .. {list(pairs.values())[0].bars[-1][0]}")
    cands=[]
    for hr in (3,7,8,9,13,14,15):
        for hold in (2,4,6):
            cands.append((f'dayopen_break h{hr} k0.5 H{hold}', sig_dayopen_break(hr,0.5), hold))
            cands.append((f'dayopen_fade  h{hr} k0.5 H{hold}', sig_dayopen_fade(hr,0.5), hold))
            cands.append((f'prevbar_mom   h{hr} k0.5 H{hold}', sig_prevbar_mom(hr,0.5), hold))
            cands.append((f'prevbar_fade  h{hr} k0.5 H{hold}', sig_prevbar_fade(hr,0.5), hold))
    print(f"\n{'signal':<30}{'n':>6}{'PF':>7}{'WR%':>6}{'t':>6}{'pos/7':>7}  IS/OOS PF")
    for name,sig,hold in cands:
        allt=[];pos=0
        for s,p in pairs.items():
            tr=bt(p,sig,hold)
            st=stat(tr)
            if st and st['pf']>1.0: pos+=1
            allt.extend(tr)
        a=stat(allt); ai=stat(allt,2021,2023); ao=stat(allt,2024,2026)
        if not a or not ai or not ao: continue
        good = a['pf']>1.10 and pos>=5 and ai['pf']>1.05 and ao['pf']>1.05
        if good or a['pf']>1.08:
            print(f"{name:<30}{a['n']:>6}{a['pf']:>7.3f}{a['wr']:>6.1f}{a['t']:>6.2f}{pos:>5}/7  "
                  f"{ai['pf']:.3f}/{ao['pf']:.3f}"+("  <<<" if good else ""))
