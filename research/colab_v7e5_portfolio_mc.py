"""
colab_v7e5_portfolio_mc.py — v7＋E5 併用で「−10%枠に収め・失格率低・期待収益高」の比率を構築。

考え方(プロップの最適化):
  プロップは最大DDで失格が決まる。よって「目標 最大DD = D（−10%の内側に安全マージン）」を固定し、
  その D の中で **期待リターンが最大になる v7:E5 比率** を選ぶ。10年で相関−0.15ゆえ、E5を混ぜるほど
  DD効率(Calmar=年率/最大DD)が上がる→同じDでより高い年率（docs/30で確認済）。
  さらに各比率×Dについて、ブロック・ブートストラップMCで **年次失格率（年内に−10%抵触する確率）** を実測。

出力: 比率×目標DD ごとに [年率 / 想定maxDD / 年次失格率 / 5年累積失格率]。
  推奨= 失格率≤しきい値の中で年率最大の比率。
データ: Drive 10年H1(v7)＋多資産日足10年(E5)。多資産は未配置なら自動取得。ローカルは34ヶ月=スモーク。
これはシミュレーション(将来保証ではない)。E5はSTRONG-LEAD(未検証)＝本番前にデモ(docs/29)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE=True; DRIVE_BASE="/content/drive/MyDrive/forex_ml"
H1_DIR="{base}/dukascopy_data_h1"; DAILY_DIR="{base}/multiasset_daily"; LOCAL_FALLBACK="./research/data"
YEN=["EURJPY","GBPJPY","USDJPY"]; HOURS=[4,6,8,10]
METALS_IDX=["XAUUSD","US500","NAS100","GER40"]; LB=[1,3,6,12]; VOLWIN=12; BPS=5.0
RATIOS=[0.0,0.15,0.25,0.35,0.50]        # E5配分
TARGET_DDS=[5.0,6.0,7.0,8.0]            # 目標 最大DD(%)
BREACH=10.0                             # 失格ライン(%)
MC_YEARS=20000; BLOCK=3; FAIL_THRESH=2.0  # 年次失格率しきい値(%)・推奨選定用
SEED=11

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e: print("Drive不可:", e)
DRIVE_OK=os.path.exists("/content/drive/MyDrive")
print(f"[データ] Drive={DRIVE_OK}")

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def _resolve(name, daily=False):
    c=([f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"] if daily
       else [f"{H1_DIR.format(base=DRIVE_BASE)}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}_h1.csv"])
    for x in c:
        if os.path.exists(x): return x
    return None
def _close(name, daily):
    p=_resolve(name,daily);
    if p is None: return None
    df=pd.read_csv(p); df.columns=[c.strip().lower() for c in df.columns]
    tc=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tc],utc=True,errors="coerce"); df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()
CACHE={}
def D(n):
    if ("d",n) not in CACHE: CACHE[("d",n)]=_close(n,True)
    return CACHE[("d",n)]
def H(p):
    if ("h",p) not in CACHE: CACHE[("h",p)]=_close(p,False)
    return CACHE[("h",p)]

# ---- v7予算校正エンジン(H1足内・SL込み)。週次リスク%を指定してv7月次を作る ----
def _load_h1_ohlc(pair):
    p=_resolve(pair,False)
    if p is None: return None
    df=pd.read_csv(p); df.columns=[c.strip().lower() for c in df.columns]
    tc=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tc],utc=True,errors="coerce"); df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def pk(*n):
        for x in n:
            if x in df.columns: return x
        return None
    o,h,l,c=pk("open","bidopen","o"),pk("high","bidhigh","h"),pk("low","bidlow","l"),pk("close","bidclose","c")
    out=pd.DataFrame(index=df.index)
    out["open"]=df[o].astype(float); out["high"]=df[h].astype(float)
    out["low"]=df[l].astype(float); out["close"]=df[c].astype(float)
    return out.dropna()
def H1OHLC(p):
    if ("ohlc",p) not in CACHE: CACHE[("ohlc",p)]=_load_h1_ohlc(p)
    return CACHE[("ohlc",p)]
def _atr_w(h1,period=24):
    h,l,c=h1["high"],h1["low"],h1["close"]; pc=c.shift(1)
    tr=pd.concat([(h-l),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/period,adjust=False).mean()
def v7_monthly_budget(weekly=0.60, shots=12, catatr=2.5, minstop=10.0, maxstop=400.0, maxspread=3.0):
    """週次リスク%を指定したv7月次(=各ショット ret/stop × (weekly/shots))。budget校正版。"""
    legs=[]
    for pair in YEN:
        h1=H1OHLC(pair)
        if h1 is None: continue
        pipv=pip_size(pair); slip=20*(0.001 if pair.endswith("JPY") else 0.00001)
        T=h1.index.values; O=h1["open"].to_numpy(); L=h1["low"].to_numpy(); C=h1["close"].to_numpy()
        atr=_atr_w(h1).to_numpy(); aidx=h1.index.values; idx=h1.index
        per_shot=(weekly/100.0)/shots
        for hr in HOURS:
            pos=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]
            for a in pos:
                ai=int(np.searchsorted(aidx,T[a],side="right"))-1
                if ai<0 or not (atr[ai]==atr[ai]) or atr[ai]<=0: continue
                sd=catatr*atr[ai]; sp=sd/pipv
                if sp<minstop: sp=minstop; sd=sp*pipv
                if sp>maxstop: continue
                entry=O[a]+slip; sl=entry-sd
                until=T[a]+np.timedelta64(24,"h"); b=int(np.searchsorted(T,until,side="left")); b=max(b,a+1)
                ll=L[a:b]
                if len(ll)>0 and (ll<=sl).any(): ex=sl
                else: ex=O[b] if b<len(O) else C[-1]
                ret_pips=(ex-entry)/pipv
                frac=(ret_pips/sp)*per_shot
                t=pd.Timestamp(T[a]); legs.append((t.tz_localize("UTC") if t.tz is None else t, frac))
    if not legs: return pd.Series(dtype=float)
    s=pd.Series([f for _,f in legs],index=[t for t,_ in legs]).sort_index()
    m=s.groupby(s.index.to_period("M")).sum(); m.index=m.index.to_timestamp("M"); return m
_YH={"XAUUSD":"GC=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}
def ensure_multiasset():
    import urllib.request, json as J, time, csv, datetime as DT
    out=(DAILY_DIR.format(base=DRIVE_BASE) if DRIVE_OK else LOCAL_FALLBACK); os.makedirs(out,exist_ok=True)
    for name in METALS_IDX:
        if _resolve(name,True) is not None: continue
        sym=_YH.get(name)
        try:
            u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10y"
            d=J.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=25).read())
            r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
            with open(os.path.join(out,f"{name}_d.csv"),"w",newline="") as f:
                w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"])
                for i,t in enumerate(ts):
                    o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                    if None in (o,h,l,c): continue
                    w.writerow([DT.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c])
            CACHE.pop(("d",name),None); print(f"  [取得]{name}"); time.sleep(1.0)
        except Exception as e: print(f"  [取得失敗]{name}:{str(e)[:40]}")

def _mc(name):
    d=D(name);
    if d is None: return None
    m=d.groupby(d.index.to_period("M")).last(); m.index=m.index.to_timestamp("M"); return m
def e5_monthly():
    rets,sigs,ws={},{},{}
    for a in METALS_IDX:
        m=_mc(a)
        if m is None or len(m)<max(LB)+VOLWIN+2: continue
        comp=sum(np.sign(m.pct_change(L)) for L in LB); pos=np.sign(comp)
        r=m.pct_change(); ws[a]=1.0/r.rolling(VOLWIN,min_periods=6).std(); rets[a]=r.shift(-1); sigs[a]=pos
    if not rets: return pd.Series(dtype=float)
    idx=sorted(set().union(*[set(s.index) for s in sigs.values()])); out={}
    for t in idx:
        num,den=0.0,0.0
        for a in rets:
            p0=sigs[a].get(t,0); w=ws[a].get(t,np.nan); nx=rets[a].get(t,np.nan)
            if not(np.isfinite(p0) and p0!=0 and np.isfinite(w) and np.isfinite(nx)): continue
            num+=w*(p0*nx-BPS/1e4); den+=w
        if den>0: out[t]=num/den
    return pd.Series(out).sort_index().dropna()
def v7_monthly():
    rows=[]
    for p in YEN:
        s=H(p)
        if s is None: continue
        cv=s.values; idx=s.index; ps=pip_size(p)
        for hr in HOURS:
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+24<len(cv)]
            for i in a: rows.append((idx[i].normalize(),(cv[i+24]-cv[i])/cv[i]-2.0*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s=pd.Series([r for _,r in rows],index=[d for d,_ in rows])
    m=s.groupby(s.index.to_period("M")).sum(); m.index=m.index.to_timestamp("M"); return m

def maxdd(s):
    eq=(1+pd.Series(s).dropna()).cumprod(); return float(((eq-eq.cummax())/eq.cummax()).min()*100)
def volnorm(s,t=0.10,ann=12):
    s=pd.Series(s).dropna(); v=s.std()*np.sqrt(ann); return s*(t/v) if v>0 else s

def mc_annual_fail(monthly, n=MC_YEARS, block=BLOCK, breach=BREACH, seed=SEED, horizon_years=5):
    """月次系列から12ヶ月パスをブロックブートストラップし、年内に−breach%抵触する割合=年次失格率。
       5年累積も。失格判定は年初を基準とした実効equityのrunning peakからのDD。"""
    x=np.asarray(pd.Series(monthly).dropna().values,float); m=len(x)
    if m<12: return None,None
    rng=np.random.default_rng(seed)
    # 年次
    fails=0
    for _ in range(n):
        path=[]
        while len(path)<12:
            i=rng.integers(0,m); path.extend(x[i:i+block])
        p=np.array(path[:12]); eq=np.cumprod(1+p); peak=np.maximum.accumulate(eq)
        if ((eq-peak)/peak).min()*100<=-breach: fails+=1
    annual=100.0*fails/n
    # H年累積(年を連結し通しのrunning peak)
    failsH=0
    for _ in range(n//2):
        path=[]
        while len(path)<12*horizon_years:
            i=rng.integers(0,m); path.extend(x[i:i+block])
        p=np.array(path[:12*horizon_years]); eq=np.cumprod(1+p); peak=np.maximum.accumulate(eq)
        if ((eq-peak)/peak).min()*100<=-breach: failsH+=1
    cumH=100.0*failsH/(n//2)
    return round(annual,2), round(cumH,2)

def run():
    if [a for a in METALS_IDX if _resolve(a,True) is None]:
        print("[診断]多資産日足未配置→取得"); ensure_multiasset()
    v7=v7_monthly(); e5=e5_monthly()
    print(f"[診断] v7月次={len(v7)} / E5月次={len(e5)}")
    if len(v7)==0 or len(e5)==0: print("計算不可: データ配置確認"); return
    j=pd.concat([v7.rename("v7"),e5.rename("e5")],axis=1).dropna()
    if len(j)<24: print(f"重複{len(j)}ヶ月=スモーク(10年はDrive)")
    print(f"重複 {j.index.min().date()}..{j.index.max().date()} ({len(j)}ヶ月) 相関{round(j.v7.corr(j.e5),3)}")
    v7n=volnorm(j.v7); e5n=volnorm(j.e5)
    out={"span":f"{j.index.min().date()}..{j.index.max().date()}","n":len(j),
         "corr":round(float(j.v7.corr(j.e5)),3),"grid":[]}
    best=None
    for Dt in TARGET_DDS:
        print(f"\n=== 目標 最大DD = −{Dt}% (失格ライン−{BREACH}%) ===")
        print(f"  {'比率v7:E5':<12}{'年率':>7}{'実maxDD':>9}{'年次失格率':>11}{'5年累積失格':>11}")
        for w in RATIOS:
            blend=(1-w)*v7n+w*e5n; dd=abs(maxdd(blend))
            if dd==0: continue
            k=Dt/dd; sc=blend*k                       # 目標DDにスケール
            cagr=((1+sc).cumprod().iloc[-1]**(12/len(sc))-1)*100
            af,cf=mc_annual_fail(sc)
            tag=f"v7:{int((1-w)*100)}/E5:{int(w*100)}"
            mark=""
            cand=dict(target_dd=Dt,ratio=tag,e5=w,CAGR=round(cagr,1),realized_maxDD=round(-Dt,1),
                      annual_fail=af,cum5y_fail=cf)
            if af is not None and af<=FAIL_THRESH:
                if best is None or cagr>best["CAGR"]: best=cand;
            print(f"  {tag:<12}{cagr:>6.1f}%{-Dt:>8.1f}%{af:>10}%{cf:>10}%")
            out["grid"].append(cand)
    if best:
        print(f"\n>>> 推奨(年次失格率≤{FAIL_THRESH}%で年率最大): 目標DD−{best['target_dd']}% / {best['ratio']} "
              f"→ 年率{best['CAGR']}% / 年次失格{best['annual_fail']}% / 5年累積{best['cum5y_fail']}%")
        out["recommended"]=best
    # ---- EA予算への変換(各レッグを年率いくらのボラで回すか) ----
    print("\n=== EA予算への変換(推奨比率を実現する各レッグの目標年率ボラ) ===")
    v7vol=float(j.v7.std()*np.sqrt(12)*100); e5vol=float(e5.std()*np.sqrt(12)*100)
    print(f"  素の年率ボラ: v7={v7vol:.1f}% / E5={e5vol:.1f}% (この素サイズ基準で倍率を出す)")
    tgt = best if best else dict(target_dd=6.0,e5=0.25,ratio="v7:75/E5:25")
    w=tgt["e5"]; Dt=tgt["target_dd"]
    blend=(1-w)*v7n+w*e5n; k=Dt/abs(maxdd(blend))
    v7_tgt_vol=k*(1-w)*10.0; e5_tgt_vol=k*w*10.0     # 各レッグの目標年率ボラ(%)
    print(f"  推奨{tgt['ratio']} @ 目標DD−{Dt}%: v7目標ボラ{v7_tgt_vol:.1f}% / E5目標ボラ{e5_tgt_vol:.1f}%")
    print(f"  → v7サイズ = 現素の {v7_tgt_vol/v7vol:.2f}倍 / E5サイズ = 現素の {e5_tgt_vol/e5vol:.2f}倍")
    print(f"  目安EA設定: v7 週次リスク ≈ 0.6%×{v7_tgt_vol/ (v7vol if v7vol>0 else 1):.2f} / "
          f"E5 legRisk ≈ 0.55%×{e5_tgt_vol/(e5vol if e5vol>0 else 1):.2f}")
    out["budget_translation"]=dict(v7_raw_vol=round(v7vol,1),e5_raw_vol=round(e5vol,1),
        v7_target_vol=round(v7_tgt_vol,1),e5_target_vol=round(e5_tgt_vol,1),
        v7_size_mult=round(v7_tgt_vol/v7vol,2) if v7vol else None,
        e5_size_mult=round(e5_tgt_vol/e5vol,2) if e5vol else None)
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/v7e5_portfolio_mc.json") if DRIVE_OK else "research/results/v7e5_portfolio_mc.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

def run_weekly_mode(scenarios, ratio_e5=0.35, fx=159.0):
    """当初倍率(週次%)を直接指定し、v7+E5(比率)の 合成maxDD/CAGR/年次失格率/手取り を確定。
       scenarios: [(ラベル, 口座$, 週次%, 分配)] 例 [("Blueberry $50k",50000,1.5,0.8),...]"""
    if [a for a in METALS_IDX if _resolve(a,True) is None]:
        ensure_multiasset()
    e5=e5_monthly()
    if len(e5)==0: print("E5空: データ確認"); return
    e5vol=float(e5.std()*np.sqrt(12))
    print("\n"+"="*78)
    print(f"=== 週次指定モード: v7+E5 比率 {int((1-ratio_e5)*100)}:{int(ratio_e5*100)} / 当初倍率 ===")
    print("="*78)
    out=[]
    for label,acc,wk,split in scenarios:
        v7=v7_monthly_budget(weekly=wk)
        if len(v7)==0: print(f"{label}: v7空(H1未配置?)"); continue
        v7vol=float(v7.std()*np.sqrt(12))
        # E5を 比率に合わせてスケール: E5vol = (e5_share/v7_share) × v7vol
        tgt_e5vol=(ratio_e5/(1-ratio_e5))*v7vol
        e5s=e5*(tgt_e5vol/e5vol if e5vol>0 else 0.0)
        j=pd.concat([v7.rename("v7"),e5s.rename("e5")],axis=1).dropna()
        comb=(j.v7+j.e5)
        # 単体(v7のみ, 同重複)も比較
        for nm,series in [("v7単体",j.v7),("v7+E5",comb)]:
            dd=maxdd(series); cagr=((1+series).cumprod().iloc[-1]**(12/len(series))-1)*100
            af,cf=mc_annual_fail(series)
            take=acc*cagr/100*split*fx
            print(f"  [{label} 週次{wk}% {nm:6s}] 年率{cagr:5.1f}% maxDD{dd:6.1f}% 年失格{af}% 5年累積{cf}% 手取り¥{take:,.0f}")
            out.append(dict(account=label,weekly=wk,mode=nm,CAGR=round(cagr,1),maxDD=round(dd,1),
                            annual_fail=af,cum5y_fail=cf,take_home_jpy=round(take)))
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/v7e5_weekly_mode.json") if DRIVE_OK else "research/results/v7e5_weekly_mode.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
    # 当初倍率での確定試算(プロップ2.5% / インスタント1.5% ・ 比率65:35)
    run_weekly_mode([("FundedNext $100k",100000,2.5,0.80),
                     ("Blueberry $50k", 50000,1.5,0.80)], ratio_e5=0.35, fx=159.0)
