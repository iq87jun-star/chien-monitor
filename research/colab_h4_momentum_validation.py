# =====================================================================
# Cell 11+: v4 H4 順張り(トレンド継続)仮説 — 厳格ハーネス検証
# ---------------------------------------------------------------------
# 目的:
#   v3(D1逆張り)は不採用。手元2.8年のプロトでは「同じ4条件を順張り(反転)で
#   読む」とOOS PF>1が一貫して出た(docs/10)。これを長期データ+あなたの
#   既存検証ハーネスで本検定する。合格して初めて v4 EA を書く。
#
# 前提(あなたのノートで既に定義済みの関数をそのまま再利用):
#   P, PAIRS, load_pair, pip_size, _ohlc_arrays, usdjpy_at, resolve_exit,
#   calc_lots, quote_to_usd, CONTRACT, evaluate, show_eval, wilson_lower,
#   usdjpy_d1  ← Cell1〜6で定義されている前提。
#
# このセルが追加するもの:
#   - build_h4_from_h1   : H1→H4リサンプル(MT5のH4境界=4hビン)
#   - compute_signals_h4 : 4条件の票集計。momentum=Trueで符号反転(順張り)
#   - run_backtest_h4    : あなたの run_backtest の忠実コピー。違いは2点だけ→
#                          (1)シグナル足=H4  (2)保有を「日」でなく「時間」で計算
#   - 検証: ベースライン / Hold-Out 75-25 / 年次WF / 順列検定 / 合否ゲート
#
# 注意: H4境界はUTCの4hビン(00,04,08,12,16,20)。実ブローカーのH4が別オフセット
#       の場合は origin を合わせること。最終判断は実運用前提で過信しない。
# =====================================================================
import numpy as np, pandas as pd

# --- H4用パラメータ(Pを継承し、H4向けに上書き) ---
P_H4 = dict(P)
P_H4.update(
    Momentum      = True,     # True=順張り(プロトで芽が出た側) / False=逆張り(=v3のH4移植)
    VotesRequired = 3,        # H4は1本の情報量が小さいのでまずK=3(プロト最良帯)
    RetThreshold  = 0.0025,   # H4リターン閾値(D1の0.5%→0.25%)
    HoldH4Bars    = 12,       # 保有=H4×12(=48時間)。"日"でなく"時間"で効かせる
    MinStopPips   = 6.0,      # H4のATRはD1より小さいので下限を緩める
)

DAY_BOUNDARY_HOUR_UTC = globals().get("DAY_BOUNDARY_HOUR_UTC", 21)

def build_h4_from_h1(h1):
    """H1→H4。UTC4hビンでOHLC集約。spread列があれば平均を引き継ぐ。"""
    agg = dict(open=("open","first"), high=("high","max"),
               low=("low","min"), close=("close","last"))
    if "spread" in h1.columns:
        agg["spread"] = ("spread","mean")
    h4 = h1.resample("4h", label="left", closed="left").agg(**agg)
    return h4.dropna(subset=["open","high","low","close"])

def _rsi_wilder(close, n):
    d=close.diff(); up=d.clip(lower=0.0); dn=(-d).clip(lower=0.0)
    ru=up.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    rd=dn.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    return 100-100/(1+ru/rd.replace(0,np.nan))

