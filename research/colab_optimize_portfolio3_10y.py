"""
colab_optimize_portfolio3_10y.py — Portfolio3(v7+v4+E5) 比率×サイズ最適化の【10年Dukascopy 確定版】。

`research/optimize_portfolio3.py`(手元Yahoo・v7は2年アンカー)と**同一の最適化ロジック**を、ユーザーの
10年H1 Dukascopy(v7)＋10年日足(v4/E5)で回し、比率(v7:v4:E5)とサイズ倍率を目的別に確定する。
docs/45 §3 が積み残した「3戦略比率の10年実測確定」を埋める。**v7も実10年ゆえアンカー補正は不要**。

使い方(Colab): USE_DRIVE=True。H1_DIR={9ペア}_h1.csv(10年, UTC), DAILY_DIR=多資産日足({XAUUSD,US500,
  NAS100,GER40}_d.csv, 無ければYahoo自動)。「すべて実行」。出力=results/optimize_portfolio3_10y.json。

⚠ 数字は盛らない。確証はデモ前進検証(docs/29)。相関は実10年で v7⇄v4 −0.13/v7⇄E5 −0.18/v4⇄E5 −0.05＝
  ほぼ0〜弱負(独立ブートストラップ=やや保守)。本ハーネスは比率と倍率の**確定**が目的。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
USE_DRIVE=True; DRIVE_BASE="/content/drive/MyDrive/forex_ml"
H1_DIR="{base}/dukascopy_data_h1"; DAILY_DIR="{base}/multiasset_daily"; LOCAL="./research/data"
PAIRS=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
JPY=["EURJPY","GBPJPY","USDJPY"]; HOURS=[4,6,8,10]
ASSETS=["XAUUSD","US500","NAS100","GER40"]; LB=[1,3,6,12]; VOLWIN=12
SPREAD={"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,"USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
DEFSPR=1.5; SLIP=0.5; E5_FRICTION=dict(idx_long=-3.0,idx_short=-1.5,gold_long=-4.0,gold_short=-1.5)
N_PATHS=6000; SEED=11; TARGET_DD=0.08
if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive",force_remount=False)
    except Exception as e: print("Drive不可:",e)
DRIVE_OK=os.path.exists("/content/drive/MyDrive")
def pipsz(p): return 0.01 if p.endswith("JPY") else 0.0001
def _read(path):
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tc=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns),df.columns[0])
    df["t"]=pd.to_datetime(df[tc],utc=True,errors="coerce"); df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def col(*n):
        for x in n:
            for c in df.columns:
                if c==x: return c
        return None
    o,h,l,c=col("open","bidopen","o"),col("high","bidhigh","h"),col("low","bidlow","l"),col("close","bidclose","c")
    if c is None: return None
    if None in (o,h,l):
        s=df[c].astype(float); return pd.DataFrame({"open":s,"high":s,"low":s,"close":s})
    return df[[o,h,l,c]].astype(float).rename(columns={o:"open",h:"high",l:"low",c:"close"})
def _yf(sym,rng="10y",iv="1d"):
    import urllib.request
    u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval={iv}&range={rng}"
    d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=25).read())
    r=d["chart"]["result"][0];ts=r["timestamp"];q=r["indicators"]["quote"][0]
    rows=[(pd.to_datetime(t,unit="s",utc=True),q["open"][i],q["high"][i],q["low"][i],q["close"][i])
          for i,t in enumerate(ts) if None not in (q["open"][i],q["high"][i],q["low"][i],q["close"][i])]
    return pd.DataFrame(rows,columns=["t","open","high","low","close"]).set_index("t")
H1={};DLY={};MUL={}
def h1(p):
    if p in H1: return H1[p]
    for path in [f"{H1_DIR.format(base=DRIVE_BASE)}/{p}_h1.csv", f"{LOCAL}/{p}_h1.csv"]:
        if os.path.exists(path): H1[p]=_read(path); return H1[p]
    H1[p]=None; return None
def daily(p):
    if p in DLY: return DLY[p]
    d=h1(p)
    if d is not None:
        g=d.resample("1D"); DLY[p]=pd.DataFrame({"open":g["open"].first(),"high":g["high"].max(),"low":g["low"].min(),"close":g["close"].last()}).dropna(); return DLY[p]
    for path in [f"{LOCAL}/{p}_d.csv"]:
        if os.path.exists(path): DLY[p]=_read(path); return DLY[p]
    try:
        sym={"EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","AUDUSD":"AUDUSD=X","USDCHF":"USDCHF=X","USDCAD":"USDCAD=X","NZDUSD":"NZDUSD=X","EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X"}[p]
        DLY[p]=_yf(sym); return DLY[p]
    except Exception: DLY[p]=None; return None
def masset(n):
    if n in MUL: return MUL[n]
    for path in [f"{DAILY_DIR.format(base=DRIVE_BASE)}/{n}_d.csv", f"{LOCAL}/{n}_d.csv"]:
        if os.path.exists(path): MUL[n]=_read(path); return MUL[n]
    try:
        sym={"XAUUSD":"GC=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}[n]; MUL[n]=_yf(sym); return MUL[n]
    except Exception: MUL[n]=None; return None
def rsi_w(c,n=14):
    d=np.diff(c,prepend=c[0]);up=np.clip(d,0,None);dn=np.clip(-d,0,None)
    au=np.empty_like(c);ad=np.empty_like(c);au[0]=up[0];ad[0]=dn[0];a=1/n
    for i in range(1,len(c)):au[i]=a*up[i]+(1-a)*au[i-1];ad[i]=a*dn[i]+(1-a)*ad[i-1]
    rs=np.divide(au,np.where(ad==0,np.nan,ad));return np.nan_to_num(100-100/(1+rs),nan=50.0)
def atr_w(h,l,c,n=14):
    pc=np.roll(c,1);pc[0]=c[0];tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)])
    o=np.empty_like(c);o[0]=tr[0];a=1/n
    for i in range(1,len(c)):o[i]=a*tr[i]+(1-a)*o[i-1]
    return o
def bb_z(c,n=20):
    z=np.full_like(c,np.nan)
    for i in range(n,len(c)):
        w=c[i-n:i];s=w.std(ddof=1)
        if s>0:z[i]=(c[i]-w.mean())/s
    return z
def v7_monthly(weekly_budget=0.60):
    cols=[]
    for p in JPY:
        d=h1(p)
        if d is None: continue
        cv=d["close"].values; idx=d.index; ps=pipsz(p)
        for hr in HOURS:
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+24<len(cv)]
            if len(a)==0: continue
            r=pd.Series((cv[a+24]-cv[a])/cv[a]-2.0*ps/cv[a], index=idx[a].to_period("M"))
            cols.append(r.groupby(level=0).sum())
    if not cols: return pd.Series(dtype=float)
    return pd.concat(cols,axis=1).sum(axis=1).dropna()*(weekly_budget/100.0)
def v4_monthly(risk_per_trade=0.15):
    from collections import defaultdict; mo=defaultdict(float)
    for p in PAIRS:
        d=daily(p)
        if d is None: continue
        o=d["open"].values;h=d["high"].values;l=d["low"].values;c=d["close"].values;idx=d.index
        rsi=rsi_w(c);z=bb_z(c);dn=np.zeros(len(c));upp=np.zeros(len(c))
        for i in range(1,len(c)):
            dn[i]=dn[i-1]+1 if c[i]<c[i-1] else 0; upp[i]=upp[i-1]+1 if c[i]>c[i-1] else 0
        ret=np.zeros(len(c));ret[1:]=(c[1:]-c[:-1])/c[:-1];sig=np.zeros(len(c))
        for i in range(20,len(c)):
            bv=int(rsi[i]<35)+int((not np.isnan(z[i]))and z[i]<-1.5)+int(dn[i]>=3)+int(ret[i]<-0.005)
            sv=int(rsi[i]>65)+int((not np.isnan(z[i]))and z[i]>1.5)+int(upp[i]>=3)+int(ret[i]>0.005)
            if bv>=4 and bv>sv: sig[i]=1
            elif sv>=4 and sv>bv: sig[i]=-1
        atr=atr_w(h,l,c);pip=pipsz(p);half=(SPREAD.get(p,DEFSPR)/2+SLIP)*pip;pos=None
        for i in range(1,len(c)):
            if pos is not None:
                dd=pos["dir"];e=pos["entry"];sl=pos["sl"];tp=pos["tp"];ex=None
                if dd>0:
                    if l[i]-half<=sl:ex=sl
                    elif h[i]-half>=tp:ex=tp
                else:
                    if h[i]+half>=sl:ex=sl
                    elif l[i]+half<=tp:ex=tp
                if ex is None and (i-pos["i"])>=8:ex=o[i]+(half if dd<0 else -half)
                if ex is not None:
                    mo[idx[pos["i"]].to_period("M")]+=((ex-e) if dd>0 else (e-ex))/pos["risk"];pos=None
            if pos is None:
                s=sig[i-1]
                if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                    e=o[i]+(half if s>0 else -half);risk=atr[i-1]*1.5
                    sl=e-risk if s>0 else e+risk;tp=e+1.2*risk if s>0 else e-1.2*risk
                    pos={"dir":s,"entry":e,"sl":sl,"tp":tp,"risk":risk,"i":i}
    s=pd.Series(mo); s.index=pd.PeriodIndex(s.index,freq="M"); return s.sort_index()*(risk_per_trade/100.0)
def e5_monthly(legRisk=0.30, fr=E5_FRICTION):
    legs=[]
    for a in ASSETS:
        d=masset(a)
        if d is None: continue
        m=d["close"].groupby(d.index.to_period("M")).last()
        if len(m)<max(LB)+VOLWIN+2: continue
        pos=np.sign(sum(np.sign(m.pct_change(L)) for L in LB)); r=m.pct_change(); nx=r.shift(-1)
        sig=r.rolling(VOLWIN,min_periods=max(6,VOLWIN//2)).std().shift(1); isg=(a=="XAUUSD")
        cl=fr["gold_long"] if isg else fr["idx_long"]; cs=fr["gold_short"] if isg else fr["idx_short"]
        out={}
        for t in m.index:
            p0=pos.get(t,0);v=sig.get(t,np.nan);fwd=nx.get(t,np.nan)
            if not(np.isfinite(p0) and p0!=0 and np.isfinite(v) and v>0 and np.isfinite(fwd)): continue
            out[t]=(legRisk/100.0)*((p0*fwd+((cl if p0>0 else cs)/100.0/12.0))/v)
        legs.append(pd.Series(out))
    if not legs: return pd.Series(dtype=float)
    return pd.concat(legs,axis=1).sum(axis=1).dropna()
def ann_return(s):
    s=pd.Series(s).dropna(); return float(((1+s).prod())**(12/len(s))-1) if len(s) else 0.0
def maxdd(s):
    eq=(1+pd.Series(s).dropna()).cumprod();pk=eq.cummax();return float(((eq-pk)/pk).min()) if len(s) else 0.0
def ann_vol(s):
    s=pd.Series(s).dropna(); return float(s.std()*np.sqrt(12)) if len(s) else 0.0
def sharpe(s):
    v=ann_vol(s); return ann_return(s)/v if v>0 else 0.0
def boot_matrix(s,n_paths=N_PATHS,months=60,block=3,seed=SEED):
    """系列sを独立ブロック再標本した (n_paths, months) 行列を一度だけ生成(ベクトル化)。"""
    w=pd.Series(s).dropna().values; n=len(w)
    if n==0: return np.zeros((n_paths,months))
    rng=np.random.default_rng(seed); nb=int(np.ceil(months/block))
    starts=rng.integers(0,n,size=(n_paths,nb)); offs=np.arange(block)
    idx=(starts[:,:,None]+offs[None,None,:])%n
    return w[idx].reshape(n_paths,nb*block)[:,:months]
def _dd_min(P):
    eq=np.cumprod(1+P,axis=1); pk=np.maximum.accumulate(eq,axis=1)
    return ((eq-pk)/pk).min(axis=1)
def path_maxdd_p95(P): return float(np.percentile(_dd_min(P),5))
def trailing_fail_rate(P,total_dd=0.10,horizon=12):
    return float((_dd_min(P[:,:min(P.shape[1],horizon)])<=-total_dd).mean())
def cagr_of(P):
    fin=np.prod(1+P,axis=1); return float(np.median(fin)**(12/P.shape[1])-1)

# 確定の比率→EA予算アンカー(docs/45): 40:40:20 ↔ v7 0.60 / v4 0.15 / E5 0.30 (INSTANT基準)
REF_BUDGET={"v7":0.60,"v4":0.15,"v5":0.30}; BASE_SHARE={"v7":40.0,"v4":40.0,"v5":20.0}
OBJECTIVES={"CALMAR_40_35_25":(40,35,25),"CAGR_45_35_20":(45,35,20),
            "DEFENSE_45_40_15":(45,40,15),"BASELINE_40_40_20":(40,40,20)}
TARGET_DD_GRID=[0.04,0.05,0.06,0.07,0.08,0.10]   # 倍率を当てる目標 p95 maxDD

def main():
    s7=v7_monthly(); s4=v4_monthly(); s5=e5_monthly()           # 参照予算(0.60/0.15/0.30)での実10年系列
    series={"v7":s7,"v4":s4,"v5":s5}; order=["v7","v4","v5"]
    stats={k:dict(n=int(len(v.dropna())),ann_ret=round(ann_return(v)*100,2),ann_vol=round(ann_vol(v)*100,2),
                  maxDD=round(maxdd(v)*100,2),sharpe=round(sharpe(v),2)) for k,v in
           {"v7(10y)":s7,"v4(10y)":s4,"E5(10y)":s5}.items()}
    if len(pd.Series(s7).dropna())<60:
        print("\n⚠⚠ 警告: v7系列が60ヶ月未満(=10年H1 Dukascopy未投入)。"
              "v7のSharpeが短期サンプルで歪み、比率(A)が信用できません(E5を過小評価する傾向)。"
              "**正式確定には10年H1 Dukascopyを H1_DIR に置いて再実行**してください。"
              "それまでは比率は docs/49 の CALMAR 40:35:25 を採用。\n")
    Bmat={k:boot_matrix(series[k]) for k in order}              # 各戦略パス行列(参照予算)を一度だけ
    sig={k:ann_vol(series[k])/np.sqrt(12) for k in order}
    # ===== (A) 比率スイープ: どの比率が最適か(リスク正規化・目標DD=8%で横並び) =====
    steps=np.arange(0,1.0001,0.05); grid=[]
    for a7 in steps:
        for a4 in steps:
            a5=1-a7-a4
            if a5<-1e-9 or a5>1+1e-9: continue
            a5=round(float(a5),4)
            if a5<0: continue
            a7r,a4r=round(float(a7),3),round(float(a4),3)
            kb=[(a/sig[k]) if sig[k]>0 and a>0 else 0.0 for k,a in zip(order,[a7r,a4r,a5])]
            if sum(kb)==0: continue
            P0=sum(kb[i]*Bmat[order[i]] for i in range(3))
            bstd=P0.std()
            if bstd<=1e-9: continue
            P0=P0*(0.01/bstd); dd0=abs(path_maxdd_p95(P0))
            if dd0<=1e-6: continue
            P=P0*(0.08/dd0)
            grid.append(dict(ratio=f"{int(a7r*100)}:{int(a4r*100)}:{int(a5*100)}",a7=a7r,a4=a4r,a5=a5,
                             cagr=round(cagr_of(P)*100,2),maxDD_p95=round(path_maxdd_p95(P)*100,2),
                             cum5y_fail=round(trailing_fail_rate(P,0.10,60)*100,2),
                             calmar=round(cagr_of(P)/max(abs(path_maxdd_p95(P)),1e-9),3)))
    valid=[g for g in grid if g["a7"]>0]
    # ===== (B) 倍率スイープ: 各目的比率で、目標DD別の「EAに入れる実予算」を確定 =====
    budget_plan={}
    for name,(s7sh,s4sh,s5sh) in OBJECTIVES.items():
        # ratio予算(M=1): REF_BUDGET × share/base_share
        rb={k:REF_BUDGET[k]*sh/BASE_SHARE[k] for k,sh in zip(order,[s7sh,s4sh,s5sh])}
        # 実予算系列 = 参照系列 × (rb/REF_BUDGET) を独立合成(=参照行列を係数倍)
        unitP=sum((rb[k]/REF_BUDGET[k])*Bmat[k] for k in order)   # M=1(実予算)のポートパス
        dd_unit=abs(path_maxdd_p95(unitP))
        rows=[]
        for tdd in TARGET_DD_GRID:
            M=tdd/dd_unit if dd_unit>1e-9 else 0.0
            P=unitP*M
            rows.append(dict(target_dd=round(tdd*100,1),mult=round(M,3),
                             v7=round(rb["v7"]*M,3),v4=round(rb["v4"]*M,3),e5=round(rb["v5"]*M,3),
                             cagr=round(cagr_of(P)*100,2),p95maxDD=round(path_maxdd_p95(P)*100,2),
                             annual_fail=round(trailing_fail_rate(P,0.10,12)*100,3),
                             cum5y_fail=round(trailing_fail_rate(P,0.10,60)*100,2)))
        budget_plan[name]=dict(ratio_budget_M1={k:round(rb[k],4) for k in order},by_target_dd=rows)
    out=dict(meta=dict(source="Dukascopy 10y (or Yahoo fallback)",note="run outputs only; ratio+multiplier finalization",
                       ref_budget=REF_BUDGET,target_dd_grid=[round(x*100,1) for x in TARGET_DD_GRID]),
             strategy_stats=stats,current_40_40_20=next((g for g in grid if g["ratio"]=="40:40:20"),None),
             opt_min_fail=sorted(valid,key=lambda g:(g["cum5y_fail"],-g["cagr"]))[0],
             opt_max_cagr=sorted(valid,key=lambda g:(-g["cagr"],g["cum5y_fail"]))[0],
             opt_max_calmar=sorted(valid,key=lambda g:(-g["calmar"]))[0],
             top_by_calmar=sorted(valid,key=lambda g:(-g["calmar"]))[:6],
             budget_plan=budget_plan, full_grid=grid)
    os.makedirs("research/results",exist_ok=True)
    json.dump(out,open("research/results/optimize_portfolio3_10y.json","w"),indent=2,default=str)
    print("各戦略(実10年・参照予算 v7 0.60/v4 0.15/E5 0.30):")
    for k,v in stats.items(): print(f"  {k:9s} n={v['n']} annRet={v['ann_ret']:+.2f}% vol={v['ann_vol']:.2f}% maxDD={v['maxDD']:+.2f}% Sharpe={v['sharpe']}")
    print("\n(A) 比率最適:")
    for t,g in [("現状40:40:20",out["current_40_40_20"]),("★Calmar最大",out["opt_max_calmar"]),
                ("★CAGR最大",out["opt_max_cagr"]),("★失格最小",out["opt_min_fail"])]:
        if g: print(f"  [{t}] {g['ratio']} CAGR={g['cagr']}% p95DD={g['maxDD_p95']}% 5yFail={g['cum5y_fail']}% Calmar={g['calmar']}")
    print("\n(B) 倍率確定 — 目的別×目標DD別の【EAに入れる実予算 v7/v4/E5 %】:")
    for name,pl in budget_plan.items():
        print(f"\n  ◆ {name}  (ratio予算M=1: v7={pl['ratio_budget_M1']['v7']} v4={pl['ratio_budget_M1']['v4']} E5={pl['ratio_budget_M1']['v5']})")
        print(f"     {'目標DD':>6} {'倍率':>6} {'v7週次':>7} {'v4/tr':>7} {'E5leg':>7} {'CAGR':>7} {'p95DD':>7} {'年失格':>7} {'5年失格':>7}")
        for r in pl["by_target_dd"]:
            print(f"     {r['target_dd']:>5}% {r['mult']:>5}x {r['v7']:>6}% {r['v4']:>6}% {r['e5']:>6}% {r['cagr']:>6}% {r['p95maxDD']:>6}% {r['annual_fail']:>6}% {r['cum5y_fail']:>6}%")
    print("\n出所: research/results/optimize_portfolio3_10y.json")
    print("→ 採用比率(既定CALMAR)×目標DD行の v7/v4/E5 を Chien_Portfolio4_Optimized の MANUAL(または該当Objective)に投入。")
if __name__=="__main__": main()
