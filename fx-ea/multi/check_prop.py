#!/usr/bin/env python3
"""prop側が採用した個別セルを全期間で検証 + JPY部分族 + v4族."""
import json, math, statistics as st
from collections import defaultdict
from fetch import fetch_daily
from screen_all import dow_cell, evaluate, COST, tstat, UNIVERSE

DOWI = {"Mon":0,"Tue":1,"Wed":2,"Thu":3,"Fri":4}

# prop側 rev6 の稼働構成(nonfx_screen_results.md より)
PROP = [
    ("US500","^GSPC","idx","Tue",+1,0.309),
    ("HK50","^HSI","idx","Mon",+1,0.209),
    ("HK50","^HSI","idx","Thu",-1,0.209),
    ("JP225","^N225","idx","Wed",+1,0.140),
    ("XAGUSD","SI=F","met","Tue",+1,0.060),
    ("XPTUSD","PL=F","met","Tue",+1,0.072),  # rev6で除外されたセル
]

print("="*96)
print("prop側 採用セルの全期間検証 (15年・往復コスト控除)")
print("="*96)
print(f"{'銘柄':<9}{'セル':<8}{'w':>6}{'n':>6}{'t':>7}{'平均%':>9}{'IS%':>9}{'OOS%':>9}{'PF':>7}  判定")
for name, ysym, cls, dn, direction, w in PROP:
    rows = fetch_daily(ysym)
    s = dow_cell(rows, DOWI[dn], direction, COST[cls])
    e = evaluate(s)
    ds = "L" if direction > 0 else "S"
    ok = e["t"] >= 3.0 and e["is_mean"] > 0 and e["oos_mean"] > 0
    mark = "○ 通過" if ok else ("△ t不足" if e["oos_mean"] > 0 else "× OOS赤字")
    print(f"{name:<9}{dn+'_'+ds:<8}{w:>6.3f}{e['n']:>6}{e['t']:>7.2f}{e['mean']:>9.3f}"
          f"{e['is_mean']:>9.3f}{e['oos_mean']:>9.3f}{e['pf']:>7.2f}  {mark}")

# --- JPY部分族 ---
print("\n" + "="*96)
print("FX 部分族: 円クロス vs 非円クロス(曜日o2o・日足)")
print("="*96)
JPY = {"USDJPY","EURJPY","GBPJPY","AUDJPY","NZDJPY","CADJPY","CHFJPY"}
FXSYM = {n:(y,c) for y,n,c in UNIVERSE if c=="fx"}
for grpname, members in (("円クロス", JPY), ("非円FX", set(FXSYM)-JPY)):
    print(f"\n--- {grpname} ({len(members)}ペア) ---")
    print(f"{'セル':<8}{'t':>7}{'平均bp':>9}{'n':>7}")
    out=[]
    for dn,di in DOWI.items():
        allr=[]
        for m in members:
            y,c = FXSYM[m]
            allr += [r for _,r in dow_cell(fetch_daily(y), di, +1, COST[c])]
        out.append((tstat(allr), dn, st.mean(allr)*100, len(allr)))
    for t,dn,mu,n in out:
        print(f"{dn+'_L':<8}{t:>7.2f}{mu:>9.2f}{n:>7}")

# --- v4族 (QuadraReversal パリティ) ---
print("\n" + "="*96)
print("v4族(4条件合議リバーサル)全銘柄検証")
print("="*96)
def v4_cells(rows, cost, zwin=20, z=1.5, run=3, move=0.005, rsin=14, rsibuy=35, rsisell=65):
    cl=[r[4] for r in rows]; op=[r[1] for r in rows]
    rets=[cl[i]/cl[i-1]-1 for i in range(1,len(cl))]
    out=[]
    for i in range(max(zwin,rsin)+2, len(rows)-1):
        w=rets[i-zwin:i]
        mu=st.mean(w); sd=st.pstdev(w)
        if sd==0: continue
        zz=(rets[i-1]-mu)/sd
        # RSI
        g=[max(0,rets[k]) for k in range(i-rsin,i)]; l=[max(0,-rets[k]) for k in range(i-rsin,i)]
        ag,al=st.mean(g),st.mean(l)
        rsi=100.0 if al==0 else 100-100/(1+ag/al)
        runs=all(cl[i-1-k]<op[i-1-k] for k in range(run))
        runl=all(cl[i-1-k]>op[i-1-k] for k in range(run))
        mv=abs(rets[i-1])>=move
        for direction in (+1,-1):
            if direction>0:
                cond = (rsi<=rsibuy) + (zz<=-z) + runs + mv
            else:
                cond = (rsi>=rsisell) + (zz>=z) + runl + mv
            if cond==4:
                r=(op[i+1]/op[i]-1)*100*direction - cost
                out.append((rows[i][0], r, direction))
    return out

tot=defaultdict(list)
for ysym,name,cls in UNIVERSE:
    rows=fetch_daily(ysym)
    s=v4_cells(rows, COST[cls])
    if len(s)>=30:
        xs=[r for _,r,_ in s]
        tot[cls]+=xs
        t=tstat(xs)
        if t>=1.5 or len(s)>=80:
            print(f"  {name:<9} n={len(s):>4} t={t:>6.2f} 平均={st.mean(xs):>7.3f}%")
print("\n  --- v4 クラス合成 ---")
for cls,xs in sorted(tot.items()):
    print(f"  {cls:<5} n={len(xs):>5} t={tstat(xs):>6.2f} 平均={st.mean(xs):>7.4f}%")
