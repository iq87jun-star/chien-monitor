"""
colab_v7_confidence.py — v7の数値"確度"を上げる検証(ウォークフォワード＋パラメータ頑健性)。

目的: 「2本目」とは別軸=v7単体のETA/DD/合格率を"どれだけ信用してよいか"を測る。過去データ検定で
  埋められる確度は次の3つ:
   (A) ウォークフォワード: 10年を時間分割し各サブ期間で net/maxDD/Phase1合格率を出す。
       全期間で符号が安定(=特定レジーム依存でない)かを見る。エッジの"持続性"の証拠。
   (B) パラメータ頑健性: 入口時刻/ATR係数/ペア除外/曜日 をずらしても net>0・低DD が保つか。
       ナイフエッジな過剰最適化でないかの証拠(曜日は月曜以外で大幅劣化=月曜特異性の再確認)。
   (C) 別ベンダー照合: 研究データ vs ユーザーDriveのDukascopyで同一v7を回し結論一致を確認(節で案内)。
  ※(A)(B)は過去データで即可能。最終確度は(C)＋デモ前進検証で確定する。

固定予算 WF_BUDGET(既定0.6%=10年で全期DD<=7%目安, budget_resizeの安全帯)で比較。
これはシミュレーション(将来保証ではない)。
"""
import os, json, copy, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

# ---------- 設定(あなたの環境) ----------
USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"

PAIRS  = ["EURJPY","GBPJPY","USDJPY"]
HOURS  = [4,6,8,10]
BUDGETS = [1.50,1.00,0.75,0.60,0.50,0.40]   # 週次リスク%スイープ
MC_PATHS = 800
MC_HORIZON_WEEKS = 156      # ★時間無制限ゆえ旧104より長く(=低予算でも+8%到達機会を与える)
MC_SEED = 7
CONTRACT = 100000.0

# v7 EA入力と一致(WeeklyRiskPctはスイープで上書き)
P = dict(InitialBalance=100000.0, ProfitTargetPct=8.0, MaxLossLimitPct=10.0,
         DailyStopPct=4.0, EquityFloorDDPct=8.0,
         EntryWeekday=0, EntryHoursUTC=HOURS, HoldHours=24, SkipFirstWeek=False,
         WeeklyRiskPct=1.50, ShotsPerWeek=12, MinLot=0.01, MaxLot=5.0,
         AtrPeriodH1=24, CatastropheATR=2.5, MinStopPips=10.0, MaxStopPips=400.0,
         MaxSpreadPips=3.0, SlippagePoints=20, SwapPipsPerNight=0.0)

# ---------- データ ----------
# Driveマウントを頑健化(既マウント検知+例外でも継続)。USE_DRIVEフラグに依らずパスは常に探索する。
if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive mount注意(継続):", e)
DRIVE_OK = os.path.exists("/content/drive/MyDrive")
print(f"[データ] Driveマウント={DRIVE_OK} / 探索基点 {H1_DIR.format(base=DRIVE_BASE)} と {LOCAL_FALLBACK}")

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def point_size(p): return 0.001 if p.endswith("JPY") else 0.00001
def _resolve(pair):
    # ★USE_DRIVEに依存せず、Drive/ローカル両方の候補を常に試す(フラグ取りこぼし対策)
    b=H1_DIR.format(base=DRIVE_BASE)
    c=[f"{b}/{pair}_h1.csv", f"{b}/{pair}.csv",
       f"{LOCAL_FALLBACK}/{pair}_h1.csv", f"{LOCAL_FALLBACK}/{pair}.csv"]
    for x in c:
        if os.path.exists(x): return x
    return None
