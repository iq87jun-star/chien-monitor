"""
colab_v7_budget_resize.py — v7【10年】予算リサイズ確定スクリプト(自己完結・あなたのColab用)。

目的(docs/18 §6-1): 10年実データで週次予算を {1.5,1.0,0.75,0.60,0.50,0.40}% と振り、
  (1) 全期間maxDD% / 年次最悪DD% / 純益%   ← 旧1.5%の14.8%が予算にほぼ線形か実測確認
  (2) ガード有り10年通しの PASS/FAIL       ← 単一パスでも失格しない予算はどれか
  (3) ブロック・ブートストラップMCの合格率  ← ★非線形。合格率を最大化する予算を選ぶ
を一覧し、「全期間maxDD <= 8%(−10%に2%以上マージン) かつ MC合格率最大」の予算を推奨する。

あなたの v7 検証ノートと同一エンジンを再現:
  ・ATR(Wilder,H1×24)×2.5 の破滅SL、足内(bid)SL判定、24h時間決済、スプレッド/スリッページ
  ・★初期残高基準の固定%サイジング(risk_money=Initial×weekly/shots) → maxDD%は予算に線形
  ・FundedNextガード(当日-4%/総合-8%floor/+8%target)、quote_to_usd換算
データ規約も同一: dukascopy_data_h1/{PAIR}_h1.csv(あれば spread/ask 列を使用、無ければ1pip)。

⚠ シミュレーション。最終判定はデモ前進検証で。数値は JSON保存/印字。
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
MC_PATHS = 2000
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
if USE_DRIVE:
    try:
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可:", e); USE_DRIVE=False

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def point_size(p): return 0.001 if p.endswith("JPY") else 0.00001
def _resolve(pair):
    c=[]
    if USE_DRIVE:
        b=H1_DIR.format(base=DRIVE_BASE); c+=[f"{b}/{pair}_h1.csv", f"{b}/{pair}.csv"]
    c+=[f"{LOCAL_FALLBACK}/{pair}_h1.csv"]
    for x in c:
        if os.path.exists(x): return x
    raise FileNotFoundError(f"{pair}: {c}")
def load_pair(pair):
    df=pd.read_csv(_resolve(pair)); df.columns=[c.strip().lower() for c in df.columns]
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
        ujpy=None if pair=="USDJPY" else usdjpy_at(r["ent_time"],usdjpy_h1)
        risk_money=Pp["InitialBalance"]*per_pct/100.0
        loss_per_lot=r["stop_pips"]*pip_size(pair)*CONTRACT*quote_to_usd(pair,mid,ujpy)
        if loss_per_lot<=0: continue
        lots=np.floor((risk_money/loss_per_lot)/0.01)*0.01
        lots=max(0.0,min(lots,Pp["MaxLot"]))
        if lots<Pp["MinLot"]: continue
        pnl=r["ret_pips"]*pip_size(pair)*lots*CONTRACT*quote_to_usd(pair,mid,ujpy)
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

def block_mc(shots, Pp, usdjpy_h1, n_paths=MC_PATHS, horizon=MC_HORIZON_WEEKS, seed=MC_SEED):
    """週ブロック・ブートストラップ。週単位で相関を保ちつつ復元抽出し各パスでPhase1合否。"""
    df=shots.copy(); df["week"]=df["ent_time"].dt.to_period("W")
    weeks=sorted(df["week"].unique()); by={w:g for w,g in df.groupby("week")}
    if len(weeks)==0: return dict(pass_rate=0,fail_rate=0,undetermined=0)
    rng=np.random.default_rng(seed); wk_arr=np.array(weeks,dtype=object)
    npass=nfail=nundet=0; init=Pp["InitialBalance"]
    target=init*(1+Pp["ProfitTargetPct"]/100.0); floor_fail=Pp["MaxLossLimitPct"]
    per_pct=Pp["WeeklyRiskPct"]/max(1,Pp["ShotsPerWeek"])
    for _ in range(n_paths):
        pick=rng.choice(len(wk_arr), size=horizon, replace=True)
        equity=init; peak=init; done=None
        for wi in pick:
            g=by[wk_arr[wi]]
            for _,r in g.iterrows():
                pair=r["pair"]; mid=r["mid"]
                ujpy=None if pair=="USDJPY" else usdjpy_at(r["ent_time"],usdjpy_h1)
                lpl=r["stop_pips"]*pip_size(pair)*CONTRACT*quote_to_usd(pair,mid,ujpy)
                if lpl<=0: continue
                lots=np.floor((init*per_pct/100.0/lpl)/0.01)*0.01
                if lots<Pp["MinLot"]: continue
                equity+=r["ret_pips"]*pip_size(pair)*lots*CONTRACT*quote_to_usd(pair,mid,ujpy)
                peak=max(peak,equity)
                if (peak-equity)/peak*100>=floor_fail: done="FAIL"; break
                if equity>=target: done="PASS"; break
            if done: break
        if done=="PASS": npass+=1
        elif done=="FAIL": nfail+=1
        else: nundet+=1
    return dict(pass_rate=round(npass/n_paths*100,1), fail_rate=round(nfail/n_paths*100,1),
               undetermined=round(nundet/n_paths*100,1))

def run():
    usdjpy_h1=H1("USDJPY")
    base=build_all_shots(P)
    span=(base["ent_time"].max()-base["ent_time"].min()).days/365.25
    print(f"総ショット {len(base)} / 期間 {span:.1f}年 / ペア{PAIRS}×時刻{HOURS}")
    out={"meta":dict(n_shots=len(base), span_years=round(span,1), mc_horizon_weeks=MC_HORIZON_WEEKS, mc_paths=MC_PATHS),"sweep":[]}
    print(f"\n{'予算%':>6} {'純益%':>8} {'maxDD%':>8} {'年次最悪%':>9} {'通しPhase1':>10} {'MC合格%':>8} {'MC失格%':>8} {'MC未決%':>8}")
    for wr in BUDGETS:
        Pp=copy.deepcopy(P); Pp["WeeklyRiskPct"]=wr
        eq_raw,tdf_raw=portfolio_equity(base,Pp,usdjpy_h1,apply_guards=False)
        net=round((eq_raw.iloc[-1]-P["InitialBalance"])/P["InitialBalance"]*100,2) if len(eq_raw) else 0
        _,dd=max_drawdown(eq_raw,P["InitialBalance"]); yw=yearly_worst_dd(tdf_raw,P["InitialBalance"])
        _,tdf_g=portfolio_equity(base,Pp,usdjpy_h1,apply_guards=True)
        ph,_=phase1_path(tdf_g,Pp)
        mc=block_mc(base,Pp,usdjpy_h1)
        row=dict(weekly_pct=wr, net_pct=net, maxDD_pct=round(dd,2), yearly_worst_pct=yw,
                 single_path_phase1=ph, **{f"mc_{k}":v for k,v in mc.items()})
        out["sweep"].append(row)
        print(f"{wr:>6.2f} {net:>8.1f} {dd:>8.2f} {yw:>9.2f} {ph:>10} {mc['pass_rate']:>8} {mc['fail_rate']:>8} {mc['undetermined']:>8}")
    # ★推奨ロジック: FundedNextは時間無制限ゆえ「未決(horizon内未到達)」は失格でなく"遅いだけ"。
    #   よって (1)全期間maxDD<=7%(−10%に3%マージン) かつ (2)MC失格率<=5%(DD抵触を稀に) を満たす中で
    #   (3)MC合格率最大(=最も速い) の予算を選ぶ。安全を確保した上で到達速度を最大化。
    SAFE_DD=7.0; MAX_FAIL=5.0
    safe=[r for r in out["sweep"] if r["maxDD_pct"]<=SAFE_DD and r["mc_fail_rate"]<=MAX_FAIL]
    rec=max(safe, key=lambda r:r["mc_pass_rate"]) if safe else None
    out["recommendation"]=rec; out["rule"]=dict(safe_maxDD_pct=SAFE_DD, max_fail_pct=MAX_FAIL)
    print(f"\n>>> 推奨(maxDD<={SAFE_DD}% かつ MC失格率<={MAX_FAIL}% の中で MC合格率最大=最速):")
    if rec:
        print(f"    週次予算 {rec['weekly_pct']}%  (maxDD {rec['maxDD_pct']}% / 失格 {rec['mc_fail_rate']}% / 合格 {rec['mc_pass_rate']}%)")
    else:
        print("    該当なし → さらに低予算を BUDGETS に追加。")
    print(f"    ★解釈: 『未決%』は失格でなく『時間無制限なら最終的に到達』。失格率だけが本当の不合格。")
    print(f"    既定0.60の妥当性: 上表0.60行の maxDD が −10%に十分マージンを残し、失格率~0 かを確認。")
    print(f"    (10年で1.5%は maxDD~14.8%/失格17%付近になり SAFE_DD で除外される想定。)")
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/v7_budget_resize.json") if USE_DRIVE else "research/results/v7_budget_resize.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
