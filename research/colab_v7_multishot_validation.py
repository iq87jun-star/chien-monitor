"""
colab_v7_multishot_validation.py — v7 マルチショット・ポートフォリオの【10年H1】追認。

位置づけ: committed 2.8年H1で設計・実測した v7(月曜 04/06/08/10 UTC × 3円クロス =
週12ショット、総リスク予算配分)を、ユーザーの Colab 環境(実10年H1, 実bid/ask 可)で
追認する自己完結スクリプト。docs/16 の主張を10年で再現できるかを検定する。

確認する核心(2.8年で見えた「数を打つ効果」が10年でも残るか):
  V1 ショット間相関 < 1(同ペア別時刻 / ペア間)→ 分散の前提
  V2 週次シャープ: 12ショット > 単一ショット平均(分散でSR改善)
  V3 同レバ比較: v7(12shot) が v6(3shot) を【リターン↑ かつ 最悪DD↓】で支配
  V4 リスク予算 sweep → 最悪側DD(p95)を-7.5%内に保ち合格率最大の予算
  V5 Phase1 / Phase1+2 連続 合格率(ブロック・ブートストラップMC)
  V6 曜日プラセボ(月曜のみ)/ 時刻帯(04-10で生存, 13で消滅)= エッジ自体の健全性再確認

全て10年で再現 → v7 を本命EAとしてデモ前進検証へ。崩れたら予算を下げる/ショットを絞る。

使い方(Colab):
  USE_DRIVE=True, DRIVE_BASE / H1_DIR を {PAIR}_h1.csv 置き場に合わせる。
  必要ペア: EURJPY GBPJPY USDJPY(H1, UTC, close必須)。
※ シミュレーション。MCはブートストラップでエッジ持続が前提。将来/ライブ約定は保証しない。
  数値は表示破損を避け JSON直読 or 単一スカラ marker で確認すること。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

# === ユーザー設定(Colabで編集) ===
USE_DRIVE      = True
DRIVE_BASE     = "/content/drive/MyDrive/forex_ml"
H1_DIR         = "{base}/dukascopy_data_h1"      # {PAIR}_h1.csv
LOCAL_FALLBACK = "./research/data"               # ローカル(2.8年)フォールバック

PAIRS   = ["EURJPY", "GBPJPY", "USDJPY"]
HOURS   = [4, 6, 8, 10]
PIP     = 0.01
COST_PIP= 2.0
HOLD    = 24
WEEKDAY = 0
CHOSEN_LEV = 1.5                                 # docs/16採用(保守なら0.75-1.0)
N_PATHS = 4000
MAX_WEEKS = 520                                  # 10年=時間無制限の上限
BLOCK = 4

if USE_DRIVE:
    try:
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive マウント不可(ローカル?):", e); USE_DRIVE=False

def _resolve(pair):
    c=[]
    if USE_DRIVE:
        b=H1_DIR.format(base=DRIVE_BASE); c+=[f"{b}/{pair}_h1.csv", f"{b}/{pair}.csv"]
    c+=[f"{LOCAL_FALLBACK}/{pair}_h1.csv"]
    for x in c:
        if os.path.exists(x): return x
    raise FileNotFoundError(f"{pair}: H1 CSV見つからず {c}")

def load(pair):
    df=pd.read_csv(_resolve(pair))
    tcol=None
    for cand in ("time","timestamp","date","datetime","gmt time"):
        m=[c for c in df.columns if c.lower()==cand]
        if m: tcol=m[0]; break
    if tcol is None: tcol=df.columns[0]
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cc=None
    for n in ("close","bidclose","bid_close","c"):
        for c in df.columns:
            if c.lower()==n: cc=c; break
        if cc: break
    out=pd.DataFrame(index=df.index); out["close"]=df[cc].astype(float)
    return out.dropna()

CACHE={p:load(p) for p in PAIRS}

def shot_returns(pair, hour):
    df=CACHE[pair]; cv=df["close"].values; idx=df.index
    a=np.where((idx.dayofweek==WEEKDAY)&(idx.hour==hour))[0]; a=a[a+HOLD<len(cv)]
    s=pd.Series((cv[a+HOLD]-cv[a])/cv[a]-COST_PIP*PIP/cv[a], index=idx[a])
    s.index=s.index.to_period("W"); return s[~s.index.duplicated()]

def build_matrix(pairs, hours):
    return pd.DataFrame({f"{p}_{h:02d}":shot_returns(p,h) for p in pairs for h in hours}).sort_index()

def weekly_portfolio(M, total_weekly_lev):
    out={}
    for wk,row in M.iterrows():
        rs=row.dropna()
        if len(rs)==0: continue
        out[wk]=float((total_weekly_lev/len(rs)*rs).sum())
    return pd.Series(out).sort_index()

def sharpe(s):
    s=pd.Series(s).dropna(); return round(float(s.mean()/s.std()*np.sqrt(52)),2) if s.std()>0 else 0.0
def net_pct(s): return round(float(((1+pd.Series(s).dropna()).prod()-1)*100),1)

def perm_p(r,n_iter=4000,seed=7):
    r=np.asarray(r,float)
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); s=np.abs(r)
    return float((np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n_iter)])>=real).mean())

def block_bootstrap(weekly,n_paths=N_PATHS,max_weeks=MAX_WEEKS,block=BLOCK,seed=11):
    rng=np.random.default_rng(seed); w=weekly.values; n=len(w)
    P=np.empty((n_paths,max_weeks))
    for p in range(n_paths):
        seq=[]
        while len(seq)<max_weeks:
            st=rng.integers(0,n); seq.extend(w[(st+k)%n] for k in range(block))
        P[p]=seq[:max_weeks]
    return P

def eval_challenge(P,target=0.08,total_dd=0.10,daily_dd=0.05):
    n,T=P.shape; pas=np.zeros(n,bool); fail=np.zeros(n,bool); wks=np.full(n,np.nan); mdd=np.zeros(n)
    for i in range(n):
        eq=1.0; peak=1.0; m=0.0
        for t in range(T):
            eq*=(1+P[i,t])
            if P[i,t]<=-daily_dd: fail[i]=True; break
            peak=max(peak,eq); dd=(eq-peak)/peak; m=min(m,dd)
            if dd<=-total_dd: fail[i]=True; break
            if eq>=1+target: pas[i]=True; wks[i]=t+1; break
        mdd[i]=m
    return dict(pass_rate=round(pas.mean()*100,1), fail_rate=round(fail.mean()*100,1),
                timeout_rate=round((~pas&~fail).mean()*100,1),
                median_weeks=(None if np.all(np.isnan(wks)) else round(float(np.nanmedian(wks)),0)),
                p95_maxDD_pct=round(float(np.percentile(mdd,5))*100,1),
                median_maxDD_pct=round(float(np.percentile(mdd,50))*100,1))

def run():
    R={}
    M=build_matrix(PAIRS,HOURS)
    R["span"]=dict(weeks=int(M.shape[0]), shots=int(M.shape[1]),
                   first=str(M.index.min()), last=str(M.index.max()))
    # V1 相関
    cc=M.corr(); cols=list(M.columns); sp=[]; xp=[]
    for i in range(len(cols)):
        for j in range(i+1,len(cols)):
            v=cc.values[i,j]
            if np.isnan(v): continue
            (sp if cols[i][:6]==cols[j][:6] else xp).append(v)
    R["V1_corr"]=dict(same_pair_diff_hour=round(float(np.mean(sp)),2),
                      cross_pair=round(float(np.mean(xp)),2),
                      mean=round(float(np.nanmean(cc.values[np.triu_indices(len(cols),1)])),2))
    # V2 シャープ
    per=[sharpe(M[c]) for c in M.columns]
    R["V2_sharpe"]=dict(single_mean=round(float(np.mean(per)),2),
                        portfolio_12shot=sharpe(weekly_portfolio(M,1.0)))
    # V3 同レバ比較 v7 vs v6
    M3=build_matrix(PAIRS,[8])
    w12=weekly_portfolio(M,CHOSEN_LEV); w3=weekly_portfolio(M3,CHOSEN_LEV)
    p12=eval_challenge(block_bootstrap(w12)); p3=eval_challenge(block_bootstrap(w3))
    R["V3_same_leverage_compare"]=dict(
        v7_12shot=dict(net_pct=net_pct(w12), sharpe=sharpe(w12),
                       worstDD_p95=p12["p95_maxDD_pct"], pass_rate=p12["pass_rate"]),
        v6_3shot =dict(net_pct=net_pct(w3),  sharpe=sharpe(w3),
                       worstDD_p95=p3["p95_maxDD_pct"], pass_rate=p3["pass_rate"]))
    # V4 sweep
    sw={}
    for lev in [0.5,0.75,1.0,1.5,2.0,2.5,3.0]:
        w=weekly_portfolio(M,lev)
        sw[f"{lev:.2f}"]=dict(**eval_challenge(block_bootstrap(w)), net_pct=net_pct(w))
    R["V4_risk_sweep"]=sw
    cand=[(k,v) for k,v in sw.items() if v["p95_maxDD_pct"]>=-7.5 and v["fail_rate"]<=2.0] or list(sw.items())
    bk,bv=max(cand,key=lambda kv:(kv[1]["pass_rate"], -(kv[1]["median_weeks"] or 9e9)))
    R["V4_chosen_lev"]=bk; R["V4_chosen"]=bv
    # V5 二段連続
    wb=weekly_portfolio(M,float(bk))
    p1=eval_challenge(block_bootstrap(wb),target=0.08)
    p2=eval_challenge(block_bootstrap(wb,seed=99),target=0.05)
    R["V5_two_phase"]=dict(phase1=p1,phase2=p2,combined_pct=round(p1["pass_rate"]*p2["pass_rate"]/100,1))
    # V6 エッジ健全性(プール=各時刻平均の月曜 vs 他曜日 / 時刻帯)
    def pool_wd(wd,hours=HOURS):
        cols=[]
        for p in PAIRS:
            df=CACHE[p]; cv=df["close"].values; idx=df.index
            for h in hours:
                a=np.where((idx.dayofweek==wd)&(idx.hour==h))[0]; a=a[a+HOLD<len(cv)]
                s=pd.Series((cv[a+HOLD]-cv[a])/cv[a]-COST_PIP*PIP/cv[a],index=idx[a].to_period("W"))
                cols.append(s[~s.index.duplicated()])
        return pd.concat(cols,axis=1).mean(axis=1).dropna()
    R["V6_weekday_placebo"]={["Mon","Tue","Wed","Thu","Fri"][wd]:round(perm_p(pool_wd(wd).values),3) for wd in range(5)}
    R["V6_hour_band"]={h:round(perm_p(pool_wd(0,[h]).values),3) for h in (4,6,8,10,13)}
    return R

if __name__=="__main__":
    R=run()
    print("=== v7 マルチショット 10年追認(週12ショット, 総レバ予算配分) ===")
    print("span:",R["span"])
    print("V1 相関  同ペア別時刻",R["V1_corr"]["same_pair_diff_hour"],"/ ペア間",R["V1_corr"]["cross_pair"],"(<1で分散効く)")
    print("V2 シャープ 単一平均",R["V2_sharpe"]["single_mean"],"→ 12ショット",R["V2_sharpe"]["portfolio_12shot"])
    v=R["V3_same_leverage_compare"]
    print(f"V3 同レバ比較  v7: net{v['v7_12shot']['net_pct']}% DD{v['v7_12shot']['worstDD_p95']}% SR{v['v7_12shot']['sharpe']}"
          f"  |  v6: net{v['v6_3shot']['net_pct']}% DD{v['v6_3shot']['worstDD_p95']}% SR{v['v6_3shot']['sharpe']}")
    print("V4 sweep:",{k:(x["pass_rate"],x["p95_maxDD_pct"],x["net_pct"]) for k,x in R["V4_risk_sweep"].items()})
    print("V4 採用レバ",R["V4_chosen_lev"],"→",R["V4_chosen"])
    print("V5 二段連続合格率",R["V5_two_phase"]["combined_pct"],"%")
    print("V6 曜日プラセボ",R["V6_weekday_placebo"])
    print("V6 時刻帯",R["V6_hour_band"],"(04-10で低p, 13で消滅なら健全)")
    gates=[R["V1_corr"]["same_pair_diff_hour"]<0.95,
           R["V2_sharpe"]["portfolio_12shot"]>=R["V2_sharpe"]["single_mean"],
           v["v7_12shot"]["net_pct"]>=v["v6_3shot"]["net_pct"] and v["v7_12shot"]["worstDD_p95"]>=v["v6_3shot"]["worstDD_p95"],
           R["V4_chosen"]["pass_rate"]>=80, R["V6_weekday_placebo"]["Mon"]<=0.05]
    print(f"\n>>> 10年追認: 5ゲート中 {sum(gates)} 通過。", "★v7をデモ前進検証へ" if all(gates) else "未達→予算減/ショット絞り")
    try:
        out=(H1_DIR.format(base=DRIVE_BASE)+"/v7_multishot_validation.json") if USE_DRIVE else "research/results/v7_multishot_validation.json"
        os.makedirs(os.path.dirname(out),exist_ok=True)
        with open(out,"w") as f: json.dump(R,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",out)
    except Exception as e:
        print("JSON保存スキップ:",e)
