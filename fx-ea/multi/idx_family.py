#!/usr/bin/env python3
"""指数の早週効果(月・火 o2o LONG)を族として検証 + 月末効果."""
import math, statistics as st, datetime as dt
from collections import defaultdict
from fetch import fetch_daily
from screen_all import dow_cell, evaluate, COST, tstat

IDX = [("^N225","JP225"),("^GSPC","US500"),("^DJI","US30"),("^NDX","NAS100"),
       ("^GDAXI","GER40"),("^FTSE","UK100"),("^HSI","HK50"),("^AXJO","AUS200")]

print("="*94)
print("指数 曜日別 o2o LONG(全期間15年・コスト0.030%控除)")
print("="*94)
print(f"{'銘柄':<9}" + "".join(f"{d:>11}" for d in ["Mon","Tue","Wed","Thu","Fri"]))
per = {}
for y,n in IDX:
    rows=fetch_daily(y); line=f"{n:<9}"
    per[n]={}
    for di,dn in enumerate(["Mon","Tue","Wed","Thu","Fri"]):
        s=dow_cell(rows,di,+1,COST["idx"]); xs=[r for _,r in s]
        per[n][dn]=s
        line+=f"{st.mean(xs)*100:>7.1f}bp"
    print(line)

print("\n" + "="*94)
print("Mon+Tue 合成(2セル/週)を銘柄ごとに")
print("="*94)
print(f"{'銘柄':<9}{'n':>6}{'t':>7}{'平均bp':>9}{'IS bp':>9}{'OOS bp':>9}{'勝率':>7}{'PF':>7}")
combos={}
for y,n in IDX:
    s = sorted(per[n]["Mon"] + per[n]["Tue"])
    combos[n]=s
    e=evaluate(s)
    print(f"{n:<9}{e['n']:>6}{e['t']:>7.2f}{e['mean']*100:>9.2f}"
          f"{e['is_mean']*100:>9.2f}{e['oos_mean']*100:>9.2f}{e['wr']:>6.1f}%{e['pf']:>7.2f}")

allmt = sorted([x for n in per for x in per[n]["Mon"]+per[n]["Tue"]])
e=evaluate(allmt)
print(f"\n{'8指数合成':<9}{e['n']:>6}{e['t']:>7.2f}{e['mean']*100:>9.2f}"
      f"{e['is_mean']*100:>9.2f}{e['oos_mean']*100:>9.2f}{e['wr']:>6.1f}%{e['pf']:>7.2f}")

# 対照: 水木金 LONG
ctrl = sorted([x for n in per for d in ("Wed","Thu","Fri") for x in per[n][d]])
ec=evaluate(ctrl)
print(f"{'(対照)水木金':<9}{ec['n']:>6}{ec['t']:>7.2f}{ec['mean']*100:>9.2f}"
      f"{ec['is_mean']*100:>9.2f}{ec['oos_mean']*100:>9.2f}{ec['wr']:>6.1f}%{ec['pf']:>7.2f}")

# 年別
print("\n" + "="*94)
print("Mon+Tue 8指数合成 の年別(平均bp / 取引数)")
print("="*94)
by=defaultdict(list)
for d,r in allmt: by[d[:4]].append(r)
neg=0
for yr in sorted(by):
    m=st.mean(by[yr])*100
    if m<0: neg+=1
    print(f"  {yr}: {m:>8.2f}bp  n={len(by[yr]):>4}  {'▲' if m<0 else ''}")
print(f"  → 負け年 {neg}/{len(by)}")

# ドリフト控除(指数は上昇バイアスがあるため全曜日平均を引く)
print("\n" + "="*94)
print("ドリフト控除: 各週の全曜日平均を引いた「超過収益」")
print("="*94)
for y,n in IDX:
    rows=fetch_daily(y)
    wk=defaultdict(dict)
    for di,dn in enumerate(["Mon","Tue","Wed","Thu","Fri"]):
        for d,r in dow_cell(rows,di,+1,0.0):
            iso=dt.date.fromisoformat(d).isocalendar()
            wk[(iso[0],iso[1])][dn]=r
    ex=defaultdict(list)
    for k,v in wk.items():
        if len(v)<5: continue
        mu=st.mean(v.values())
        for dn,r in v.items(): ex[dn].append(r-mu)
    line=f"{n:<9}"
    for dn in ["Mon","Tue","Wed","Thu","Fri"]:
        line+=f"{st.mean(ex[dn])*100:>7.1f}bp"
    print(line)

allex=defaultdict(list)
for y,n in IDX:
    rows=fetch_daily(y)
    wk=defaultdict(dict)
    for di,dn in enumerate(["Mon","Tue","Wed","Thu","Fri"]):
        for d,r in dow_cell(rows,di,+1,0.0):
            iso=dt.date.fromisoformat(d).isocalendar()
            wk[(iso[0],iso[1])][dn]=r
    for k,v in wk.items():
        if len(v)<5: continue
        mu=st.mean(v.values())
        for dn,r in v.items(): allex[dn].append(r-mu)
print(f"\n{'8指数合成':<9}" + "".join(f"{st.mean(allex[d])*100:>7.1f}bp" for d in ["Mon","Tue","Wed","Thu","Fri"]))
print(f"{'  t値':<9}" + "".join(f"{tstat(allex[d]):>9.2f}" for d in ["Mon","Tue","Wed","Thu","Fri"]))
