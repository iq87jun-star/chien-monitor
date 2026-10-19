"""
edge4_batch_10y.py — 未検定の構造的に別物の系統を【一括事前登録】して10年検定。

経緯: v7(円月曜LONG)生存。v8/gotobi/TOM(順方向カレンダー)・平均回帰=全て10年で全滅(docs/17,20,21)。
本バッチは「まだ打っていない王道」を一気に検定する。検出力が足りる(フェアに勝負できる)6系統に限定。
薄いネタ(JPY3月=標本~10でBonferroni不可)は試行枠の浪費なので除外。

事前登録6候補(N=6, Bonferroni α=0.05/6=0.0083):
  TS1 TSMOM_YEN  : 時系列モメンタム(トレンド追随)。円3クロス。各月、過去{1,3,6,12}ヶ月リターンの
                   符号の多数決で翌月の方向を決め1ヶ月保有。文献上もっとも頑健なFXエッジ。
  TS2 TSMOM_MAJ  : 同 majors(EURUSD/GBPUSD/AUDUSD/USDCHF/USDCAD)。
  TS3 TSMOM_ALL  : 同 全8ペア。
  XS1 XSMOM_ALL  : 横断モメンタム。毎月、過去12ヶ月で全8ペアを順位付けし上位2をLONG下位2をSHORT、1ヶ月保有。
  DON DONCHIAN_ALL: 55日ブレイクアウト(タートル流トレンド)。終値が55日高値更新でLONG/55日安値でSHORT、
                   反対シグナルまで保有。全8ペア。
  SBR SESSION_BRK_MAJ: セッション窓ブレイクアウト。アジア時間(0-7UTC)レンジを欧州時間(8-20UTC)に
                   上抜けLONG/下抜けSHORT(順方向継続)、当日終値で手仕舞い。majors。
  PLC 各候補に整合プラセボ=同じ機会で「ランダム方向」(方向シグナルが無価値かの帰無)。

ゲート(全て10年・採用は全主要通過):
  G_perm 順列p<=Bonferroni(0.0083) / G_jk JKmax<=0.10 / G_oos IS・OOS両符号 /
  G_indep v7月次相関<=0.4(できれば負) / G_plac プラセボ非有意かつ候補>プラセボ / G_cost 往復1-4pipで+
ADOPT=主要ゲート全通過。1つも無ければ→新規エッジ探索を正式終了、v7一本で確定。

⚠ 日次/月次/セッション終値モデル。スワップ未計上。DD/合格率はユーザー足内エンジンで別途実測。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"

COST_PIP = 2.0
YEN    = ["EURJPY","GBPJPY","USDJPY"]
MAJORS = ["EURUSD","GBPUSD","AUDUSD","USDCHF","USDCAD"]
ALL8   = YEN + MAJORS
LOOKBACKS = [1,3,6,12]   # TSMOMルックバック(月)
DON_N  = 55              # Donchianブレイク窓(日)

if USE_DRIVE:
    try:
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル?):", e); USE_DRIVE=False

def pip(p): return 0.01 if p.endswith("JPY") else 0.0001
def _resolve(pair):
    c=[]
    if USE_DRIVE:
        b=H1_DIR.format(base=DRIVE_BASE); c+=[f"{b}/{pair}_h1.csv", f"{b}/{pair}.csv"]
    c+=[f"{LOCAL_FALLBACK}/{pair}_h1.csv"]
    for x in c:
        if os.path.exists(x): return x
    return None
def load(pair):
    path=_resolve(pair)
    if path is None: return None
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=next((c for c in ["close","bidclose","bid_close","c"] if c in df.columns), None)
    return pd.Series(df[cc].astype(float).values, index=df.index).dropna()

CACHE={}
def H1(p):
    if p not in CACHE: CACHE[p]=load(p)
    return CACHE[p]
def have(p): return H1(p) is not None
def avail(pairs): return [p for p in pairs if have(p)]

def daily_close(pair):
    s=H1(pair);  return None if s is None else s.resample("1D").last().dropna()
def monthly_close(pair):
    d=daily_close(pair)
    if d is None: return None
    m=d.groupby(d.index.to_period("M")).last(); m.index=m.index.to_timestamp("M"); return m

# ---------- 候補シグナル(randomize=Trueで整合プラセボ:同機会・ランダム方向) ----------
def tsmom(pairs, randomize=False, seed=1, costpip=COST_PIP):
    rng=np.random.default_rng(seed); legs=[]
    for pair in avail(pairs):
        m=monthly_close(pair)
        if m is None or len(m)<max(LOOKBACKS)+3: continue
        comp=sum(np.sign(m.pct_change(L)) for L in LOOKBACKS)
        pos=np.sign(comp)                          # -1/0/1 多数決
        nxt=m.pct_change().shift(-1)               # 翌月リターン
        ps=pip(pair); cpr=costpip*ps/m
        for t in m.index[:-1]:
            p0=pos.get(t,0)
            if not np.isfinite(p0) or p0==0: continue
            d=rng.choice([-1,1]) if randomize else p0
            legs.append((t, d*nxt[t]-cpr[t]))
    return _legs(legs)

def xsmom(pairs, randomize=False, seed=2, costpip=COST_PIP, k=2):
    rng=np.random.default_rng(seed); ps=avail(pairs)
    M=pd.concat({p:monthly_close(p) for p in ps if monthly_close(p) is not None},axis=1).dropna(how="all")
    if M.shape[1]<2*k+1 or len(M)<15: return pd.Series(dtype=float)
    R=M.pct_change(); past=M.pct_change(12); nxt=R.shift(-1)
    cost=pd.DataFrame({p:costpip*pip(p)/M[p] for p in M.columns})
    out={}
    for t in M.index[:-1]:
        rk=past.loc[t].dropna()
        if len(rk)<2*k: continue
        if randomize:
            cols=list(rk.index); rng.shuffle(cols); lo,sh=cols[:k],cols[k:2*k]
        else:
            srt=rk.sort_values(); sh=list(srt.index[:k]); lo=list(srt.index[-k:])
        nx=nxt.loc[t]; ct=cost.loc[t]
        r=np.nanmean([nx[c]-ct[c] for c in lo]) - np.nanmean([nx[c]+ct[c] for c in sh])
        if np.isfinite(r): out[t]=r
    return pd.Series(out).sort_index()

def donchian(pairs, randomize=False, seed=3, costpip=COST_PIP, n=DON_N):
    rng=np.random.default_rng(seed); cols=[]
    for pair in avail(pairs):
        d=daily_close(pair)
        if d is None or len(d)<n+10: continue
        hi=d.rolling(n).max().shift(1); lo=d.rolling(n).min().shift(1)
        sig=pd.Series(np.where(d>hi,1.0,np.where(d<lo,-1.0,np.nan)),index=d.index)
        if randomize:  # 同じブレイク時点でランダム方向→ffill
            br=sig.dropna().index
            sig=pd.Series(np.nan,index=d.index); sig.loc[br]=rng.choice([-1,1],size=len(br))
        pos=sig.ffill().fillna(0.0)
        dret=d.pct_change(); ps=pip(pair)
        gross=pos.shift(1)*dret
        cost=pos.diff().abs()*costpip*ps/d
        cols.append((gross-cost).dropna())
    if not cols: return pd.Series(dtype=float)
    return pd.concat(cols,axis=1).mean(axis=1).dropna()

def session_brk(pairs, randomize=False, seed=4, costpip=COST_PIP):
    rng=np.random.default_rng(seed); cols=[]
    for pair in avail(pairs):
        s=H1(pair)
        if s is None: continue
        ps=pip(pair); recs={}
        for day,df in s.groupby(s.index.normalize()):
            asia=df[(df.index.hour>=0)&(df.index.hour<=7)]
            sess=df[(df.index.hour>=8)&(df.index.hour<=20)]
            if len(asia)<3 or len(sess)<2: continue
            ah,al=asia.max(),asia.min(); entry=None;dir_=0
            for t,px in sess.items():
                if px>ah: entry=px;dir_=1;break
                if px<al: entry=px;dir_=-1;break
            if entry is None: continue
            ex=sess.iloc[-1]
            if randomize: dir_=rng.choice([-1,1])
            recs[day]=dir_*(ex/entry-1.0)-costpip*ps/entry
        if recs: cols.append(pd.Series(recs))
    if not cols: return pd.Series(dtype=float)
    return pd.concat(cols,axis=1).mean(axis=1).dropna()

def _legs(legs):
    if not legs: return pd.Series(dtype=float)
    s=pd.Series([v for _,v in legs], index=[t for t,_ in legs])
    return s.groupby(s.index).mean().sort_index()

# ---------- 統計 ----------
def perm_p(r,n=3000,seed=13):
    r=np.asarray(r,float)
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); a=np.abs(r)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)])>=real).mean())
def stats(x):
    x=pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0,win_pct=0,maxDD_pct=0,n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1),win_pct=round((x>0).mean()*100,0),maxDD_pct=round(dd,1),n=int(len(x)))
def jackknife(s):
    yrs=sorted(set(s.index.year))
    if len(yrs)<3: return None
    jk={int(y):round(perm_p(s[s.index.year!=y].values),3) for y in yrs}
    return jk, round(max(jk.values()),3)
def mP(s): return s.groupby(s.index.to_period("M")).sum() if len(s) else pd.Series(dtype=float)

def yen_monday_monthly():
    rows=[]
    for p in YEN:
        if not have(p): continue
        s=H1(p); cv=s.values; idx=s.index; ps=pip(p)
        for hr in (4,6,8,10):
            a=np.where((idx.dayofweek==0)&(idx.hour==hr))[0]; a=a[a+24<len(cv)]
            for i in a: rows.append((idx[i].normalize(), (cv[i+24]-cv[i])/cv[i]-COST_PIP*ps/cv[i]))
    if not rows: return pd.Series(dtype=float)
    s=pd.Series([r for _,r in rows], index=[d for d,_ in rows])
    return s.groupby(s.index.to_period("M")).sum()

CAND={
 "TS1_TSMOM_YEN":    lambda cp=COST_PIP: tsmom(YEN,   costpip=cp),
 "TS2_TSMOM_MAJ":    lambda cp=COST_PIP: tsmom(MAJORS,costpip=cp),
 "TS3_TSMOM_ALL":    lambda cp=COST_PIP: tsmom(ALL8,  costpip=cp),
 "XS1_XSMOM_ALL":    lambda cp=COST_PIP: xsmom(ALL8,  costpip=cp),
 "DON_DONCHIAN_ALL": lambda cp=COST_PIP: donchian(ALL8,costpip=cp),
 "SBR_SESSION_BRK":  lambda cp=COST_PIP: session_brk(MAJORS,costpip=cp),
}
PLAC={
 "TS1_TSMOM_YEN":    lambda: tsmom(YEN,randomize=True),
 "TS2_TSMOM_MAJ":    lambda: tsmom(MAJORS,randomize=True),
 "TS3_TSMOM_ALL":    lambda: tsmom(ALL8,randomize=True),
 "XS1_XSMOM_ALL":    lambda: xsmom(ALL8,randomize=True),
 "DON_DONCHIAN_ALL": lambda: donchian(ALL8,randomize=True),
 "SBR_SESSION_BRK":  lambda: session_brk(MAJORS,randomize=True),
}

def run():
    print("利用可能ペア:", avail(ALL8))
    N=len(CAND); bonf=round(0.05/N,4); ym=yen_monday_monthly()
    out={"meta":dict(n_candidates=N,bonferroni_alpha=bonf,lookbacks=LOOKBACKS,don_n=DON_N,available=avail(ALL8)),"candidates":{}}
    print(f"\n試行数N={N} Bonferroniα={bonf}")
    for name,fn in CAND.items():
        s=fn()
        if len(s)<30:
            out["candidates"][name]=dict(note="insufficient",n=len(s)); print(f"\n{name}: データ不足 n={len(s)}"); continue
        st=stats(s); p=round(perm_p(s.values),4)
        jk=jackknife(s); jkmax=jk[1] if jk else None
        h=s.index[len(s)//2]; isr,oos=s[s.index<h],s[s.index>=h]
        j=pd.concat([mP(s).rename("c"),ym.rename("y")],axis=1).dropna()
        corr=round(float(j["c"].corr(j["y"])),2) if len(j)>12 else None
        plc=PLAC[name](); plc_p=round(perm_p(plc.values),3); plc_net=stats(plc)["net_pct"]
        cost={f"{c}pip":stats(fn(float(c)))["net_pct"] for c in (1,2,3,4)}
        g_perm=p<=bonf; g_jk=(jkmax is not None and jkmax<=0.10)
        g_oos=(isr.sum()>0 and oos.sum()>0); g_indep=(corr is None) or abs(corr)<=0.4
        g_plac=(plc_p>0.05 and st["net_pct"]>plc_net); g_cost=all(v>0 for v in cost.values())
        passed=sum([g_perm,g_jk,g_oos,g_indep,g_plac,g_cost])
        grade="ADOPT" if (g_perm and g_jk and g_oos and g_indep and g_plac) else ("LEAD" if (st["net_pct"]>0 and p<=0.10) else "REJECT")
        out["candidates"][name]=dict(**st,perm_p=p,jackknife_max_p=jkmax,IS_net=stats(isr)["net_pct"],
            OOS_net=stats(oos)["net_pct"],corr_to_v7=corr,placebo_net=plc_net,placebo_p=plc_p,cost=cost,
            gates=dict(perm=g_perm,jk=g_jk,oos=g_oos,indep=g_indep,placebo=g_plac,cost=g_cost),
            gates_passed=f"{passed}/6",grade=grade)
        print(f"\n### {name}  [{grade}] {passed}/6")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} | p={p}(Bonf{bonf}:{g_perm}) JKmax={jkmax}({g_jk})")
        print(f"   IS{stats(isr)['net_pct']}/OOS{stats(oos)['net_pct']}({g_oos}) | v7相関{corr}({g_indep}) | placebo净{plc_net}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")
    adopts=[n for n,r in out["candidates"].items() if r.get("grade")=="ADOPT"]
    leads=[n for n,r in out["candidates"].items() if r.get("grade")=="LEAD"]
    print("\n>>> 10年ADOPT:", adopts if adopts else "なし")
    print(">>> LEAD(要追検):", leads if leads else "なし")
    if not adopts: print(">>> 新規エッジ探索を終了、v7一本で確定。")
    out["adopted"]=adopts; out["leads"]=leads
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/edge4_batch_10y.json") if USE_DRIVE else "research/results/edge4_batch_10y.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
