"""
colab_v7_e5_blend_10y.py — v7×E5 合成 vs 既存EA(v7単体) を【10年×10年フェア】で再計算。

背景: docs/30 の比較は重複34ヶ月(v7月次がローカルH1=2.76年の好調期)で、v7の最大DDが異常に
  浅く出ていた。本スクリプトは v7月次を【Drive 10年H1】から、E5月次を【Drive 多資産日足10年】から
  作り、フルの重複期間で §1(質) と §2(同一DD予算の年率) を再計算して決着させる。

データ(あなたのDrive配置・edge2-5/confidenceと同じ):
  ・v7: dukascopy_data_h1/{EURJPY,GBPJPY,USDJPY}_h1.csv (10年, 実bid/ask)
  ・E5: multiasset_daily/{XAUUSD,US500,NAS100,GER40}_d.csv (10年日足)
両方ともローカル(./research/data)にフォールバック(ローカルはH1が2.76年=スモークのみ)。

出力: v7×E5 の質テーブル(CAGR/Sharpe/maxDD/Calmar/勝率/最悪月) + 同一DD予算での年率 +
  月次相関。JSONをDriveに保存。これがdocs/30を10年で確定する版。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
DAILY_DIR  = "{base}/multiasset_daily"
LOCAL_FALLBACK = "./research/data"

PAIRS  = ["EURJPY","GBPJPY","USDJPY"]      # v7
HOURS  = [4,6,8,10]
METALS_IDX = ["XAUUSD","US500","NAS100","GER40"]  # E5
LOOKBACKS = [1,3,6,12]
WEEKLY_RISK = 0.60     # v7週次予算(質比較はスケール不変なので任意。docs既定0.6)
SHOTS = 12
ATR_PERIOD_H1 = 24; CAT_ATR = 2.5; MIN_STOP = 10.0; MAX_STOP = 400.0; MAX_SPREAD = 3.0

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル継続):", e)
DRIVE_OK = os.path.exists("/content/drive/MyDrive")
print(f"[データ] Drive={DRIVE_OK} / H1={H1_DIR.format(base=DRIVE_BASE)} / DAILY={DAILY_DIR.format(base=DRIVE_BASE)}")

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def point_size(p): return 0.001 if p.endswith("JPY") else 0.00001

def _resolve(name, daily=False):
    if daily:
        c=[f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv", f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}.csv",
           f"{LOCAL_FALLBACK}/{name}_d.csv"]
    else:
        c=[f"{H1_DIR.format(base=DRIVE_BASE)}/{name}_h1.csv", f"{H1_DIR.format(base=DRIVE_BASE)}/{name}.csv",
           f"{LOCAL_FALLBACK}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}.csv"]
    for x in c:
        if os.path.exists(x): return x
    return None

def _load_h1(pair):
    path=_resolve(pair, daily=False)
    if path is None: return None
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def pk(*n):
        for x in n:
            if x in df.columns: return x
        return None
    o,h,l,c=pk("open","bidopen","o"),pk("high","bidhigh","h"),pk("low","bidlow","l"),pk("close","bidclose","c")
    out=pd.DataFrame(index=df.index)
    out["open"]=df[o].astype(float); out["high"]=df[h].astype(float)
    out["low"]=df[l].astype(float);  out["close"]=df[c].astype(float)
    ac=pk("askclose","ask_close","ask"); sp=pk("spread")
    if sp: out["spread"]=df[sp].astype(float)
    elif ac: out["spread"]=(df[ac].astype(float)-out["close"]).clip(lower=0)
    else: out["spread"]=1.0*pip_size(pair)
    return out.dropna(subset=["open","high","low","close"])

def _load_close(name):
    path=_resolve(name, daily=True)
    if path is None: return None
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()

CACHE={}
def H1(p):
    if ("h1",p) not in CACHE: CACHE[("h1",p)]=_load_h1(p)
    return CACHE[("h1",p)]
def DCLOSE(n):
    if ("d",n) not in CACHE: CACHE[("d",n)]=_load_close(n)
    return CACHE[("d",n)]

def atr_wilder(h1, period):
    h,l,c=h1["high"],h1["low"],h1["close"]; pc=c.shift(1)
    tr=pd.concat([(h-l),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/period, adjust=False).mean()

# ---------- v7 月次リターン(予算スケール) ----------
def v7_shot_fracs(pair, hour):
    """1ショットのリターン(=equity分数)系列。ret_pips/stop_pips × per_shot_risk。"""
    h1=H1(pair)
    if h1 is None: return pd.Series(dtype=float)
    pip=pip_size(pair); slip=20*point_size(pair)
    T=h1.index.values; O=h1["open"].to_numpy(); L=h1["low"].to_numpy(); C=h1["close"].to_numpy(); S=h1["spread"].to_numpy()
    atr=atr_wilder(h1,ATR_PERIOD_H1); aidx=atr.index.values; aval=atr.to_numpy(); idx=h1.index
    pos=np.where((idx.dayofweek==0)&(idx.hour==hour))[0]
    per_shot=(WEEKLY_RISK/100.0)/SHOTS
    out=[]
    for a in pos:
        ai=int(np.searchsorted(aidx,T[a],side="right"))-1
        if ai<0 or not (aval[ai]==aval[ai]) or aval[ai]<=0: continue
        spread0=S[a] if S[a]==S[a] else pip
        if spread0/pip>MAX_SPREAD: continue
        sd=CAT_ATR*aval[ai]; sp=sd/pip
        if sp<MIN_STOP: sp=MIN_STOP; sd=sp*pip
        if sp>MAX_STOP: continue
        entry=O[a]+spread0/2+slip; sl=entry-sd
        until=T[a]+np.timedelta64(24,"h"); b=int(np.searchsorted(T,until,side="left")); b=max(b,a+1)
        ll=L[a:b]; ss=S[a:b]; ss=np.where(np.isnan(ss),spread0,ss)
        if len(ll)>0 and ((ll-ss/2)<=sl).any(): ex=sl
        else: ex=(O[b]-spread0/2) if b<len(O) else (C[-1]-spread0/2)
        ret_pips=(ex-entry)/pip
        frac=(ret_pips/sp)*per_shot     # stopにサイズを合わせる=損益はret/stop×リスク
        t=pd.Timestamp(T[a]); t=t.tz_localize("UTC") if t.tz is None else t
        out.append((t, frac))
    if not out: return pd.Series(dtype=float)
    return pd.Series([f for _,f in out], index=[t for t,_ in out])

def v7_monthly():
    legs=[]
    for p in PAIRS:
        for hr in HOURS:
            s=v7_shot_fracs(p,hr)
            if len(s): legs.append(s)
    if not legs: return pd.Series(dtype=float)
    alls=pd.concat(legs).sort_index()
    m=alls.groupby(alls.index.to_period("M")).sum(); m.index=m.index.to_timestamp("M")
    return m

# ---------- E5 月次(リスクパリティ多資産トレンド) ----------
def _mclose(name):
    d=DCLOSE(name)
    if d is None: return None
    m=d.groupby(d.index.to_period("M")).last(); m.index=m.index.to_timestamp("M"); return m

def e5_monthly(bps=5.0):
    rets,sigs,ws={},{},{}
    for a in METALS_IDX:
        m=_mclose(a)
        if m is None or len(m)<max(LOOKBACKS)+3: continue
        comp=sum(np.sign(m.pct_change(L)) for L in LOOKBACKS); pos=np.sign(comp)
        r=m.pct_change(); invvol=1.0/r.rolling(12,min_periods=6).std()
        rets[a]=r.shift(-1); sigs[a]=pos; ws[a]=invvol
    if not rets: return pd.Series(dtype=float)
    idx=sorted(set().union(*[set(s.index) for s in sigs.values()])); out={}
    for t in idx:
        num,den=0.0,0.0
        for a in rets:
            p0=sigs[a].get(t,0); w=ws[a].get(t,np.nan); nx=rets[a].get(t,np.nan)
            if not (np.isfinite(p0) and p0!=0 and np.isfinite(w) and np.isfinite(nx)): continue
            num+=w*(p0*nx - bps/1e4); den+=w
        if den>0: out[t]=num/den
    s=pd.Series(out).sort_index().dropna()
    return s   # 既にmonthly index

# ---------- 多資産日足の自動取得(Driveに未配置なら Yahoo から10年取得して配置) ----------
_YH={"XAUUSD":"GC=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}
def ensure_multiasset():
    import urllib.request, json as _json, time, csv, datetime as _dt
    out_dir = (DAILY_DIR.format(base=DRIVE_BASE) if DRIVE_OK else LOCAL_FALLBACK)
    os.makedirs(out_dir, exist_ok=True)
    for name in METALS_IDX:
        if _resolve(name, daily=True) is not None:
            continue
        sym=_YH.get(name)
        if not sym: continue
        try:
            u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&period1=1451606400&period2=1767225599"
            req=urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"})
            d=_json.loads(urllib.request.urlopen(req, timeout=25).read())
            r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
            p=os.path.join(out_dir, f"{name}_d.csv")
            with open(p,"w",newline="") as f:
                w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"])
                for i,t in enumerate(ts):
                    o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                    if None in (o,h,l,c): continue
                    w.writerow([_dt.datetime.fromtimestamp(t, _dt.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c])
            CACHE.pop(("d",name),None)   # 再読込
            print(f"  [取得] {name} <- {sym} → {p}")
            time.sleep(1.0)
        except Exception as e:
            print(f"  [取得失敗] {name} ({sym}): {type(e).__name__} {str(e)[:60]}")

# ---------- 比較指標 ----------
def volmatch(s,t=0.10,ann=12):
    s=pd.Series(s).dropna(); v=s.std()*np.sqrt(ann); return s*(t/v) if v>0 else s
def M(s,ann=12):
    s=pd.Series(s).dropna();
    if len(s)==0: return dict(CAGR=0,vol=0,Sharpe=0,maxDD=0,Calmar=0,win=0,worst=0)
    eq=(1+s).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    mu=s.mean()*ann; vol=s.std()*np.sqrt(ann); shp=mu/vol if vol>0 else 0
    cagr=(eq.iloc[-1]**(ann/len(s))-1)*100; calmar=cagr/abs(dd) if dd!=0 else 0
    return dict(CAGR=round(cagr,1),vol=round(vol*100,1),Sharpe=round(shp,2),maxDD=round(dd,1),
                Calmar=round(calmar,2),win=round((s>0).mean()*100,0),worst=round(s.min()*100,2))

def run():
    # 多資産日足がDriveに無ければ自動取得(E5空の最頻原因)
    miss=[a for a in METALS_IDX if _resolve(a, daily=True) is None]
    if miss:
        print(f"[診断] 多資産日足が未配置: {miss} → Yahooから10年取得を試みます")
        ensure_multiasset()
    # 可用性レポート
    h1ok=[p for p in PAIRS if H1(p) is not None]
    dok =[a for a in METALS_IDX if DCLOSE(a) is not None]
    print(f"[診断] v7用H1={h1ok} / E5用日足={dok}")
    v7=v7_monthly(); e5=e5_monthly()
    print(f"[診断] v7月次={len(v7)}ヶ月 / E5月次={len(e5)}ヶ月")
    if len(v7)==0:
        print("計算不可: v7月次が空 → dukascopy_data_h1 のEURJPY/GBPJPY/USDJPY_h1.csv配置を確認"); return
    if len(e5)==0:
        print("計算不可: E5月次が空 → multiasset_daily の取得/配置に失敗(上の取得ログ確認)"); return
    j=pd.concat([v7.rename("v7"),e5.rename("e5")],axis=1).dropna()
    corr=round(float(j["v7"].corr(j["e5"])),3) if len(j)>2 else None
    span=f"{j.index.min().date()}..{j.index.max().date()} ({len(j)}ヶ月)"
    print(f"\n重複期間: {span} / 月次相関={corr}")
    if len(j)<60: print("⚠ 重複が短い(ローカルH1=2.76年?)=スモーク。10年確定はDriveで。")
    v7n=volmatch(j["v7"]); e5n=volmatch(j["e5"])
    print("\n【A】ボラ10%/年に正規化(質) — 既存EA=v7単体 vs 合成")
    print(f"{'配分 v7:E5':<14}{'CAGR':>7}{'Sharpe':>8}{'maxDD':>8}{'Calmar':>8}{'勝率':>6}{'最悪月':>8}")
    rows={}
    for w in (0.0,0.15,0.25,0.35,0.5):
        m=M((1-w)*v7n+w*e5n); rows[w]=m
        print(f"{('v7:'+str(int((1-w)*100))+'/E5:'+str(int(w*100))):<14}{m['CAGR']:>6}%{m['Sharpe']:>8}{m['maxDD']:>7}%{m['Calmar']:>8}{m['win']:>5}%{m['worst']:>7}%")
    base=rows[0.0]; bdd=abs(base['maxDD'])
    print(f"\n【B】最大DD予算を v7単体({base['maxDD']}%)に揃えた年率 — プロップの肝")
    for w in (0.0,0.25,0.35,0.5):
        m=rows[w]; cagr_eq=m['CAGR']*(bdd/abs(m['maxDD'])) if m['maxDD']!=0 else 0
        print(f"  v7:{int((1-w)*100)}/E5:{int(w*100):<3}  年率(DD同一)={cagr_eq:>6.1f}%  対v7単体={ (cagr_eq/base['CAGR']-1)*100:>+5.0f}%")
    print("\n【C】単体(無正規化)  v7:", M(j["v7"]), "\n               E5(全期間):", M(e5))
    out=dict(span=span,corr=corr,quality={f"E5_{int(w*100)}pct":rows[w] for w in rows},
             v7_solo=M(j["v7"]), e5_full=M(e5), drive=DRIVE_OK)
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/v7_e5_blend_10y.json") if DRIVE_OK else "research/results/v7_e5_blend_10y.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("\n保存:",path)
    except Exception as e: print("保存スキップ:",e)
    print("\n>>> 判定指針: Calmar(=年率/最大DD)が高い方がプロップ有利。【B】が＋なら合成優位、−なら"
          "v7単体優位。34ヶ月では−(v7優位)だった。10年でどう動くかが結論。")
    return out

if __name__=="__main__":
    run()
