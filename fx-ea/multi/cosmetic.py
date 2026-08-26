#!/usr/bin/env python3
"""「販売ページに載る見た目の成績」を基準にすると窓長で何本増えるか.

統計的な t 値ではなく、購入者と審査が見る指標(PF・勝率・純益プラス)で数える。
"""
import statistics as st, datetime as dt
from collections import defaultdict
from fetch import fetch_daily
from screen_all import dow_cell, COST, tstat, UNIVERSE

DOWS=["Mon","Tue","Wed","Thu","Fri"]
CELLS={}
for y,name,cls in UNIVERSE:
    rows=fetch_daily(y)
    for di,dn in enumerate(DOWS):
        for direction,ds in ((1,"L"),(-1,"S")):
            CELLS[(name,f"{dn}_{ds}")]=dow_cell(rows,di,direction,COST[cls])

END="2026-08-26"
def yb(end,n):
    e=dt.date.fromisoformat(end); return e.replace(year=e.year-n).isoformat()
def win(s,a,b): return [r for d,r in s if a<=d<b]

def pf(xs):
    g=sum(x for x in xs if x>0); l=abs(sum(x for x in xs if x<0))
    return g/l if l else 99.0

print("="*90)
print("「販売ページ映えする成績」を基準にした通過本数")
print("  基準: 純益プラス かつ PF>=1.30 かつ 勝率>=52% かつ 最低30取引")
print("="*90)
print(f"{'窓':>6}{'通過本数':>10}{'全290セル中':>12}   通過セル例")
counts={}
for W in (2,3,5,10,15):
    start=yb(END,W); hits=[]
    for k,s in CELLS.items():
        xs=win(s,start,END)
        if len(xs)<30: continue
        wr=100*sum(1 for x in xs if x>0)/len(xs)
        if sum(xs)>0 and pf(xs)>=1.30 and wr>=52:
            hits.append((pf(xs),k,tstat(xs)))
    hits.sort(reverse=True)
    counts[W]=hits
    ex=", ".join(f"{k[0]} {k[1]}(PF{p:.2f}/t{t:.1f})" for p,k,t in hits[:3])
    print(f"{W:>5}年{len(hits):>10}{100*len(hits)/290:>11.1f}%   {ex}")

print("\n" + "="*90)
print("3年窓で「合格」した各セルが、全期間15年ではどうだったか")
print("="*90)
print(f"{'セル':<20}{'3年PF':>8}{'3年t':>8}{'15年PF':>9}{'15年t':>8}{'15年平均bp':>12}")
n_survive=0
for p,k,t in counts[3][:15]:
    xs15=[r for _,r in CELLS[k]]
    p15,t15=pf(xs15),tstat(xs15)
    if t15>=3.0: n_survive+=1
    print(f"{k[0]+' '+k[1]:<20}{p:>8.2f}{t:>8.2f}{p15:>9.2f}{t15:>8.2f}{st.mean(xs15)*100:>12.2f}")
print(f"\n  3年合格 {len(counts[3])}本 のうち、全期間でも t>=3.0 だったのは {n_survive}本")

print("\n" + "="*90)
print("逆向き: 各年の3年窓で合格したセルの「翌12ヶ月」実績")
print("="*90)
print(f"{'選抜年':>8}{'合格本数':>10}{'翌12M平均bp':>14}{'翌12M t':>10}{'翌12M PF':>10}")
allf=[]
for endyear in range(2015,2026):
    se=f"{endyear}-08-26"; ss=yb(se,3); fe=f"{endyear+1}-08-26"
    ok=[]
    for k,s in CELLS.items():
        xs=win(s,ss,se)
        if len(xs)<30: continue
        wr=100*sum(1 for x in xs if x>0)/len(xs)
        if sum(xs)>0 and pf(xs)>=1.30 and wr>=52: ok.append(k)
    fwd=[r for k in ok for r in win(CELLS[k],se,fe)]
    if not fwd: continue
    allf+=fwd
    m="▲" if st.mean(fwd)<0 else " "
    print(f"{endyear:>8}{len(ok):>10}{st.mean(fwd)*100:>14.2f}{tstat(fwd):>10.2f}{pf(fwd):>10.2f} {m}")
print(f"{'通算':>8}{'':>10}{st.mean(allf)*100:>14.2f}{tstat(allf):>10.2f}{pf(allf):>10.2f}")
