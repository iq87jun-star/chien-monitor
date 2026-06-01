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
USE_DRIVE  = False
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
# 業者プラン比較シミュレーション(安全性の高い老舗業者 × v7)
# 手数料/分配は2026時点の概算。改定されるので★必ず購入画面で最新を確認し編集すること。
# dd_type: static=初期残高基準フロア(block_mcのpeak基準より実際は緩い→pass率は表より高め傾向)
#          trailing=ピーク基準(block_mcと一致)
# phases : 各フェーズ利益目標%のリスト([8,5]=2段, [10]=1段)
# ============================================================================
PLANS = [
    # ---- 評価型(チャレンジ): 合格→ファンド。手数料は合格で返金が多い。最大DDは緩め ----
    dict(model="評価型", firm="FTMO(2015)",       plan="2-Step",        size=100000, phases=[10,5],
         daily_pct=5.0, max_loss_pct=10.0, dd_type="static",
         fee=580, fee_refunded=True,  eval_bonus_pct=0.0,  split=0.80, min_days=4),
    dict(model="評価型", firm="FTMO(2015)",       plan="1-Step",        size=100000, phases=[10],
         daily_pct=3.0, max_loss_pct=10.0, dd_type="trailing",
         fee=580, fee_refunded=True,  eval_bonus_pct=0.0,  split=0.90, min_days=4),
    dict(model="評価型", firm="FundedNext(2022)", plan="Stellar 2-Step",size=100000, phases=[8,5],
         daily_pct=5.0, max_loss_pct=10.0, dd_type="static",
         fee=549, fee_refunded=True,  eval_bonus_pct=15.0, split=0.90, min_days=5),
    dict(model="評価型", firm="FundedNext(2022)", plan="Stellar Lite",  size=100000, phases=[8,4],
         daily_pct=4.0, max_loss_pct=8.0,  dd_type="static",
         fee=399, fee_refunded=False, eval_bonus_pct=0.0,  split=0.80, min_days=5),
    dict(model="評価型", firm="The5ers(2016)",    plan="High Stakes",   size=100000, phases=[10,5],
         daily_pct=99.0, max_loss_pct=6.0, dd_type="static",
         fee=495, fee_refunded=False, eval_bonus_pct=0.0,  split=0.80, min_days=3),
    # ---- インスタント(即時資金): テスト無しで即口座。手数料返金なし・DDタイト・口座小さめ ----
    #   phases=[5] は『+5%到達で初回出金』。资金化%=「6%トレ破綻前に+5%到達できる確率」。
    dict(model="インスタント", firm="FundedNext(2022)", plan="Stellar Instant 20k", size=20000, phases=[5],
         daily_pct=99.0, max_loss_pct=6.0, dd_type="trailing",
         fee=599, fee_refunded=False, eval_bonus_pct=0.0, split=0.70, min_days=0),
    dict(model="インスタント", firm="FundedNext(2022)", plan="Stellar Instant 10k", size=10000, phases=[5],
         daily_pct=99.0, max_loss_pct=6.0, dd_type="trailing",
         fee=299, fee_refunded=False, eval_bonus_pct=0.0, split=0.70, min_days=0),
]
# 予算選択の候補(低DDプラン用に低予算も用意)。MARGIN=最大DDに対する安全余裕。
PLAN_BUDGETS = [1.00,0.85,0.75,0.60,0.50,0.40,0.30,0.25,0.20,0.15]

def _maxdd_at(base, usdjpy_h1, wr):
    Pp=copy.deepcopy(P); Pp["WeeklyRiskPct"]=wr
    eq_raw,tdf=portfolio_equity(base,Pp,usdjpy_h1,apply_guards=False)
    if len(eq_raw)==0: return 0.0, 0.0, 0.0
    _,dd=max_drawdown(eq_raw,P["InitialBalance"])
    net=(eq_raw.iloc[-1]-P["InitialBalance"])/P["InitialBalance"]*100
    return round(dd,2), round(net,2), tdf

