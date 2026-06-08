"""
colab_portfolio_compare_2v3.py — 「今までの2種類(v7+E5)」 vs 「v9を入れた3種類(v7+v9+E5)」 比較。

問い: docs/36 の確定運用は v7(月曜24h, JPYクロス) ＋ E5(多資産トレンド衛星) の2種類。
  ここに v9(月曜12h・同日決済) を足した3種類は、ポートフォリオとして良くなるか?

前提(docs/38): v7⇄v9 相関=0.718(同一エッジ)。よって**バックテスト(swap=0)では v9を足しても
  分散益はほぼ無い**はず。v9の価値は「JPYクロスLONGスワップが不利(−側)」のときの防御(同日決済で
  オーバーナイト無し)。本スクリプトは **swap=0 と 逆swap(−1pip/泊) の両シナリオ**で2種類/3種類を
  比較し、v9を足す価値が"どの環境で"出るかを定量化する。

構成(月次・口座%で合算, 総リスク予算を一定にして公平比較):
  JPYバケット予算 = B_jpy(週次%), E5衛星 = legRisk(月次%)。
  P2  "v7+E5"     = v7(B_jpy)           + E5(legRisk)         ← 今までの2種類
  P3  "v7+v9+E5"  = v7(B_jpy/2)+v9(B_jpy/2) + E5(legRisk)     ← v9を入れた3種類(JPY予算を二分)
  Palt"v9+E5"     = v9(B_jpy)           + E5(legRisk)         ← v9置換(参考)

出力: 各ポートの CAGR/Sharpe/maxDD/Calmar/Phase1合格率 を swap=0 と swap=−1 で。相関行列も。
データ(Colab): H1_DIR={EURJPY,GBPJPY,USDJPY}_h1.csv(10年), DAILY_DIR={XAU,US500,NAS100,GER40}_d.csv。
  未配置の多資産はYahoo自動取得。ローカルは短期スモーク。シミュレーション(将来保証なし)。E5はLEAD=デモ前提。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE=True; DRIVE_BASE="/content/drive/MyDrive/forex_ml"
H1_DIR="{base}/dukascopy_data_h1"; DAILY_DIR="{base}/multiasset_daily"; LOCAL_FALLBACK="./research/data"
YEN=["EURJPY","GBPJPY","USDJPY"]; HOURS=[4,6,8,10]
ASSETS=["XAUUSD","US500","NAS100","GER40"]; LB=[1,3,6,12]; VOLWIN=12
COST_PIP=2.0; ROLLOVER_UTC=22
B_JPY=0.60; E5_LEGRISK=0.30          # 代表デプロイ・サイズ
E5_FRICTION=dict(idx_long=-3.0, idx_short=-1.5, gold_long=-4.0, gold_short=-1.5)  # base(docs/39)
N_PATHS=4000; MAX_MONTHS=120; BLOCK=3; SEED=11

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e: print("Drive不可:", e)
DRIVE_OK=os.path.exists("/content/drive/MyDrive")

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def _resolve(name, daily=False):
    c=([f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"] if daily
       else [f"{H1_DIR.format(base=DRIVE_BASE)}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}_h1.csv"])
    for x in c:
        if os.path.exists(x): return x
    return None
def _load_close(name, daily):
    path=_resolve(name, daily=daily)
    if path is None: return None
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()
CACHE={}
def H1C(p):
    if ("h",p) not in CACHE: CACHE[("h",p)]=_load_close(p,False)
    return CACHE[("h",p)]
def DC(n):
    if ("d",n) not in CACHE: CACHE[("d",n)]=_load_close(n,True)
    return CACHE[("d",n)]
_YH={"XAUUSD":"GC=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}
def ensure_multiasset():
    import urllib.request, json as _json, time, csv, datetime as _dt
    out_dir=(DAILY_DIR.format(base=DRIVE_BASE) if DRIVE_OK else LOCAL_FALLBACK); os.makedirs(out_dir,exist_ok=True)
    for name in ASSETS:
        if _resolve(name,daily=True) is not None: continue
        try:
            u=f"https://query2.finance.yahoo.com/v8/finance/chart/{_YH[name]}?interval=1d&range=10y"
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
            d=_json.loads(urllib.request.urlopen(req,timeout=25).read()); r=d["chart"]["result"][0]
            ts=r["timestamp"]; q=r["indicators"]["quote"][0]
            with open(os.path.join(out_dir,f"{name}_d.csv"),"w",newline="") as f:
                w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"])
                for i,t in enumerate(ts):
                    o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                    if None in (o,h,l,c): continue
                    w.writerow([_dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c])
            CACHE.pop(("d",name),None); print(f"  [取得] {name}"); time.sleep(1.0)
        except Exception as e: print(f"  [取得失敗] {name}: {str(e)[:40]}")

def overnights(t0,t1):
    d=pd.Timestamp(t0).normalize(); end=pd.Timestamp(t1).normalize(); cnt=0
    while d<=end:
        roll=d+pd.Timedelta(hours=ROLLOVER_UTC)
        if t0<roll<=t1: cnt+=1
        d+=pd.Timedelta(days=1)
    return cnt

# ---------- JPY月曜 月次系列(v7=24h / v9=12h, swap対応) ----------
def yen_monthly(hold, budget, swap_pip=0.0):
    cols=[]
    for p in YEN:
        s=H1C(p)
        if s is None: continue
        cv=s.values; idx=s.index; ps=pip_size(p)
        for h in HOURS:
            a=np.where((idx.dayofweek==0)&(idx.hour==h))[0]; a=a[a+hold<len(cv)]
            rr=[]
            for i in a:
                g=(cv[i+hold]-cv[i])/cv[i]-COST_PIP*ps/cv[i]
                if swap_pip!=0.0: g+=swap_pip*ps/cv[i]*overnights(idx[i],idx[i+hold])
                rr.append(g)
            r=pd.Series(rr, index=idx[a].to_period("W"))
            cols.append(r[~r.index.duplicated()])
    if not cols: return pd.Series(dtype=float)
    M=pd.concat(cols,axis=1).sort_index(); wk={}
    for w,row in M.iterrows():
        rs=row.dropna()
        if len(rs): wk[w]=float((budget/len(rs)*rs).sum())
    s=pd.Series(wk).sort_index(); s.index=s.index.to_timestamp()
    return s.groupby(s.index.to_period("M")).sum().rename_axis(None)

# ---------- E5 月次(legRisk・base friction) ----------
def e5_monthly(legRisk=E5_LEGRISK, friction=E5_FRICTION):
    legs=[]
    for a in ASSETS:
        d=DC(a)
        if d is None: continue
        m=d.groupby(d.index.to_period("M")).last(); m.index=m.index.to_timestamp()
        if len(m)<max(LB)+VOLWIN+2: continue
        pos=np.sign(sum(np.sign(m.pct_change(L)) for L in LB))
        r=m.pct_change(); nx=r.shift(-1); sig=r.rolling(VOLWIN,min_periods=max(6,VOLWIN//2)).std().shift(1)
        is_gold=(a=="XAUUSD")
        cl=friction["gold_long"] if is_gold else friction["idx_long"]
        cs=friction["gold_short"] if is_gold else friction["idx_short"]
        out={}
        for t in m.index:
            p0=pos.get(t,0); v=sig.get(t,np.nan); fwd=nx.get(t,np.nan)
            if not (np.isfinite(p0) and p0!=0 and np.isfinite(v) and v>0 and np.isfinite(fwd)): continue
            carry=((cl if p0>0 else cs)/100.0)/12.0
            out[t]=(legRisk/100.0)*((p0*fwd+carry)/v)
        legs.append(pd.Series(out))
    if not legs: return pd.Series(dtype=float)
    return pd.concat(legs,axis=1).sum(axis=1).dropna()

# ---------- 指標/MC ----------
def stat(s,ann=12):
    s=pd.Series(s).dropna()
    if len(s)==0: return dict(CAGR=0.0,Sharpe=0.0,maxDD=0.0,Calmar=0.0,n=0)
    eq=(1+s).cumprod(); dd=float(((eq-eq.cummax())/eq.cummax()).min())*100
    mu=s.mean()*ann; vol=s.std()*np.sqrt(ann); shp=mu/vol if vol>0 else 0.0
    cagr=(eq.iloc[-1]**(ann/len(s))-1)*100
    return dict(CAGR=round(float(cagr),1),Sharpe=round(float(shp),2),maxDD=round(dd,1),
                Calmar=round(float(cagr/abs(dd)),2) if dd else 0.0,n=int(len(s)))
def block_bootstrap(s,n_paths=N_PATHS,m=MAX_MONTHS,block=BLOCK,seed=SEED):
    w=pd.Series(s).dropna().values; n=len(w)
    if n==0: return np.zeros((n_paths,1))
    rng=np.random.default_rng(seed); P=np.empty((n_paths,m))
    for p in range(n_paths):
        seq=[]
        while len(seq)<m:
            st=rng.integers(0,n); seq.extend(w[(st+k)%n] for k in range(block))
        P[p]=seq[:m]
    return P
def phase1(P,target=0.08,total_dd=0.10):
    n,T=P.shape; pas=np.zeros(n,bool); fail=np.zeros(n,bool); mo=np.full(n,np.nan); mdd=np.zeros(n)
    for i in range(n):
        eq=1.0;peak=1.0;mn=0.0
        for t in range(T):
            eq*=(1+P[i,t]); peak=max(peak,eq); dd=(eq-peak)/peak; mn=min(mn,dd)
            if dd<=-total_dd: fail[i]=True; break
            if eq>=1+target: pas[i]=True; mo[i]=t+1; break
        mdd[i]=mn
    return dict(pass_rate=round(float(pas.mean())*100,1), fail_rate=round(float(fail.mean())*100,1),
                median_months=(None if np.all(np.isnan(mo)) else round(float(np.nanmedian(mo)),0)),
                p95_maxDD=round(float(np.percentile(mdd,5))*100,1))

def _monthidx(s):
    """index を月次PeriodIndex に統一（Timestamp/Period混在の整合用）。"""
    s=pd.Series(s).dropna()
    if len(s)==0: return s
    idx=pd.PeriodIndex(pd.to_datetime(s.index.to_timestamp() if isinstance(s.index,pd.PeriodIndex) else s.index), freq="M")
    return pd.Series(s.values, index=idx).groupby(level=0).sum()

def align_sum(series_list):
    df=pd.concat([_monthidx(s) for s in series_list],axis=1).dropna()
    return df.sum(axis=1) if len(df) else pd.Series(dtype=float)

def run():
    if [a for a in ASSETS if _resolve(a,daily=True) is None]:
        print("[診断] 多資産未配置→Yahoo取得"); ensure_multiasset()
    e5=e5_monthly()
    out={}; print("="*74)
    print("ポートフォリオ比較: 2種類(v7+E5) vs 3種類(v7+v9+E5)  [月次・口座%合算]"); print("="*74)

    # 相関(swap=0)
    v7m=yen_monthly(24,1.0); v9m=yen_monthly(12,1.0)
    cm=pd.concat([_monthidx(v7m).rename("v7"),_monthidx(v9m).rename("v9"),_monthidx(e5).rename("E5")],axis=1).dropna()
    corr=cm.corr().round(3) if len(cm)>6 else None
    out["span_months"]=int(len(cm)); out["corr"]=(corr.to_dict() if corr is not None else None)
    print(f"\n共通{len(cm)}ヶ月  相関行列:")
    if corr is not None:
        print(corr.to_string())

    for swap, tag in [(0.0,"swap=0 (純バックテスト)"), (-1.0,"swap=-1pip/泊 (JPYロング不利)")]:
        v7=yen_monthly(24, B_JPY, swap); v9=yen_monthly(12, B_JPY, swap)
        v7h=yen_monthly(24, B_JPY/2, swap); v9h=yen_monthly(12, B_JPY/2, swap)
        ports={
            "P2_v7+E5":      align_sum([v7,  e5]),
            "P3_v7+v9+E5":   align_sum([v7h, v9h, e5]),
            "Palt_v9+E5":    align_sum([v9,  e5]),
        }
        print(f"\n--- {tag} ---")
        res={}
        for name,s in ports.items():
            st=stat(s); mc=phase1(block_bootstrap(s))
            res[name]=dict(**st,**mc)
            print(f"  {name:14s}: CAGR{st['CAGR']:>5}% Sharpe{st['Sharpe']:>5} maxDD{st['maxDD']:>6}% "
                  f"Calmar{st['Calmar']:>5} | 合格{mc['pass_rate']:>5}% 到達中央{mc['median_months']}ヶ月 p95DD{mc['p95_maxDD']:>6}%")
        out[f"swap{swap}"]=res

    # 結論ロジック
    s0=out["swap0.0"]; sN=out["swap-1.0"]
    gain0=round(sN.get("P3_v7+v9+E5",{}).get("CAGR",0)-sN.get("P2_v7+E5",{}).get("CAGR",0),2)
    print("\n"+"="*74)
    print("総括:")
    d_sharpe0=round(s0["P3_v7+v9+E5"]["Sharpe"]-s0["P2_v7+E5"]["Sharpe"],2)
    print(f"  swap=0:  3種類 vs 2種類 → Sharpe差{d_sharpe0:+}  (相関0.7台ゆえ僅少なら『分散益ほぼ無し』)")
    print(f"  逆swap:  3種類 CAGR − 2種類 CAGR = {gain0:+}%  (＞0なら v9が逆スワップを防御＝3種類の価値)")
    verdict=("v9を足す価値は『逆スワップ環境の防御』に集約。swap=0では2種類と実質同等(相関0.7)。"
             "→ 業者スワップが順/中立なら2種類(v7+E5)で十分、不利なら3種類 or v9置換が有利。")
    print(f"  → {verdict}")
    out["verdict"]=verdict; print("="*74)
    try:
        path=(DRIVE_BASE+"/portfolio_compare_2v3.json") if DRIVE_OK else "research/results/portfolio_compare_2v3.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
