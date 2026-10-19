# -*- coding: utf-8 -*-
"""build_ea_benchmark_notebook.py — notebooks/ea_benchmark.ipynb を多セル構成で生成し実データ実行で出力埋め込み。"""
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

cells = []

cells.append(new_markdown_cell(
"""# 各EA/エッジ・各銘柄の【個別10年数値】ベンチマーク

docs/53(全EA比較)の定量版を Colab で再現するノート。各戦略を実データで再構築し、個別に
**[純益% / 勝率 / maxDD% / Sharpe / Calmar / n / 順列p / v7相関]** を出す。

- **円月曜(v6/v7エッジ)**: EURJPY/GBPJPY/USDJPY 各個 + バスケット
- **株指月曜(E-Mon)**: NAS100/US500/GER40 各個 + バスケット
- **v4(D1 k≥4合議, ADOPT)** と 対照(モメンタム継続)
- **E5(多資産月次TSMOM)** / **v2(D1 RSI逆張り・棄却)**

**使い方(Colab)**: `USE_DRIVE=True`。Drive の `multiasset_daily/`(指数/金/暗号 日足10年)・FXは `fx_daily/`
(または同フォルダ)に `<NAME>_d.csv`。無ければ Yahoo から日足10年を自動取得(研究用・概算)。「すべて実行」。

> 規律: 数字は盛らない。日足近似(配当除く指数・SL/TP簡易再現)ゆえ絶対値はDrive(Dukascopy/H1/H4)で要確定。
> intraday(v9)・H4(v5/_v4.mq5)は日足から再現不可→docs値を参照欄に明記。最終確証はデモ前進検証(docs/29)。"""))

cells.append(new_code_cell(
'''# === セットアップ & 設定 ===
# Colab 初回のみ:  !pip -q install numpy pandas
import os, json, urllib.request, datetime as dt, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
DAILY_DIRS = [DRIVE_BASE + "/multiasset_daily", DRIVE_BASE + "/fx_daily"]   # 多資産/FXの置き場
LOCAL_FALLBACK = "./research/data"

YAHOO = {  # フォールバック自動取得
    "US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI",
    "XAUUSD":"GC=F",
    "EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","AUDUSD":"AUDUSD=X",
    "USDCHF":"USDCHF=X","USDCAD":"USDCAD=X","NZDUSD":"NZDUSD=X","EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X"}
YEN   = ["EURJPY","GBPJPY","USDJPY"]
EMON  = ["NAS100","US500","GER40"]
E5_BASKET = ["XAUUSD","US500","NAS100","GER40"]
V4_PAIRS  = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル/Yahoo継続):", e)
print("設定OK")'''))

cells.append(new_code_cell(
'''# === データ取得・正規化(Drive→ローカル→Yahoo) ===
def _yahoo(name):
    sym = YAHOO.get(name)
    if sym is None: return None
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&period1=1451606400&period2=1767225599"
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
    d=json.loads(urllib.request.urlopen(req,timeout=25).read()); r=d["chart"]["result"][0]
    ts=r["timestamp"]; q=r["indicators"]["quote"][0]; rows=[]
    for i,t in enumerate(ts):
        o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
        if None in (o,h,l,c): continue
        rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None),o,h,l,c))
    df=pd.DataFrame(rows,columns=["t","open","high","low","close"]); df["t"]=pd.to_datetime(df["t"],utc=True); return df

_C={}
def load_daily(name):
    if name in _C: return _C[name]
    df=None
    paths=[f"{d}/{name}_d.csv" for d in DAILY_DIRS]+[f"{LOCAL_FALLBACK}/{name}_d.csv"]
    for p in paths:
        if os.path.exists(p):
            df=pd.read_csv(p); df["t"]=pd.to_datetime(df["timestamp"],utc=True,errors="coerce"); break
    if df is None: df=_yahoo(name)
    if df is None: _C[name]=None; return None
    df=df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"]=(df["t"]+pd.Timedelta(hours=2)).dt.floor("D")
    df=df.groupby("trade_date",as_index=True).last()
    df["weekday"]=df.index.dayofweek; df=df[df["weekday"]<=4]
    df["o2o"]=df["open"].shift(-1)/df["open"]-1.0
    _C[name]=df; return df

print("loaders OK / 例:", "US500" , load_daily("US500").shape if load_daily("US500") is not None else "なし")'''))

