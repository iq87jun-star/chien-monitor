#!/usr/bin/env python3
"""Multi-pair daily-decision portfolio backtest on real MT5 H1 exports.
Decisions at daily close; execution next day at the 02:00 H1 bar open with
that bar's recorded spread; fixed 3*ATR20 stop checked on H1 bars; no trailing."""
from datetime import datetime
import statistics, math

UP='/root/.claude/uploads/a60920ff-b5f1-54fc-b986-4629d305c95d'
FILES={
 'USDJPY':'197eb218-USDJPY_H1_201601040000_202608260600.csv',
 'GBPJPY':'d4fd87a5-GBPJPY_H1_201601040000_202608260600.csv',
 'EURJPY':'9ba031e2-EURJPY_H1_201601040000_202608260700.csv',
 'USDCHF':'3f69a794-USDCHF_H1_201601040000_202608260600.csv',
 'USDCAD':'4937f389-USDCAD_H1_201601040000_202608260600.csv',
 'AUDUSD':'42d19b48-AUDUSD_H1_201601040000_202608260600.csv',
 'GBPUSD':'8031024f-GBPUSD_H1_201601040000_202608260600.csv',
}

def load(sym):
    rows=[]
    with open(f"{UP}/{FILES[sym]}") as f:
        next(f)
        for line in f:
            c=line.strip().split('\t')
            if len(c)<9: continue
            t=datetime.strptime(c[0]+' '+c[1],'%Y.%m.%d %H:%M:%S')
            rows.append((t,float(c[2]),float(c[3]),float(c[4]),float(c[5]),int(c[8])))
    # infer point from decimals of first close
    dec=len(str(rows[0][4]).split('.')[1]) if '.' in str(rows[0][4]) else 0
    point=10**-dec
    return rows,point

class Pair:
    def __init__(self,sym):
        rows,point=load(sym)
        self.sym=sym; self.point=point
        days={}; order=[]
        hbar={}
        for t,o,h,l,c,sp in rows:
            d=t.date()
            hbar[(d,t.hour)]=(o,h,l,c,sp)
            if d not in days:
                days[d]=[o,h,l,c]; order.append(d)
            else:
                b=days[d]; b[1]=max(b[1],h); b[2]=min(b[2],l); b[3]=c
        self.order=order; self.hbar=hbar
        self.o=[days[d][0] for d in order]; self.h=[days[d][1] for d in order]
        self.l=[days[d][2] for d in order]; self.c=[days[d][3] for d in order]
        n=len(order); self.atr=[None]*n
        trs=[]
        for i in range(n):
            tr=self.h[i]-self.l[i] if i==0 else max(self.h[i]-self.l[i],
                abs(self.h[i]-self.c[i-1]),abs(self.l[i]-self.c[i-1]))
            trs.append(tr)
            if i>=19: self.atr[i]=sum(trs[i-19:i+1])/20
        # rolling extremes cache: computed on demand
    def roll_max(self,i,n):  # max high over [i-n, i-1]
        if i-n<0: return None
        return max(self.h[i-n:i])
    def roll_min(self,i,n):
        if i-n<0: return None
        return min(self.l[i-n:i])