def _atr_wilder(df, n):
    h,l,c=df["high"],df["low"],df["close"]; pc=c.shift(1)
    tr=pd.concat([(h-l),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False,min_periods=n).mean()

def compute_signals_h4(h4, P):
    """v3の4条件をH4確定足[1]で評価。Cell3 compute_signals と同ロジック。
       P['Momentum']=True なら最終シグナルの符号を反転(=順張り/トレンド継続)。"""
    c=h4["close"]
    rsi=_rsi_wilder(c, P["RsiPeriod"])
    n=P["BBPeriod"]
    mean=c.shift(1).rolling(n).mean()
    std =c.shift(1).rolling(n).std(ddof=1)
    z=(c-mean)/std
    down=(c<c.shift(1)).astype(int); up=(c>c.shift(1)).astype(int)
    def streak(flag):
        s=[]; run=0
        for v in flag.values:
            run=run+1 if v==1 else 0; s.append(run)
        return pd.Series(s,index=flag.index)
    ds=streak(down); us=streak(up); ret=c.pct_change()
    bv=((rsi<P["RsiBuyLevel"]).astype(int)+(z<-P["BBZThreshold"]).astype(int)
        +(ds>=P["StreakDays"]).astype(int)+(ret<-P["RetThreshold"]).astype(int))
    sv=((rsi>P["RsiSellLevel"]).astype(int)+(z>P["BBZThreshold"]).astype(int)
        +(us>=P["StreakDays"]).astype(int)+(ret>P["RetThreshold"]).astype(int))
    K=P["VotesRequired"]
    sig=pd.Series(0,index=c.index,dtype=int)
    sig[(bv>=K)&(bv>sv)]=1
    sig[(sv>=K)&(sv>bv)]=-1
    if P.get("Momentum"): sig=-sig          # 逆張り条件→順張り(継続)として読む
    return pd.DataFrame({"signal":sig,"atr":_atr_wilder(h4,P["AtrPeriod"])})

def run_backtest_h4(pair, h4, h1, P, usdjpy_d1=None, verbose=False):
    """あなたの run_backtest の忠実コピー。相違点は↓の2行(★)のみ。"""
    sg=compute_signals_h4(h4, P)                                   # ★1 H4順張り
    pip=pip_size(pair); slip=P["SlippagePoints"]*(pip/10.0)
    T,O,H,L,C,S=_ohlc_arrays(h1)
    idx=list(sg.index); sigv=sg["signal"].to_numpy(); atrv=sg["atr"].to_numpy()
    equity=P["InitialBalance"]; trades=[]; eq_curve=[]
    cur_day=None; day_start_eq=equity; trades_today=0; risk_used=0.0
    day_blocked=False; halted=False
    floor_eq=P["InitialBalance"]*(1-P["EquityFloorDDPct"]/100.0)
    target_eq=P["InitialBalance"]*(1+P["ProfitTargetPct"]/100.0)
    for i in range(len(idx)-1):
        t=idx[i]; t_next=idx[i+1]; sig=sigv[i]; atr=atrv[i]
        if cur_day!=t_next.date():
            cur_day=t_next.date(); day_start_eq=equity
            trades_today=0; risk_used=0.0; day_blocked=False
        if equity<=floor_eq: halted=True
        if halted: break
        if equity>=target_eq: break
        if sig==0 or not (atr==atr) or atr<=0: continue
        if day_blocked: continue
        if trades_today>=P["MaxTradesPerDay"]: continue
        if risk_used+P["RiskPerTradePct"]>P["MaxDailyRiskPct"]+1e-9: continue
        a=int(np.searchsorted(T, t_next.to_datetime64(), side="right"))
        if a>=len(T): break
        spread0=S[a] if S[a]==S[a] else pip
        if spread0/pip>P["MaxSpreadPips"]: continue
        sd=P["AtrSLMult"]*atr
        if sd/pip<P["MinStopPips"] or sd/pip>P["MaxStopPips"]: continue
        until=T[a]+np.timedelta64(P["HoldH4Bars"]*4,"h")           # ★2 保有=時間
        b=int(np.searchsorted(T, until, side="right")); b=max(b,a+1)
        ujpy=usdjpy_at(t_next,pair,usdjpy_d1); mid=O[a]
        R,off,why,entry=resolve_exit(int(sig),mid,sd,spread0,slip,O,H,L,C,S,a,b,P)
        lots=calc_lots(equity,sd,pair,mid,ujpy,P)
        if lots<P["MinLot"]: continue
        pnl=R*sd*lots*CONTRACT*quote_to_usd(pair,mid,ujpy)
        equity+=pnl; trades_today+=1; risk_used+=P["RiskPerTradePct"]
        ent_time=pd.Timestamp(T[a]); exit_time=pd.Timestamp(T[a+off])
        eq_curve.append((exit_time,equity))
        trades.append(dict(pair=pair,sig=int(sig),ent_time=ent_time,entry=entry,
            exit_time=exit_time,exit=np.nan,reason=why,lots=lots,
            stop_pips=sd/pip,pnl=pnl,equity=equity,rmultiple=R))
        if equity-day_start_eq <= -P["InitialBalance"]*P["DailyStopPct"]/100.0:
            day_blocked=True
    tdf=pd.DataFrame(trades)
    eqdf=pd.DataFrame(eq_curve,columns=["time","equity"]).set_index("time")
    return tdf, eqdf

print("H4順張りハーネス定義完了。 Momentum =", P_H4["Momentum"],
      " K =", P_H4["VotesRequired"], " hold =", P_H4["HoldH4Bars"], "H4")


# =====================================================================
# Cell 12: 全ペア・全期間ベースライン (H4順張り)
# =====================================================================
h4_results={}; h4_tdf={}; h4_eqdf={}
for pair in PAIRS:
    try:
        d1,h1 = load_pair(pair)                 # d1は使わずh1だけ使う
        h4 = build_h4_from_h1(h1)
        tdf,eqdf = run_backtest_h4(pair, h4, h1, P_H4, usdjpy_d1=usdjpy_d1)
        ev = evaluate(tdf, P_H4, label=f"{pair} 全期間(H4順張り K={P_H4['VotesRequired']})")
        h4_results[pair]=ev; h4_tdf[pair]=tdf; h4_eqdf[pair]=eqdf
        show_eval(ev); print()
    except Exception as e:
        print(f"[{pair}] スキップ:", e)

summary_h4 = pd.DataFrame([{k:v for k,v in r.items() if k!="note"}
                           for r in h4_results.values()])
cols=["label","n","trades_per_year","wr","wilson_lo","wilson_gt_BE","edge_pp",
      "PF","sharpe","max_consec_loss","total_pct","maxDD_pct","DD_to_profit",
      "fundednext_pass"]
if len(summary_h4):
    display(summary_h4[[c for c in cols if c in summary_h4.columns]])


# =====================================================================
# Cell 13: Hold-Out 75/25 (直近25%を完全に伏せてOOS評価)
# =====================================================================
def split_h4(h4, h1, frac=0.75):
    cut=h4.index[int(len(h4)*frac)]
    h4i,h4o = h4[h4.index<=cut], h4[h4.index>cut]
    h1i,h1o = h1[h1.index<=cut], h1[h1.index> (cut - pd.Timedelta(days=10))]
    return (h4i,h1i),(h4o,h1o),cut

ho_rows=[]
for pair in PAIRS:
    try:
        d1,h1=load_pair(pair); h4=build_h4_from_h1(h1)
        (h4i,h1i),(h4o,h1o),cut=split_h4(h4,h1,0.75)
        ti,_=run_backtest_h4(pair,h4i,h1i,P_H4,usdjpy_d1=usdjpy_d1)
        to,_=run_backtest_h4(pair,h4o,h1o,P_H4,usdjpy_d1=usdjpy_d1)
        ei=evaluate(ti,P_H4,f"{pair} IS"); eo=evaluate(to,P_H4,f"{pair} OOS")
        ho_rows.append(dict(pair=pair,cut=str(cut.date()),
            IS_n=ei.get("n",0),IS_PF=ei.get("PF"),IS_pct=ei.get("total_pct"),
            OOS_n=eo.get("n",0),OOS_PF=eo.get("PF"),OOS_pct=eo.get("total_pct"),
            OOS_wlo=eo.get("wilson_lo"),OOS_gtBE=eo.get("wilson_gt_BE"),
            OOS_DDpct=eo.get("maxDD_pct")))
    except Exception as e:
        print(f"[{pair}] HOスキップ:", e)
display(pd.DataFrame(ho_rows))
print("合格の目安: OOS PF>1.2 かつ OOS_n>=30 かつ OOS Wilson下限>BE。")


# =====================================================================
# Cell 14: 年次ローリングWF (レジーム依存=特定年だけで稼いでないか)
# =====================================================================
def yearly_wf_h4(pair, h4, h1, P):
    rows=[]
    for y in sorted(set(h4.index.year)):
        h4y=h4[h4.index.year==y]
        if len(h4y)<200: continue
        h1y=h1[(h1.index.year>=y)&(h1.index<=h4y.index.max()+pd.Timedelta(days=5))]
        t,_=run_backtest_h4(pair,h4y,h1y,P,usdjpy_d1=usdjpy_d1)
        e=evaluate(t,P,f"{pair} {y}")
        rows.append(dict(year=y,n=e.get("n",0),PF=e.get("PF"),
                         pct=e.get("total_pct"),DDpct=e.get("maxDD_pct"),
                         wr=e.get("wr")))
    return pd.DataFrame(rows)

for pair in PAIRS[:3]:
    try:
        d1,h1=load_pair(pair); h4=build_h4_from_h1(h1)
        wf=yearly_wf_h4(pair,h4,h1,P_H4)
        print(f"\n===== {pair} 年次WF(H4順張り) =====")
        display(wf)
        if len(wf):
            pos=(wf["pct"]>0).sum()
            print(f"  プラス年 {pos}/{len(wf)}  年平均件数={wf['n'].mean():.0f}")
    except Exception as e:
        print(f"[{pair}] 年次WFスキップ:", e)


# =====================================================================
# Cell 15: 順列検定 (実Rの合計が「ランダム日エントリー」分布の上位何%か)
#   実トレードのrmultipleを使い、同数・同方向比のトレードをランダムな
#   H4足に置換してn_iter回。実合計R > 帰無分布95%tile なら有意。
# =====================================================================
def permutation_h4(pair, P, n_iter=2000, seed=20260531):
    d1,h1=load_pair(pair); h4=build_h4_from_h1(h1)
    sg=compute_signals_h4(h4,P)
    pip=pip_size(pair); slip=P["SlippagePoints"]*(pip/10.0)
    T,O,H,L,C,S=_ohlc_arrays(h1)
    idx=list(sg.index); atrv=sg["atr"].to_numpy()
    # 全候補H4足について buy(+1)/sell(-1)のRを1回だけ前計算(無条件統計)
    Rb=[]; Rs=[]; cand=[]
    for i in range(len(idx)-1):
        atr=atrv[i]
        if not (atr==atr) or atr<=0: continue
        sd=P["AtrSLMult"]*atr
        if sd/pip<P["MinStopPips"] or sd/pip>P["MaxStopPips"]: continue
        t_next=idx[i+1]
        a=int(np.searchsorted(T,t_next.to_datetime64(),side="right"))
        if a>=len(T): continue
        spread0=S[a] if S[a]==S[a] else pip
        if spread0/pip>P["MaxSpreadPips"]: continue
        until=T[a]+np.timedelta64(P["HoldH4Bars"]*4,"h")
        b=int(np.searchsorted(T,until,side="right")); b=max(b,a+1)
        mid=O[a]
        rb,_,_,_=resolve_exit(+1,mid,sd,spread0,slip,O,H,L,C,S,a,b,P)
        rs,_,_,_=resolve_exit(-1,mid,sd,spread0,slip,O,H,L,C,S,a,b,P)
        Rb.append(rb); Rs.append(rs); cand.append((i,sg["signal"].to_numpy()[i]))
    Rb=np.array(Rb); Rs=np.array(Rs)
    real=[k for k,(i,s) in enumerate(cand) if s!=0]
    n=len(real)
    if n<5: return dict(pair=pair,n=int(n),note="件数<5 検定不能")
    dirs=np.array([cand[k][1] for k in real])
    realR=float(np.where(dirs>0, Rb[real], Rs[real]).sum())
    n_buy=int((dirs>0).sum()); M=len(Rb)
    rng=np.random.default_rng(seed); null=np.empty(n_iter)
    base=np.array([1]*n_buy+[-1]*(n-n_buy))
    for it in range(n_iter):
        pick=rng.choice(M,size=min(n,M),replace=False)
        d=base.copy(); rng.shuffle(d)
        null[it]=np.where(d[:len(pick)]>0, Rb[pick], Rs[pick]).sum()
    p=float((null>=realR).mean())
    return dict(pair=pair,n=int(n),real_totalR=round(realR,2),
                null_mean=round(float(null.mean()),2),
                null_p95=round(float(np.percentile(null,95)),2),
                emp_p=round(p,4),significant_005=(p<0.05))

for pair in PAIRS[:3]:
    try:
        print(f"[{pair}] 順列検定:", permutation_h4(pair,P_H4,n_iter=2000))
    except Exception as e:
        print(f"[{pair}] 順列スキップ:", e)
print("注: n<30ではWilson幅が広く、p<0.05でも実運用再現は別問題。")


# =====================================================================
# Cell 16: 合否ゲート (v4 EAを書いてよいかの自動判定)
#   全て満たせば「v4 EA実装に進む」。1つでも欠ければ見送り or 別エッジ。
# =====================================================================
def decide_v4():
    if not len(summary_h4): print("データ無し"); return
    s=summary_h4
    pass_pairs = s[(s["fundednext_pass"]==True) &
                   (s["wilson_gt_BE"]==True) &
                   (s["PF"]>1.0)]
    oos = pd.DataFrame(ho_rows)
    oos_ok = oos[(oos["OOS_PF"]>1.2)&(oos["OOS_n"]>=30)&(oos["OOS_gtBE"]==True)] if len(oos) else oos
    print("="*60)
    print("v4 合否ゲート")
    print(f"  全期間fundednext合格&Wilson>BE&PF>1 : {len(pass_pairs)}/{len(s)} ペア")
    print(f"  OOS PF>1.2 & n>=30 & Wilson>BE      : {len(oos_ok)}/{len(oos)} ペア")
    go = (len(pass_pairs)>=max(1,int(0.5*len(s)))) and (len(oos_ok)>=max(1,int(0.5*len(oos))))
    print("-"*60)
    print("判定:", "✅ v4 EA実装に進んでよい" if go else
          "❌ 見送り(優位性の確証不足) → 別エッジ探索 or 撤退")
    print("  ※ これは研究判定。実運用前に必ずフォワード/デモで再確認。")
decide_v4()
