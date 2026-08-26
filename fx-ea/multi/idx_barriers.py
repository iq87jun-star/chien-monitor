#!/usr/bin/env python3
"""指数商品化の障壁を実測する.

(A) エッジは「オーバーナイトのギャップ」か「日中セッション」か
    → 現物指数の始値は 9:30ET だが、MT5指数CFDの日足始値はサーバー0時。
      エッジがギャップ側にあると、CFDのEAでは取りに行けない。
(B) コスト感度: 往復コストを変えたときに何bpまで耐えるか
"""
import statistics as st, math
from fetch import fetch_daily
from screen_all import dow_cell, COST, tstat

IDX=[("^N225","JP225"),("^GSPC","US500"),("^DJI","US30"),("^NDX","NAS100"),
     ("^GDAXI","GER40"),("^FTSE","UK100"),("^HSI","HK50"),("^AXJO","AUS200")]

def decomp(rows, dow):
    """対象曜日について o2o を「前夜ギャップ」と「当日セッション」に分解.
    o2o(i) = [O(i)/C(i-1) - 1] + [C(i)/O(i) - 1] + [O(i+1)/C(i) - 1] を近似的に
    ギャップ(建玉前は取らない) / セッション / 翌朝ギャップ に分ける。
    実際に保有するのは O(i) -> O(i+1)。その内訳:
      セッション  = C(i)/O(i) - 1
      翌朝ギャップ = O(i+1)/C(i) - 1
    """
    import datetime as dt
    sess=[]; gap=[]
    for i in range(len(rows)-1):
        if dt.date.fromisoformat(rows[i][0]).weekday()!=dow: continue
        o,c = rows[i][1], rows[i][4]
        o1 = rows[i+1][1]
        sess.append((c/o-1)*100)
        gap.append((o1/c-1)*100)
    return sess, gap

print("="*94)
print("(A) 保有区間の内訳: 当日セッション vs 翌朝までのオーバーナイト")
print("="*94)
print(f"{'銘柄':<9}{'曜日':<6}{'セッションbp':>13}{'t':>7}{'オーバーナイトbp':>17}{'t':>7}{'合計bp':>9}")
for y,n in IDX:
    rows=fetch_daily(y)
    for di,dn in ((0,"Mon"),(1,"Tue")):
        s,g=decomp(rows,di)
        print(f"{n:<9}{dn:<6}{st.mean(s)*100:>13.1f}{tstat(s):>7.2f}"
              f"{st.mean(g)*100:>17.1f}{tstat(g):>7.2f}{(st.mean(s)+st.mean(g))*100:>9.1f}")

print("\n--- 8指数合成 ---")
for di,dn in ((0,"Mon"),(1,"Tue")):
    S=[];G=[]
    for y,n in IDX:
        s,g=decomp(fetch_daily(y),di); S+=s; G+=g
    print(f"  {dn}: セッション {st.mean(S)*100:>6.1f}bp (t={tstat(S):>5.2f}) / "
          f"オーバーナイト {st.mean(G)*100:>6.1f}bp (t={tstat(G):>5.2f})")

print("\n"+"="*94)
print("NAS100 月曜 の内訳(唯一の全期間通過セル)")
print("="*94)
s,g=decomp(fetch_daily("^NDX"),0)
print(f"  当日セッション(9:30ET→16:00ET) : {st.mean(s)*100:>7.2f}bp  t={tstat(s):>5.2f}")
print(f"  オーバーナイト(16:00ET→翌9:30ET): {st.mean(g)*100:>7.2f}bp  t={tstat(g):>5.2f}")
print(f"  合計                            : {(st.mean(s)+st.mean(g))*100:>7.2f}bp")
tot=st.mean(s)+st.mean(g)
print(f"  → エッジの {100*st.mean(s)/tot:.0f}% がセッション、{100*st.mean(g)/tot:.0f}% がオーバーナイト")

print("\n"+"="*94)
print("(B) コスト感度: 往復コストを変えたときの NAS100 月曜L / 8指数火曜L")
print("="*94)
print(f"{'往復コスト':>10}{'NAS100月L 平均':>16}{'t':>8}{'PF':>7}   {'8指数火L 平均':>15}{'t':>8}{'PF':>7}")
def pf(xs):
    gp=sum(x for x in xs if x>0); l=abs(sum(x for x in xs if x<0)); return gp/l if l else 99.0
for c in (0.02,0.03,0.05,0.08,0.12,0.16,0.20):
    a=[r for _,r in dow_cell(fetch_daily("^NDX"),0,+1,c)]
    b=[]
    for y,n in IDX: b+=[r for _,r in dow_cell(fetch_daily(y),1,+1,c)]
    print(f"{c*100:>9.0f}bp{st.mean(a)*100:>16.2f}{tstat(a):>8.2f}{pf(a):>7.2f}   "
          f"{st.mean(b)*100:>15.2f}{tstat(b):>8.2f}{pf(b):>7.2f}")
print("\n  ※ 指数CFDのオーバーナイト金利は概ね (指標金利+2〜3%)/360 /泊。")
print("     現行金利水準では 1泊あたり約1.5〜2.5bp。スプレッドは NAS100 で 1〜2pt")
print("     (指数値25000に対し 0.4〜0.8bp)。合計の実勢往復コストは 3〜6bp 程度。")
