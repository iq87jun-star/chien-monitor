#!/usr/bin/env python3
"""Re-test the user's own prop strategies (v4 / v7) on real MT5 H1 exports.
v7: Monday open -> Tuesday open on yen crosses, 2 pip cost.
v4: 4-condition consensus mean reversion, SL 1.5ATR, TP 1.2*SL, max hold 8d."""
import statistics, math
from portfolio import Pair, FILES

def daily(pair):
    """server-day OHLC from H1 (MT5 server day == the broker's trading day)."""
    d={}; order=[]
    for (dt,hh),v in sorted(pair.hbar.items()):
        if dt not in d: d[dt]=[v[0],v[1],v[2],v[3]]; order.append(dt)
        else:
            x=d[dt]; x[1]=max(x[1],v[1]); x[2]=min(x[2],v[2]); x[3]=v[3]
    return order,d

def rsi_w(c,n=14):
    out=[None]*len(c); g=l=0.0
    for i in range(1,n+1):
        ch=c[i]-c[i-1]; g+=max(ch,0); l+=max(-ch,0)
    au,ad=g/n,l/n
    out[n]=100-100/(1+au/ad) if ad>0 else 100.0
    for i in range(n+1,len(c)):
        ch=c[i]-c[i-1]
        au=(au*(n-1)+max(ch,0))/n; ad=(ad*(n-1)+max(-ch,0))/n
        out[i]=100-100/(1+au/ad) if ad>0 else 100.0
    return out

def atr_w(h,l,c,n=14):
    out=[None]*len(c); tr=[]
    for i in range(len(c)):
        t=h[i]-l[i] if i==0 else max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
        tr.append(t)
    out[0]=tr[0]
    for i in range(1,len(c)): out[i]=(out[i-1]*(n-1)+tr[i])/n
    return out

def pipsize(sym): return 0.01 if sym.endswith('JPY') else 0.0001

def v7(pair, cost_pips=2.0):
    """Monday open -> Tuesday(next trading day) open."""
    order,d=daily(pair)
    ps=pipsize(pair.sym); rets=[]
    for i in range(len(order)-1):
        if order[i].weekday()!=0: continue
        o0=d[order[i]][0]; o1=d[order[i+1]][0]
        rets.append((order[i], (o1-o0)/o0 - cost_pips*ps/o0))
    return rets

def v4(pair, cost_pips=2.0, need=4):
    order,d=daily(pair)
    o=[d[x][0] for x in order]; h=[d[x][1] for x in order]
    l=[d[x][2] for x in order]; c=[d[x][3] for x in order]
    rsi=rsi_w(c); atr=atr_w(h,l,c)
    ps=pipsize(pair.sym); cost=cost_pips*ps
    n=len(c); trades=[]; i=22
    while i<n-1:
        w=c[i-20:i]; m=statistics.mean(w); sd=statistics.stdev(w) if len(w)>1 else 0
        z=(c[i]-m)/sd if sd>0 else 0.0
        down=0
        for k in range(12):
            if i-k-1>=0 and c[i-k]<c[i-k-1]: down+=1
            else: break
        up=0
        for k in range(12):
            if i-k-1>=0 and c[i-k]>c[i-k-1]: up+=1
            else: break
        ret=(c[i]-c[i-1])/c[i-1] if c[i-1] else 0.0
        mv=0.005
        buy=(rsi[i]<35)+(z<-1.5)+(down>=3)+(ret<-mv)
        sell=(rsi[i]>65)+(z>1.5)+(up>=3)+(ret>mv)
        sig=1 if (buy>=need and buy>sell) else (-1 if (sell>=need and sell>buy) else 0)
        if sig==0: i+=1; continue
        entry=o[i+1]; sld=1.5*atr[i]; tpd=1.2*sld
        if sld<=0: i+=1; continue
        sl=entry-sig*sld; tp=entry+sig*tpd
        ex=None; j=i+1; held=0
        while j<n and held<8:
            if sig>0:
                if l[j]<=sl: ex=sl; break
                if h[j]>=tp: ex=tp; break
            else:
                if h[j]>=sl: ex=sl; break
                if l[j]<=tp: ex=tp; break
            j+=1; held+=1
        if ex is None: ex=c[min(j,n-1)]
        r=sig*(ex/entry-1.0)-cost/entry
        trades.append((order[min(j,n-1)], r))
        i=max(i+1,j)
    return trades