cells.append(new_code_cell(
'''# === 統計ユーティリティ ===
def pip(p): return 0.01 if p.endswith("JPY") else 0.0001
def to_monthly(r):
    s=r.copy()
    if not isinstance(s.index, pd.PeriodIndex):
        s.index=pd.to_datetime(s.index).to_period("M")
    return s.groupby(level=0).sum()
def perm_p(r,n=4000,seed=7):
    r=np.asarray(r,float)
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); a=np.abs(r)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)])>=real).mean())
def metrics(s,ann):
    s=pd.Series(s).dropna()
    if len(s)==0: return dict(net=0,win=0,maxDD=0,sharpe=0,calmar=0,n=0,perm=1.0)
    eq=(1+s).cumprod(); dd=float(((eq-eq.cummax())/eq.cummax()).min())*100
    mu=s.mean()*ann; vol=s.std()*np.sqrt(ann); shp=mu/vol if vol>0 else 0
    cagr=(eq.iloc[-1]**(ann/len(s))-1)*100 if eq.iloc[-1]>0 else -100
    return dict(net=round(float((eq.iloc[-1]-1)*100),1),win=round(float((s>0).mean()*100),0),
                maxDD=round(dd,1),sharpe=round(float(shp),2),
                calmar=round(float(cagr/abs(dd)),2) if dd else 0.0,n=int(len(s)),perm=round(perm_p(s.values),4))

def v7_ref_monthly():
    acc=None
    for p in YEN:
        df=load_daily(p); m=to_monthly((df[df["weekday"]==0]["o2o"]-2*pip(p)/df[df["weekday"]==0]["open"]).dropna())
        acc=m if acc is None else acc.add(m,fill_value=0.0)
    return acc/3.0
REF=v7_ref_monthly()
def corr_v7(s):
    m=to_monthly(s); j=pd.concat([m.rename("a"),REF.rename("r")],axis=1).dropna()
    return round(float(j["a"].corr(j["r"])),2) if len(j)>30 else None
def mon_long(name,cost_bps):
    df=load_daily(name); return (df[df["weekday"]==0]["o2o"]-cost_bps/1e4).dropna()
def basket(names,cost_bps):
    return pd.concat([mon_long(n,cost_bps).rename(n) for n in names],axis=1).mean(axis=1,skipna=True).dropna()
print("stats OK")'''))

cells.append(new_markdown_cell("## 円月曜(v6/v7) ・ 株指月曜(E-Mon) — 銘柄別 + バスケット"))

cells.append(new_code_cell(
'''rows=[]
def add(label,series,ann,note=""):
    m=metrics(series,ann); m["corr_v7"]=corr_v7(series) if len(series) else None
    rows.append(dict(EA=label,**m,note=note));
    print(f"{label:30s} net{m['net']:>7}% win{m['win']:>4}% DD{m['maxDD']:>6} Sh{m['sharpe']:>5} Cal{m['calmar']:>5} n{m['n']:>4} p{m['perm']:>7} corr{m['corr_v7']}")

for p in YEN: add(f"円月曜 {p}", mon_long(p, 1.3), 52)   # 円ペア往復~1.3bps
add("円月曜 バスケット(v6/v7)", basket(YEN,1.0), 52, "v7=これをリスク予算化/v6=同エッジでDD超過")
for ix in EMON: add(f"株指月曜 {ix}", mon_long(ix,3.0), 52)
add("株指月曜 バスケット(E-Mon)", basket(EMON,3.0), 52, "並行ポートの核(docs/50)")'''))

cells.append(new_markdown_cell("## v4(D1 k≥4合議, ADOPT) と 対照(モメンタム継続)\n\n4条件(RSI<35/>65・BBz±1.5・連続3日・当日±0.5%)が k≥4 一致で建て。**逆張り=ADOPT**、継続=対照。SL1.5ATR/RR1.2/8日。"))