def load_pair(pair):
    path=_resolve(pair)
    if path is None:
        raise FileNotFoundError(
            f"{pair} のH1 CSVが見つかりません。Driveマウント={os.path.exists('/content/drive/MyDrive')}。"
            f" 期待パス例: {H1_DIR.format(base=DRIVE_BASE)}/{pair}_h1.csv "
            f"(edge2/3/4が読めた場所と同じ。DRIVE_BASE/H1_DIRを確認)")
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce")
    df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def pick(*n):
        for x in n:
            if x in df.columns: return x
        return None
    o,h,l,c=pick("open","bidopen","o"),pick("high","bidhigh","h"),pick("low","bidlow","l"),pick("close","bidclose","c")
    out=pd.DataFrame(index=df.index)
    out["open"]=df[o].astype(float); out["high"]=df[h].astype(float)
    out["low"]=df[l].astype(float);  out["close"]=df[c].astype(float)
    ac=pick("askclose","ask_close","ask"); sp=pick("spread")
    if sp: out["spread"]=df[sp].astype(float)
    elif ac: out["spread"]=(df[ac].astype(float)-out["close"]).clip(lower=0)
    else: out["spread"]=1.0*pip_size(pair)   # フォールバック=1pip
    return out.dropna(subset=["open","high","low","close"])

CACHE={}
def H1(p):
    if p not in CACHE: CACHE[p]=load_pair(p)
    return CACHE[p]

