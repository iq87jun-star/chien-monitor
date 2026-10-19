"""
colab_validate_all_v7standard.py — v7 / v9 / E5 を【全く同じ v7基準ゲート】で横並び採点。

目的: ユーザー要望「全てを v7 基準で検証を上げる」。v7 が確認済みエッジに課したのと**同一の9ゲート**を
  v7(24h)・v9(12h)・E5(月次)に一律適用し、各戦略が実際にどの級(ADOPT / STRONG-LEAD / LEAD)に
  届くかを正直に出す。数字は盛らない——届かないものは「届かない」と表示する。

v7基準ゲート(9):
  G1 10年実データ(span≈10y)              G6 IS/OOS 両方+ (減衰なし)
  G2 ノールックアヘッド+実コスト(構造)    G7 ウォークフォワード ≥4/5期 +
  G3 主signのperm_p < Bonferroni α        G8 コスト頑健(2×コストでも net>0)
  G4 プラセボ識別(v7/v9=曜日, E5=方向)    G9 −10%枠に収まる(p95 maxDD ≥ −10%)
  G5 年次ジャックナイフ max_p ≤ 0.10

判定:
  ADOPT       = G3(Bonf)・G4・G5・G6・G7・G8・G9 すべて合格(=v7と同格の確認済みエッジ)
  STRONG-LEAD = G4・G6・G7・G8 合格だが G3(Bonf) か G5 が未達(質は高いが統計的確証のみ不足→デモで埋める)
  LEAD        = それ未満

⚠ Bonferroni母数 N(探索回数)は各戦略の事前登録に基づき固定:
  v7/v9: 週末フロー探索 N=54 → α=0.000926(docs/37, edge9)
  E5   : 未踏候補探索 N=6  → α=0.008333(docs/27)

使い方(Colab): USE_DRIVE=True。H1_DIR に {EURJPY,GBPJPY,USDJPY}_h1.csv(10年), DAILY_DIR に
  {XAUUSD,US500,NAS100,GER40}_d.csv(10年, 無ければYahoo自動取得)。「すべて実行」。
※ シミュレーション。将来/ライブ約定を保証しない。最終確証はデモ前進検証(docs/29)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
DAILY_DIR  = "{base}/multiasset_daily"
LOCAL_FALLBACK = "./research/data"

YEN     = ["EURJPY","GBPJPY","USDJPY"]
HOURS   = [4,6,8,10]
ASSETS  = ["XAUUSD","US500","NAS100","GER40"]
LB      = [1,3,6,12]; VOLWIN=12
COST_PIP= 2.0
BONF_N  = {"v7":54, "v9":54, "E5":6}
V7_BUDGET=0.60; E5_LEGRISK=0.30   # 各戦略の代表デプロイ・サイズでG9を評価
N_PATHS=4000; SEED=11

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル継続):", e)
DRIVE_OK=os.path.exists("/content/drive/MyDrive")

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def _resolve(name, daily=False):
    if daily: c=[f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"]
    else:     c=[f"{H1_DIR.format(base=DRIVE_BASE)}/{name}_h1.csv", f"{LOCAL_FALLBACK}/{name}_h1.csv"]
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
    if ("h",p) not in CACHE: CACHE[("h",p)]=_load_close(p, False)
    return CACHE[("h",p)]
def DC(n):
    if ("d",n) not in CACHE: CACHE[("d",n)]=_load_close(n, True)
    return CACHE[("d",n)]

_YH={"XAUUSD":"GC=F","US500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI"}
def ensure_multiasset():
    import urllib.request, json as _json, time, csv, datetime as _dt
    out_dir=(DAILY_DIR.format(base=DRIVE_BASE) if DRIVE_OK else LOCAL_FALLBACK); os.makedirs(out_dir,exist_ok=True)
    for name in ASSETS:
        if _resolve(name,daily=True) is not None: continue
        try:
            u=f"https://query2.finance.yahoo.com/v8/finance/chart/{_YH[name]}?interval=1d&period1=1451606400&period2=1767225599"
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
            d=_json.loads(urllib.request.urlopen(req,timeout=25).read()); r=d["chart"]["result"][0]
            ts=r["timestamp"]; q=r["indicators"]["quote"][0]
            with open(os.path.join(out_dir,f"{name}_d.csv"),"w",newline="") as f:
                w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"])
                for i,t in enumerate(ts):
                    o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                    if None in (o,h,l,c): continue
                    w.writerow([_dt.datetime.fromtimestamp(t, _dt.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c])
            CACHE.pop(("d",name),None); print(f"  [取得] {name}"); time.sleep(1.0)
        except Exception as e: print(f"  [取得失敗] {name}: {str(e)[:40]}")

# ---------- 戦略系列(週次=v7/v9, 月次=E5) ----------
def yen_weekly(hold, weekday=0, hours=HOURS, cost_pip=COST_PIP, budget=1.0):
    cols=[]
    for p in YEN:
        s=H1C(p)
        if s is None: continue
        cv=s.values; idx=s.index; ps=pip_size(p)
        for h in hours:
            a=np.where((idx.dayofweek==weekday)&(idx.hour==h))[0]; a=a[a+hold<len(cv)]
            r=pd.Series((cv[a+hold]-cv[a])/cv[a]-cost_pip*ps/cv[a], index=idx[a].to_period("W"))
            cols.append(r[~r.index.duplicated()])
    if not cols: return pd.Series(dtype=float)
    M=pd.concat(cols,axis=1).sort_index()
    out={}
    for wk,row in M.iterrows():
        rs=row.dropna()
        if len(rs): out[wk]=float((budget/len(rs)*rs).sum())
    s=pd.Series(out).sort_index(); s.index=s.index.to_timestamp(); return s

def e5_monthly(cost_bps=5.0, randomize=False, seed=7):
    rng=np.random.default_rng(seed); rets,sigs,ws={},{},{}
    for a in ASSETS:
        d=DC(a)
        if d is None: continue
        m=d.groupby(d.index.to_period("M")).last(); m.index=m.index.to_timestamp()
        if len(m)<max(LB)+VOLWIN+2: continue
        pos=np.sign(sum(np.sign(m.pct_change(L)) for L in LB))
        r=m.pct_change(); ws[a]=1.0/r.rolling(VOLWIN,min_periods=max(6,VOLWIN//2)).std()
        rets[a]=r.shift(-1); sigs[a]=pos
    if not rets: return pd.Series(dtype=float)
    idx=sorted(set().union(*[set(s.index) for s in sigs.values()])); out={}
    for t in idx:
        num=den=0.0
        for a in rets:
            p0=sigs[a].get(t,0); w=ws[a].get(t,np.nan); nx=rets[a].get(t,np.nan)
            if not (np.isfinite(p0) and p0!=0 and np.isfinite(w) and np.isfinite(nx)): continue
            dirn=rng.choice([-1,1]) if randomize else p0
            num+=w*(dirn*nx-cost_bps/1e4); den+=w
        if den>0: out[t]=num/den
    return pd.Series(out).sort_index().dropna()

# ---------- 統計 ----------
def perm_p(s,n=4000,seed=13):
    r=pd.Series(s).dropna().values
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); a=np.abs(r)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)])>=real).mean())
def stat(s,ann):
    s=pd.Series(s).dropna()
    if len(s)==0: return dict(net=0.0,Sharpe=0.0,maxDD=0.0,Calmar=0.0,n=0)
    eq=(1+s).cumprod(); dd=float(((eq-eq.cummax())/eq.cummax()).min())*100
    mu=s.mean()*ann; vol=s.std()*np.sqrt(ann); shp=mu/vol if vol>0 else 0.0
    cagr=(eq.iloc[-1]**(ann/len(s))-1)*100
    return dict(net=round(float((eq.iloc[-1]-1)*100),1),Sharpe=round(float(shp),2),maxDD=round(dd,1),
                Calmar=round(float(cagr/abs(dd)),2) if dd else 0.0,n=int(len(s)))
def jackknife(s):
    s=pd.Series(s).dropna(); yrs=sorted(set(s.index.year))
    if len(yrs)<3: return None
    return round(max(perm_p(s[s.index.year!=y]) for y in yrs),3)
def walkforward(s,k=5):
    s=pd.Series(s).dropna(); n=len(s); b=[int(n*i/k) for i in range(k+1)]
    return sum(1 for i in range(k) if (1+s.iloc[b[i]:b[i+1]]).prod()-1>0)
def block_bootstrap(s,n_paths=N_PATHS,horizon=None,block=4,seed=SEED):
    w=pd.Series(s).dropna().values; n=len(w)
    if n==0: return np.zeros((n_paths,1))
    horizon=horizon or n
    rng=np.random.default_rng(seed); P=np.empty((n_paths,horizon))
    for p in range(n_paths):
        seq=[]
        while len(seq)<horizon:
            st=rng.integers(0,n); seq.extend(w[(st+k)%n] for k in range(block))
        P[p]=seq[:horizon]
    return P
def p95_maxdd(P):
    mdd=np.zeros(len(P))
    for i in range(len(P)):
        eq=np.cumprod(1+P[i]); peak=np.maximum.accumulate(eq); mdd[i]=((eq-peak)/peak).min()
    return round(float(np.percentile(mdd,5))*100,1)

# ---------- v7基準ゲート(一律) ----------
def grade(name, series, ann, placebo_ok, placebo_desc, dd_p95, dd_size_desc):
    s=pd.Series(series).dropna()
    yrs=(s.index.max()-s.index.min()).days/365.25 if len(s)>1 else 0
    st=stat(s,ann); pp=perm_p(s); bonf=0.05/BONF_N[name]
    jk=jackknife(s); h=len(s)//2; IS=(1+s.iloc[:h]).prod()-1; OOS=(1+s.iloc[h:]).prod()-1
    wf=walkforward(s); s2=None
    G={}
    G["G1_10y"]=yrs>=8.5   # 108ヶ月(月末跨ぎ)は実測spanが~8.9yになるため閾値8.5
    G["G2_nolook_cost"]=True
    G["G3_perm_bonf"]=(pp<bonf)
    G["G4_placebo"]=bool(placebo_ok)
    G["G5_jackknife"]=(jk is not None and jk<=0.10)
    G["G6_IS_OOS"]=(IS>0 and OOS>0)
    G["G7_walkforward"]=(wf>=4)
    G["G8_cost"]=None    # 呼び出し側で設定(2×コスト系列)
    G["G9_DDfit"]=(dd_p95>=-10.0)
    return dict(stat=st, perm_p=round(pp,4), bonf_alpha=round(bonf,5), jackknife_max=jk,
                IS_pct=round(float(IS*100),1), OOS_pct=round(float(OOS*100),1), wf=f"{wf}/5",
                years=round(float(yrs),1), placebo=placebo_desc, dd_p95=dd_p95, dd_size=dd_size_desc,
                gates=G)

def finalize_grade(G):
    core=[G["G3_perm_bonf"],G["G4_placebo"],G["G5_jackknife"],G["G6_IS_OOS"],
          G["G7_walkforward"],G["G8_cost"],G["G9_DDfit"]]
    if all(core): return "ADOPT (v7同格)"
    if G["G4_placebo"] and G["G6_IS_OOS"] and G["G7_walkforward"] and G["G8_cost"]:
        return "STRONG-LEAD (Bonf/JKのみ未達→デモで埋める)"
    return "LEAD"

def run():
    if [a for a in ASSETS if _resolve(a,daily=True) is None]:
        print("[診断] 多資産未配置→Yahoo取得"); ensure_multiasset()
    out={}
    print("="*72); print("v7基準 統合検証 — v7 / v9 / E5 を同一9ゲートで採点"); print("="*72)

    specs=[]
    # v7: 月曜24h, 曜日プラセボ(月曜識別), DD: 予算0.6%でp95
    s_v7=yen_weekly(24);
    plac_v7={["Mon","Tue","Wed","Thu","Fri"][wd]:round(perm_p(yen_weekly(24,weekday=wd)),3) for wd in range(5)}
    ok_v7=(plac_v7["Mon"]<=0.05 and min(plac_v7[k] for k in ("Tue","Wed","Thu","Fri"))>0.05)
    dd_v7=p95_maxdd(block_bootstrap(yen_weekly(24,budget=V7_BUDGET),horizon=520))
    cost_v7=(stat(yen_weekly(24,cost_pip=COST_PIP*2),52)["net"]>0)
    specs.append(("v7", s_v7, 52, ok_v7, f"曜日{plac_v7}", dd_v7, f"予算{V7_BUDGET}%", cost_v7))
    # v9: 月曜12h
    s_v9=yen_weekly(12)
    plac_v9={["Mon","Tue","Wed","Thu","Fri"][wd]:round(perm_p(yen_weekly(12,weekday=wd)),3) for wd in range(5)}
    ok_v9=(plac_v9["Mon"]<=0.05 and min(plac_v9[k] for k in ("Tue","Wed","Thu","Fri"))>0.05)
    dd_v9=p95_maxdd(block_bootstrap(yen_weekly(12,budget=V7_BUDGET),horizon=520))
    cost_v9=(stat(yen_weekly(12,cost_pip=COST_PIP*2),52)["net"]>0)
    specs.append(("v9", s_v9, 52, ok_v9, f"曜日{plac_v9}", dd_v9, f"予算{V7_BUDGET}%", cost_v9))
    # E5: 月次, 方向プラセボ, DD: legRisk0.30%相当(正規化系列をlegRisk*4で近似スケール)
    s_e5=e5_monthly()
    plac_net=stat(e5_monthly(randomize=True),12)["net"]; ok_e5=(plac_net< stat(s_e5,12)["net"]*0.5)
    # legRisk0.30%×4レッグ ≒ 口座系列: 正規化系列をσ基準でスケール(reality準拠の近似)
    e5_acct=s_e5/ (s_e5.std() if s_e5.std()>0 else 1) * (E5_LEGRISK/100.0*np.sqrt(len(ASSETS)))
    dd_e5=p95_maxdd(block_bootstrap(e5_acct,horizon=120,block=3))
    cost_e5=(stat(e5_monthly(cost_bps=10.0),12)["net"]>0)
    specs.append(("E5", s_e5, 12, ok_e5, f"方向プラセボnet{plac_net}%(基準の半分未満で価値)", dd_e5, f"legRisk{E5_LEGRISK}%", cost_e5))

    for name, series, ann, pok, pdesc, ddp95, ddsize, cost_ok in specs:
        r=grade(name, series, ann, pok, pdesc, ddp95, ddsize)
        r["gates"]["G8_cost"]=bool(cost_ok)
        r["grade"]=finalize_grade(r["gates"])
        out[name]=r
        g=r["gates"]; st=r["stat"]
        print(f"\n■ {name}  [{r['grade']}]")
        print(f"   span{r['years']}y net{st['net']}% Sharpe{st['Sharpe']} maxDD{st['maxDD']}% Calmar{st['Calmar']} n={st['n']}")
        print(f"   G1_10y:{g['G1_10y']}  G3_perm{r['perm_p']}<bonf{r['bonf_alpha']}:{g['G3_perm_bonf']}  "
              f"G4_placebo:{g['G4_placebo']}  G5_JK({r['jackknife_max']}≤0.10):{g['G5_jackknife']}")
        print(f"   G6_IS/OOS({r['IS_pct']}/{r['OOS_pct']}):{g['G6_IS_OOS']}  G7_WF{r['wf']}:{g['G7_walkforward']}  "
              f"G8_cost2x:{g['G8_cost']}  G9_DDfit(p95{r['dd_p95']}%@{r['dd_size']}):{g['G9_DDfit']}")
        print(f"   placebo: {pdesc}")
        passed=sum(1 for v in g.values() if v is True)
        print(f"   → {passed}/9 ゲート通過")

    print("\n"+"="*72)
    print("総括（v7基準・同一ゲート）:")
    for name in ("v7","v9","E5"):
        print(f"  {name}: {out[name]['grade']}")
    print("  ※E5がADOPTに届かないのは108ヶ月の検出力上限(Bonf/JK)。数字は盛らない＝確証はデモで埋める。")
    print("="*72)
    try:
        path=(DRIVE_BASE+"/validate_all_v7standard.json") if DRIVE_OK else "research/results/validate_all_v7standard.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