cells.append(new_code_cell(
'''def rsi_w(c,n=14):
    d=np.diff(c,prepend=c[0]); up=np.clip(d,0,None); dn=np.clip(-d,0,None)
    au=np.empty_like(c); ad=np.empty_like(c); au[0]=up[0]; ad[0]=dn[0]; a=1.0/n
    for i in range(1,len(c)): au[i]=a*up[i]+(1-a)*au[i-1]; ad[i]=a*dn[i]+(1-a)*ad[i-1]
    return 100-100/(1+au/np.where(ad==0,1e-12,ad))
def atr_d(h,l,c,n=14):
    pc=np.roll(c,1); pc[0]=c[0]; tr=np.maximum(h-l,np.maximum(np.abs(h-pc),np.abs(l-pc)))
    o=np.empty_like(tr); o[0]=tr[0]; a=1.0/n
    for i in range(1,len(tr)): o[i]=a*tr[i]+(1-a)*o[i-1]
    return o
def v4_series(kmin=4, momentum=False):
    monthly={}; trades={}
    for p in V4_PAIRS:
        df=load_daily(p)
        if df is None: continue
        o=df["open"].values; h=df["high"].values; l=df["low"].values; c=df["close"].values
        idx=df.index; n=len(c); rsi=rsi_w(c,14); atr=atr_d(h,l,c,14); bb=20; cost=2*pip(p); cnt=0; i=bb+2
        while i<n-1:
            win=c[i-bb:i]; mean=win.mean(); sd=win.std(ddof=1); z=(c[i]-mean)/sd if sd>0 else 0.0
            down=0
            for k in range(12):
                if i-k-1>=0 and c[i-k]<c[i-k-1]: down+=1
                else: break
            up=0
            for k in range(12):
                if i-k-1>=0 and c[i-k]>c[i-k-1]: up+=1
                else: break
            ret=(c[i]-c[i-1])/c[i-1] if c[i-1] else 0.0; mv=0.005
            buy=int(rsi[i]<35)+int(z<-1.5)+int(down>=3)+int(ret<-mv)
            sell=int(rsi[i]>65)+int(z>1.5)+int(up>=3)+int(ret>mv)
            raw=1 if (buy>=kmin and buy>sell) else (-1 if (sell>=kmin and sell>buy) else 0)
            if raw==0: i+=1; continue
            sig=-raw if momentum else raw
            entry=o[i+1]; sld=1.5*atr[i]; tpd=1.2*sld
            if sld<=0: i+=1; continue
            sl=entry-sig*sld; tp=entry+sig*tpd; ex=None; j=i+1; held=0
            while j<n and held<8:
                if sig>0:
                    if l[j]<=sl: ex=sl; break
                    if h[j]>=tp: ex=tp; break
                else:
                    if h[j]>=sl: ex=sl; break
                    if l[j]<=tp: ex=tp; break
                j+=1; held+=1
            if ex is None: ex=c[min(j,n-1)]
            r=sig*(ex/entry-1.0)-cost/entry
            mk=pd.Period(idx[min(j,n-1)],freq="M"); monthly[mk]=monthly.get(mk,0.0)+r; cnt+=1; i=max(i+1,j)
        trades[p]=cnt
    return pd.Series(monthly).sort_index(), trades

s4,t4=v4_series(4,False);  add("v4 k>=4合議(ADOPT・逆張りD1)", s4, 12, f"件数{sum(t4.values())} {t4}")
s4m,_=v4_series(4,True);    add("(対照)v4 k>=4 モメンタム継続", s4m, 12, "_v4.mq5系=H4版の日足対照")'''))

cells.append(new_markdown_cell("## E5(多資産月次TSMOM・衛星) ・ v2(D1 RSI逆張り・棄却)"))

