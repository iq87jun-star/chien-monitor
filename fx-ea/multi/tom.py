#!/usr/bin/env python3
"""月末効果(turn-of-month)と NAS100 月曜の個別精査."""
import statistics as st, datetime as dt
from collections import defaultdict
from fetch import fetch_daily
from screen_all import dow_cell, evaluate, COST, tstat, UNIVERSE

def tom_cell(rows, cost, days_before=1, days_after=3):
    """月末n営業日前の寄りで建て、翌月m営業日目の寄りで決済。"""
    idx_by_month=defaultdict(list)
    for i,(d,o,h,l,c) in enumerate(rows): idx_by_month[d[:7]].append(i)
    keys=sorted(idx_by_month)
    out=[]
    for k in range(len(keys)-1):
        cur, nxt = idx_by_month[keys[k]], idx_by_month[keys[k+1]]
        if len(cur)<days_before or len(nxt)<days_after: continue
        i0 = cur[-days_before]; i1 = nxt[days_after-1]
        held = i1-i0
        r=(rows[i1][1]/rows[i0][1]-1)*100 - cost - 0.002*held
        out.append((rows[i0][0], r))
    return out

print("="*92); print("月末効果 (月末1営業日前の寄り → 翌月3営業日目の寄り)"); print("="*92)
print(f"{'銘柄':<9}{'クラス':<6}{'n':>5}{'t':>7}{'平均bp':>10}{'IS bp':>10}{'OOS bp':>10}{'PF':>7}")
byc=defaultdict(list)
res=[]
for y,n,cls in UNIVERSE:
    s=tom_cell(fetch_daily(y), COST[cls])
    if len(s)<100: continue
    byc[cls]+=s
    xs=[r for _,r in s]; cut=int(len(xs)*0.6)
    res.append((tstat(xs), n, cls, len(xs), st.mean(xs), st.mean(xs[:cut]), st.mean(xs[cut:])))
res.sort(reverse=True)
for t,n,cls,cnt,mu,ism,oos in res:
    pf_x=[x for _,x in tom_cell(fetch_daily([a for a,b,c in UNIVERSE if b==n][0]), COST[cls])]
    pf=sum(x for x in pf_x if x>0)/abs(sum(x for x in pf_x if x<0))
    print(f"{n:<9}{cls:<6}{cnt:>5}{t:>7.2f}{mu*100:>10.2f}{ism*100:>10.2f}{oos*100:>10.2f}{pf:>7.2f}")

print("\n--- クラス合成 ---")
for cls,s in sorted(byc.items()):
    xs=[r for _,r in s]; cut=int(len(xs)*0.6)
    print(f"  {cls:<5} n={len(xs):>5} t={tstat(xs):>6.2f} 平均={st.mean(xs)*100:>7.2f}bp "
          f"IS={st.mean(xs[:cut])*100:>7.2f} OOS={st.mean(xs[cut:])*100:>7.2f}")

print("\n"+"="*92); print("NAS100 月曜LONG 精査(唯一 t>=3.0 を通過した単独セル)"); print("="*92)
rows=fetch_daily("^NDX")
s=dow_cell(rows,0,+1,COST["idx"])
e=evaluate(s)
print(f"  n={e['n']} t={e['t']:.2f} 平均={e['mean']*100:.2f}bp IS={e['is_mean']*100:.2f} "
      f"OOS={e['oos_mean']*100:.2f} 勝率={e['wr']:.1f}% PF={e['pf']:.2f}")
by=defaultdict(list)
for d,r in s: by[d[:4]].append(r)
neg=[y for y in by if st.mean(by[y])<0]
print(f"  負け年 {len(neg)}/{len(by)}: {sorted(neg)}")
x2020=[r for d,r in s if d[:4]!="2020"]
print(f"  2020除外: n={len(x2020)} t={tstat(x2020):.2f} 平均={st.mean(x2020)*100:.2f}bp")
# ドリフト控除
wk=defaultdict(dict)
for di,dn in enumerate(["Mon","Tue","Wed","Thu","Fri"]):
    for d,r in dow_cell(rows,di,+1,0.0):
        iso=dt.date.fromisoformat(d).isocalendar(); wk[(iso[0],iso[1])][dn]=r
ex=defaultdict(list)
for k,v in wk.items():
    if len(v)<5: continue
    mu=st.mean(v.values())
    for dn,r in v.items(): ex[dn].append(r-mu)
print(f"  ドリフト控除後の月曜超過: {st.mean(ex['Mon'])*100:.2f}bp (t={tstat(ex['Mon']):.2f})")
print(f"  → 平均{e['mean']*100:.1f}bpのうち、指数ドリフト分が{(e['mean']*100-st.mean(ex['Mon'])*100):.1f}bp")
