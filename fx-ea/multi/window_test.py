#!/usr/bin/env python3
"""検証期間を短くすると通過セルは何本増えるか、そしてそれは本物か.

(A) 窓長別の通過セル数
(B) ウォークフォワード: 窓Wで選抜 → 直後12ヶ月の実際の成績
"""
import math, statistics as st, datetime as dt
from collections import defaultdict
from fetch import fetch_daily
from screen_all import dow_cell, COST, tstat, UNIVERSE

DOWS = ["Mon","Tue","Wed","Thu","Fri"]

# 全セルの (日付, リターン) 系列を一度だけ構築
CELLS = {}
for y, name, cls in UNIVERSE:
    rows = fetch_daily(y)
    for di, dn in enumerate(DOWS):
        for direction, ds in ((1,"L"), (-1,"S")):
            CELLS[(name, f"{dn}_{ds}")] = dow_cell(rows, di, direction, COST[cls])
print(f"セル総数: {len(CELLS)}\n")

END = "2026-08-26"
def window(series, start, end):
    return [r for d, r in series if start <= d < end]

def years_before(end, n):
    e = dt.date.fromisoformat(end)
    return (e.replace(year=e.year - n)).isoformat()

# ---------------- (A) 窓長別の通過セル数 ----------------
print("="*88)
print("(A) 検証期間を変えたときの「基準通過セル数」")
print("="*88)
print(f"{'窓':>6}{'最低n':>7}{'通過数':>8}{'期待誤検出':>11}{'比率':>8}   通過セル(上位)")
for W, minn in ((3,120),(5,200),(10,400),(15,500)):
    start = years_before(END, W)
    hits=[]
    for k, s in CELLS.items():
        xs = window(s, start, END)
        if len(xs) < minn: continue
        t = tstat(xs)
        cut = int(len(xs)*0.6)
        if t >= 3.0 and st.mean(xs[:cut]) > 0 and st.mean(xs[cut:]) > 0:
            hits.append((t, k, st.mean(xs)*100, len(xs)))
    hits.sort(reverse=True)
    exp = len(CELLS)*0.0013
    top = ", ".join(f"{k[0]} {k[1]}(t{t:.1f})" for t,k,_,_ in hits[:4])
    print(f"{W:>5}年{minn:>7}{len(hits):>8}{exp:>11.1f}{len(hits)/exp:>8.1f}x   {top}")

# ---------------- (B) ウォークフォワード ----------------
print("\n"+"="*88)
print("(B) ウォークフォワード検証: 窓Wで選抜し、その直後12ヶ月を実際に運用したら")
print("="*88)
print("  選抜規則: 窓内 t が最大の上位3セル(n下限あり)を等ウェイトで採用")
print()
print(f"{'選抜窓':>7}  {'年':>6}{'選抜時t平均':>12}{'翌12M平均bp':>13}{'翌12M t':>10}  採用セル")

for W, minn in ((3,120),(5,200),(10,400)):
    fwd_all=[]
    rows_out=[]
    for endyear in range(2016, 2026):
        sel_end = f"{endyear}-08-26"
        sel_start = years_before(sel_end, W)
        fwd_end = f"{endyear+1}-08-26"
        cand=[]
        for k, s in CELLS.items():
            xs = window(s, sel_start, sel_end)
            if len(xs) < minn: continue
            cand.append((tstat(xs), k))
        if len(cand) < 3: continue
        cand.sort(reverse=True)
        picks = cand[:3]
        fwd=[]
        for t,k in picks:
            fwd += window(CELLS[k], sel_end, fwd_end)
        if not fwd: continue
        fwd_all += fwd
        rows_out.append((endyear, st.mean([t for t,_ in picks]), st.mean(fwd)*100,
                         tstat(fwd), ", ".join(f"{k[0]} {k[1]}" for _,k in picks)))
    for yr, seat, fm, ft, names in rows_out:
        mark = "▲" if fm < 0 else " "
        print(f"{W:>6}年  {yr:>6}{seat:>12.2f}{fm:>13.2f}{ft:>10.2f} {mark} {names}")
    neg = sum(1 for r in rows_out if r[2] < 0)
    print(f"{'':>8}{'→ 通算':>8}{'':>12}{st.mean(fwd_all)*100:>13.2f}"
          f"{tstat(fwd_all):>10.2f}    負け年 {neg}/{len(rows_out)}\n")
