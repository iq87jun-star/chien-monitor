#!/usr/bin/env python3
"""「短期窓で選抜し、定期的に入れ替える」戦略の総当たり検証(高速版)."""
import statistics as st, datetime as dt, bisect, math
from fetch import fetch_daily
from screen_all import dow_cell, COST, UNIVERSE

DOWS=["Mon","Tue","Wed","Thu","Fri"]
KEYS=[]; DATES={}; RETS={}; CUM={}; CUM2={}
for y,name,cls in UNIVERSE:
    rows=fetch_daily(y)
    for di,dn in enumerate(DOWS):
        for direction,ds in ((1,"L"),(-1,"S")):
            s=dow_cell(rows,di,direction,COST[cls])
            k=(name,f"{dn}_{ds}"); KEYS.append(k)
            DATES[k]=[d for d,_ in s]; RETS[k]=[r for _,r in s]
            c=[0.0]; c2=[0.0]
            for r in RETS[k]: c.append(c[-1]+r); c2.append(c2[-1]+r*r)
            CUM[k]=c; CUM2[k]=c2

def sl(k,a,b):
    i=bisect.bisect_left(DATES[k],a); j=bisect.bisect_left(DATES[k],b)
    return i,j
def stats(k,a,b):
    i,j=sl(k,a,b); n=j-i
    if n<5: return n,0.0,0.0
    s=CUM[k][j]-CUM[k][i]; s2=CUM2[k][j]-CUM2[k][i]
    mu=s/n; var=s2/n-mu*mu
    return n,mu,(0.0 if var<=0 else mu/math.sqrt(var/n))
def vals(k,a,b):
    i,j=sl(k,a,b); return RETS[k][i:j]
def shift(d,years=0,months=0):
    x=dt.date.fromisoformat(d); m=x.month-1+months
    return dt.date(x.year+years+m//12, m%12+1, min(x.day,28)).isoformat()
def tst(xs):
    n=len(xs)
    if n<5: return 0.0
    s=st.pstdev(xs); return 0.0 if s==0 else st.mean(xs)/(s/math.sqrt(n))
def pf(xs):
    g=sum(x for x in xs if x>0); l=abs(sum(x for x in xs if x<0)); return g/l if l else 99.0

def run(sel_years, hold_months, topn, rule):
    cur="2013-08-26"; allf=[]; per=[]
    minn = 34*sel_years
    while shift(cur,months=hold_months) <= "2026-08-26":
        se=cur; fe=shift(cur,months=hold_months)
        ss=shift(se,years=-sel_years)
        cand=[]
        for k in KEYS:
            n,mu,t=stats(k,ss,se)
            if n<minn: continue
            if rule=="both":
                n5,_,t5=stats(k,shift(se,years=-5),se)
                if n5<170 or t5<=0: continue
                t=min(t,t5)
            elif rule=="fullpos":
                nh,muh,_=stats(k,"2011-01-01",ss)
                if nh<120 or muh<=0: continue
            cand.append((t,k))
        if len(cand)>=topn:
            cand.sort(reverse=True)
            fwd=[r for _,k in cand[:topn] for r in vals(k,se,fe)]
            if fwd: allf+=fwd; per.append(st.mean(fwd))
        cur=fe
    if not allf: return None
    return dict(n=len(allf), mean=st.mean(allf)*100, t=tst(allf), pf=pf(allf),
                neg=sum(1 for m in per if m<0), periods=len(per))

print("="*96)
print("入れ替え戦略の総当たり(2013-08 〜 2026-08 ウォークフォワード・290セル)")
print("="*96)
print(f"{'選抜窓':>6}{'入替':>6}{'本数':>6}{'選抜規則':>12}{'n':>7}{'平均bp':>9}{'t':>7}{'PF':>7}{'負け期間':>10}")
best=[]
for sel in (3,5):
    for hold in (12,6,3):
        for topn in (3,5,10,20):
            for rule,label in (("t","t上位"),("both","3年&5年一致"),("fullpos","過去もプラス")):
                r=run(sel,hold,topn,rule)
                if not r: continue
                best.append((r["t"],sel,hold,topn,label,r))
                print(f"{sel:>5}年{hold:>5}M{topn:>6}{label:>12}{r['n']:>7}"
                      f"{r['mean']:>9.2f}{r['t']:>7.2f}{r['pf']:>7.2f}{r['neg']:>6}/{r['periods']:<3}")

print("\n"+"="*96); print("最良構成トップ5"); print("="*96)
best.sort(reverse=True)
for t,sel,hold,topn,label,r in best[:5]:
    print(f"  {sel}年窓/{hold}ヶ月入替/{topn}本/{label}: 平均{r['mean']:.2f}bp "
          f"t={r['t']:.2f} PF={r['pf']:.2f} 負け{r['neg']}/{r['periods']}")
print(f"\n  総構成数 {len(best)} のうち PF>=1.10 は {sum(1 for b in best if b[5]['pf']>=1.10)} 構成")
print(f"  {'':>16} PF<1.00 は {sum(1 for b in best if b[5]['pf']<1.00)} 構成")

print("\n"+"="*96); print("対照: 入れ替えをしない固定運用(同一期間 2013-08〜)"); print("="*96)
x=vals(("NAS100","Mon_L"),"2013-08-26","2026-08-26")
print(f"  NAS100 Mon_L 固定 : n={len(x):>5} 平均={st.mean(x)*100:>6.2f}bp t={tst(x):>5.2f} PF={pf(x):.2f}")
i8=[r for nm in ("JP225","US500","US30","NAS100","GER40","UK100","HK50","AUS200")
      for r in vals((nm,"Tue_L"),"2013-08-26","2026-08-26")]
print(f"  8指数 Tue_L 固定  : n={len(i8):>5} 平均={st.mean(i8)*100:>6.2f}bp t={tst(i8):>5.2f} PF={pf(i8):.2f}")
