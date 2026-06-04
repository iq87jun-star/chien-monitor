"""
colab_v9_holdcompare_10y.py — v9(月曜・週末フロー intraday, 12h同日決済)の【10年H1】追認。

位置づけ:
  v9 は「新エッジ」ではなく v7 と同じ確認済みエッジ(月曜 04/06/08/10 UTC × 3円クロス LONG)を、
  保有 24h→12h(同日決済)にして【DD効率(Calmar)を上げ・スワップ符号リスクを構造排除】した工学改良。
  その中核主張を committed 2.8年(Yahoo H1)で実証した(docs/37)。本スクリプトはユーザーの Colab 環境
  (実10年H1, 実bid/ask 可)で、docs/18 の規律「短期DDは楽観側・10年で直接再測」に従い追認する。

⚠ docs/18 の教訓: v7 の maxDD は 2.8年(-4.9%)が10年(-14.8%)の約1/3だった。v9 の 2.76年(-4.08%)も
  同じく楽観側の可能性が高い。本スクリプトの目的は【12h保有の真の10年DD】を測り、
  ①12hが24hより本当にDDが小さいか(相対主張)、②12hの絶対DDが-10%枠の十分内側か、を確認すること。

確認ゲート(全7):
  V0 データ範囲・サニティ(10年あるか, 同日決済=オーバーナイト無しの確認)
  V1 ★保有スイープ DD/Calmar: hold∈{6,8,12,16,24,36,48} で net/maxDD/Calmar/SR/OOS。
       v9主張= 12h は 24h比でmaxDDがほぼ半分・Calmar最良・OOS陽性、かつ近傍が滑らか(ナイフエッジでない)。
  V2 エッジ健全性@12h: 曜日プラセボ(月曜のみ低p) / 時刻帯(04-10生存, 13消滅)。
  V3 ★年次ジャックナイフ@12h: 各年を除外しても順列p ≤ 0.10(単一年依存でない)。
  V4 ★スワップ符号耐性: overnight跨ぎ数×swap_pip を控除。24hは符号で純益が動くが、
       12h(同日)は overnight=0 ゆえ swap に【不変】であることを実証(v9の構造的優位)。
  V5 リスク予算sweep@12h + Phase1合格率(ブロック・ブートストラップMC): p95 DDを-7.5%内に保つ最大予算。
       低DDゆえ v7(0.60)より高い予算が積めるか(docs/37の「約2倍」主張)を10年で検証。
  V6 ★v7(24h) vs v9(12h) 同予算 直接比較: net / worstDD p95 / 合格率 / 中央到達週 / 週次PnL相関。

判定: V1で「12h<24hのDD」かつ V3でJK生存 かつ V4でswap不変 → v9をデモ前進検証へ(置換 or 別Magic併走)。
       崩れたら24h(v7)維持 or 予算を下げる。

使い方(Colab):
  USE_DRIVE=True, DRIVE_BASE / H1_DIR を {PAIR}_h1.csv 置き場に。必要ペア: EURJPY GBPJPY USDJPY
  (H1, UTC, close 必須。bid/ask 列があれば自動で実約定寄りに計上)。
  ROLLOVER_UTC_HOUR は業者のスワップ加算時刻(多くは22:00 UTC=サーバ00:00)。要確認。
※ シミュレーション。MCはブロック・ブートストラップでエッジ持続が前提。将来/ライブ約定は保証しない。
  数値は表示破損を避け JSON直読 / 単一スカラ print で確認すること(docs/15の教訓)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

# === ユーザー設定(Colabで編集) ===
USE_DRIVE      = True
DRIVE_BASE     = "/content/drive/MyDrive/forex_ml"
H1_DIR         = "{base}/dukascopy_data_h1"      # {PAIR}_h1.csv
LOCAL_FALLBACK = "./research/data"               # ローカル(2.76年)フォールバック

PAIRS    = ["EURJPY", "GBPJPY", "USDJPY"]
HOURS    = [4, 6, 8, 10]                          # v7/v9 同帯(時刻の事後選択をしない)
WEEKDAY  = 0                                      # Mon (pandas: Mon=0)
PIP      = 0.01                                   # JPYクロス
COST_PIP = 2.0                                    # 往復(spread+slippage)。bid/askがあればそちら優先
HOLDS    = [6, 8, 12, 16, 24, 36, 48]            # 保有スイープ(v9=12, v7=24)
V9_HOLD  = 12
V7_HOLD  = 24
ROLLOVER_UTC_HOUR = 22                            # スワップ加算時刻(UTC)。業者で要確認
SWAP_SWEEP = [+1.0, 0.0, -0.5, -1.0, -2.0]        # LONGの1泊あたり pip(符号は局面/業者で変化, docs/13)
CHOSEN_LEV = 0.60                                 # v7の保守既定(比較の基準)
N_PATHS  = 4000
MAX_WEEKS= 520
BLOCK    = 4

if USE_DRIVE:
    try:
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive マウント不可(ローカル?):", e); USE_DRIVE=False

# ---------- データ ----------
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
    def pick(*names):
        for n in names:
            for c in df.columns:
                if c.lower()==n: return c
        return None
    cc=pick("close","bidclose","bid_close","c")
    bid=pick("bidclose","bid_close","bid"); ask=pick("askclose","ask_close","ask")
    out=pd.DataFrame(index=df.index)
    out["close"]=df[cc].astype(float)
    # 実約定寄り: LONGは建て=ask / 決済=bid。無ければ close±COST/2 を後段で使う。
    out["ask"]=df[ask].astype(float) if ask else np.nan
    out["bid"]=df[bid].astype(float) if bid else np.nan
    return out.dropna(subset=["close"])

CACHE={p:load(p) for p in PAIRS}
HAS_BIDASK=all(CACHE[p]["ask"].notna().any() and CACHE[p]["bid"].notna().any() for p in PAIRS)

# ---------- overnight(スワップ)跨ぎ数 ----------
def overnight_crossings(t_entry, t_exit):
    """(entry, exit] の間に ROLLOVER_UTC_HOUR を跨ぐ回数。12h(同日)なら多くが0。"""
    # 各日 ROLLOVER 時刻の datetime を生成して個数を数える
    d0=pd.Timestamp(t_entry).normalize(); d1=pd.Timestamp(t_exit).normalize()
    cnt=0
    d=d0
    while d<=d1:
        roll=d+pd.Timedelta(hours=ROLLOVER_UTC_HOUR)
        if t_entry < roll <= t_exit: cnt+=1
        d+=pd.Timedelta(days=1)
    return cnt

# ---------- ショット・リターン(LONG, hold本後決済, 実コスト/スワップ) ----------
def shot_returns(pair, hour, hold, swap_pip=0.0):
    df=CACHE[pair]; idx=df.index
    cv=df["close"].values; av=df["ask"].values; bv=df["bid"].values
    a=np.where((idx.dayofweek==WEEKDAY)&(idx.hour==hour))[0]; a=a[a+hold<len(cv)]
    rets=[]; wk=[]
    for i in a:
        j=i+hold
        if HAS_BIDASK and not (np.isnan(av[i]) or np.isnan(bv[j])):
            entry=av[i]; exit_=bv[j]; gross=(exit_-entry)/entry          # 実bid/ask: 建てask→決済bid
        else:
            entry=cv[i]; exit_=cv[j]; gross=(exit_-entry)/entry - COST_PIP*PIP/entry
        nights=overnight_crossings(idx[i], idx[j])
        gross += swap_pip*PIP/entry*nights                               # LONG: swap_pip符号は局面で変化
        rets.append(gross); wk.append(idx[i])
    s=pd.Series(rets, index=pd.DatetimeIndex(wk))
    s.index=s.index.to_period("W"); return s[~s.index.duplicated()]

def build_matrix(pairs, hours, hold, swap_pip=0.0):
    return pd.DataFrame({f"{p}_{h:02d}":shot_returns(p,h,hold,swap_pip)
                         for p in pairs for h in hours}).sort_index()

def weekly_portfolio(M, total_weekly_lev):
    out={}
    for wk,row in M.iterrows():
        rs=row.dropna()
        if len(rs)==0: continue
        out[wk]=float((total_weekly_lev/len(rs)*rs).sum())
    return pd.Series(out).sort_index()

# ---------- 指標 ----------
def sharpe(s):
    s=pd.Series(s).dropna(); return round(float(s.mean()/s.std()*np.sqrt(52)),2) if s.std()>0 else 0.0
def net_pct(s): return round(float(((1+pd.Series(s).dropna()).prod()-1)*100),2)
def maxdd_pct(s):
    eq=(1+pd.Series(s).dropna()).cumprod(); peak=eq.cummax()
    return round(float(((eq-peak)/peak).min())*100,2)
def calmar(s):
    dd=maxdd_pct(s); n=net_pct(s); return round(n/abs(dd),2) if dd!=0 else float("nan")
def oos_mean_bps(s, frac=0.7):
    s=pd.Series(s).dropna(); k=int(len(s)*frac)
    return round(float(s.iloc[k:].mean())*1e4,2) if len(s)>k else float("nan")

def perm_p(r,n_iter=5000,seed=7):
    """符号反転順列(自己相関は週次集約で緩和済み)。p=frac(perm合計>=実合計)。"""
    r=np.asarray(r,float)
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); s=np.abs(r)
    return float((np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n_iter)])>=real).mean())

def block_bootstrap(weekly,n_paths=N_PATHS,max_weeks=MAX_WEEKS,block=BLOCK,seed=11):
    rng=np.random.default_rng(seed); w=weekly.values; n=len(w)
    if n==0: return np.zeros((n_paths,max_weeks))
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
    return dict(pass_rate=round(float(pas.mean())*100,1), fail_rate=round(float(fail.mean())*100,1),
                timeout_rate=round(float((~pas&~fail).mean())*100,1),
                median_weeks=(None if np.all(np.isnan(wks)) else round(float(np.nanmedian(wks)),0)),
                p95_maxDD_pct=round(float(np.percentile(mdd,5))*100,1),
                median_maxDD_pct=round(float(np.percentile(mdd,50))*100,1))

def pool_weekly(hours, hold, wd=WEEKDAY, swap_pip=0.0):
    """JPYクロス×時刻 を等加重した週次ポートフォリオ(予算1.0)。"""
    M=build_matrix(PAIRS, hours, hold, swap_pip)
    return weekly_portfolio(M, 1.0), M

# ---------- 実行 ----------
def run():
    R={}
    base12,_=pool_weekly(HOURS, V9_HOLD)
    R["span"]=dict(weeks=int(len(base12)), first=str(base12.index.min()), last=str(base12.index.max()),
                   has_bidask=bool(HAS_BIDASK), cost_pip=COST_PIP, rollover_utc=ROLLOVER_UTC_HOUR)

    # V0 同日決済の確認(12h: overnight跨ぎ=0が大半か)
    nights12=[]; nights24=[]
    for p in PAIRS:
        idx=CACHE[p].index
        for h in HOURS:
            a=np.where((idx.dayofweek==WEEKDAY)&(idx.hour==h))[0]
            for i in a:
                if i+V9_HOLD<len(idx): nights12.append(overnight_crossings(idx[i],idx[i+V9_HOLD]))
                if i+V7_HOLD<len(idx): nights24.append(overnight_crossings(idx[i],idx[i+V7_HOLD]))
    R["V0_overnight"]=dict(v9_12h_mean_nights=round(float(np.mean(nights12)),3),
                           v7_24h_mean_nights=round(float(np.mean(nights24)),3),
                           note="v9(12h)≈0 なら同日決済=swap不変の前提が成立")

    # V1 保有スイープ DD/Calmar
    sweep={}
    for hold in HOLDS:
        w,_=pool_weekly(HOURS, hold)
        sweep[hold]=dict(net_pct=net_pct(w), maxDD_pct=maxdd_pct(w), calmar=calmar(w),
                         sharpe=sharpe(w), oos_bps=oos_mean_bps(w), n=int(len(w)))
    R["V1_hold_sweep"]=sweep
    dd12=sweep[V9_HOLD]["maxDD_pct"]; dd24=sweep[V7_HOLD]["maxDD_pct"]
    R["V1_v9_vs_v7"]=dict(v9_12h_maxDD=dd12, v7_24h_maxDD=dd24,
                          dd_ratio=round(dd12/dd24,3) if dd24 else None,
                          v9_calmar=sweep[V9_HOLD]["calmar"], v7_calmar=sweep[V7_HOLD]["calmar"],
                          claim_dd_about_half=(dd24!=0 and 0.35<=abs(dd12/dd24)<=0.70))

    # V2 エッジ健全性@12h
    def pool_wd(wd, hours=HOURS, hold=V9_HOLD):
        cols=[]
        for p in PAIRS:
            for h in hours:
                cols.append(shot_returns(p,h,hold).rename(f"{p}_{h}"))
        return pd.concat(cols,axis=1).mean(axis=1).dropna()
    wd_p={["Mon","Tue","Wed","Thu","Fri"][wd]:round(perm_p(pool_wd(wd).values),4) for wd in range(5)}
    others=[wd_p[k] for k in ("Tue","Wed","Thu","Fri")]
    R["V2_weekday_placebo@12h"]=dict(p=wd_p, mon_is_min=(wd_p["Mon"]==min(wd_p.values())),
        discriminates=(wd_p["Mon"]<=0.05 and min(others)>0.05),
        note="10年なら月曜のみ低p(他は非有意)を期待。短期/一方向標本では全曜日が+で非識別になる(=10年が必要な証拠)")
    R["V2_hour_band@12h"]={h:round(perm_p(pool_wd(0,[h]).values),4) for h in (4,6,8,10,13)}

    # V3 年次ジャックナイフ@12h
    s12=pool_wd(0)                      # 月曜プールの週次系列
    yrs=sorted(set(s12.index.year))
    jk={}
    for y in yrs:
        sub=s12[s12.index.year!=y]
        jk[int(y)]=round(perm_p(sub.values),4)
    R["V3_jackknife@12h"]=dict(by_year_drop=jk, max_p=round(max(jk.values()),4) if jk else None,
                               pass_le_0_10=(max(jk.values())<=0.10 if jk else None))

    # V4 スワップ符号耐性(12h vs 24h)
    swp={"12h":{}, "24h":{}}
    for s in SWAP_SWEEP:
        w12,_=pool_weekly(HOURS, V9_HOLD, swap_pip=s)
        w24,_=pool_weekly(HOURS, V7_HOLD, swap_pip=s)
        swp["12h"][f"{s:+.1f}"]=dict(net_pct=net_pct(w12), maxDD_pct=maxdd_pct(w12))
        swp["24h"][f"{s:+.1f}"]=dict(net_pct=net_pct(w24), maxDD_pct=maxdd_pct(w24))
    n12=[v["net_pct"] for v in swp["12h"].values()]; n24=[v["net_pct"] for v in swp["24h"].values()]
    R["V4_swap_robustness"]=dict(detail=swp,
        v9_12h_net_spread=round(max(n12)-min(n12),2), v7_24h_net_spread=round(max(n24)-min(n24),2),
        note="v9(同日)はswapで純益がほぼ動かない(spread小)＝符号リスクを構造排除")

    # V5 予算sweep@12h + Phase1合格率
    sw={}
    for lev in [0.60,0.90,1.20,1.50,2.00,2.50,3.00]:
        w,_=pool_weekly(HOURS, V9_HOLD); w=w*(lev/1.0)
        sw[f"{lev:.2f}"]=dict(**eval_challenge(block_bootstrap(w)), net_pct=net_pct(w), maxDD_pct=maxdd_pct(w))
    R["V5_budget_sweep@12h"]=sw
    cand=[(k,v) for k,v in sw.items() if v["p95_maxDD_pct"]>=-7.5 and v["fail_rate"]<=2.0] or list(sw.items())
    bk,bv=max(cand,key=lambda kv:(kv[1]["pass_rate"], -(kv[1]["median_weeks"] or 9e9)))
    R["V5_chosen_budget"]=bk; R["V5_chosen"]=bv

    # V6 v7(24h) vs v9(12h) 同予算 直接比較 + 週次相関
    w12c,_=pool_weekly(HOURS, V9_HOLD); w12c=w12c*(CHOSEN_LEV/1.0)
    w24c,_=pool_weekly(HOURS, V7_HOLD); w24c=w24c*(CHOSEN_LEV/1.0)
    p12=eval_challenge(block_bootstrap(w12c)); p24=eval_challenge(block_bootstrap(w24c,seed=23))
    al=pd.concat([w12c.rename("v9"), w24c.rename("v7")],axis=1).dropna()
    corr=round(float(al["v9"].corr(al["v7"])),3) if len(al)>10 else None
    R["V6_v7_vs_v9_same_budget"]=dict(budget_pct=CHOSEN_LEV,
        v9_12h=dict(net_pct=net_pct(w12c), worstDD_p95=p12["p95_maxDD_pct"], pass_rate=p12["pass_rate"],
                    median_weeks=p12["median_weeks"]),
        v7_24h=dict(net_pct=net_pct(w24c), worstDD_p95=p24["p95_maxDD_pct"], pass_rate=p24["pass_rate"],
                    median_weeks=p24["median_weeks"]),
        weekly_pnl_corr=corr, note="相関が低ければ別Magic併走で分散; 高ければ低DDのv9へ置換")
    return R

if __name__=="__main__":
    R=run()
    print("=== v9(12h同日決済) 10年追認 vs v7(24h) ===")
    print("span:",R["span"])
    print("V0 overnight: v9_12h泊数",R["V0_overnight"]["v9_12h_mean_nights"],
          "/ v7_24h泊数",R["V0_overnight"]["v7_24h_mean_nights"],"(v9≈0で同日決済)")
    print("V1 保有スイープ:")
    for h,v in R["V1_hold_sweep"].items():
        tag=" <-v9" if h==V9_HOLD else (" <-v7" if h==V7_HOLD else "")
        print(f"   hold {h:2d}h: net{v['net_pct']:+7.2f}% DD{v['maxDD_pct']:7.2f}% Calmar{v['calmar']:5.2f} "
              f"SR{v['sharpe']:5.2f} OOS{v['oos_bps']:+6.2f}bps{tag}")
    c=R["V1_v9_vs_v7"]; print(f"   → v9 DD/v7 DD = {c['dd_ratio']} (約半分={c['claim_dd_about_half']}), "
          f"Calmar v9 {c['v9_calmar']} vs v7 {c['v7_calmar']}")
    print("V2 曜日プラセボ@12h",R["V2_weekday_placebo@12h"]["p"],
          "識別=",R["V2_weekday_placebo@12h"]["discriminates"],"(10年で月曜のみ低pなら健全)")
    print("V2 時刻帯@12h",R["V2_hour_band@12h"],"(04-10低p,13消滅で健全)")
    print("V3 年次JK@12h max_p",R["V3_jackknife@12h"]["max_p"],"(≤0.10で単一年依存なし=",
          R["V3_jackknife@12h"]["pass_le_0_10"],")")
    print("V4 swap耐性 純益spread: v9_12h",R["V4_swap_robustness"]["v9_12h_net_spread"],
          "% vs v7_24h",R["V4_swap_robustness"]["v7_24h_net_spread"],"%(v9が小=符号不変)")
    print("V5 予算sweep@12h 採用",R["V5_chosen_budget"],"→",R["V5_chosen"])
    v=R["V6_v7_vs_v9_same_budget"]
    print(f"V6 同予算{v['budget_pct']}%  v9: net{v['v9_12h']['net_pct']}% DD{v['v9_12h']['worstDD_p95']}% "
          f"pass{v['v9_12h']['pass_rate']}%  |  v7: net{v['v7_24h']['net_pct']}% DD{v['v7_24h']['worstDD_p95']}% "
          f"pass{v['v7_24h']['pass_rate']}%  corr{v['weekly_pnl_corr']}")
    gates=[c["claim_dd_about_half"],
           R["V2_weekday_placebo@12h"]["discriminates"],
           R["V3_jackknife@12h"]["pass_le_0_10"] is True,
           R["V4_swap_robustness"]["v9_12h_net_spread"] < R["V4_swap_robustness"]["v7_24h_net_spread"],
           abs(R["V1_v9_vs_v7"]["v9_12h_maxDD"])<=10.0]
    print(f"\n>>> 10年追認: 5ゲート中 {sum(g is True for g in gates)} 通過。",
          "★v9をデモ前進検証へ(置換 or 別Magic併走)" if all(gates) else "未達→24h(v7)維持 or 予算減")
    try:
        out=(H1_DIR.format(base=DRIVE_BASE)+"/v9_holdcompare_validation.json") if USE_DRIVE else \
            "research/results/v9_holdcompare_validation.json"
        os.makedirs(os.path.dirname(out),exist_ok=True)
        with open(out,"w") as f: json.dump(R,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",out)
    except Exception as e:
        print("JSON保存スキップ:",e)