def compare_firms(base, usdjpy_h1, span_years):
    print("\n"+"="*96)
    print("【業者プラン比較】安全性の高い老舗業者 × v7(週次予算は各プランの最大DDに収まる最大値を自動選択)")
    print("  方針: 各プランの最大DDに対し安全余裕(margin=max(2.5%, 0.3×最大DD))を取り、")
    print("        その内側に収まる最大の週次予算を選択 → その予算で Phase別MC合格率/失格率/期待値を算出。")
    print("="*96)
    # 予算ごとの全期間maxDD/netを1度だけ計算(予算間で使い回し)
    dd_cache={wr:_maxdd_at(base,usdjpy_h1,wr) for wr in PLAN_BUDGETS}
    hdr=(f"{'型':<6}{'業者/プラン':<28}{'予算%':>6}{'10yDD%':>7}{'枠DD':>6}{'P1%':>6}{'P2%':>6}"
         f"{'到達%':>6}{'試行':>5}{'到達月':>6}{'期待手数料$':>10}{'月収益$':>8}{'回収月':>6}")
    print(hdr); print("-"*len(hdr))
    results=[]
    for pl in PLANS:
        ml=pl["max_loss_pct"]; margin=max(2.5, 0.30*ml); cap=ml-margin
        # capを満たす最大予算(降順で最初にcap以下になるもの)
        chosen=None
        for wr in PLAN_BUDGETS:
            dd,net,_=dd_cache[wr]
            if dd<=cap: chosen=wr; chosen_dd=dd; chosen_net=net; break
        if chosen is None:
            wr=PLAN_BUDGETS[-1]; chosen=wr; chosen_dd,chosen_net,_=dd_cache[wr]
        Pp=copy.deepcopy(P); Pp["WeeklyRiskPct"]=chosen; Pp["MaxLossLimitPct"]=ml; Pp["DailyStopPct"]=min(pl["daily_pct"],4.0)
        # Phase別MC(各フェーズ目標で先着判定)
        p_pass=1.0; tot_weeks=0.0; phase_rates=[]; fails=[]
        for i,tgt in enumerate(pl["phases"]):
            mc=block_mc(base,Pp,usdjpy_h1,target_pct=float(tgt),seed=MC_SEED+i)
            phase_rates.append(mc["pass_rate"]); fails.append(mc["fail_rate"])
            p_pass*=mc["pass_rate"]/100.0
            tot_weeks+=(mc["med_weeks"] or 0)
        funded_pct=round(p_pass*100,1)
        attempts=round(1.0/p_pass,2) if p_pass>0 else 999
        months_to_fund=round(tot_weeks/4.345,1) if tot_weeks>0 else None
        # 期待手数料(資金化までに払う総額)。返金は合格分の手数料を1回戻す。
        exp_fee=pl["fee"]*attempts if p_pass>0 else None
        net_fee_cost=(pl["fee"]*(attempts-(1.0 if pl["fee_refunded"] else 0.0))) if p_pass>0 else None
        # 資金化後の月次期待収益(=10y raw net を年率化×分配×口座サイズ)。netは予算に線形。
        monthly_net_pct=chosen_net/(span_years*12.0)
        monthly_payout=monthly_net_pct/100.0*pl["size"]*pl["split"]
        # eval合格ボーナス(FundedNext: eval利益の15%)。eval利益≈最終フェーズ目標%。
        eval_bonus=pl["eval_bonus_pct"]/100.0*(pl["phases"][-1]/100.0)*pl["size"]
        recoup_months=round((net_fee_cost-eval_bonus)/monthly_payout,1) if (monthly_payout>0 and net_fee_cost is not None and (net_fee_cost-eval_bonus)>0) else 0.0
        results.append(dict(model=pl["model"],size=pl["size"],firm=pl["firm"],plan=pl["plan"],budget=chosen,dd=chosen_dd,max_loss=ml,
                            p1=phase_rates[0],p2=(phase_rates[1] if len(phase_rates)>1 else None),
                            funded_pct=funded_pct,attempts=attempts,months_to_fund=months_to_fund,
                            exp_fee=round(exp_fee) if exp_fee else None,monthly_payout=round(monthly_payout),
                            recoup_months=recoup_months,fail1=fails[0],fee=pl["fee"],
                            refunded=pl["fee_refunded"],split=pl["split"]))
        p2s=f"{phase_rates[1]:>6}" if len(phase_rates)>1 else f"{'—':>6}"
        mdl="即時" if pl["model"]=="インスタント" else "評価"
        print(f"{mdl:<6}{pl['firm']+'/'+pl['plan']:<28}{chosen:>6.2f}{chosen_dd:>7.2f}{ml:>6.0f}"
              f"{phase_rates[0]:>6}{p2s}{funded_pct:>6}{attempts:>5}"
              f"{str(months_to_fund):>6}{(round(exp_fee) if exp_fee else 0):>10}{round(monthly_payout):>8}{recoup_months:>6}")
    print("-"*len(hdr))
    # 推奨: 資金化%が高く・期待手数料が低く・回収月が短いプラン
    valid=[r for r in results if r["funded_pct"]>0]
    if valid:
        best=max(valid, key=lambda r:(r["funded_pct"]/max(1,r["recoup_months"] or 1)))
        print(f"\n>>> v7に最も相性が良いプラン: 【{best['firm']} / {best['plan']}】")
        print(f"    週次予算 {best['budget']}%(10y全期間DD {best['dd']}% ≤ 最大{best['max_loss']}%)。")
        print(f"    資金化確率 {best['funded_pct']}%(=平均{best['attempts']}回購入で1回ファンド)。")
        print(f"    到達まで中央 約{best['months_to_fund']}ヶ月 / 期待手数料総額 ${best['exp_fee']}"
              f"{'(合格で返金あり)' if best['refunded'] else '(返金なし)'}。")
        print(f"    ファンド後 月次期待収益 ≈ ${best['monthly_payout']}(分配{int(best['split']*100)}%後) → 期待手数料の回収 約{best['recoup_months']}ヶ月。")
    print("\n  ★読み方:")
    print("   ・型『評価』=チャレンジ合格→ファンド。『即時』=テスト無しで即口座(インスタント)。")
    print("   ・『到達%』= 評価型は『Phase合格率の積(=資金化確率)』。即時は『6%トレ破綻前に+5%到達し初回出金できる確率』。")
    print("   ・『試行』= 到達に必要な平均購入回数(=1/到達%)。失敗/破綻分の手数料は埋没。")
    print("   ・『期待手数料$』= 到達までに払う手数料総額の期待値(= 1回手数料×試行)。即時は返金なしで全額コスト。")
    print("   ・『回収月』= ファンド後の月次期待収益で、払った手数料(返金/eval賞与控除後)を取り戻す月数。")
    print("   ・『月収益$』『回収月』は口座サイズに比例 → 即時は口座が小さい($10-20k)ため評価型($100k)より絶対額は小さい。")
    print("\n  ★評価型 vs インスタント(v7視点):")
    print("   - 評価型10%静的枠(FTMO/FN 2-Step): DDに余裕→予算を取れ到達速い・手数料返金=本命。")
    print("   - インスタント(6%トレDD・返金なし): 即トレード/最短出金は利点だが、v7のDDに対しタイトで")
    print("     破綻確率が上がり、手数料も埋没。口座も小さい→絶対回収額は小。v7とは相性が悪め。")
    print("   ⚠ 手数料/分配/口座サイズは2026概算。最新値をPLANSに入れて再実行で精度UP。staticDD枠は表より実pass率は高めに出る(block_mcはpeak基準で保守的)。")
    return results

