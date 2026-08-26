#!/usr/bin/env python3
"""Strategy exploration on real MT5 data. Low path-dependency designs only:
enter at bar open, exit at bar open N bars later or on SL/TP touch.
Costs: per-bar recorded spread on entry (buy) / exit (sell side)."""
from real import load_real, ema, atr_s, stats, POINT

def rsi_series(cl,p):
    out=[None]*len(cl)
    if len(cl)<=p: return out
    g=l=0.0
    for i in range(1,p+1):
        d=cl[i]-cl[i-1]; g+=max(d,0); l+=max(-d,0)
    ag,al=g/p,l/p
    out[p]=100.0 if al==0 else 100-100/(1+ag/al)
    for i in range(p+1,len(cl)):
        d=cl[i]-cl[i-1]
        ag=(ag*(p-1)+max(d,0))/p; al=(al*(p-1)+max(-d,0))/p
        out[i]=100.0 if al==0 else 100-100/(1+ag/al)
    return out

def run_generic(rows, signal, sl_mult=2.0, tp_mult=0.0, max_hold=0, max_spread=30):
    """signal(i, ctx) -> +1/-1/0 evaluated at bar i open (uses bars <= i-1).
    Exit: SL/TP touch intrabar, or at open of bar entry_index+max_hold."""
    cl=[r[4] for r in rows]
    ctx={'cl':cl,'ef':ema(cl,50),'es':ema(cl,200),'e5':ema(cl,5),
         'at':atr_s(rows,14),'rsi2':rsi_series(cl,2),'rsi14':rsi_series(cl,14),'rows':rows}
    n=len(rows); pos=None; trades=[]
    for i in range(210,n):
        t,o,h,l,c,sp=rows[i]
        spread=sp*POINT
        if pos:
            d=pos['dir']; ex=None
            # time exit at this bar's open
            if pos['hold']>0 and i-pos['i0']>=pos['hold']:
                ex=o if d>0 else o+spread
            elif d>0:
                if pos['sl'] and l<=pos['sl']: ex=pos['sl']
                elif pos['tp'] and h>=pos['tp']: ex=pos['tp']
            else:
                if pos['sl'] and h+spread>=pos['sl']: ex=pos['sl']
                elif pos['tp'] and l+spread<=pos['tp']: ex=pos['tp']
            if ex is not None:
                trades.append((t,d*(ex-pos['entry'])/pos['risk'])); pos=None
        if pos is None:
            if t.weekday()>=5: continue
            if max_spread>0 and sp>max_spread: continue
            a=ctx['at'][i-1]
            if a is None or a<=0: continue
            sig=signal(i,ctx)
            if sig==0: continue
            risk=a*sl_mult if sl_mult>0 else a*2.0
            if sig>0:
                e=o+spread
                pos={'dir':1,'entry':e,'i0':i,'hold':max_hold,'risk':risk,
                     'sl':e-a*sl_mult if sl_mult>0 else None,
                     'tp':e+a*tp_mult if tp_mult>0 else None}
            else:
                e=o
                pos={'dir':-1,'entry':e,'i0':i,'hold':max_hold,'risk':risk,
                     'sl':e+a*sl_mult if sl_mult>0 else None,
                     'tp':e-a*tp_mult if tp_mult>0 else None}
    return trades

# --- signal definitions (evaluated at bar i open, data through i-1) ---
def sig_rsi2_mr(i,ctx):
    """Connors-style: uptrend + RSI(2) deeply oversold -> buy (mirror short)."""
    cl,es,r=ctx['cl'],ctx['es'],ctx['rsi2']
    if es[i-1] is None or r[i-1] is None: return 0
    if cl[i-1]>es[i-1] and r[i-1]<10: return 1
    if cl[i-1]<es[i-1] and r[i-1]>90: return -1
    return 0

def sig_rsi14_mr(i,ctx):
    cl,es,r=ctx['cl'],ctx['es'],ctx['rsi14']
    if es[i-1] is None or r[i-1] is None: return 0
    if cl[i-1]>es[i-1] and r[i-1]<30: return 1
    if cl[i-1]<es[i-1] and r[i-1]>70: return -1
    return 0

