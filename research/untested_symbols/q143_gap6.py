# Q143(新規 6 セル・結果前に固定): 月曜の下窓 → 07:00→09:00 JST HIGH(07 時未埋め <50%・中値)を CHF/CAD/NZD クロス 6 本に。
# 判定: 3 窓とも勝率 > 55%(バイナリー損益分岐)/ CFD 実行値(ASK 買い・BID 売り)の平均 pips。
import pandas as pd, numpy as np
from scipy import stats
D1=pd.Timestamp("2022-01-01",tz="Asia/Tokyo"); D2=pd.Timestamp("2026-05-29",tz="Asia/Tokyo")
PAIRS=["AUDCAD","EURCHF","GBPCHF","NZDCAD","CADCHF","AUDNZD"]
def load(p,s=""):
    d=pd.read_csv(f"{p}_h1{s}.csv",index_col=0,parse_dates=True); d.index=pd.to_datetime(d.index,utc=True).tz_convert("Asia/Tokyo"); return d
rows=[]
for p in PAIRS:
    b,a=load(p),load(p,"_ask"); j=b.index.intersection(a.index); b,a=b.loc[j],a.loc[j]
    mo=(b.open+a.open)/2; mc=(b.close+a.close)/2; pip=0.0001
    for d0 in sorted({t.normalize() for t in mo.index[mo.index.weekday==0]}):
        t7=d0+pd.Timedelta(hours=7); t9=t7+pd.Timedelta(hours=2)
        if t7 not in mo.index or t9 not in mo.index: continue
        prev=mc[mc.index<=t7-pd.Timedelta(hours=24)]; mon=mo[(mo.index>t7-pd.Timedelta(hours=24))&(mo.index<=t7)]
        if prev.empty or mon.empty: continue
        fri,first=prev.iloc[-1],mon.iloc[0]
        if first>=fri: continue
        if (mo[t7]-first)/(fri-first)>=0.5: continue
        r=mo[t9]-mo[t7]
        if r==0: continue
        rows.append(dict(pair=p,t=t7,win=int(r>0),net=(b.open[t9]-a.open[t7])/pip,per="A" if t7<D1 else ("B" if t7<D2 else "C")))
X=pd.DataFrame(rows)
def f(g): return f"{100*g.win.mean():5.1f}%({len(g):3d})" if len(g) else "-"
print(f"{'ペア':8s} {'2016-21':>11s} {'2022-26.5':>11s} {'2026.6-10':>11s}  CFD 実行値 pips(A/B/C)")
for p in PAIRS+["合算"]:
    g=X if p=="合算" else X[X.pair==p]
    print(f"{p:8s} "+" ".join(f"{f(g[g.per==q]):>11s}" for q in "ABC")+"   "+" / ".join(f"{g[g.per==q].net.mean():+.1f}" for q in "ABC"))
X.to_csv("q143_gap6_rows.csv",index=False)
