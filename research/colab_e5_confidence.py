"""
colab_e5_confidence.py — E5(リスクパリティ多資産トレンド)を【v7と同じ検証レベル】に引き上げる。

背景: v7は docs/23(colab_v7_confidence)で (A)ウォークフォワード (B)パラメータ頑健性 (C)曜日プラセボ
  により"高確度"を確定した。E5はLEAD(頑健p0.042/JK0.171=有意水準未達, docs/27)止まり。本ノートは
  E5に【同じ3本柱】を課し、確度を測る:
   (A) ウォークフォワード: 10年を5分割し各期の net/CAGR/maxDD/Sharpe/Calmar と符号。レジーム非依存か。
   (B) パラメータ頑健性: ルックバック集合 / 逆ボラ窓 / 銘柄除外(各1) / リバランス遅延 / コストを
       ずらしても net>0・正Sharpe・低DDが保つか。ナイフエッジな過剰最適化でないか。
   (C) 方向プラセボ + 有意性ゲート: ランダム方向で崩れるか(方向シグナルの価値)。頑健順列p・JK・
       OOS・v7相関も併記。
  ※v7との違い=「曜日プラセボ」は無いので「方向プラセボ」で代替。最終確度はデモ前進検証(docs/29)で確定。

データ(Drive配置・blendノートと同じ): multiasset_daily/{XAUUSD,US500,NAS100,GER40}_d.csv(10年),
  v7相関用に dukascopy_data_h1/{EURJPY,GBPJPY,USDJPY}_h1.csv。未配置の多資産は自動でYahoo取得。
  ローカル(./research/data)にフォールバック。これはシミュレーション(将来保証ではない)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
DAILY_DIR  = "{base}/multiasset_daily"
LOCAL_FALLBACK = "./research/data"

METALS_IDX = ["XAUUSD","US500","NAS100","GER40"]
YEN        = ["EURJPY","GBPJPY","USDJPY"]
HOURS      = [4,6,8,10]
LB_DEFAULT = [1,3,6,12]
VOLWIN_DEFAULT = 12
BPS_DEFAULT = 5.0
WF_SPLITS  = 5

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル継続):", e)
DRIVE_OK = os.path.exists("/content/drive/MyDrive")
print(f"[データ] Drive={DRIVE_OK} / DAILY={DAILY_DIR.format(base=DRIVE_BASE)} / H1={H1_DIR.format(base=DRIVE_BASE)}")

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def _resolve(name, daily=False):
    if daily:
        c=[f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"]
    else:
        c=[f"{H1_DIR.format(base=DRIVE_BASE)}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}_h1.csv"]
    for x in c:
        if os.path.exists(x): return x
    return None

def _load_close(name, daily=True):
    path=_resolve(name, daily=daily)
    if path is None: return None
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()

CACHE={}
def DCLOSE(n):
    if ("d",n) not in CACHE: CACHE[("d",n)]=_load_close(n, daily=True)
    return CACHE[("d",n)]
def H1C(p):
    if ("h",p) not in CACHE: CACHE[("h",p)]=_load_close(p, daily=False)
    return CACHE[("h",p)]

_YH={"XAUUSD":"GC=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}
def ensure_multiasset():
    import urllib.request, json as _json, time, csv, datetime as _dt
    out_dir=(DAILY_DIR.format(base=DRIVE_BASE) if DRIVE_OK else LOCAL_FALLBACK); os.makedirs(out_dir,exist_ok=True)
    for name in METALS_IDX:
        if _resolve(name,daily=True) is not None: continue
        sym=_YH.get(name);
        if not sym: continue
        try:
            u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10y"
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
            d=_json.loads(urllib.request.urlopen(req,timeout=25).read())
            r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
            p=os.path.join(out_dir,f"{name}_d.csv")
            with open(p,"w",newline="") as f:
                w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"])
                for i,t in enumerate(ts):
                    o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                    if None in (o,h,l,c): continue
                    w.writerow([_dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c])
            CACHE.pop(("d",name),None); print(f"  [取得] {name}<-{sym}"); time.sleep(1.0)
        except Exception as e:
            print(f"  [取得失敗] {name}: {type(e).__name__} {str(e)[:50]}")

def _mclose(name):
    d=DCLOSE(name)
    if d is None: return None
    m=d.groupby(d.index.to_period("M")).last(); m.index=m.index.to_timestamp("M"); return m

# ---------- E5本体(パラメータ化) ----------
def e5_series(assets=METALS_IDX, lookbacks=LB_DEFAULT, volwin=VOLWIN_DEFAULT, bps=BPS_DEFAULT,
              lag=0, randomize=False, seed=7):
    """金+指数TSMOM・逆ボラ加重・月次。lag=シグナル遅延(月)。randomize=方向プラセボ。"""
    rng=np.random.default_rng(seed); rets,sigs,ws={},{},{}
    for a in assets:
        m=_mclose(a)
        if m is None or len(m)<max(lookbacks)+volwin+2: continue
        comp=sum(np.sign(m.pct_change(L)) for L in lookbacks); pos=np.sign(comp)
        if lag>0: pos=pos.shift(lag)
        r=m.pct_change(); invvol=1.0/r.rolling(volwin,min_periods=max(6,volwin//2)).std()
        rets[a]=r.shift(-1); sigs[a]=pos; ws[a]=invvol
    if not rets: return pd.Series(dtype=float)
    idx=sorted(set().union(*[set(s.index) for s in sigs.values()])); out={}
    for t in idx:
        num,den=0.0,0.0
        for a in rets:
            p0=sigs[a].get(t,0); w=ws[a].get(t,np.nan); nx=rets[a].get(t,np.nan)
            if not (np.isfinite(p0) and p0!=0 and np.isfinite(w) and np.isfinite(nx)): continue
            d=rng.choice([-1,1]) if randomize else p0
            num+=w*(d*nx - bps/1e4); den+=w
        if den>0: out[t]=num/den
    return pd.Series(out).sort_index().dropna()

def v7_monthly():
    rows=[]
    for p in YEN:
        s=H1C(p)
        if s is None: continue
        cv=s.values; idx=s.index; ps=pip_size(p)
        for hr in HOURS:
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+24<len(cv)]
            for i in a: rows.append((idx[i].normalize(),(cv[i+24]-cv[i])/cv[i]-2.0*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s=pd.Series([r for _,r in rows],index=[d for d,_ in rows])
    m=s.groupby(s.index.to_period("M")).sum(); m.index=m.index.to_timestamp("M"); return m

# ---------- 統計 ----------
def perm_p(r,n=3000,seed=13):
    r=np.asarray(r,float)
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); a=np.abs(r)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)])>=real).mean())
def perm_p_robust(s,n=3000,seed=13):
    s=pd.Series(s).dropna()
    if len(s)==0: return 1.0
    ms=s.groupby(s.index.to_period("M")).sum(); return perm_p(ms.values,n=n,seed=seed)
def stat(s,ann=12):
    s=pd.Series(s).dropna()
    if len(s)==0: return dict(net=0,CAGR=0,Sharpe=0,maxDD=0,Calmar=0,win=0,n=0)
    eq=(1+s).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    mu=s.mean()*ann; vol=s.std()*np.sqrt(ann); shp=mu/vol if vol>0 else 0
    cagr=(eq.iloc[-1]**(ann/len(s))-1)*100
    return dict(net=round((eq.iloc[-1]-1)*100,1),CAGR=round(cagr,1),Sharpe=round(shp,2),maxDD=round(dd,1),
                Calmar=round(cagr/abs(dd),2) if dd else 0,win=round((s>0).mean()*100,0),n=int(len(s)))
def jackknife(s):
    yrs=sorted(set(s.index.year))
    if len(yrs)<3: return None
    jk={int(y):round(perm_p_robust(s[s.index.year!=y]),3) for y in yrs}; return jk,round(max(jk.values()),3)

def run_e5_confidence():
    if [a for a in METALS_IDX if _resolve(a,daily=True) is None]:
        print("[診断] 多資産日足が未配置 → Yahoo取得"); ensure_multiasset()
    base=e5_series();
    if len(base)<36: print(f"E5月次不足 n={len(base)} (データ確認)"); return
    out={"meta":dict(splits=WF_SPLITS,lookbacks=LB_DEFAULT,volwin=VOLWIN_DEFAULT,bps=BPS_DEFAULT)}
    st=stat(base); p=perm_p_robust(base); jk=jackknife(base); jkmax=jk[1] if jk else None
    h=base.index[len(base)//2]; isr,oos=base[base.index<h],base[base.index>=h]
    ym=v7_monthly(); jj=pd.concat([base.rename("c"),ym.rename("y")],axis=1).dropna()
    corr=round(float(jj["c"].corr(jj["y"])),3) if len(jj)>12 else None
    print(f"\n=== E5 基準(全期間) {base.index.min().date()}..{base.index.max().date()} n={st['n']} ===")
    print(f"  net{st['net']}% CAGR{st['CAGR']}% Sharpe{st['Sharpe']} maxDD{st['maxDD']}% Calmar{st['Calmar']} 勝率{st['win']}%")
    print(f"  頑健p={p} JKmax={jkmax} IS{stat(isr)['net']}/OOS{stat(oos)['net']} v7相関={corr}")
    out["headline"]=dict(**st,perm_p=p,jackknife_max_p=jkmax,IS=stat(isr)["net"],OOS=stat(oos)["net"],corr_v7=corr)

    # (A) ウォークフォワード(5分割)
    print("\n=== (A) ウォークフォワード(5分割) — 符号の安定性 ===")
    n=len(base); bnds=[int(n*k/WF_SPLITS) for k in range(WF_SPLITS+1)]; wf=[]
    pos_periods=0
    for k in range(WF_SPLITS):
        seg=base.iloc[bnds[k]:bnds[k+1]]; s=stat(seg); sign="+" if s["net"]>0 else "−"
        if s["net"]>0: pos_periods+=1
        print(f"  期{k+1} {seg.index.min().date()}..{seg.index.max().date()}: net{s['net']:>6}% maxDD{s['maxDD']:>6}% Sharpe{s['Sharpe']:>5} [{sign}]")
        wf.append(dict(period=f"{seg.index.min().date()}..{seg.index.max().date()}",**s))
    print(f"  → 黒字 {pos_periods}/{WF_SPLITS} 期")
    out["walkforward"]=dict(positive=f"{pos_periods}/{WF_SPLITS}",segments=wf)

    # (B) パラメータ頑健性
    print("\n=== (B) パラメータ頑健性 — net/maxDD/Sharpe/頑健p が崩れないか ===")
    rob={}
    def rep(tag,s):
        st2=stat(s); pp=perm_p_robust(s) if st2["n"]>=24 else 1.0
        print(f"  {tag:<26} net{st2['net']:>7}% maxDD{st2['maxDD']:>6}% Sharpe{st2['Sharpe']:>5} 頑健p{pp}")
        rob[tag]=dict(**st2,perm_p=pp)
    for lb in ([3,6,12],[1,6,12],[6,12],[1,3,6,12],[1,3,6]):
        rep(f"LB={lb}", e5_series(lookbacks=lb))
    for vw in (6,12,18):
        rep(f"volwin={vw}", e5_series(volwin=vw))
    for drop in METALS_IDX:
        rep(f"除外:{drop}", e5_series(assets=[a for a in METALS_IDX if a!=drop]))
    for lg in (0,1):
        rep(f"lag={lg}ヶ月", e5_series(lag=lg))
    for c in (2,5,10,20):
        rep(f"cost={c}bps", e5_series(bps=float(c)))
    out["robustness"]=rob
    nets=[v["net"] for v in rob.values()]; sharpes=[v["Sharpe"] for v in rob.values()]
    print(f"  → net範囲 {min(nets)}〜{max(nets)}% / Sharpe範囲 {min(sharpes)}〜{max(sharpes)}")

    # (C) 方向プラセボ
    print("\n=== (C) 方向プラセボ(ランダム方向) — 方向シグナルの価値 ===")
    pl=e5_series(randomize=True); ps=stat(pl); pp=perm_p_robust(pl)
    print(f"  placebo net{ps['net']}% Sharpe{ps['Sharpe']} 頑健p{pp}  (基準net{st['net']}% を大きく下回れば方向に価値)")
    out["placebo"]=dict(**ps,perm_p=pp)

    # 判定
    g_perm=p<=0.0083; g_jk=(jkmax is not None and jkmax<=0.10); g_oos=(isr.sum()>0 and oos.sum()>0)
    g_indep=(corr is None) or abs(corr)<=0.4; g_wf=(pos_periods>=4); g_rob=(min(nets)>0)
    g_plac=(ps["net"]<st["net"])
    passed=sum([g_perm,g_jk,g_oos,g_indep,g_wf,g_rob,g_plac])
    grade="ADOPT(v7並み確度)" if (g_perm and g_jk and g_wf and g_rob and g_plac and g_oos and g_indep) else \
          ("STRONG-LEAD(頑健だが有意水準のみ未達)" if (g_wf and g_rob and g_oos and g_indep and g_plac) else "LEAD")
    print("\n=== 判定(v7と同じ基準) ===")
    print(f"  perm≤0.0083:{g_perm} JK≤0.10:{g_jk} OOS両+:{g_oos} v7相関≤0.4:{g_indep} "
          f"WF≥4/5:{g_wf} 頑健net>0:{g_rob} placebo劣:{g_plac}  → {passed}/7")
    print(f"  >>> E5 グレード: {grade}")
    if grade.startswith("STRONG"):
        print("  解釈: 頑健性・WF・分散・プラセボはv7並みに通るが、Bonferroni/JKの厳格有意水準のみ未達。")
        print("        =『質は高いが統計的確証はデモでのみ埋まる』。docs/29のデモ追検へ。")
    out["verdict"]=dict(gates_passed=f"{passed}/7",grade=grade,
        gates=dict(perm=g_perm,jk=g_jk,oos=g_oos,indep=g_indep,wf=g_wf,robust=g_rob,placebo=g_plac))
    try:
        path=(DAILY_DIR.format(base=DRIVE_BASE)+"/e5_confidence.json") if DRIVE_OK else "research/results/e5_confidence.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("\n保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run_e5_confidence()
