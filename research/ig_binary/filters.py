import pandas as pd, numpy as np
from scipy import stats
PAIRS=["USDJPY","EURJPY","GBPJPY","AUDJPY","EURUSD","GBPUSD","AUDUSD"]
D1=pd.Timestamp("2022-01-01",tz="Asia/Tokyo"); D2=pd.Timestamp("2026-05-29",tz="Asia/Tokyo")
def load(p,s=""):
    d=pd.read_csv(f"{p}_h1{s}.csv",index_col=0,parse_dates=True)
    d.index=pd.to_datetime(d.index,utc=True).tz_convert("Asia/Tokyo"); return d
rows=[]
for p in PAIRS:
    b,a=load(p),load(p,"_ask"); j=b.index.intersection(a.index)
    m=(b.loc[j,["open","high","low","close"]]+a.loc[j,["open","high","low","close"]])/2
    sp=(a.loc[j,"open"]-b.loc[j,"open"])
    pip=0.01 if p.endswith("JPY") else 1e-4
    # daily ranges for ATR (24h blocks)
    rng=(m.high.rolling(24).max()-m.low.rolling(24).min())
    for t in m.index[(m.index.weekday==0)&(m.index.hour==7)]:
        t2=t+pd.Timedelta(hours=2)
        if t2 not in m.index: continue
        prev=m[m.index<=t-pd.Timedelta(hours=24)]
        if len(prev)<24*25: continue
        fri_close=prev.close.iloc[-1]
        mon=m[(m.index<=t)&(m.index>t-pd.Timedelta(hours=24))]
        first=mon.open.iloc[0]; e=m.loc[t,"open"]; x=m.loc[t2,"open"]
        gap=first-fri_close
        if gap>=0 or x==e: continue
        atr=rng[prev.index].iloc[-20*24::24].mean()   # 平均日足値幅(直近20日)
        fri=prev[prev.index>prev.index[-1]-pd.Timedelta(hours=24)]
        wk=prev[prev.index>prev.index[-1]-pd.Timedelta(days=5)]
        rows.append(dict(pair=p,t=t,win=int(x>e),gap_pips=-gap/pip,gap_atr=-gap/atr,
            filled=(e-first)/(-gap),                       # 07:00 時点で窓をどれだけ埋めたか
            fri_ret=(fri.close.iloc[-1]-fri.open.iloc[0])/atr, wk_ret=(wk.close.iloc[-1]-wk.open.iloc[0])/atr,
            spread_pips=sp.get(t,np.nan)/pip, jpy=p.endswith("JPY"),
            dst=bool(t.tz_convert("America/New_York").dst()),
            per="A" if t<D1 else ("B" if t<D2 else "C")))
X=pd.DataFrame(rows)
X["n_down"]=X.groupby("t").pair.transform("size")   # 同じ月曜に下窓のペア数
X.to_csv("gap_features.csv",index=False)
def s(g):
    n=len(g); k=int(g.win.sum()); return n, (100*k/n if n else np.nan)
base={per:s(X[X.per==per]) for per in "ABC"}
print("基準(下窓すべて):"," ".join(f"{per}:n={v[0]} {v[1]:.1f}%" for per,v in base.items()))
# しきい値は発見期間 A の分位で決める(B・C には持ち込むだけ)
A=X[X.per=="A"]
q=lambda c,qq: A[c].quantile(qq)
F={
 "窓 大(gap/ATR 上位半分)":X.gap_atr>=q("gap_atr",.5),
 "窓 小(gap/ATR 下位半分)":X.gap_atr<q("gap_atr",.5),
 "窓 極小を除く(gap/ATR 下位25%除外)":X.gap_atr>=q("gap_atr",.25),
 "07時に未だ埋まっていない(filled<0.5)":X.filled<0.5,
 "07時に半分以上埋まった(filled>=0.5)":X.filled>=0.5,
 "07時に窓をさらに広げた(filled<0)":X.filled<0,
 "金曜 陰線":X.fri_ret<0, "金曜 陽線":X.fri_ret>0,
 "前週 下落":X.wk_ret<0, "前週 上昇":X.wk_ret>0,
 "円の通貨ペアのみ":X.jpy, "ドルストレートのみ":~X.jpy,
 "冬時間のみ":~X.dst, "夏時間のみ":X.dst,
 "下窓ペア 4以上(全体的な下窓)":X.n_down>=4, "下窓ペア 3以下(個別の下窓)":X.n_down<=3,
 "07時スプレッド 小(下位半分)":X.spread_pips<q("spread_pips",.5),
}
out=[]
for name,mask in F.items():
    r=dict(filter=name)
    for per in "ABC":
        n,w=s(X[mask&(X.per==per)]); b=base[per][1]
        r[f"n_{per}"]=n; r[f"WR_{per}"]=round(w,1); r[f"Δ_{per}"]=round(w-b,1)
        k=int(round(w*n/100)) if n else 0
        r[f"p_{per}"]=round(stats.binomtest(k,n,.55,alternative="greater").pvalue,4) if n else np.nan
    out.append(r)
R=pd.DataFrame(out)
pd.set_option("display.width",250)
print(R[["filter","n_A","WR_A","Δ_A","n_B","WR_B","Δ_B","n_C","WR_C","Δ_C"]].to_string(index=False))
print("\n合格(A と B の両方で 基準より +3pt 以上・B で p<0.01):")
ok=R[(R.Δ_A>=3)&(R.Δ_B>=3)&(R.p_B<0.01)]
print(ok[["filter","WR_A","WR_B","WR_C","n_C"]].to_string(index=False) if len(ok) else "なし")
