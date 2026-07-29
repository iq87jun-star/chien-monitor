"""
colab_oss_ea_validation.py — OSS公開ロジック2候補のTier A検証(docs/187 事前登録に従う)。

位置づけ: docs/186 で「買うEA」を棄却し、ロジック全文が読める OSS 候補のみを
  Tier A(自前再実装→実データBT→ゲート判定)に載せると決めた。その実行スクリプト。
  ⚠ 実行前に docs/187(事前登録)を読むこと。パラメータは登録値で凍結済み。
  探索(パラメータいじり)をした場合は多重検定割引をやり直す義務がある(docs/165)。

候補(ロジック出所は docs/187 に記録):
  C1: Donchian Trend Engine 型 — N本ドンチャン終値ブレイク+ATRハードSL+ATRトレール+時間切れ決済。
      原典: USDJPY H1 実ティック9.4年 WR34.5%/PF1.50/DD10.3%(631取引)。
      原典パラメータ非公開分は登録値で固定: N∈{20,55}(2案のみ), SL=2.0×ATR14,
      trail=2.5×ATR14, timeout=48本, リスク0.5%/取引。
  C2: GOLD_ORB 型 — XAUUSD H1 の当日オープニングレンジ(最初の1本+3本確定)ブレイク。
      SL=400pt/TP=1200pt/トレール(+700pt起動,100pt刻み), リスク1%/取引,
      1日 long1+short1 まで, equity DD 10% ブレーカー。

ゲート(docs/187 登録・全通過で「デモ前進検証候補」へ。1つでも落ちれば棄却):
  G1 PF≥1.30(コスト込) / G2 maxDD≤8%(equity) / G3 LOYO 負け年≤2 /
  G4 コスト2倍で PF>1.10 / G5 プラセボ(トレード符号シャッフル2000回, p<0.05) /
  G6 自ポートフォリオ月次との相関 |ρ|<0.30(Driveに月次があれば。無ければ保留印)

使い方(Colab): USE_DRIVE=True。H1_DIR に USDJPY_h1.csv / XAUUSD_h1.csv(10年, UTC)。
  「すべて実行」。結果は research/results/oss_ea_validation.json 形式で出力。
※ シミュレーション。合格しても ADOPT ではなくデモ前進検証(docs/29)が次段。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE=True; DRIVE_BASE="/content/drive/MyDrive/forex_ml"
H1_DIR="{base}/dukascopy_data_h1"; LOCAL_FALLBACK="./research/data"
OWN_MONTHLY="{base}/results/own_portfolio_monthly.csv"   # 任意: t,ret 形式
RNG=np.random.default_rng(20260729)

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e: print("Drive不可:",e)

def _read(path):
    df=pd.read_csv(path); df.columns=[c.strip().lower() for c in df.columns]
    tcol=next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"]=pd.to_datetime(df[tcol],utc=True,errors="coerce"); df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
    cols={}
    for want in ["open","high","low","close"]:
        for c in df.columns:
            if c==want or c==f"bid{want}" or c==want[0]: cols[want]=c; break
    if len(cols)<4: return None
    return df[[cols["open"],cols["high"],cols["low"],cols["close"]]].astype(float)\
             .rename(columns=dict((v,k) for k,v in cols.items()))

def load_h1(sym):
    for p in [f"{H1_DIR.format(base=DRIVE_BASE)}/{sym}_h1.csv", f"{H1_DIR.format(base=DRIVE_BASE)}/{sym}.csv",
              f"{LOCAL_FALLBACK}/{sym}_h1.csv"]:
        if os.path.exists(p):
            df=_read(p)
            if df is not None: print(f"  {sym}: {p} rows={len(df)}"); return df
    print(f"  {sym}: H1データ無し(DriveのH1_DIRに置くこと) → この候補はスキップ"); return None

def atr_w(h,l,c,n=14):
    pc=np.roll(c,1); pc[0]=c[0]; tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)])
    out=np.empty_like(c); out[0]=tr[0]; a=1.0/n
    for i in range(1,len(c)): out[i]=a*tr[i]+(1-a)*out[i-1]
    return out

# ---------------- C1: Donchian Trend Engine 型 (USDJPY H1) ----------------
def run_donchian(df, N, sl_mult=2.0, tr_mult=2.5, timeout=48, risk=0.005,
                 spread=0.012, slip=0.005, cost_mult=1.0, equity0=100_000.0):
    """spread/slip は price 単位(USDJPY: 1.2pips=0.012)。戻り: trades(list of dict), equity curve(月次)"""
    o,h,l,c=(df[k].values for k in ["open","high","low","close"])
    t=df.index; a=atr_w(h,l,c); eq=equity0
    hh=pd.Series(h).rolling(N).max().shift(1).values
    ll=pd.Series(l).rolling(N).min().shift(1).values
    pos=0; entry=stop=0.0; bars=0; ext=0.0; trades=[]; ec={}
    cost=(spread+slip)*cost_mult
    for i in range(N+15,len(c)):
        if pos!=0:
            bars+=1
            if pos>0:
                ext=max(ext,c[i]); stop=max(stop, ext-tr_mult*a[i])
                hit = l[i]<=stop or bars>=timeout
                px = stop if l[i]<=stop else c[i]
            else:
                ext=min(ext,c[i]); stop=min(stop, ext+tr_mult*a[i])
                hit = h[i]>=stop or bars>=timeout
                px = stop if h[i]>=stop else c[i]
            if hit:
                pnl_price=(px-entry)*pos - cost
                risk_price=sl_mult*a_ent
                pnl=eq*risk*(pnl_price/risk_price)
                eq+=pnl; trades.append(dict(t=str(t[i]),pnl=pnl,r=pnl_price/risk_price))
                ec[str(t[i])[:7]]=eq; pos=0
        if pos==0:
            if not np.isnan(hh[i]) and c[i]>hh[i]:
                pos=1; entry=c[i]; a_ent=a[i]; stop=entry-sl_mult*a_ent; ext=entry; bars=0
            elif not np.isnan(ll[i]) and c[i]<ll[i]:
                pos=-1; entry=c[i]; a_ent=a[i]; stop=entry+sl_mult*a_ent; ext=entry; bars=0
    return trades, ec, eq, equity0

# ---------------- C2: GOLD_ORB 型 (XAUUSD H1) ----------------
def run_orb(df, sl_pt=4.00, tp_pt=12.00, tr_act=7.00, tr_step=1.00, risk=0.01,
            spread=0.35, slip=0.10, cost_mult=1.0, equity0=100_000.0, dd_brk=0.10):
    o,h,l,c=(df[k].values for k in ["open","high","low","close"])
    t=df.index; eq=equity0; peak=eq; trades=[]; ec={}
    cost=(spread+slip)*cost_mult
    days=pd.Series(t.date, index=range(len(t)))
    day_start={d:i for i,d in reversed(list(enumerate(days)))}
    pos=0; entry=stop=tp=0.0; done_long=done_short=False; cur_day=None; rh=rl=None; halted=False
    for i in range(len(c)):
        d=days[i]
        if d!=cur_day:
            cur_day=d; s=day_start[d]; rh,rl=h[s],l[s]; done_long=done_short=False
            if eq<peak*(1-dd_brk): halted=True   # equity DD ブレーカー(以後停止=保守評価)
        k=i-day_start[d]
        if pos!=0:
            if pos>0:
                if c[i]-entry>=tr_act: stop=max(stop, c[i]-tr_step)
                hitp = h[i]>=tp; hits = l[i]<=stop
                px = tp if hitp else (stop if hits else None)
            else:
                if entry-c[i]>=tr_act: stop=min(stop, c[i]+tr_step)
                hitp = l[i]<=tp; hits = h[i]>=stop
                px = tp if hitp else (stop if hits else None)
            if px is not None:
                pnl_price=(px-entry)*pos - cost
                pnl=eq*risk*(pnl_price/sl_pt)
                eq+=pnl; peak=max(peak,eq); trades.append(dict(t=str(t[i]),pnl=pnl,r=pnl_price/sl_pt))
                ec[str(t[i])[:7]]=eq; pos=0
        if pos==0 and not halted and k>=3 and rh is not None:
            if not done_long and c[i]>rh:
                pos=1; entry=c[i]; stop=entry-sl_pt; tp=entry+tp_pt; done_long=True
            elif not done_short and c[i]<rl:
                pos=-1; entry=c[i]; stop=entry+sl_pt; tp=entry-tp_pt; done_short=True
    return trades, ec, eq, equity0

# ---------------- ゲート判定 ----------------
def gates(name, trades, ec, eq_end, eq0, trades2x):
    if not trades: return dict(name=name, verdict="NO-TRADES")
    pnl=np.array([x["pnl"] for x in trades])
    win=pnl[pnl>0].sum(); loss=-pnl[pnl<0].sum()
    pf=win/loss if loss>0 else np.inf
    curve=np.array(list(ec.values())); peak=np.maximum.accumulate(curve)
    dd=((peak-curve)/peak).max() if len(curve) else 1.0
    years=pd.Series(pnl, index=pd.to_datetime([x["t"] for x in trades],utc=True)).groupby(lambda i:i.year).sum()
    losing=(years<0).sum()
    p2=np.array([x["pnl"] for x in trades2x]); w2=p2[p2>0].sum(); l2=-p2[p2<0].sum()
    pf2=w2/l2 if l2>0 else np.inf
    # プラセボ: 符号シャッフル
    obs=pnl.sum(); cnt=0
    for _ in range(2000):
        if (np.abs(pnl)*RNG.choice([-1,1],len(pnl))).sum()>=obs: cnt+=1
    pval=cnt/2000
    g=dict(G1_PF=(float(round(float(pf),3)), bool(pf>=1.30)),
           G2_DD=(float(round(float(dd),4)), bool(dd<=0.08)),
           G3_LOYO_losing_years=(int(losing), bool(losing<=2)),
           G4_cost2x_PF=(float(round(float(pf2),3)), bool(pf2>1.10)),
           G5_placebo_p=(float(round(pval,4)), bool(pval<0.05)))
    ok=all(v[1] for v in g.values())
    return dict(name=name, n_trades=int(len(trades)), total_return=float(round(float(eq_end)/eq0-1,4)),
                yearly={int(k):float(round(float(v),0)) for k,v in years.items()},
                gates=g, verdict="→デモ前進検証候補(G6相関は別途)" if ok else "REJECT")

def main():
    print("="*88); print("OSS EA Tier A 検証(docs/187 登録ゲート)"); print("="*88)
    out={"prereg":"docs/187","results":[]}
    dj=load_h1("USDJPY")
    if dj is not None:
        for N in (20,55):
            tr,ec,eqe,eq0=run_donchian(dj,N)
            tr2,_,_,_=run_donchian(dj,N,cost_mult=2.0)
            r=gates(f"C1_Donchian_N{N}",tr,ec,eqe,eq0,tr2); out["results"].append(r)
            print(json.dumps(r,ensure_ascii=False,indent=1))
    gx=load_h1("XAUUSD")
    if gx is not None:
        tr,ec,eqe,eq0=run_orb(gx)
        tr2,_,_,_=run_orb(gx,cost_mult=2.0)
        r=gates("C2_GOLD_ORB",tr,ec,eqe,eq0,tr2); out["results"].append(r)
        print(json.dumps(r,ensure_ascii=False,indent=1))
    # G6: 自ポートフォリオ相関(月次があれば)
    om=OWN_MONTHLY.format(base=DRIVE_BASE)
    print("\nG6 相関判定:", "own_portfolio_monthly.csv 検出 → 手動確認" if os.path.exists(om)
          else "自ポートフォリオ月次CSVなし → G6保留(合格候補もADOPT禁止のまま)")
    os.makedirs("research/results",exist_ok=True)
    with open("research/results/oss_ea_validation.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    print("\n保存: research/results/oss_ea_validation.json → docs/188(結果)に転記のこと")

main()
