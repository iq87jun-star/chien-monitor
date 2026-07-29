"""
colab_e5_reality_10y.py — E5(リスクパリティ多資産トレンド)の【10年・実運用フリクション】再測。

位置づけ:
  `colab_e5_confidence.py` は E5 の7ゲート確度(WF/頑健性/プラセボ/perm/JK/v7相関)を既に検証済みで、
  E5 は STRONG-LEAD(質は高いが Bonferroni/JK の厳格有意水準のみ未達)と判定された。
  だが docs/36・27・31 が繰り返し明記する通り、**指数/金CFDの実スプレッド・スワップ・配当調整は
  バックテスト未計上**(Yahoo指数は配当を含まない『価格指数』)で、**legRisk→口座maxDD→−10%枠適合**の
  マップも運用書で未確定のまま。本スクリプトはその2つの欠落を、EAのサイジング(各レッグを月次P&L σ≒
  legRisk%×equityに揃えるリスクパリティ)を忠実に再現して埋める。

本スクリプトが測るもの:
  R0 データ範囲・銘柄被覆・Yahoo価格指数=配当抜きの明示
  R1 ★CFDキャリー感応: 指数LONG/SHORT・金LONG/SHORT に方向別の月次キャリー(配当受取−金利支払 等)を
       与え、none/base/pess の3シナリオで net/CAGR/maxDD/Sharpe がどれだけ削れるかを定量化。
       (E5は指数ロング寄り→金利>配当で純キャリーがマイナスになりやすい。ここが未計上の本丸。)
  R2 ★legRisk → 口座maxDD/Phase1合格率: legRisk∈{0.30,0.46,0.55,0.75,1.00,1.23}% を、リスクパリティで
       口座月次系列に変換し、10年maxDD と 月次ブロック・ブートストラップで Phase1(+8%/累積-10%)の
       合格率・失格率・中央到達月・p95最悪DDを算出。**各フリクション下で −10%枠に収まる legRisk** を提示。
  R3 配当(トータルリターン)補正の上下界: 価格指数 vs 概算TR(ロング指数月に配当利回りを足し戻し)で
       ヘッドラインnetの誤差幅を挟む(Yahoo価格指数を使うことの誤差を正直に bound)。
  R4 v9(12h)との月次相関: 衛星としてv7/v9と低相関か(ポートフォリオ構築の材料, docs/32)。

判定: 「base フリクション下でも net>0 を保ち、legRisk を下げれば p95 maxDD が −7.5% 内に収まる」なら
  デモ前進検証(docs/29)へ進める縮小サイズが定量化できる。pess で純益消失なら本資金不可。

使い方(Colab): USE_DRIVE=True, DAILY_DIR を {XAUUSD,US500,NAS100,GER40}_d.csv 置き場に。
  v9相関用に dukascopy_data_h1/{EURJPY,GBPJPY,USDJPY}_h1.csv(任意)。未配置はYahoo自動取得・ローカル
  フォールバック。⚠ Yahoo指数は配当抜き=フリクション再測の前提そのもの。実CFD条件は業者で要確認。
※ シミュレーション。将来/ライブ約定を保証しない。数値はJSON直読/単一スカラprintで確認(docs/15)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
DAILY_DIR  = "{base}/multiasset_daily"
LOCAL_FALLBACK = "./research/data"

INDICES    = ["US500","NAS100","GER40"]
GOLD       = "XAUUSD"
ASSETS     = [GOLD] + INDICES
YEN        = ["EURJPY","GBPJPY","USDJPY"]
HOURS      = [4,6,8,10]
LB         = [1,3,6,12]
VOLWIN     = 12
SPREAD_BPS = 5.0                       # 売買コスト(往復, turnover時のみ)
V9_HOLD    = 12                        # v9相関用
LEGRISK_SWEEP = [0.30,0.46,0.55,0.75,1.00,1.23]
DIV_YIELD_ANN = {"US500":1.6,"NAS100":0.8,"GER40":2.5}   # 概算・配当利回り%/年(TR補正・R3用)

# 方向別 年率キャリー%(配当受取は+, 金利・配当支払は−)。実CFDは業者で要確認。
FRICTION = {
  "none": dict(idx_long=0.0, idx_short=0.0, gold_long=0.0, gold_short=0.0),
  "base": dict(idx_long=-3.0, idx_short=-1.5, gold_long=-4.0, gold_short=-1.5),
  "pess": dict(idx_long=-5.0, idx_short=-2.5, gold_long=-5.5, gold_short=-2.5),
}

N_PATHS=6000; MAX_MONTHS=120; BLOCK=3; SEED=11

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル継続):", e)
DRIVE_OK = os.path.exists("/content/drive/MyDrive")

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def _resolve(name, daily=False):
    if daily: c=[f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"]
    else:     c=[f"{H1_DIR.format(base=DRIVE_BASE)}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}_h1.csv"]
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
    for name in ASSETS:
        if _resolve(name,daily=True) is not None: continue
        sym=_YH.get(name)
        if not sym: continue
        try:
            u=f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&period1=1451606400&period2=1767225599"
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
            d=_json.loads(urllib.request.urlopen(req,timeout=25).read())
            r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
            p=os.path.join(out_dir,f"{name}_d.csv")
            with open(p,"w",newline="") as f:
                w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"])
                for i,t in enumerate(ts):
                    o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                    if None in (o,h,l,c): continue
                    w.writerow([_dt.datetime.fromtimestamp(t, _dt.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c])
            CACHE.pop(("d",name),None); print(f"  [取得] {name}<-{sym}"); time.sleep(1.0)
        except Exception as e:
            print(f"  [取得失敗] {name}: {type(e).__name__} {str(e)[:50]}")

def _mclose(name):
    d=DCLOSE(name)
    if d is None: return None
    m=d.groupby(d.index.to_period("M")).last(); m.index=m.index.to_timestamp("M"); return m

# ---------- per-leg 口座%寄与(EAサイジング忠実: 各レッグ月次σ=legRisk%) ----------
def leg_account_returns(asset, legRisk, friction, tr_adjust=False):
    """1レッグの月次・口座%寄与系列。pos=TSMOM符号, σ=trailing月次vol(=ATR(MN1)代理),
       寄与 = (legRisk/100) * (pos*nx + carry - cost) / σ_trailing。"""
    m=_mclose(asset)
    if m is None or len(m)<max(LB)+VOLWIN+2: return None
    comp=sum(np.sign(m.pct_change(L)) for L in LB); pos=np.sign(comp)
    r=m.pct_change(); nx=r.shift(-1)                                   # 翌月リターン(ノールックアヘッド)
    sig=r.rolling(VOLWIN,min_periods=max(6,VOLWIN//2)).std().shift(1)  # サイジング用trailing σ(先読み無し)
    is_gold=(asset==GOLD)
    cl = friction["gold_long"]  if is_gold else friction["idx_long"]
    cs = friction["gold_short"] if is_gold else friction["idx_short"]
    turn=(pos!=pos.shift(1)).astype(float)                            # 建て替え月のみコスト
    out={}
    for t in m.index:
        p0=pos.get(t,0); v=sig.get(t,np.nan); fwd=nx.get(t,np.nan)
        if not (np.isfinite(p0) and p0!=0 and np.isfinite(v) and v>0 and np.isfinite(fwd)): continue
        carry=((cl if p0>0 else cs)/100.0)/12.0
        if tr_adjust and (not is_gold) and p0>0:                       # R3: ロング指数にTR(配当)足し戻し
            carry += (DIV_YIELD_ANN.get(asset,0.0)/100.0)/12.0
        cost=(SPREAD_BPS/1e4)*turn.get(t,0.0)
        out[t]=(legRisk/100.0)*((p0*fwd + carry - cost)/v)
    return pd.Series(out).sort_index()

def e5_account(legRisk=0.55, friction=FRICTION["none"], tr_adjust=False):
    legs=[leg_account_returns(a, legRisk, friction, tr_adjust) for a in ASSETS]
    legs=[s for s in legs if s is not None and len(s)>0]
    if not legs: return pd.Series(dtype=float)
    return pd.concat(legs,axis=1).sum(axis=1).dropna()

def v9_monthly():
    rows=[]
    for p in YEN:
        s=H1C(p)
        if s is None: continue
        cv=s.values; idx=s.index; ps=pip_size(p)
        for hr in HOURS:
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+V9_HOLD<len(cv)]
            for i in a: rows.append((idx[i].normalize(),(cv[i+V9_HOLD]-cv[i])/cv[i]-2.0*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s=pd.Series([r for _,r in rows],index=[d for d,_ in rows])
    mm=s.groupby(s.index.to_period("M")).sum(); mm.index=mm.index.to_timestamp("M"); return mm

# ---------- 統計 / MC ----------
def stat(s,ann=12):
    s=pd.Series(s).dropna()
    if len(s)==0: return dict(net=0.0,CAGR=0.0,Sharpe=0.0,maxDD=0.0,Calmar=0.0,n=0)
    eq=(1+s).cumprod(); dd=float(((eq-eq.cummax())/eq.cummax()).min())*100
    mu=s.mean()*ann; vol=s.std()*np.sqrt(ann); shp=mu/vol if vol>0 else 0.0
    cagr=(eq.iloc[-1]**(ann/len(s))-1)*100
    return dict(net=round(float((eq.iloc[-1]-1)*100),1),CAGR=round(float(cagr),1),
                Sharpe=round(float(shp),2),maxDD=round(dd,1),
                Calmar=round(float(cagr/abs(dd)),2) if dd else 0.0,n=int(len(s)))

def block_bootstrap(monthly,n_paths=N_PATHS,max_m=MAX_MONTHS,block=BLOCK,seed=SEED):
    rng=np.random.default_rng(seed); w=pd.Series(monthly).dropna().values; n=len(w)
    if n==0: return np.zeros((n_paths,max_m))
    P=np.empty((n_paths,max_m))
    for p in range(n_paths):
        seq=[]
        while len(seq)<max_m:
            st=rng.integers(0,n); seq.extend(w[(st+k)%n] for k in range(block))
        P[p]=seq[:max_m]
    return P

def eval_phase1(P,target=0.08,total_dd=0.10):
    """E5は月次→『日次-5%』は月足で判定不能(intradayで別途)。ここでは累積-10%と+8%到達のみ。"""
    n,T=P.shape; pas=np.zeros(n,bool); fail=np.zeros(n,bool); mo=np.full(n,np.nan); mdd=np.zeros(n)
    for i in range(n):
        eq=1.0; peak=1.0; m=0.0
        for t in range(T):
            eq*=(1+P[i,t]); peak=max(peak,eq); dd=(eq-peak)/peak; m=min(m,dd)
            if dd<=-total_dd: fail[i]=True; break
            if eq>=1+target: pas[i]=True; mo[i]=t+1; break
        mdd[i]=m
    return dict(pass_rate=round(float(pas.mean())*100,1), fail_rate=round(float(fail.mean())*100,1),
                timeout_rate=round(float((~pas&~fail).mean())*100,1),
                median_months=(None if np.all(np.isnan(mo)) else round(float(np.nanmedian(mo)),0)),
                p95_maxDD_pct=round(float(np.percentile(mdd,5))*100,1),
                median_maxDD_pct=round(float(np.percentile(mdd,50))*100,1))

def run():
    if [a for a in ASSETS if _resolve(a,daily=True) is None]:
        print("[診断] 多資産日足が未配置 → Yahoo取得"); ensure_multiasset()
    R={}
    base=e5_account(0.55, FRICTION["none"])
    if len(base)<36: print(f"E5月次不足 n={len(base)}"); return
    R["R0_meta"]=dict(span=f"{base.index.min().date()}..{base.index.max().date()}", months=int(len(base)),
        assets=ASSETS, missing=[a for a in ASSETS if _mclose(a) is None],
        note="Yahoo指数=配当抜き価格指数。R1キャリー/R3 TR補正で誤差を挟む。実CFD条件は業者確認")
    print(f"=== E5 実運用フリクション再測 | {R['R0_meta']['span']} | {R['R0_meta']['months']}ヶ月 ===")
    print(f"  assets={ASSETS} 欠損={R['R0_meta']['missing']}  (Yahoo指数=配当抜き)")

    # R1 キャリー感応(legRisk0.55固定)
    print("\n=== R1 CFDキャリー感応(legRisk0.55%/月・方向別 年率キャリー) ===")
    r1={}
    for name,fr in FRICTION.items():
        s=e5_account(0.55, fr); st=stat(s); r1[name]=dict(**st,friction=fr)
        print(f"  {name:5s}: net{st['net']:>7}% CAGR{st['CAGR']:>5}% maxDD{st['maxDD']:>6}% "
              f"Sharpe{st['Sharpe']:>5} Calmar{st['Calmar']:>5}  carry(idxL/idxS/goldL/goldS)="
              f"{fr['idx_long']}/{fr['idx_short']}/{fr['gold_long']}/{fr['gold_short']}")
    R["R1_friction"]=r1
    base_net=r1["none"]["net"]; surv=r1["base"]["net"]>0 and r1["pess"]["net"]>0
    print(f"  → エッジ生存(base&pess共にnet>0): {surv}  (nonenet{base_net}% → base{r1['base']['net']}% → pess{r1['pess']['net']}%)")

    # R2 legRisk → maxDD / Phase1(各フリクション)
    print("\n=== R2 legRisk → 口座maxDD / Phase1合格率(累積-10%/+8%) ===")
    r2={}
    for name in ("none","base","pess"):
        fr=FRICTION[name]; tbl={}
        for lr in LEGRISK_SWEEP:
            s=e5_account(lr, fr); hist=stat(s); mc=eval_phase1(block_bootstrap(s))
            tbl[f"{lr:.2f}"]=dict(hist_net=hist["net"], hist_maxDD=hist["maxDD"], **mc)
        r2[name]=tbl
        # −10%枠(p95DD>=-7.5 安全マージン)に収まる最大legRisk
        ok=[k for k,v in tbl.items() if v["p95_maxDD_pct"]>=-7.5 and v["fail_rate"]<=5.0]
        safe=max(ok,key=lambda k:float(k)) if ok else None
        print(f"  [{name}] " + " | ".join(
            f"lr{k}:DD{v['hist_maxDD']}%/p95{v['p95_maxDD_pct']}%/pass{v['pass_rate']}%" for k,v in tbl.items()))
        print(f"     → −10%枠に安全(p95≥-7.5%, 失格≤5%)な最大legRisk = {safe}")
        r2[name+"_safe_legRisk"]=safe
    R["R2_legrisk"]=r2

    # R3 配当TR補正の上下界(legRisk0.55, baseフリクション)
    s_price=e5_account(0.55, FRICTION["base"], tr_adjust=False)
    s_tr   =e5_account(0.55, FRICTION["base"], tr_adjust=True)
    R["R3_TR_bound"]=dict(price_index_net=stat(s_price)["net"], tr_adjusted_net=stat(s_tr)["net"],
        note="価格指数(配当抜き) vs TR概算(ロング指数月に配当足し戻し)。真値はこの間")
    print(f"\n=== R3 配当TR補正(base下) ===\n  価格指数net{R['R3_TR_bound']['price_index_net']}% .. TR概算net{R['R3_TR_bound']['tr_adjusted_net']}% (真値はこの間)")

    # R4 v9相関(月次)
    ym=v9_monthly()
    if len(ym)>12:
        jj=pd.concat([e5_account(0.55,FRICTION["base"]).rename("e5"), ym.rename("v9")],axis=1).dropna()
        corr=round(float(jj["e5"].corr(jj["v9"])),3) if len(jj)>12 else None
    else: corr=None
    R["R4_corr_v9_monthly"]=corr
    print(f"\n=== R4 v9(12h)との月次相関 = {corr} (低いほど衛星として分散に有効) ===")

    # 判定
    safe_base=r2.get("base_safe_legRisk")
    verdict=("base下でエッジ生存＋安全legRiskあり → 縮小サイズでデモ前進検証可"
             if (surv and safe_base) else
             "pessで純益消失 or 安全legRisk無し → 本資金不可・要再設計/デモ厳守")
    R["verdict"]=dict(edge_survives_friction=bool(surv), base_safe_legRisk=safe_base, summary=verdict)
    print(f"\n>>> 判定: {verdict}")
    print("    ※Yahoo指数=配当抜き。実CFDのスワップ/配当/ロールは業者で確認しデモ実測すること。")
    try:
        path=(DAILY_DIR.format(base=DRIVE_BASE)+"/e5_reality_10y.json") if DRIVE_OK else "research/results/e5_reality_10y.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(R,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return R

if __name__=="__main__":
    run()
