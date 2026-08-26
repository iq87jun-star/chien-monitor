#!/usr/bin/env python3
"""ドリフト中立な曜日構造: 火曜L + 木曜S を検証."""
import statistics as st
from collections import defaultdict
from fetch import fetch_daily
from screen_all import dow_cell, evaluate, COST, tstat

IDX = [("^N225","JP225"),("^GSPC","US500"),("^DJI","US30"),("^NDX","NAS100"),
       ("^GDAXI","GER40"),("^FTSE","UK100"),("^HSI","HK50"),("^AXJO","AUS200")]

def show(title, builder):
    print("\n"+"="*92); print(title); print("="*92)
    print(f"{'銘柄':<9}{'n':>6}{'t':>7}{'平均bp':>9}{'IS bp':>9}{'OOS bp':>9}{'勝率':>7}{'PF':>7}")
    allx=[]
    for y,n in IDX:
        s=builder(fetch_daily(y)); allx+=s
        e=evaluate(sorted(s))
        if e: print(f"{n:<9}{e['n']:>6}{e['t']:>7.2f}{e['mean']*100:>9.2f}"
                    f"{e['is_mean']*100:>9.2f}{e['oos_mean']*100:>9.2f}{e['wr']:>6.1f}%{e['pf']:>7.2f}")
    e=evaluate(sorted(allx))
    print(f"{'合成':<9}{e['n']:>6}{e['t']:>7.2f}{e['mean']*100:>9.2f}"
          f"{e['is_mean']*100:>9.2f}{e['oos_mean']*100:>9.2f}{e['wr']:>6.1f}%{e['pf']:>7.2f}")
    return sorted(allx)

c=COST["idx"]
a = show("① 火曜LONG + 木曜SHORT(ドリフト中立)", lambda r: dow_cell(r,1,+1,c)+dow_cell(r,3,-1,c))
b = show("② 火曜LONG のみ", lambda r: dow_cell(r,1,+1,c))
d = show("③ 木曜SHORT のみ", lambda r: dow_cell(r,3,-1,c))
e_ = show("④ 月曜LONG + 火曜LONG(参考・ドリフト依存)", lambda r: dow_cell(r,0,+1,c)+dow_cell(r,1,+1,c))

print("\n"+"="*92); print("2020年(コロナ)を除外した場合"); print("="*92)
for label,ser in (("① 火L+木S",a),("② 火Lのみ",b),("③ 木Sのみ",d),("④ 月L+火L",e_)):
    x=[r for dt_,r in ser if dt_[:4]!="2020"]
    print(f"  {label:<12} n={len(x):>6} t={tstat(x):>6.2f} 平均={st.mean(x)*100:>7.2f}bp")

print("\n"+"="*92); print("① 火L+木S の年別"); print("="*92)
by=defaultdict(list)
for dt_,r in a: by[dt_[:4]].append(r)
neg=0
for yr in sorted(by):
    m=st.mean(by[yr])*100
    if m<0: neg+=1
    print(f"  {yr}: {m:>8.2f}bp  n={len(by[yr]):>4}  {'▲' if m<0 else ''}")
print(f"  → 負け年 {neg}/{len(by)}")