def atr_wilder(h1, period):
    h,l,c=h1["high"],h1["low"],h1["close"]; pc=c.shift(1)
    tr=pd.concat([(h-l),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()

def shot_returns(pair, wd, hour, Pp):
    """月曜LONG・24h・足内SL。1ショットの ret_pips/stop_pips/reason 系列。あなたのCell3再現。"""
    h1=H1(pair); pip=pip_size(pair); slip=Pp["SlippagePoints"]*point_size(pair)
    T=h1.index.values; O=h1["open"].to_numpy(); Hh=h1["high"].to_numpy()
    L=h1["low"].to_numpy(); C=h1["close"].to_numpy(); S=h1["spread"].to_numpy()
    atr=atr_wilder(h1,Pp["AtrPeriodH1"]); aidx=atr.index.values; aval=atr.to_numpy()
    idx=h1.index
    pos=np.where((idx.dayofweek==wd)&(idx.hour==hour))[0]
    rows=[]
    for a in pos:
        if Pp["SkipFirstWeek"] and ((idx[a].day-1)//7+1)==1: continue
        ai=int(np.searchsorted(aidx,T[a],side="right"))-1
        if ai<0 or not (aval[ai]==aval[ai]) or aval[ai]<=0: continue
        spread0=S[a] if S[a]==S[a] else pip
        if spread0/pip>Pp["MaxSpreadPips"]: continue
        sd=Pp["CatastropheATR"]*aval[ai]; sp=sd/pip
        if sp<Pp["MinStopPips"]: sp=Pp["MinStopPips"]; sd=sp*pip
        if sp>Pp["MaxStopPips"]: continue
        entry=O[a]+spread0/2+slip; sl=entry-sd
        until=T[a]+np.timedelta64(Pp["HoldHours"],"h")
        b=int(np.searchsorted(T,until,side="left")); b=max(b,a+1)
        ll=L[a:b]; ss=S[a:b]; ss=np.where(np.isnan(ss),spread0,ss)
        if len(ll)>0 and ((ll-ss/2)<=sl).any():
            ex=sl; reason="SL"
        else:
            ex=(O[b]-spread0/2) if b<len(O) else (C[-1]-spread0/2); reason="TIME"
        swap=Pp["SwapPipsPerNight"]*pip
        ret_pips=((ex-entry)+swap)/pip
        rows.append(dict(pair=pair, hour=hour, ent_time=pd.Timestamp(T[a]).tz_localize("UTC") if pd.Timestamp(T[a]).tz is None else pd.Timestamp(T[a]),
                         ret_pips=ret_pips, stop_pips=sp, reason=reason, mid=O[a]))
    return pd.DataFrame(rows)

def build_all_shots(Pp):
    allrows=[]
    for pair in PAIRS:
        for hr in Pp["EntryHoursUTC"]:
            s=shot_returns(pair,Pp["EntryWeekday"],hr,Pp)
            if len(s): allrows.append(s)
    if not allrows: return pd.DataFrame()
    return pd.concat(allrows,ignore_index=True).sort_values("ent_time").reset_index(drop=True)

def attach_usd_conv(base, usdjpy_h1):
    """各ショットの quote→USD 換算を【一度だけ】ベクトル計算して列に保持(MC内の reindex を撲滅)。
       損益/lot あたり額は usd_conv に比例。全ペアJPYクロス: USDJPY=1/mid, それ以外=1/USDJPY(同時刻)。"""
    if len(base)==0: return base
    uj=usdjpy_h1["close"].reindex(pd.DatetimeIndex(base["ent_time"]), method="ffill").to_numpy()
    uj=np.where(np.isnan(uj),150.0,uj)
    conv=np.where(base["pair"].values=="USDJPY", 1.0/base["mid"].values, 1.0/uj)
    base=base.copy(); base["usd_conv"]=conv
    return base

def usdjpy_at(t, usdjpy_h1):
    sub=usdjpy_h1["close"].reindex([t],method="ffill"); v=sub.iloc[0] if len(sub) else np.nan
    return float(v) if v==v else 150.0
def quote_to_usd(pair, price, ujpy):
    q=pair[3:6]
    if q=="USD": return 1.0
    if q=="JPY": return 1.0/(price if pair=="USDJPY" else ujpy)
    if q=="CHF": return 1.0/(price if pair=="USDCHF" else 0.9)
    return 1.0

def portfolio_equity(shots, Pp, usdjpy_h1, apply_guards=True):
    """素のret_pipsに per_shot_risk を当てて合算equity。あなたのCell4再現。"""
    if shots is None or len(shots)==0: return pd.Series(dtype=float), pd.DataFrame()
    per_pct=Pp["WeeklyRiskPct"]/max(1,Pp["ShotsPerWeek"])
    equity=Pp["InitialBalance"]; rows=[]
    cur_day=None; day_start_eq=equity; day_blocked=False; halted=False
    floor_eq=Pp["InitialBalance"]*(1-Pp["EquityFloorDDPct"]/100.0)
    target_eq=Pp["InitialBalance"]*(1+Pp["ProfitTargetPct"]/100.0)
    for _,r in shots.iterrows():
        d=r["ent_time"].date()
        if cur_day!=d: cur_day=d; day_start_eq=equity; day_blocked=False
        if apply_guards:
            if equity<=floor_eq: halted=True
            if halted: break
            if equity>=target_eq: break
            if day_blocked: continue
        pair=r["pair"]; mid=r["mid"]
        conv=r["usd_conv"] if "usd_conv" in r and r["usd_conv"]==r["usd_conv"] else quote_to_usd(pair,mid,None if pair=="USDJPY" else usdjpy_at(r["ent_time"],usdjpy_h1))
        risk_money=Pp["InitialBalance"]*per_pct/100.0
        loss_per_lot=r["stop_pips"]*pip_size(pair)*CONTRACT*conv
        if loss_per_lot<=0: continue
        lots=np.floor((risk_money/loss_per_lot)/0.01)*0.01
        lots=max(0.0,min(lots,Pp["MaxLot"]))
        if lots<Pp["MinLot"]: continue
        pnl=r["ret_pips"]*pip_size(pair)*lots*CONTRACT*conv
        equity+=pnl
        if apply_guards and (equity-day_start_eq)<=-Pp["InitialBalance"]*Pp["DailyStopPct"]/100.0:
            day_blocked=True
        rows.append(dict(ent_time=r["ent_time"], equity=equity, pnl=pnl))
    tdf=pd.DataFrame(rows)
    eq=tdf.set_index("ent_time")["equity"] if len(tdf) else pd.Series(dtype=float)
    return eq, tdf

def max_drawdown(eq, initial):
    e=pd.concat([pd.Series([initial]), eq.reset_index(drop=True)]).reset_index(drop=True)
    peak=e.cummax(); dd=e-peak
    return float(-dd.min()), float(-(dd/peak*100).min())

def yearly_worst_dd(tdf, initial):
    if len(tdf)==0: return 0.0
    worst=0.0
    for y in sorted(set(tdf["ent_time"].dt.year)):
        ey=tdf[tdf["ent_time"].dt.year==y]
        if len(ey): _,d=max_drawdown(ey.set_index("ent_time")["equity"], ey["equity"].iloc[0]); worst=max(worst,d)
    return round(worst,2)

def phase1_path(tdf, Pp):
    """ガード有り単一パスで +8%到達 vs -10%抵触 の先着判定。"""
    if len(tdf)==0: return "NO_TRADE", None
    init=Pp["InitialBalance"]; target=init*(1+Pp["ProfitTargetPct"]/100.0)
    floor_fail=Pp["MaxLossLimitPct"]; peak=init
    for _,r in tdf.iterrows():
        eq=r["equity"]; peak=max(peak,eq)
        if (peak-eq)/peak*100>=floor_fail: return "FAIL", r["ent_time"]
        if eq>=target: return "PASS", r["ent_time"]
    return "UNDET", None

def block_mc(shots, Pp, usdjpy_h1, n_paths=MC_PATHS, horizon=MC_HORIZON_WEEKS, seed=MC_SEED,
             target_pct=None):
    """週ブロック・ブートストラップ。週単位で相関を保ちつつ復元抽出し各パスで合否+到達週数。
       target_pct=利益目標%(既定=ProfitTargetPct=Phase1の8%)。Phase2再測時は5を渡す。"""
    df=shots.copy(); df["week"]=df["ent_time"].dt.to_period("W")
    weeks=sorted(df["week"].unique())
    if len(weeks)==0: return dict(pass_rate=0,fail_rate=0,undetermined=0,med_weeks=None,med_months=None,p25_weeks=None,p75_weeks=None)
    init=Pp["InitialBalance"]; per_pct=Pp["WeeklyRiskPct"]/max(1,Pp["ShotsPerWeek"])
    risk_money=init*per_pct/100.0; minlot=Pp["MinLot"]
    # ★各週の (損失/lot=denom, 利益/lot=gain) を numpy配列で事前計算 → 内側ループは純算術のみ
    pipv=df["pair"].map(pip_size).to_numpy(); convv=df["usd_conv"].to_numpy()
    df["_denom"]=df["stop_pips"].to_numpy()*pipv*CONTRACT*convv
    df["_gain"]=df["ret_pips"].to_numpy()*pipv*CONTRACT*convv
    wk_blocks=[ (g["_denom"].to_numpy(), g["_gain"].to_numpy()) for _,g in df.groupby("week") ]
    nW=len(wk_blocks)
    rng=np.random.default_rng(seed); npass=nfail=nundet=0
    tgt=Pp["ProfitTargetPct"] if target_pct is None else target_pct
    target=init*(1+tgt/100.0); floor_fail=Pp["MaxLossLimitPct"]; wk_to_pass=[]
    for _ in range(n_paths):
        pick=rng.integers(0,nW,size=horizon)
        equity=init; peak=init; done=None; wks=0
        for wi in pick:
            wks+=1; denom,gain=wk_blocks[wi]
            for k in range(len(denom)):
                d=denom[k]
                if d<=0: continue
                lots=np.floor((risk_money/d)/0.01)*0.01
                if lots<minlot: continue
                equity+=gain[k]*lots
                if equity>peak: peak=equity
                if (peak-equity)/peak*100>=floor_fail: done="FAIL"; break
                if equity>=target: done="PASS"; break
            if done: break
        if done=="PASS": npass+=1; wk_to_pass.append(wks)
        elif done=="FAIL": nfail+=1
        else: nundet+=1
    w=np.array(wk_to_pass) if wk_to_pass else None
    medw=float(np.median(w)) if w is not None else None
    return dict(pass_rate=round(npass/n_paths*100,1), fail_rate=round(nfail/n_paths*100,1),
               undetermined=round(nundet/n_paths*100,1),
               med_weeks=medw, med_months=(round(medw/4.345,1) if medw else None),
               p25_weeks=(float(np.percentile(w,25)) if w is not None else None),
               p75_weeks=(float(np.percentile(w,75)) if w is not None else None))

def typical_lots(base, Pp, usdjpy_h1):
    """推奨予算での1ショット実ロット枚数(中央値/10-90%帯)とストップ幅をペア別に集計。"""
    per_pct=Pp["WeeklyRiskPct"]/max(1,Pp["ShotsPerWeek"]); rm=Pp["InitialBalance"]*per_pct/100.0
    pipv=base["pair"].map(pip_size).to_numpy(); convv=base["usd_conv"].to_numpy()
    lpl=base["stop_pips"].to_numpy()*pipv*CONTRACT*convv
    lots=np.where(lpl>0, np.floor((rm/np.where(lpl>0,lpl,1))/0.01)*0.01, 0.0)
    d=pd.DataFrame(dict(pair=base["pair"].values, lots=lots, stop_pips=base["stop_pips"].values))
    d=d[d["lots"]>0]
    if len(d)==0: return {}
    out={}
    for pair,g in d.groupby("pair"):
        out[pair]=dict(med_lots=round(float(g["lots"].median()),2),
                       lot_p10_p90=[round(float(g["lots"].quantile(.1)),2), round(float(g["lots"].quantile(.9)),2)],
                       med_stop_pips=round(float(g["stop_pips"].median()),1))
    out["_per_shot_risk_pct"]=round(per_pct,4); out["_risk_usd_per_shot"]=round(Pp["InitialBalance"]*per_pct/100.0,2)
    return out


# ============================================================================
# v7 確度検証(ウォークフォワード＋パラメータ頑健性)
# ============================================================================
WF_BUDGET = 0.6     # 固定の週次予算%(DD安全帯)。budget_resizeの10年安全予算に合わせる
WF_FOLDS  = 5       # ウォークフォワードの時間分割数
ATR_VARIANTS  = [2.0, 2.5, 3.0]                       # CatastropheATR(基準2.5)
HOUR_VARIANTS = {"基準[4,6,8,10]":[4,6,8,10], "shift[5,7,9,11]":[5,7,9,11],
                 "shift[3,5,7,9]":[3,5,7,9], "wide[2,6,10,14]":[2,6,10,14]}
WEEKDAYS = {"Mon(基準)":0,"Tue":1,"Wed":2,"Thu":3,"Fri":4}

def _metrics(base, usdjpy, wr=WF_BUDGET, mc=True):
    Pp=copy.deepcopy(P); Pp["WeeklyRiskPct"]=wr
    eq,tdf=portfolio_equity(base,Pp,usdjpy,apply_guards=False)
    if len(eq)==0: return dict(net=0.0,dd=0.0,n=0,p1=None,p1m=None)
    _,dd=max_drawdown(eq,P["InitialBalance"])
    net=(eq.iloc[-1]-P["InitialBalance"])/P["InitialBalance"]*100
    p1=p1m=None
    if mc:
        m=block_mc(base,Pp,usdjpy,target_pct=8.0)
        p1=m["pass_rate"]; p1m=m["med_months"]
    return dict(net=round(net,1),dd=round(dd,2),n=len(base),p1=p1,p1m=p1m)

def _rebuild(usdjpy, hours=None, weekday=0, atr=2.5, pairs=None):
    global PAIRS
    orig=PAIRS
    if pairs is not None: PAIRS=pairs
    Pp=copy.deepcopy(P); Pp["EntryHoursUTC"]=hours or HOURS; Pp["EntryWeekday"]=weekday; Pp["CatastropheATR"]=atr
    base=build_all_shots(Pp); base=attach_usd_conv(base,usdjpy)
    PAIRS=orig
    return base

def run_confidence():
    usdjpy=H1("USDJPY")
    base=build_all_shots(P); base=attach_usd_conv(base,usdjpy)
    span=(base["ent_time"].max()-base["ent_time"].min()).days/365.25
    print("="*96)
    print(f"【v7 確度検証】固定予算 週次{WF_BUDGET}% / データ {span:.2f}年 {len(base)}ショット / ペア{PAIRS}")
    print("="*96)
    full=_metrics(base,usdjpy)
    print(f"全期間: net{full['net']}% / maxDD{full['dd']}% / Phase1合格{full['p1']}%(中央{full['p1m']}ヶ月) n={full['n']}")
    out={"meta":dict(span_years=round(span,2),budget=WF_BUDGET,folds=WF_FOLDS),"full":full,"walkforward":[],"robustness":{}}

    # (A) ウォークフォワード(時間等分割・各期間で符号が安定か)
    print(f"\n--- (A) ウォークフォワード {WF_FOLDS}分割: 各サブ期間で net/DD/合格率が安定=レジーム非依存 ---")
    print(f"  {'期間':<22}{'net%':>8}{'maxDD%':>8}{'P1合格%':>8}{'P1中央月':>9}{'n':>6}")
    b=base.sort_values("ent_time").reset_index(drop=True); L=len(b)
    pos=0
    for k in range(WF_FOLDS):
        sub=b.iloc[k*L//WF_FOLDS:(k+1)*L//WF_FOLDS]
        t0=sub["ent_time"].min().date(); t1=sub["ent_time"].max().date()
        mm=_metrics(sub,usdjpy)
        sign="✓" if mm["net"]>0 else "✗"
        print(f"  {str(t0)+'..'+str(t1):<22}{mm['net']:>8}{mm['dd']:>8}{str(mm['p1']):>8}{str(mm['p1m']):>9}{mm['n']:>6} {sign}")
        out["walkforward"].append(dict(start=str(t0),end=str(t1),**mm))
    pos_folds=sum(1 for r in out["walkforward"] if r["net"]>0)
    print(f"  → 黒字サブ期間 {pos_folds}/{WF_FOLDS}(多いほどレジーム非依存=確度高)")

    # (B) パラメータ頑健性(ずらしてもnet>0・低DDか)
    print(f"\n--- (B) パラメータ頑健性: ずらしてもnet>0・低DD維持=過剰最適化でない ---")
    rob={}
    print("  [入口時刻]")
    for label,hrs in HOUR_VARIANTS.items():
        bb=_rebuild(usdjpy,hours=hrs); mm=_metrics(bb,usdjpy,mc=False)
        rob.setdefault("hours",{})[label]=mm; print(f"    {label:<16} net{mm['net']:>7}% / maxDD{mm['dd']:>6}% / n={mm['n']}")
    print("  [ATR係数(破滅SL幅)]")
    for a in ATR_VARIANTS:
        bb=_rebuild(usdjpy,atr=a); mm=_metrics(bb,usdjpy,mc=False)
        rob.setdefault("atr",{})[str(a)]=mm; print(f"    ATR×{a:<12} net{mm['net']:>7}% / maxDD{mm['dd']:>6}% / n={mm['n']}")
    print("  [ペア除外(1つ抜いても生存するか)]")
    for drop in PAIRS:
        keep=[p for p in PAIRS if p!=drop]
        bb=_rebuild(usdjpy,pairs=keep); mm=_metrics(bb,usdjpy,mc=False)
        rob.setdefault("leave_one_out",{})[f"−{drop}"]=mm; print(f"    −{drop:<13} net{mm['net']:>7}% / maxDD{mm['dd']:>6}% / n={mm['n']}")
    print("  [曜日プラセボ(月曜が突出=月曜特異性の再確認)]")
    for label,wd in WEEKDAYS.items():
        bb=_rebuild(usdjpy,weekday=wd); mm=_metrics(bb,usdjpy,mc=False)
        rob.setdefault("weekday",{})[label]=mm; print(f"    {label:<12} net{mm['net']:>7}% / maxDD{mm['dd']:>6}% / n={mm['n']}")
    out["robustness"]=rob

    print("\n  ★読み方:")
    print("   ・(A)黒字サブ期間が多い=特定の年だけでなく持続=ETA/合格率の確度が高い。少ない=レジーム依存で楽観の恐れ。")
    print("   ・(B)時刻/ATR/ペア除外でnetが正のまま=頑健。曜日は月曜が突出し他が弱い=v7の月曜特異性が本物の証拠。")
    print("   ・確度の最終確定は(C)別ベンダー(Dukascopy)＋デモ前進。過去データだけでは外挿の保証は出せない。")
    print("\n  --- (C) 別ベンダー照合の手順 ---")
    print("   1. このノートはDrive(Dukascopy)接続時=本番データで上記を算出済み。")
    print("   2. 同じ期間の別ソース(研究Yahoo等)で再実行し、(A)の符号と(B)の頑健性が一致するか確認。")
    print("   3. 一致すればデータ依存でない=確度UP。乖離すればデータ品質要因を精査。")
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/v7_confidence.json") if USE_DRIVE else "research/results/v7_confidence.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("\n保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run_confidence()
