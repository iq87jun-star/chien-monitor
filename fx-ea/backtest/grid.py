#!/usr/bin/env python3
"""Grid / scaled-entry basket simulator on real MT5 H1 bars with recorded spread.

Design under test (deliberately NOT classic martingale):
  - open a basket in the mean-reverting direction when price is stretched
  - add a position every `step` x ATR further against us, lot x `mult`
  - close the whole basket at `tp` x ATR of favourable move from the
    volume-weighted average entry
  - hard exit the whole basket if its open loss exceeds `ruin_pct` of equity
Costs: real per-bar spread on every fill, plus a per-day swap charge.
Intrabar order is pessimistic: adds are processed before take-profit.
"""
from datetime import datetime
import statistics
from portfolio import Pair, FILES

def run_grid(pair, step_atr=1.0, mult=1.4, max_levels=6, tp_atr=1.0,
             ruin_pct=30.0, entry_lookback=20, swap_pips_day=0.3,
             base_risk_pct=0.25, max_spread_x=3.0):
    """Returns (baskets, equity_curve, ruin_events).
    base_risk_pct: first leg risks this % of equity per `step_atr` of adverse move,
    so total exposure is bounded by the geometric series."""
    meds=statistics.median([pair.hbar[k][4] for k in pair.hbar if k[1]==2])
    cap=meds*max_spread_x
    pip=10*pair.point

    equity=100.0
    baskets=[]; curve=[]; ruins=0
    pos=None   # dict: dir, legs[(price,lot)], next_add, level, day_opened
    n=len(pair.order)
    for i in range(60,n):
        d=pair.order[i]
        a=pair.atr[i-1]
        if a is None or a<=0: continue
        for hh in range(24):
            b=pair.hbar.get((d,hh))
            if not b: continue
            o,h,l,c,sp=b
            spread=sp*pair.point
            if pos:
                # 1) adds (pessimistic: before TP)
                while pos['level']<max_levels:
                    lvl=pos['next_add']
                    hit = (l<=lvl) if pos['dir']>0 else (h+spread>=lvl)
                    if not hit: break
                    lot=pos['legs'][-1][1]*mult
                    fill=lvl+spread if pos['dir']>0 else lvl
                    pos['legs'].append((fill,lot))
                    pos['level']+=1
                    pos['next_add']=lvl-a*step_atr if pos['dir']>0 else lvl+a*step_atr
                # 2) basket state at this bar's extremes
                tot=sum(x[1] for x in pos['legs'])
                vwap=sum(p*w for p,w in pos['legs'])/tot
                adverse = l if pos['dir']>0 else h+spread
                fav     = h if pos['dir']>0 else l+spread
                open_loss = pos['dir']*(adverse-vwap)*tot        # in price*lot units
                held=(d-pos['d0']).days
                swap_cost = swap_pips_day*pip*held*tot
                loss_pct = -(open_loss-swap_cost)/pos['unit']*base_risk_pct
                if loss_pct>=ruin_pct:
                    equity*= (1-ruin_pct/100)
                    baskets.append((datetime.combine(d,datetime.min.time()),-ruin_pct,'RUIN'))
                    ruins+=1; pos=None
                    curve.append(equity); continue
                # 3) take profit
                tgt = vwap+a*tp_atr if pos['dir']>0 else vwap-a*tp_atr
                if (fav>=tgt if pos['dir']>0 else fav<=tgt):
                    pnl = pos['dir']*(tgt-vwap)*tot - swap_cost
                    pct = pnl/pos['unit']*base_risk_pct
                    equity*=(1+pct/100)
                    baskets.append((datetime.combine(d,datetime.min.time()),pct,'TP'))
                    pos=None
                    curve.append(equity); continue
            elif hh==2 and sp<=cap:
                # entry: fade a stretch away from the N-day mean
                if i<entry_lookback+2: continue
                m=sum(pair.c[i-entry_lookback:i])/entry_lookback
                dev=pair.c[i-1]-m
                if abs(dev)<a*step_atr: continue
                dirn = 1 if dev<0 else -1
                fill = o+spread if dirn>0 else o
                # unit = price move of one step_atr on lot 1.0 => normalises risk
                pos={'dir':dirn,'legs':[(fill,1.0)],'level':1,'d0':d,
                     'next_add': fill-a*step_atr if dirn>0 else fill+a*step_atr,
                     'unit': a*step_atr}
        curve.append(equity)
    return baskets, curve, ruins

def summarise(baskets, curve, ruins, label):
    if not baskets: return None
    w=[p for _,p,_ in baskets if p>0]; l=[-p for _,p,_ in baskets if p<0]
    gp,gl=sum(w),sum(l)
    peak=curve[0]; dd=0
    for v in curve:
        peak=max(peak,v); dd=max(dd,(peak-v)/peak*100)
    return dict(label=label,n=len(baskets),wr=100*len(w)/len(baskets),
                pf=gp/gl if gl else 99, net=curve[-1]-100, dd=dd, ruins=ruins)

if __name__=='__main__':
    pairs={s:Pair(s) for s in FILES}
    print("=== baseline grid: step1.0ATR mult1.4 max6 tp1.0ATR ruin30% swap0.3 ===")
    print(f"{'pair':<8}{'n':>5}{'WR%':>6}{'PF':>7}{'net%':>9}{'DD%':>7}{'ruins':>7}")
    for s,p in pairs.items():
        b,c,r=run_grid(p)
        st=summarise(b,c,r,s)
        if not st: print(f"{s:<8} no baskets"); continue
        print(f"{s:<8}{st['n']:>5}{st['wr']:>6.1f}{st['pf']:>7.3f}{st['net']:>+9.1f}{st['dd']:>7.1f}{st['ruins']:>7}")