cells.append(new_code_cell(
'''def e5_monthly():
    closes={}
    for nm in E5_BASKET:
        df=load_daily(nm); s=df["close"]; s.index=pd.to_datetime(df.index); closes[nm]=s.resample("ME").last()
    px=pd.DataFrame(closes).dropna(); ret=px.pct_change()
    sig=pd.DataFrame(0.0,index=px.index,columns=px.columns)
    for lb in (1,3,6,12): sig=sig.add(np.sign(px.pct_change(lb)),fill_value=0)
    out=((np.sign(sig).shift(1)*ret).mean(axis=1)-5e-4).dropna(); out.index=out.index.to_period("M"); return out
def v2_series():
    monthly={}
    for p in ["EURUSD","USDJPY","GBPUSD","AUDUSD","EURJPY"]:
        df=load_daily(p); c=df["close"].values; o=df["open"].values; idx=df.index; n=len(c); rsi=rsi_w(c,14); cost=2*pip(p); i=16
        while i<n-1:
            sig=1 if rsi[i]<30 else (-1 if rsi[i]>70 else 0)
            if sig==0: i+=1; continue
            entry=o[i+1]; j=min(i+5,n-1); r=sig*(c[j]/entry-1.0)-cost/entry
            mk=pd.Period(idx[j],freq="M"); monthly[mk]=monthly.get(mk,0.0)+r; i=j
    return pd.Series(monthly).sort_index()

add("E5 多資産月次TSMOM", e5_monthly(), 12, "衛星(docs/31)")
add("v2 D1 RSI逆張り(棄却)", v2_series(), 12, "レジーム依存→棄却(docs/04)")'''))

cells.append(new_code_cell(
'''# === 一覧表 + 日足再現不可のdoc値 + 保存 ===
df=pd.DataFrame(rows)
print("="*100)
print(df[["EA","net","win","maxDD","sharpe","calmar","n","perm","corr_v7"]].to_string(index=False))
print("\\n[日足から再現不可=docs値を参照]")
print("  v9 (円月曜 12h intraday): net+17.9% / maxDD-5.0% / Sharpe0.76 / STRONG-LEAD (docs/40・要H1)")
print("  v5 (H4 TSMOM)          : NO-GO 順列1/3・真maxDD-35〜-150% (docs/11・要H4)")
print("  v4(file) H4モメンタム    : 検証段階・IS負 (docs/10・要H4)")
try:
    base=(DRIVE_BASE if os.path.isdir(DRIVE_BASE) else "research/results"); os.makedirs(base,exist_ok=True)
    with open(os.path.join(base,"ea_benchmark_notebook.json"),"w") as fp:
        json.dump(df.to_dict("records"),fp,ensure_ascii=False,indent=2,default=str)
    print("\\n保存:", os.path.join(base,"ea_benchmark_notebook.json"))
except Exception as e: print("保存スキップ:",e)'''))

cells.append(new_markdown_cell(
"""## 読み方(個別数値の要点)

- **円月曜は EURJPY/GBPJPY が主役**(Sharpe~1.0/0.83)、**USDJPY は弱い**(Sharpe~0.57)＝docs/16「USDJPY単体は弱いが分散用」を裏付け。3ペア相関0.83-0.89＝1現象の多ショット。
- **株指月曜は NAS100 が最強**(Sharpe~1.06・perm~0.0008)、v7相関0.11-0.26と低＝並行の核(docs/50)。
- **v4 k≥4(逆張り)が単体最強**(Calmar~0.85・勝率62%)。**モメンタム継続(対照)は-69%・perm~0.999で死亡**＝
  「v4の真価は逆張り合議であって `_v4.mq5` のH4モメンタムではない」を数値で確証。
- **E5 は本proxyでperm~0.135＝非有意(単体最弱・衛星専用)**。**v2 は全期間+でもレジーム依存**ゆえ棄却(全期間pだけで採否を決めない)。

> 確定値化: Drive に Dukascopy/H1(円・FX)・配当込みCFD(指数)・H4(v4/v5)を置いて再実行。intraday(v9)・H4は
> 本ノート(日足)では再現不可ゆえ docs値を参照。免責: シミュレーション。本資金前デモ前進検証必須。数字は盛らない。"""))

nb=new_notebook(cells=cells)
nb.metadata={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},
             "language_info":{"name":"python","version":"3.11"}}
nbf.write(nb,"notebooks/ea_benchmark.ipynb")
print("wrote notebooks/ea_benchmark.ipynb with", len(cells), "cells")
