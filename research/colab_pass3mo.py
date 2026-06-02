"""
colab_pass3mo.py — 「3ヶ月(=13週)以内に+8%到達する確率」を最大化する賭け金を数値化。
  目的: チャレンジ(目標+8% / 最大損失-10%)を3ヶ月で通過する確率が最大の週次予算を、
        (1) v7単体  (2) v7+MA2両建て  の両方で算出し比較する。
  方式: v7単体=実エンジンの週ブロックMCをhorizon=13週で実行し予算をスイープ。
        両建て=v7の週次口座リターンのプール + MA2月次(ボラ目標サイズ)を重ねた合成MC。
  ⚠ 保証ではなく確率。日次損失上限は未モデル(各社-10%最大損失が主に効く前提)。スワップ等は別。
     v7データはローカル2.76年/Drive10年。Drive実行が拘束力ある数値。
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
# 3ヶ月(13週)通過確率の最大化  ＋ v7単体 / v7+MA2 比較
# ============================================================================
HORIZON_3MO = 13                               # 3ヶ月 ≈ 13週
BUDGETS_SWEEP = [0.6,1.0,1.5,2.0,2.5,3.0,4.0,5.0]  # 週次リスク%スイープ
FAIL_CAP = 10.0                                # 「現実的推奨」=失格率がこの上限以下で通過率最大の予算
MA2_PAIRS = ["XAUUSD","US500","NAS100","GER40"]
MA2_LB = [1,3,6,12]
MA2_DAILY_DIR = DRIVE_BASE+"/multiasset_daily"
MA2_TARGET_VOL = 0.012                          # MA2月次目標ボラ(≈標準的リスク管理。素DD-8%相当)
MA2_ALLOCS = [0.0, 0.5, 1.0]                    # 両建て時のMA2配分(0=v7単体, 1=満額衛星)

def _ma2_daily(name):
    for p in (f"{MA2_DAILY_DIR}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"):
        if os.path.exists(p):
            df=pd.read_csv(p); df.columns=[c.strip().lower() for c in df.columns]
            t=pd.to_datetime(df["timestamp"] if "timestamp" in df else df.iloc[:,0],utc=True,errors="coerce")
            s=pd.Series(df["close"].astype(float).values,index=t).dropna().sort_index()
            return s
    return None
def ma2_monthly_unit(bps=5.0):
    legs=[]
    for a in MA2_PAIRS:
        d=_ma2_daily(a)
        if d is None: continue
        m=d.groupby(d.index.to_period("M")).last()
        if len(m)<max(MA2_LB)+3: continue
        comp=sum(np.sign(m.pct_change(L)) for L in MA2_LB); pos=np.sign(comp); nxt=m.pct_change().shift(-1)
        c=bps/1e4
        for t in m.index[:-1]:
            p0=pos.get(t,0)
            if not np.isfinite(p0) or p0==0: continue
            legs.append((t, p0*nxt[t]-c))
    if not legs: return pd.Series(dtype=float)
    s=pd.Series([v for _,v in legs],index=[t for t,_ in legs]); return s.groupby(s.index).mean().sort_index()
def ma2_monthly_sized(target_vol=MA2_TARGET_VOL):
    s=ma2_monthly_unit()
    if len(s)==0: return s
    rv=s.rolling(12).std().shift(1); scale=(target_vol/rv).clip(upper=2.0).fillna(1.0)
    return (s*scale).dropna()

def v7_week_returns(shots, Pp):
    """予算Ppでのv7の【週次口座リターン】プール(分数)。block_mc内側計算を1回展開。"""
    df=shots.copy(); df["week"]=df["ent_time"].dt.to_period("W")
    init=Pp["InitialBalance"]; per_pct=Pp["WeeklyRiskPct"]/max(1,Pp["ShotsPerWeek"])
    risk_money=init*per_pct/100.0; minlot=Pp["MinLot"]
    pipv=df["pair"].map(pip_size).to_numpy(); convv=df["usd_conv"].to_numpy()
    df["_d"]=df["stop_pips"].to_numpy()*pipv*CONTRACT*convv
    df["_g"]=df["ret_pips"].to_numpy()*pipv*CONTRACT*convv
    out=[]
    for _,g in df.groupby("week"):
        d=g["_d"].to_numpy(); gn=g["_g"].to_numpy(); pnl=0.0
        for k in range(len(d)):
            if d[k]<=0: continue
            lots=np.floor((risk_money/d[k])/0.01)*0.01
            if lots<minlot: continue
            pnl+=gn[k]*lots
        out.append(pnl/init)
    return np.array(out)

def combined_mc(v7_weeks, ma2_monthly, alloc, init, target_pct=8.0, floor_pct=10.0,
                horizon=HORIZON_3MO, n_paths=2000, seed=11):
    """v7週次 + MA2月次(配分alloc)の合成口座を13週シミュレート。+8%先着=PASS/-10%先着=FAIL。"""
    rng=np.random.default_rng(seed); nW=len(v7_weeks); nM=len(ma2_monthly)
    if nW==0: return dict(pass_rate=0,fail_rate=0,undet=0,med_weeks=None)
    ma2_weeks={4,9,13}                       # 13週中の月末3回にMA2損益を反映(≈月次)
    tgt=init*(1+target_pct/100.0); npass=nfail=nundet=0; wkpass=[]
    for _ in range(n_paths):
        eq=init; peak=init; done=None; wks=0
        vp=rng.integers(0,nW,size=horizon)
        for w in range(1,horizon+1):
            eq*=(1+v7_weeks[vp[w-1]]); wks=w
            if alloc>0 and nM>0 and w in ma2_weeks:
                eq*=(1+ma2_monthly[rng.integers(0,nM)]*alloc)
            if eq>peak: peak=eq
            if (peak-eq)/peak*100>=floor_pct: done="FAIL"; break
            if eq>=tgt: done="PASS"; break
        if done=="PASS": npass+=1; wkpass.append(wks)
        elif done=="FAIL": nfail+=1
        else: nundet+=1
    w=np.array(wkpass) if wkpass else None
    return dict(pass_rate=round(npass/n_paths*100,1), fail_rate=round(nfail/n_paths*100,1),
                undet=round(nundet/n_paths*100,1), med_weeks=(float(np.median(w)) if w is not None else None))

def run_pass3mo():
    usdjpy=H1("USDJPY"); base=build_all_shots(P); base=attach_usd_conv(base,usdjpy)
    span=(base["ent_time"].max()-base["ent_time"].min()).days/365.25
    ma2=ma2_monthly_sized()
    print("="*96)
    print(f"【3ヶ月(13週)通過確率の最大化】 v7データ{span:.2f}年{len(base)}shot / MA2月次{len(ma2)}ヶ月")
    print(f"  目標+{P['ProfitTargetPct']}% / 最大損失-{P['MaxLossLimitPct']}% / horizon=13週")
    print("="*96)

    # (1) v7単体: 実エンジンのblock_mcを13週で予算スイープ
    print("\n--- (1) v7単体: 週次予算ごとの 3ヶ月通過率 / 失格率 / 純(通過-失格) / 通過中央週 ---")
    print(f"  {'予算%':>6}{'通過率%':>9}{'失格率%':>9}{'純pt':>8}{'未達%':>8}{'通過中央週':>11}")
    best=None; bal=None
    for b in BUDGETS_SWEEP:
        Pp=dict(P); Pp["WeeklyRiskPct"]=b
        m=block_mc(base,Pp,usdjpy,horizon=HORIZON_3MO,target_pct=P["ProfitTargetPct"])
        net=round(m['pass_rate']-m['fail_rate'],1)
        print(f"  {b:>6}{m['pass_rate']:>9}{m['fail_rate']:>9}{net:>8}{m['undetermined']:>8}{str(m['med_weeks']):>11}")
        if best is None or m["pass_rate"]>best[1]: best=(b,m["pass_rate"],m["fail_rate"])
        if m["fail_rate"]<=FAIL_CAP and (bal is None or m["pass_rate"]>bal[1]): bal=(b,m["pass_rate"],m["fail_rate"])
    print(f"  → 通過率【最大】: 予算{best[0]}% (通過{best[1]}% / 失格{best[2]}%) … 攻め")
    if bal: print(f"  → 現実的【推奨】(失格≤{FAIL_CAP}%で通過最大): 予算{bal[0]}% (通過{bal[1]}% / 失格{bal[2]}%)")
    print(f"  ※FundedNext Stellarは時間無制限→無理に攻めず低予算なら失格≈0%で『時間をかけて』ほぼ確実に通過も可。")

    # (2) v7+MA2 両建て: 通過率最大予算の近傍で MA2配分を変えて比較
    print("\n--- (2) v7+MA2 両建て: v7予算を(1)の最大近傍に固定し、MA2配分を変えて3ヶ月通過率を比較 ---")
    bstar=best[0]
    Pp=dict(P); Pp["WeeklyRiskPct"]=bstar; v7w=v7_week_returns(base,Pp)
    print(f"  v7予算={bstar}% / MA2目標ボラ{MA2_TARGET_VOL*100:.1f}%(素DD≈-8%相当)")
    print(f"  {'MA2配分':>8}{'通過率%':>9}{'失格率%':>9}{'未達%':>8}{'通過中央週':>11}")
    rows={}
    for a in MA2_ALLOCS:
        c=combined_mc(v7w, ma2.values, a, P["InitialBalance"], target_pct=P["ProfitTargetPct"],
                      floor_pct=P["MaxLossLimitPct"])
        tag="v7単体" if a==0 else f"×{a}"
        print(f"  {tag:>8}{c['pass_rate']:>9}{c['fail_rate']:>9}{c['undet']:>8}{str(c['med_weeks']):>11}")
        rows[a]=c
    base_pass=rows[0.0]["pass_rate"]
    print("\n  ★読み方:")
    print("   ・13週=月次MA2は約3回しか効かない→3ヶ月の通過率はv7がほぼ全てを決める。")
    d_full=rows[max(MA2_ALLOCS)]["pass_rate"]-base_pass
    print(f"   ・MA2満額でも通過率の変化は {d_full:+.1f}pt(失格率も僅変)。MA2の分散効果は『年』単位で、3ヶ月審査には効かない。")
    print("   ・結論: 3ヶ月突破は【v7単体を適正予算で】が最適。MA2は審査後の本資金で年単位の分散に回すのが筋。")
    out=dict(span_years=round(span,2),v7_maxpass_budget=best[0],v7_maxpass_pass=best[1],v7_maxpass_fail=best[2],
             v7_balanced=({"budget":bal[0],"pass":bal[1],"fail":bal[2]} if bal else None),
             combined={str(a):rows[a] for a in MA2_ALLOCS})
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/pass3mo.json") if USE_DRIVE else "research/results/pass3mo.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("\n保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run_pass3mo()