def run(pair, sig_fn, exit_fn, sl_mult=3.0, max_spread_x=3.0):
    """sig_fn(pair,i)->dir for entry decided at close of day i.
    exit_fn(pair,i,pos)->bool decided at close of day i.
    Execution at day i+1's 02:00 bar. max_spread: skip if spread pts >
    max_spread_x * median spread (per pair adaptive)."""
    meds=statistics.median([pair.hbar[k][4] for k in pair.hbar if k[1]==2])
    cap=meds*max_spread_x
    trades=[]; pos=None; pending=None
    n=len(pair.order)
    for i in range(60,n):
        d=pair.order[i]
        eb=pair.hbar.get((d,2))
        # execute pending
        if pending and eb:
            o,h,l,c,sp=eb
            if sp<=cap:
                a=pair.atr[i-1]
                if a:
                    dirn,kind=pending
                    if kind=='open' and pos is None:
                        e=o+sp*pair.point if dirn>0 else o
                        pos={'dir':dirn,'entry':e,'risk':a*sl_mult,
                             'sl':e-a*sl_mult if dirn>0 else e+a*sl_mult}
                    elif kind=='close' and pos:
                        ex=o if pos['dir']>0 else o+sp*pair.point
                        trades.append((datetime.combine(d,datetime.min.time()),
                                       pos['dir']*(ex-pos['entry'])/pos['risk'],pair.sym))
                        pos=None
            pending=None
        # stop check on H1
        if pos:
            for hh in range(24):
                b=pair.hbar.get((d,hh))
                if not b: continue
                o,h,l,c,sp=b
                if pos['dir']>0 and l<=pos['sl']:
                    trades.append((datetime.combine(d,datetime.min.time()),-sl_mult*pair.atr[i-1]/pos['risk'] if False else pos['dir']*(pos['sl']-pos['entry'])/pos['risk'],pair.sym))
                    pos=None; break
                if pos['dir']<0 and h+sp*pair.point>=pos['sl']:
                    trades.append((datetime.combine(d,datetime.min.time()),pos['dir']*(pos['sl']-pos['entry'])/pos['risk'],pair.sym))
                    pos=None; break
        # decide at close
        if pos is None:
            s=sig_fn(pair,i)
            if s: pending=(s,'open')
        else:
            if exit_fn(pair,i,pos): pending=(pos['dir'],'close')
    return trades

# --- systems ---
def don_entry(n):
    def f(p,i):
        hh=p.roll_max(i,n); ll=p.roll_min(i,n)
        if hh is None: return 0
        if p.c[i]>hh: return 1
        if p.c[i]<ll: return -1
        return 0
    return f
def don_exit(n):
    def f(p,i,pos):
        if pos['dir']>0:
            m=p.roll_min(i,n); return m is not None and p.c[i]<m
        else:
            m=p.roll_max(i,n); return m is not None and p.c[i]>m
    return f
def mom_entry(n):
    def f(p,i):
        if i<n+1: return 0
        return 1 if p.c[i]>p.c[i-n] else -1
    return f
def mom_exit(n):
    def f(p,i,pos):
        if i<n+1: return False
        return (p.c[i]<p.c[i-n]) if pos['dir']>0 else (p.c[i]>p.c[i-n])
    return f

def stats(tr,risk=1.0,y0=1900,y1=3000):
    s=[x for x in tr if y0<=x[0].year<=y1]
    if not s: return None
    s.sort()
    bal=100;peak=100;dd=0;gp=gl=0;w=0
    for _,r,_ in s:
        pnl=risk*r
        if pnl>0: gp+=pnl;w+=1
        else: gl+=-pnl
        bal*=(1+pnl/100);peak=max(peak,bal);dd=max(dd,(peak-bal)/peak*100)
    return dict(n=len(s),pf=gp/gl if gl else 99,net=bal-100,dd=dd,wr=100*w/len(s))

if __name__=='__main__':
    pairs=[Pair(s) for s in FILES]
    print("loaded:",", ".join(f"{p.sym}({len(p.order)}d,pt={p.point})" for p in pairs))
    systems=[]
    for n in (10,20,40,55,80):
        systems.append((f'Don{n}/x{n//2}',don_entry(n),don_exit(max(2,n//2))))
    for n in (30,50,60,80,100):
        systems.append((f'Mom{n}',mom_entry(n),mom_exit(n)))
    print(f"\n{'system':<12}{'n':>6}{'PF':>7}{'IS':>7}{'OOS':>7}{'DD%':>6}{'net%':>8}   per-pair PF")
    for name,ef,xf in systems:
        allt=[]; per=[]
        for p in pairs:
            tr=run(p,ef,xf)
            allt.extend(tr)
            st=stats(tr)
            per.append(f"{p.sym[:6]}:{st['pf']:.2f}" if st else f"{p.sym}:n/a")
        st=stats(allt); si=stats(allt,1,2016,2021); so=stats(allt,1,2022,2026)
        print(f"{name:<12}{st['n']:>6}{st['pf']:>7.3f}{si['pf']:>7.3f}{so['pf']:>7.3f}{st['dd']:>6.1f}{st['net']:>+8.1f}   "+" ".join(per))
