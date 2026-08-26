#!/usr/bin/env python3
"""Correct swap accounting: track actual calendar days held per trade."""
from datetime import datetime
import statistics
from portfolio import Pair, FILES, stats

def run_hold(pair, sig_fn, exit_fn, sl_mult=3.0, max_spread_x=3.0, long_only=False):
    """Same engine as portfolio.run but returns (time, R, sym, days_held)."""
    meds=statistics.median([pair.hbar[k][4] for k in pair.hbar if k[1]==2])
    cap=meds*max_spread_x
    trades=[]; pos=None; pending=None
    n=len(pair.order)
    for i in range(60,n):
        d=pair.order[i]
        eb=pair.hbar.get((d,2))
        if pending and eb:
            o,h,l,c,sp=eb
            if sp<=cap:
                a=pair.atr[i-1]
                if a:
                    dirn,kind=pending
                    if kind=='open' and pos is None:
                        e=o+sp*pair.point if dirn>0 else o
                        pos={'dir':dirn,'entry':e,'risk':a*sl_mult,
                             'sl':e-a*sl_mult if dirn>0 else e+a*sl_mult,'d0':d}
                    elif kind=='close' and pos:
                        ex=o if pos['dir']>0 else o+sp*pair.point
                        trades.append((datetime.combine(d,datetime.min.time()),
                                       pos['dir']*(ex-pos['entry'])/pos['risk'],
                                       pair.sym,(d-pos['d0']).days))
                        pos=None
            pending=None
        if pos:
            for hh in range(24):
                b=pair.hbar.get((d,hh))
                if not b: continue
                o,h,l,c,sp=b
                hit = (pos['dir']>0 and l<=pos['sl']) or (pos['dir']<0 and h+sp*pair.point>=pos['sl'])
                if hit:
                    trades.append((datetime.combine(d,datetime.min.time()),
                                   pos['dir']*(pos['sl']-pos['entry'])/pos['risk'],
                                   pair.sym,(d-pos['d0']).days))
                    pos=None; break
        if pos is None:
            s=sig_fn(pair,i)
            if s and not (long_only and s<0): pending=(s,'open')
        else:
            if exit_fn(pair,i,pos): pending=(pos['dir'],'close')
    return trades

def apply_swap(trades, pair, pips_per_day, sign):
    """sign=+1 credit (we receive), -1 debit. Applied per actual day held."""
    risk=3*statistics.median([a for a in pair.atr if a])
    pip=10*pair.point
    out=[]
    for t,r,sym,days in trades:
        adj = sign*pips_per_day*pip*days/risk
        out.append((t,r+adj,sym))
    return out

if __name__=='__main__':
    pairs={s:Pair(s) for s in FILES}
    def mom(n,long_only=False):
        def e(p,i):
            if i<n+1: return 0
            return 1 if p.c[i]>p.c[i-n] else -1
        def x(p,i,pos):
            if i<n+1: return False
            return (p.c[i]<p.c[i-n]) if pos['dir']>0 else (p.c[i]>p.c[i-n])
        return e,x

    print("=== holding-period reality check (Mom60, both directions) ===")
    for s in ('USDJPY','GBPJPY','USDCHF'):
        e,x=mom(60)
        tr=run_hold(pairs[s],e,x)
        hd=[d for *_,d in tr]
        print(f"{s}: n={len(tr)} median hold={statistics.median(hd):.0f}d mean={statistics.mean(hd):.0f}d max={max(hd)}d")

    print("\n=== LONG-ONLY carry pairs, CORRECT per-day swap accounting ===")
    CARRY=['USDJPY','GBPJPY','USDCHF']
    print(f"{'system':<10}{'swap/d':>8}{'n':>5}{'PF':>7}{'IS':>7}{'OOS':>7}{'DD%':>6}{'net%':>8}  per-pair PF")
    for nm,nn in (('Mom60',60),('Mom100',100)):
        for credit in (0.0,0.2,0.4):
            allt=[];per=[]
            for s in CARRY:
                e,x=mom(nn)
                tr=run_hold(pairs[s],e,x,long_only=True)
                tr2=apply_swap(tr,pairs[s],credit,+1)
                allt.extend(tr2)
                st=stats(tr2)
                per.append(f"{s[:6]}:{st['pf']:.2f}" if st else f"{s}:-")
            a=stats(allt); ai=stats(allt,1,2016,2021); ao=stats(allt,1,2022,2026)
            if not a: continue
            flag=' <<<' if (ai['pf']>1.3 and ao['pf']>1.3) else ''
            print(f"{nm:<10}{credit:>8.1f}{a['n']:>5}{a['pf']:>7.3f}{ai['pf']:>7.3f}{ao['pf']:>7.3f}{a['dd']:>6.1f}{a['net']:>+8.1f}  "+" ".join(per)+flag)