def make_boll(dev):
    def sig(i,ctx):
        cl,es=ctx['cl'],ctx['es']
        if i<22 or es[i-1] is None: return 0
        w=cl[i-21:i-1]
        m=sum(w)/20
        v=sum((x-m)**2 for x in w)/20
        sd=v**0.5
        if sd<=0: return 0
        if cl[i-1]<m-dev*sd and cl[i-1]>es[i-1]: return 1
        if cl[i-1]>m+dev*sd and cl[i-1]<es[i-1]: return -1
        return 0
    return sig

def make_hour_long(h0):
    def sig(i,ctx):
        return 1 if ctx['rows'][i][0].hour==h0 else 0
    return sig

def make_gotobi(h0):
    def sig(i,ctx):
        t=ctx['rows'][i][0]
        if t.hour!=h0: return 0
        d=t.day
        if d%5==0: return 1
        # weekend-shifted gotobi: Friday before a weekend gotobi
        if t.weekday()==4 and ((d+1)%5==0 or (d+2)%5==0): return 1
        return 0
    return sig

def make_london_bo(rh0,rh1,th):
    """Asia range rows hours [rh0,rh1); at hour th enter breakout direction."""
    def sig(i,ctx):
        rows=ctx['rows']
        t=rows[i][0]
        if t.hour!=th: return 0
        # collect same-day bars with hour in range
        hs=[];ls=[]
        j=i-1
        while j>0 and rows[j][0].date()==t.date() or (j>0 and (t.hour<rh1)):
            tj=rows[j][0]
            if tj.date()!=t.date(): break
            if rh0<=tj.hour<rh1: hs.append(rows[j][2]); ls.append(rows[j][3])
            j-=1
        if len(hs)<3: return 0
        if ctx['cl'][i-1]>max(hs): return 1
        if ctx['cl'][i-1]<min(ls): return -1
        return 0
    return sig

CANDS=[
    ('MR rsi2<10 hold4 SL2',   sig_rsi2_mr,   2.0,0.0,4),
    ('MR rsi2<10 hold8 SL2',   sig_rsi2_mr,   2.0,0.0,8),
    ('MR rsi2<10 hold12 SL3',  sig_rsi2_mr,   3.0,0.0,12),
    ('MR rsi14 30/70 hold12',  sig_rsi14_mr,  2.0,0.0,12),
    ('Boll2.0 fade hold12',    make_boll(2.0),2.0,0.0,12),
    ('Boll2.5 fade hold12',    make_boll(2.5),2.0,0.0,12),
    ('Boll2.5 fade hold24 SL3',make_boll(2.5),3.0,0.0,24),
    ('gotobi buy h1 hold2',    make_gotobi(1),3.0,0.0,2),
    ('gotobi buy h0 hold3',    make_gotobi(0),3.0,0.0,3),
    ('gotobi buy h23p hold4',  make_gotobi(23),3.0,0.0,4),
    ('LDN bo r0-6 t7 hold8',   make_london_bo(0,6,7), 2.0,0.0,8),
    ('LDN bo r0-7 t8 hold6',   make_london_bo(0,7,8), 2.0,0.0,6),
]

if __name__=='__main__':
    import sys
    data={s:load_real(s) for s in ('USDJPY','GBPJPY')}
    print(f"{'strategy':<26}{'pair':<8}{'n':>6}{'WR%':>7}{'PF':>7}{'net%':>9}{'DD%':>7}{'IS PF':>8}{'OOS PF':>8}")
    for name,sig,slm,tpm,hold in CANDS:
        for s in ('USDJPY','GBPJPY'):
            tr=run_generic(data[s],sig,slm,tpm,hold)
            st=stats(tr); si=stats(tr,0.5,2016,2021); so=stats(tr,0.5,2022,2026)
            if not st or not si or not so or st['n']<100:
                print(f"{name:<26}{s:<8}   insufficient trades"); continue
            flag=' <<<' if (si['pf']>1.25 and so['pf']>1.25) else ''
            print(f"{name:<26}{s:<8}{st['n']:>6}{st['wr']:>7.1f}{st['pf']:>7.3f}{st['net']:>+9.1f}{st['dd']:>7.1f}{si['pf']:>8.3f}{so['pf']:>8.3f}{flag}")