def run():
    usdjpy_h1=H1("USDJPY")
    base=build_all_shots(P)
    base=attach_usd_conv(base, usdjpy_h1)
    span=(base["ent_time"].max()-base["ent_time"].min()).days/365.25
    print(f"総ショット {len(base)} / 期間 {span:.1f}年 / ペア{PAIRS}×時刻{HOURS}")
    out={"meta":dict(n_shots=len(base), span_years=round(span,1), mc_horizon_weeks=MC_HORIZON_WEEKS, mc_paths=MC_PATHS),"sweep":[]}
    print(f"\n{'予算%':>6} {'純益%':>8} {'maxDD%':>8} {'年次最悪%':>9} {'通しP1':>7} {'P1合格%':>7} {'P1失格%':>7} {'P1中央月':>8} {'P2合格%':>7} {'通算合格%':>8}")
    for wr in BUDGETS:
        Pp=copy.deepcopy(P); Pp["WeeklyRiskPct"]=wr
        eq_raw,tdf_raw=portfolio_equity(base,Pp,usdjpy_h1,apply_guards=False)
        net=round((eq_raw.iloc[-1]-P["InitialBalance"])/P["InitialBalance"]*100,2) if len(eq_raw) else 0
        _,dd=max_drawdown(eq_raw,P["InitialBalance"]); yw=yearly_worst_dd(tdf_raw,P["InitialBalance"])
        _,tdf_g=portfolio_equity(base,Pp,usdjpy_h1,apply_guards=True)
        ph,_=phase1_path(tdf_g,Pp)
        mc1=block_mc(base,Pp,usdjpy_h1)                        # Phase1: +8%
        mc2=block_mc(base,Pp,usdjpy_h1,target_pct=Pp["ProfitTargetPct"]*0+5.0, seed=MC_SEED+1)  # Phase2: +5%
        combined=round(mc1["pass_rate"]*mc2["pass_rate"]/100.0,1)
        comb_med_months=round(((mc1["med_weeks"] or 0)+(mc2["med_weeks"] or 0))/4.345,1) if (mc1["med_weeks"] and mc2["med_weeks"]) else None
        row=dict(weekly_pct=wr, net_pct=net, maxDD_pct=round(dd,2), yearly_worst_pct=yw,
                 single_path_phase1=ph, phase1={f"{k}":v for k,v in mc1.items()},
                 phase2={f"{k}":v for k,v in mc2.items()},
                 combined_pass_pct=combined, combined_median_months=comb_med_months)
        out["sweep"].append(row)
        print(f"{wr:>6.2f} {net:>8.1f} {dd:>8.2f} {yw:>9.2f} {ph:>7} {mc1['pass_rate']:>7} {mc1['fail_rate']:>7} {str(mc1['med_months']):>8} {mc2['pass_rate']:>7} {combined:>8}")
    # ★推奨ロジック: FundedNextは時間無制限ゆえ「未決(horizon内未到達)」は失格でなく"遅いだけ"。
    #   よって (1)全期間maxDD<=7%(−10%に3%マージン) かつ (2)MC失格率<=5%(DD抵触を稀に) を満たす中で
    #   (3)MC合格率最大(=最も速い) の予算を選ぶ。安全を確保した上で到達速度を最大化。
    SAFE_DD=7.0; MAX_FAIL=5.0
    safe=[r for r in out["sweep"] if r["maxDD_pct"]<=SAFE_DD and r["phase1"]["fail_rate"]<=MAX_FAIL]
    rec=max(safe, key=lambda r:r["phase1"]["pass_rate"]) if safe else None
    out["recommendation"]=rec; out["rule"]=dict(safe_maxDD_pct=SAFE_DD, max_fail_pct=MAX_FAIL)
    print(f"\n>>> 推奨(全期間maxDD<={SAFE_DD}% かつ Phase1失格率<={MAX_FAIL}% の中で 合格率最大=最速):")
    if rec:
        p1=rec["phase1"]
        print(f"    週次予算 {rec['weekly_pct']}%  (全期間maxDD {rec['maxDD_pct']}% / 年次最悪 {rec['yearly_worst_pct']}%)")
        print(f"    Phase1: 合格{p1['pass_rate']}% / 失格{p1['fail_rate']}% / 到達中央 {p1['med_weeks']}週≈{p1['med_months']}ヶ月 (p25-p75: {p1['p25_weeks']}-{p1['p75_weeks']}週)")
        print(f"    通算(Phase1×2): 合格{rec['combined_pass_pct']}% / 中央 約{rec['combined_median_months']}ヶ月")
        # ★実ロット枚数を推奨予算で算出
        Pr=copy.deepcopy(P); Pr["WeeklyRiskPct"]=rec["weekly_pct"]
        lots=typical_lots(base,Pr,usdjpy_h1); out["lots_at_recommendation"]=lots
        print(f"\n    ◆実ロット(週次予算{rec['weekly_pct']}% / 1ショット={lots.get('_per_shot_risk_pct')}%=${lots.get('_risk_usd_per_shot')}):")
        for pair in PAIRS:
            if pair in lots:
                d=lots[pair]; print(f"      {pair}: 中央 {d['med_lots']}lot (10-90%帯 {d['lot_p10_p90']}) / 典型ストップ {d['med_stop_pips']}pips")
    else:
        print("    該当なし → さらに低予算を BUDGETS に追加。")
    print(f"    ★解釈: 『未決(horizon内未到達)』は失格でなく『時間無制限なら最終到達=遅いだけ』。失格率だけが本当の不合格。")
    print(f"    既定0.60の妥当性: 上表0.60行の maxDD が −10%に十分マージン・失格率~0・到達月数が現実的かを確認。")
    print(f"    (10年で1.5%は maxDD~14.8%/失格17%付近になり SAFE_DD で除外される想定。)")
    # ★業者プラン比較シミュレーション
    out["firm_compare"]=compare_firms(base, usdjpy_h1, span)
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/v7_budget_resize.json") if USE_DRIVE else "research/results/v7_budget_resize.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run()
