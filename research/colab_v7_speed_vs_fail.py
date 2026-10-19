"""
colab_v7_speed_vs_fail.py — v7【あなたのFN Stellar 2-Step口座】速度×失格率トレードオフ確定スクリプト。

目的: 「失敗率を上げてでも◯ヶ月で審査到達させたい」という要望に答える。
  あなたの実プラン = FundedNext Stellar 2-Step (P1 +8% / P2 +5% / 最大DD10% / 手数料$549返金+eval賞与15% / 分配90%)。
  週次予算(リスク%)を SPEED_BUDGETS で振り、予算ごとに
    (1) 全期間maxDD% / 年次最悪DD% / 1ショットrisk$        ← 破綻余地(−10%まで)の実測
    (2) Phase1(+8%) 合格%/失格%/到達月(中央&25-75%帯)        ← 速度と破綻確率のトレードオフ本体
    (3) Phase2(+5%) 合格%/到達月、通算(funded)合格%/到達月
    (4) 期待購入回数 / 純手数料コスト(失敗分は埋没・成功で返金)  ← 速度を買うコストの期待値
  を一覧し、『約N ヶ月で到達』に必要な予算と、その時の失格率・手数料コストを提示する。

★現在地: あなたの口座は残高 CURRENT_EQUITY(既定$98,465.70=開始から−1.53%)。
  P1目標$108,000まで残り REMAIN_PCT を併記(MCは新規スタート基準=ほぼ現在地と同等)。

⚠ 重大注意: 本ノートのデータが約2.8年だと数値は楽観側。あなたが確認済みの通り【10年だとDDは約3倍】。
  → 高予算(週次2%超)は10年実データでDDが−10%を超え"ほぼ確実に破綻"。3ヶ月ETAは短期相場前提のギャンブル。
  必ずDriveの10年H1で再実行し、各予算の全期間maxDDが10%に十分マージンを持つか確認すること。
  これはシミュレーション(将来保証ではない)。最終判定はデモ前進検証で。
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


# ============================================================================
# 速度×失格率トレードオフ分析(FundedNext Stellar 2-Step / v7)
#   ★手数料/分配/賞与は2026概算。購入画面の最新値で FN_* を必ず更新して再実行。
# ============================================================================
SPEED_BUDGETS = [0.4, 0.5, 0.6, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]  # 週次リスク%スイープ(1%未満=DD安全帯も探索)
TARGET_MONTHS = 3.0          # ★狙いたい到達月数(これに最も近い"DD安全"予算を強調表示)
DD_MARGIN     = 3.0          # −10%上限への安全余裕%。全期DD<=(FN_MAXLOSS-DD_MARGIN) を"安全(OK)"と判定

# --- あなたの実プラン(FundedNext Stellar 2-Step) ---
FN_P1_PCT     = 8.0          # Phase1 利益目標%
FN_P2_PCT     = 5.0          # Phase2 利益目標%
FN_MAXLOSS    = 10.0         # 最大損失%(static; block_mcはpeak基準=保守的)
FN_DAILY      = 4.0          # 当日上限(ガード)
FN_FEE        = 549          # 1回手数料$(合格で返金)
FN_REFUND     = True         # 合格時 手数料返金
FN_BONUS_PCT  = 15.0         # eval賞与(資金化時の追加)%
FN_SPLIT      = 0.90         # 利益分配(トレーダー取り分)
FN_SIZE       = 100000       # 口座サイズ$

# --- あなたの現在地(スクショ反映。残高を変えれば残り%が再計算される) ---
CURRENT_EQUITY = 98465.70    # 現在残高$(=開始$100,000から−1.53%)

def _fmt_m(w):  # 週→月
    return round(w/4.345,1) if w else None

def run_speed_vs_fail():
    usdjpy=H1("USDJPY")
    base=build_all_shots(P); base=attach_usd_conv(base, usdjpy)
    span=(base["ent_time"].max()-base["ent_time"].min()).days/365.25
    p1_target_usd=FN_SIZE*(1+FN_P1_PCT/100.0)
    remain_pct=(p1_target_usd-CURRENT_EQUITY)/CURRENT_EQUITY*100.0
    print("="*112)
    print("【速度×失格率トレードオフ】FundedNext Stellar 2-Step × v7  (週次予算を上げると速いが失格率↑)")
    print(f"  データ期間 {span:.2f}年 / ショット{len(base)} / ペア{PAIRS}×時刻{HOURS}")
    print(f"  現在残高 ${CURRENT_EQUITY:,.2f} → P1目標 ${p1_target_usd:,.0f}(+{FN_P1_PCT:.0f}%) まで残り +{remain_pct:.2f}%(MCは新規スタート基準≈現在地)")
    print(f"  プラン: P1+{FN_P1_PCT:.0f}%/P2+{FN_P2_PCT:.0f}% 最大DD{FN_MAXLOSS:.0f}% 手数料${FN_FEE}{'(返金)' if FN_REFUND else '(返金なし)'} 賞与{FN_BONUS_PCT:.0f}% 分配{int(FN_SPLIT*100)}%")
    print("="*112)
    safe_dd=FN_MAXLOSS-DD_MARGIN
    print(f"  ★DD判定: 全期間maxDD <= {safe_dd:.0f}%(=−{FN_MAXLOSS:.0f}%上限に{DD_MARGIN:.0f}%余裕) を『OK』、超過は『✕破綻』(10年実シーケンスで−{FN_MAXLOSS:.0f}%抵触リスク)")
    hdr=(f"{'週次%':>6}{'全期DD%':>8}{'判定':>8}{'年最悪%':>8}{'1回risk$':>9}"
         f"{'P1合格%':>8}{'P1失格%':>8}{'P1月(中)':>9}{'P1[25-75]':>13}"
         f"{'P2合格%':>8}{'通算funded%':>11}{'通算月(中)':>10}{'期待購入':>8}{'純手数料$':>10}")
    print(hdr); print("-"*len(hdr))
    out={"meta":dict(span_years=round(span,2), n_shots=len(base), mc_paths=MC_PATHS,
                     mc_horizon_weeks=MC_HORIZON_WEEKS, current_equity=CURRENT_EQUITY,
                     p1_target_usd=p1_target_usd, remain_pct=round(remain_pct,2),
                     plan=dict(p1=FN_P1_PCT,p2=FN_P2_PCT,maxloss=FN_MAXLOSS,fee=FN_FEE,
                               refund=FN_REFUND,bonus_pct=FN_BONUS_PCT,split=FN_SPLIT,size=FN_SIZE)),
         "sweep":[]}
    rows=[]
    for wr in SPEED_BUDGETS:
        Pp=copy.deepcopy(P); Pp["WeeklyRiskPct"]=wr
        Pp["MaxLossLimitPct"]=FN_MAXLOSS; Pp["DailyStopPct"]=min(FN_DAILY,4.0)
        eq_raw,tdf=portfolio_equity(base,Pp,usdjpy,apply_guards=False)
        _,dd=max_drawdown(eq_raw,P["InitialBalance"]); yw=yearly_worst_dd(tdf,P["InitialBalance"])
        risk=FN_SIZE*(wr/Pp["ShotsPerWeek"])/100.0
        mc1=block_mc(base,Pp,usdjpy,target_pct=float(FN_P1_PCT),seed=MC_SEED+1)
        mc2=block_mc(base,Pp,usdjpy,target_pct=float(FN_P2_PCT),seed=MC_SEED+2)
        funded=round(mc1["pass_rate"]*mc2["pass_rate"]/100.0,1)
        comb_m=_fmt_m((mc1["med_weeks"] or 0)+(mc2["med_weeks"] or 0)) if (mc1["med_weeks"] and mc2["med_weeks"]) else None
        # 期待値: 1口座funded到達まで平均購入回数=100/funded。成功1回分は返金、失敗分は埋没。
        exp_buys=round(100.0/funded,2) if funded>0 else None
        net_fee=round((exp_buys-1)*FN_FEE) if (exp_buys and FN_REFUND) else (round(exp_buys*FN_FEE) if exp_buys else None)
        p25=_fmt_m(mc1["p25_weeks"]); p75=_fmt_m(mc1["p75_weeks"])
        viable=(dd<=safe_dd); judge="OK" if viable else "✕破綻"
        print(f"{wr:>6.2f}{dd:>8.2f}{judge:>8}{yw:>8.2f}{risk:>9.0f}"
              f"{mc1['pass_rate']:>8}{mc1['fail_rate']:>8}{str(_fmt_m(mc1['med_weeks'])):>9}{('['+str(p25)+'-'+str(p75)+']'):>13}"
              f"{mc2['pass_rate']:>8}{funded:>11}{str(comb_m):>10}{str(exp_buys):>8}{str(net_fee):>10}")
        row=dict(weekly_pct=wr, maxDD_pct=round(dd,2), viable=viable, yearly_worst_pct=yw, risk_usd_per_shot=round(risk),
                 phase1=mc1, phase2=mc2, funded_pct=funded, p1_med_months=_fmt_m(mc1["med_weeks"]),
                 combined_median_months=comb_m, expected_buys=exp_buys, net_fee_cost=net_fee)
        out["sweep"].append(row); rows.append(row)
    # ★速度狙いの予算(target最近)と、DD安全な最速予算を別々に提示
    cand=[r for r in rows if r["p1_med_months"] is not None]
    safe=[r for r in cand if r["viable"]]                       # DD安全(−10%上限に余裕)な予算のみ
    fast_pick=min(cand, key=lambda r:abs(r["p1_med_months"]-TARGET_MONTHS)) if cand else None   # 速度最優先(DD無視)
    # DD安全帯で TARGET に最も近い(=安全な範囲で最速)。無ければ最速の安全予算。
    safe_pick=(min(safe, key=lambda r:abs(r["p1_med_months"]-TARGET_MONTHS)) if safe else None)
    safe_fastest=(min(safe, key=lambda r:r["p1_med_months"]) if safe else None)
    target_viable=(fast_pick is not None and fast_pick["viable"])
    out.update(target_months=TARGET_MONTHS, pick_for_target=fast_pick,
               safe_pick=safe_pick, safe_fastest=safe_fastest, safe_dd=safe_dd, target_viable=target_viable)

    def _detail(label, r):
        if not r: print(f"\n>>> {label}: 該当なし"); return
        p=r["phase1"]; bust=round(100.0/p["fail_rate"],1) if p["fail_rate"]>0 else None
        flag="OK(DD安全)" if r["viable"] else f"✕破綻(全期DD {r['maxDD_pct']}%>−{FN_MAXLOSS:.0f}%)"
        print(f"\n>>> {label}: 週次{r['weekly_pct']}%  [{flag}]")
        print(f"    Phase1到達 中央 約{r['p1_med_months']}ヶ月 (1ショット約${r['risk_usd_per_shot']}) / MC失格率 {p['fail_rate']}%(≈{bust}回に1回)")
        print(f"    全期間maxDD {r['maxDD_pct']}% / 年最悪 {r['yearly_worst_pct']}% / 通算funded {r['funded_pct']}% / 通算到達中央 約{r['combined_median_months']}ヶ月")
        print(f"    速度を買うコスト: 期待購入 {r['expected_buys']}回 → 純手数料 約${r['net_fee_cost']}")
        Pr=copy.deepcopy(P); Pr["WeeklyRiskPct"]=r["weekly_pct"]; lots=typical_lots(base,Pr,usdjpy)
        out.setdefault("lots",{})[str(r["weekly_pct"])]=lots
        print(f"    ◆実ロット(1ショット=${lots.get('_risk_usd_per_shot')}): " +
              " / ".join(f"{pr} {lots[pr]['med_lots']}lot@{lots[pr]['med_stop_pips']}pips" for pr in PAIRS if pr in lots))

    print("\n"+"="*112)
    print(f">>> あなたの要望『約{TARGET_MONTHS:.0f}ヶ月でPhase1到達』への回答:")
    if fast_pick and not fast_pick["viable"]:
        print(f"    ★{TARGET_MONTHS:.0f}ヶ月に必要な週次{fast_pick['weekly_pct']}%は【全期間DD {fast_pick['maxDD_pct']}% ≫ −{FN_MAXLOSS:.0f}%上限】=10年実データでは口座が破綻。")
        print(f"      → 『失格率を上げて{TARGET_MONTHS:.0f}ヶ月』は実データ上【ほぼ確実に−10%抵触で口座消滅】。現実には到達不能。")
    _detail(f"(参考)速度最優先={TARGET_MONTHS:.0f}ヶ月狙いの予算※DD無視", fast_pick)
    _detail("◎現実的な最速=DD安全帯で最も速い予算", safe_fastest)
    print("\n  ★読み方:")
    print(f"   ・『判定』=全期間maxDDが−{FN_MAXLOSS:.0f}%上限に{DD_MARGIN:.0f}%余裕を持つか。✕破綻は10年の実シーケンスで−10%に当たる=口座消滅。")
    print("   ・『P1月(中)』=合格する経路の到達月数中央値。予算↑で速いが『全期DD』も比例で増え、ある所で✕破綻に転落。")
    print("   ・『MC失格率』はpeak基準で保守的(FNの−10%はstatic=やや緩い)。但し『全期DD』が上限超なら実口座は確実に破綻。")
    print("   ・『年最悪%』=年単位の最悪DD。10年では毎年この規模の下振れが来る前提で予算を選ぶ。")
    print("\n  ★結論:")
    print(f"   - 【確定(10年実データ)】速度を出す高予算ほど全期DDが−10%上限を突破し、{TARGET_MONTHS:.0f}ヶ月狙いは口座破綻=到達不能。")
    print(f"   - 安全に出せる最速は上記『◎』予算(中央 約{safe_fastest['p1_med_months'] if safe_fastest else '?'}ヶ月)。これ以上速くするとDDが上限を超える。")
    print("   - もっと速くしたいなら『同一の安全予算で複数口座を並行』。1口座を無理させるより全滅リスクを避けて実質短縮できる。")
    print(f"   ⚠ 手数料/分配/賞与は2026概算 → FN_* を購入画面の最新値に更新して再実行で精度UP。これはシミュレーション。")
    try:
        path=(H1_DIR.format(base=DRIVE_BASE)+"/v7_speed_vs_fail.json") if USE_DRIVE else "research/results/v7_speed_vs_fail.json"
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,"w") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str)
        print("保存:",path)
    except Exception as e: print("保存スキップ:",e)
    return out

if __name__=="__main__":
    run_speed_vs_fail()