def stat(rs,y0=1900,y1=3000):
    s=[(t,r) for t,r in rs if y0<=t.year<=y1]
    if len(s)<20: return None
    w=[r for _,r in s if r>0]; l=[-r for _,r in s if r<0]
    gp,gl=sum(w),sum(l)
    m=statistics.mean([r for _,r in s]); sd=statistics.stdev([r for _,r in s])
    eq=1.0; peak=1.0; dd=0
    for _,r in s:
        eq*=(1+r); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
    return dict(n=len(s),pf=gp/gl if gl else 99,wr=100*len(w)/len(s),
                mean_bp=m*1e4,t=m/(sd/math.sqrt(len(s))),net=(eq-1)*100,dd=dd)

if __name__=='__main__':
    pairs={s:Pair(s) for s in FILES}
    YEN=['EURJPY','GBPJPY','USDJPY']
    print("=== v7: Monday open->next open, yen crosses, MT5 real data, 2pip cost ===")
    print(f"{'pair':<8}{'n':>5}{'PF':>7}{'WR%':>6}{'bp/tr':>8}{'t':>6}{'net%':>9}{'DD%':>7}   IS/OOS PF")
    allv7=[]
    for s in YEN:
        r=v7(pairs[s]); allv7+= [(t,x/3) for t,x in r]
        a=stat(r); i1=stat(r,2016,2020); i2=stat(r,2021,2026)
        print(f"{s:<8}{a['n']:>5}{a['pf']:>7.3f}{a['wr']:>6.1f}{a['mean_bp']:>8.2f}{a['t']:>6.2f}"
              f"{a['net']:>+9.1f}{a['dd']:>7.1f}   {i1['pf']:.3f}/{i2['pf']:.3f}")
    a=stat(allv7); i1=stat(allv7,2016,2020); i2=stat(allv7,2021,2026)
    print(f"{'PORT':<8}{a['n']:>5}{a['pf']:>7.3f}{a['wr']:>6.1f}{a['mean_bp']:>8.2f}{a['t']:>6.2f}"
          f"{a['net']:>+9.1f}{a['dd']:>7.1f}   {i1['pf']:.3f}/{i2['pf']:.3f}")

    print("\n=== v4: 4-condition consensus mean reversion, 7 pairs ===")
    print(f"{'pair':<8}{'n':>5}{'PF':>7}{'WR%':>6}{'bp/tr':>8}{'t':>6}{'net%':>9}   IS/OOS PF")
    allv4=[]
    for s in FILES:
        tr=v4(pairs[s])
        a=stat(tr)
        if not a: print(f"{s:<8} too few"); continue
        allv4+=tr
        i1=stat(tr,2016,2020); i2=stat(tr,2021,2026)
        print(f"{s:<8}{a['n']:>5}{a['pf']:>7.3f}{a['wr']:>6.1f}{a['mean_bp']:>8.2f}{a['t']:>6.2f}"
              f"{a['net']:>+9.1f}   {i1['pf'] if i1 else 0:.3f}/{i2['pf'] if i2 else 0:.3f}")
    a=stat(allv4); i1=stat(allv4,2016,2020); i2=stat(allv4,2021,2026)
    print(f"{'PORT':<8}{a['n']:>5}{a['pf']:>7.3f}{a['wr']:>6.1f}{a['mean_bp']:>8.2f}{a['t']:>6.2f}"
          f"{a['net']:>+9.1f}   {i1['pf']:.3f}/{i2['pf']:.3f}")
