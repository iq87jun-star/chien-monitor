import pandas as pd, numpy as np
from scipy import stats
BE=0.55
PAIRS=["USDJPY","EURJPY","GBPJPY","AUDJPY","EURUSD","GBPUSD","AUDUSD"]
D1=pd.Timestamp("2022-01-01",tz="Asia/Tokyo"); D2=pd.Timestamp("2026-05-29",tz="Asia/Tokyo")
def load(p,s=""):
    d=pd.read_csv(f"{p}_h1{s}.csv",index_col=0,parse_dates=True)
    d.index=pd.to_datetime(d.index,utc=True).tz_convert("Asia/Tokyo"); return d["open"]
recs=[]
for p in PAIRS:
    b,a=load(p),load(p,"_ask"); j=b.index.intersection(a.index); m=((b[j]+a[j])/2)
    nxt=m.reindex(m.index+pd.Timedelta(hours=2)); nxt.index=m.index
    r=pd.DataFrame({"ret":nxt-m}).dropna(); r=r[r.ret!=0]
    r["pair"]=p; r["wd"]=r.index.weekday; r["h"]=r.index.hour
    r["per"]=np.where(r.index<D1,"A_disc",np.where(r.index<D2,"B_val","C_oos"))
    recs.append(r[r.h%2==1])  # IG 2h windows start at odd JST hours
R=pd.concat(recs)
rows=[]
for (p,wd,h),g in R.groupby(["pair","wd","h"]):
    for dr in ["HIGH","LOW"]:
        win=(g.ret>0) if dr=="HIGH" else (g.ret<0)
        row=dict(pair=p,wd=wd,h=h,dir=dr)
        for per in ["A_disc","B_val","C_oos"]:
            w=win[g.per==per]; n=len(w); k=int(w.sum())
            row[f"n_{per}"]=n; row[f"wr_{per}"]=100*k/n if n else np.nan
            row[f"p_{per}"]=stats.binomtest(k,n,BE,alternative="greater").pvalue if n else np.nan
        rows.append(row)
G=pd.DataFrame(rows)
N=len(G); print("総パターン数:",N)
disc=G[(G.p_A_disc<0.01)]
print(f"発見期間(2016-21)で 勝率>55% p<0.01: {len(disc)}件  (偶然で出る期待数 ≈ {N*0.01:.1f}件)")
val=disc[(disc.wr_B_val>55)&(disc.p_B_val<0.05)]
print(f"→ 確認期間(2022-26/5)でも 勝率>55% p<0.05: {len(val)}件")
wd=["月","火","水","木","金"]
v=val.copy(); v["曜日"]=v.wd.map(lambda x:wd[x]); v["時間"]=v.h.map(lambda h:f"{h:02d}→{(h+2)%24:02d}")
cols=["pair","曜日","時間","dir","n_A_disc","wr_A_disc","n_B_val","wr_B_val","n_C_oos","wr_C_oos"]
print(v.sort_values("wr_B_val",ascending=False)[cols].round(1).to_string(index=False))
oo=val; k=(oo.wr_C_oos*oo.n_C_oos/100).sum(); n=oo.n_C_oos.sum()
print(f"\n生存戦略の検証後(2026/6-10)合算: n={n:.0f} WR={100*k/n:.1f}%  p={stats.binomtest(int(round(k)),int(n),BE,alternative='greater').pvalue:.3f}")
G.to_csv("grid_all.csv",index=False); val.to_csv("grid_survivors.csv",index=False)
# 構造仮説: 曜日まとめ (時刻×方向×ペア)
print("\n=== 曜日を問わない 07→09 HIGH (MID) ===")
x=R[R.h==7]
for p in PAIRS:
    g=x[x.pair==p]
    print(p," ".join(f"{per}:{100*(g[g.per==per].ret>0).mean():.1f}%" for per in ["A_disc","B_val","C_oos"]))
