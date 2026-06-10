# -*- coding: utf-8 -*-
"""edge10 — 10年H1 日中構造エッジ探索（事前登録 docs/72）。

確認的仮説（ADOPT判定に使用, N_conf=4 → Bonferroni α=0.0125）:
  H1_gapfade6   月曜窓の週末ギャップを fade, hold 6h
  H2_gapfadeEOD 同上, hold 24h
  H3_tokyofix   23:00 UTC LONG, hold 4h（東京仲値フロー）
  H4_londonfix  14:00 UTC LONG, hold 4h（ロンドン16:00 fix）
探索的スキャン（参考のみ・採否に不使用）: 時刻0..23 × {L,S} の無条件ドリフト。

統計関数は colab_validate_all_v7standard.py を逐語流用。ローダ/コストは colab_v7_confidence.py 準拠。
実データ未配置時は EDGE10_SELFTEST=1 で合成H1を生成し、エンジンの健全性のみ自己テストする
（埋め込みドリフトを検出/ノイズで非有意 を確認。実数値は必ず Dukascopy 実行で出す）。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

# ---------- 設定 ----------
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"
PAIRS  = ["EURJPY", "GBPJPY", "USDJPY"]
RISK   = 0.006        # 1ショットのリスク予算（=フルSLで約 -0.6%）
SEED   = 13
N_PATHS = 2000
COST_EXTRA_PIP = 0.0  # spread/slip はエンジンで反映済（2×コストは出口spreadを倍化）
BONF_N = {"H1_gapfade6": 4, "H2_gapfadeEOD": 4, "H3_tokyofix": 4, "H4_londonfix": 4}

P = dict(AtrPeriodH1=24, CatastropheATR=2.5, MinStopPips=10.0, MaxStopPips=400.0,
         MaxSpreadPips=3.0, SlippagePoints=20)

def pip_size(p):   return 0.01 if p.endswith("JPY") else 0.0001
def point_size(p): return 0.001 if p.endswith("JPY") else 0.00001

# ---------- ローダ（colab_v7_confidence.py 準拠） ----------
def _resolve(pair):
    b = H1_DIR.format(base=DRIVE_BASE)
    for x in [f"{b}/{pair}_h1.csv", f"{b}/{pair}.csv",
              f"{LOCAL_FALLBACK}/{pair}_h1.csv", f"{LOCAL_FALLBACK}/{pair}.csv"]:
        if os.path.exists(x): return x
    return None

def _synth_h1(pair, seed):
    """自己テスト用合成H1。乱歩 + 埋め込み(23時LONGドリフト & 週末ギャップ回帰)。"""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2016-01-04", "2025-12-31 23:00", freq="h", tz="UTC")
    idx = idx[idx.dayofweek < 5]                          # 平日のみ
    n = len(idx); pip = pip_size(pair)
    step = rng.normal(0, 6*pip, n)                        # ~6pip/h ボラ
    step[idx.hour == 23] += 1.2*pip                       # ★埋め込み: 23時にLONGドリフト
    base = 110.0 if pair.endswith("JPY") else 1.3
    close = base + np.cumsum(step)
    # 週末ギャップ + 部分回帰を埋め込む
    is_mon_first = (idx.dayofweek == 0) & (pd.Series(idx.hour).values <
                                           np.r_[24, idx.hour[:-1]])  # 簡易: 週初
    gap = rng.normal(0, 30*pip, n) * is_mon_first
    close = close + np.cumsum(-0.4*gap)                   # ★ギャップの40%が後で回帰
    close = close + gap                                   # 当該足にギャップ自体を乗せる
    o = close - step; h = np.maximum(o, close) + np.abs(rng.normal(0, 3*pip, n))
    l = np.minimum(o, close) - np.abs(rng.normal(0, 3*pip, n))
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": close,
                       "spread": 1.2*pip}, index=idx)
    return df

def load_pair(pair):
    if os.environ.get("EDGE10_SELFTEST") == "1" and _resolve(pair) is None:
        return _synth_h1(pair, SEED + hash(pair) % 1000)
    path = _resolve(pair)
    if path is None:
        raise FileNotFoundError(f"{pair} H1 CSV 未検出。{H1_DIR.format(base=DRIVE_BASE)}/{pair}_h1.csv を確認")
    df = pd.read_csv(path); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time","timestamp","date","datetime","gmt time"] if c in df.columns), df.columns[0])
    df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def pick(*n):
        for x in n:
            if x in df.columns: return x
        return None
    o,h,l,c = pick("open","bidopen","o"),pick("high","bidhigh","h"),pick("low","bidlow","l"),pick("close","bidclose","c")
    out = pd.DataFrame(index=df.index)
    out["open"]=df[o].astype(float); out["high"]=df[h].astype(float)
    out["low"]=df[l].astype(float);  out["close"]=df[c].astype(float)
    ac=pick("askclose","ask_close","ask"); sp=pick("spread")
    if sp: out["spread"]=df[sp].astype(float)
    elif ac: out["spread"]=(df[ac].astype(float)-out["close"]).clip(lower=0)
    else: out["spread"]=1.0*pip_size(pair)
    return out.dropna(subset=["open","high","low","close"])

_CACHE = {}
def H1(p):
    if p not in _CACHE: _CACHE[p] = load_pair(p)
    return _CACHE[p]

def atr_wilder(df, period):
    h,l,c = df["high"],df["low"],df["close"]; pc=c.shift(1)
    tr = pd.concat([(h-l),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()

# ---------- 統計（colab_validate_all_v7standard.py 逐語） ----------
def perm_p(s,n=4000,seed=13):
    r=pd.Series(s).dropna().values
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); a=np.abs(r)
    return float((np.array([(a*rng.choice([-1,1],size=len(a))).sum() for _ in range(n)])>=real).mean())
def stat(s,ann):
    s=pd.Series(s).dropna()
    if len(s)==0: return dict(net=0.0,Sharpe=0.0,maxDD=0.0,Calmar=0.0,n=0)
    eq=(1+s).cumprod(); dd=float(((eq-eq.cummax())/eq.cummax()).min())*100
    mu=s.mean()*ann; vol=s.std()*np.sqrt(ann); shp=mu/vol if vol>0 else 0.0
    cagr=(eq.iloc[-1]**(ann/len(s))-1)*100
    return dict(net=round(float((eq.iloc[-1]-1)*100),1),Sharpe=round(float(shp),2),maxDD=round(dd,1),
                Calmar=round(float(cagr/abs(dd)),2) if dd else 0.0,n=int(len(s)))
def jackknife(s):
    s=pd.Series(s).dropna(); yrs=sorted(set(s.index.year))
    if len(yrs)<3: return None
    return round(max(perm_p(s[s.index.year!=y]) for y in yrs),3)
def walkforward(s,k=5):
    s=pd.Series(s).dropna(); n=len(s); b=[int(n*i/k) for i in range(k+1)]
    return sum(1 for i in range(k) if (1+s.iloc[b[i]:b[i+1]]).prod()-1>0)
def block_bootstrap(s,n_paths=N_PATHS,horizon=None,block=4,seed=SEED):
    w=pd.Series(s).dropna().values; n=len(w)
    if n==0: return np.zeros((n_paths,1))
    horizon=horizon or n
    rng=np.random.default_rng(seed); Pmat=np.empty((n_paths,horizon))
    for p in range(n_paths):
        seq=[]
        while len(seq)<horizon:
            st=rng.integers(0,n); seq.extend(w[(st+k)%n] for k in range(block))
        Pmat[p]=seq[:horizon]
    return Pmat
def p95_maxdd(Pmat):
    mdd=np.zeros(len(Pmat))
    for i in range(len(Pmat)):
        eq=np.cumprod(1+Pmat[i]); peak=np.maximum.accumulate(eq); mdd[i]=((eq-peak)/peak).min()
    return round(float(np.percentile(mdd,5))*100,1)

# ---------- トレードエンジン（1ショット=建値→Hホールド→足内SL） ----------
def _trade(pair, entry_pos, signs, hold_h, cost_mult=1.0):
    """entry_pos: 建玉する整数バー位置 array。signs: 各建玉の方向(+1/-1) array。
       戻り: per-trade リターン(リスク正規化, フルSL≈-RISK) の pd.Series(建玉時刻index)。"""
    df=H1(pair); pip=pip_size(pair); slip=P["SlippagePoints"]*point_size(pair)
    T=df.index.values; O=df["open"].to_numpy(); Hh=df["high"].to_numpy()
    L=df["low"].to_numpy(); C=df["close"].to_numpy(); S=df["spread"].to_numpy()
    atr=atr_wilder(df,P["AtrPeriodH1"]); aidx=atr.index.values; aval=atr.to_numpy()
    rets=[]; tims=[]
    for a,sgn in zip(entry_pos, signs):
        if sgn==0: continue
        ai=int(np.searchsorted(aidx,T[a],side="right"))-1
        if ai<0 or not (aval[ai]==aval[ai]) or aval[ai]<=0: continue
        spr=S[a] if S[a]==S[a] else pip
        if spr/pip>P["MaxSpreadPips"]: continue
        sd=P["CatastropheATR"]*aval[ai]; sp=sd/pip
        if sp<P["MinStopPips"]: sp=P["MinStopPips"]; sd=sp*pip
        if sp>P["MaxStopPips"]: continue
        cost_in = spr/2*cost_mult + slip
        entry = O[a] + sgn*cost_in            # 不利側に建値
        sl = entry - sgn*sd
        until=T[a]+np.timedelta64(hold_h,"h")
        b=int(np.searchsorted(T,until,side="left")); b=max(b,a+1); b=min(b,len(T))
        seg_l=L[a:b]; seg_h=Hh[a:b]
        hit=False; ex=None
        if sgn>0:
            if len(seg_l)>0 and (seg_l<=sl).any(): ex=sl; hit=True
        else:
            if len(seg_h)>0 and (seg_h>=sl).any(): ex=sl; hit=True
        if not hit:
            ex = C[b-1] - sgn*(spr/2*cost_mult)   # 時間決済も出口spread負担
        gross_pips = sgn*(ex-entry)/pip
        rets.append(gross_pips/sp*RISK); tims.append(T[a])
    return pd.Series(rets, index=pd.DatetimeIndex(tims)).sort_index()

# ---------- エントリ・ビルダー ----------
def _hour_entries(df, hour):
    idx=df.index; return np.where(idx.hour==hour)[0]

def _week_first_entries(df):
    """各週の最初のH1足（=週末ギャップを跨いだ建玉点）と、直前足(=金曜引け)のギャップ。"""
    idx=df.index; pos=[]; gap=[]
    iso=idx.isocalendar()
    wk=(iso.year.values.astype(np.int64)*100 + iso.week.values.astype(np.int64))
    O=df["open"].to_numpy(); C=df["close"].to_numpy()
    seen=set()
    for i in range(len(idx)):
        if wk[i] in seen: continue
        seen.add(wk[i])
        if i==0: continue
        pos.append(i); gap.append(O[i]-C[i-1])
    return np.array(pos), np.array(gap)

def series_gapfade(pair, hold_h, shuffle=False, seed=7, cost_mult=1.0):
    df=H1(pair); pos,gap=_week_first_entries(df)
    signs=-np.sign(gap)                              # fade
    if shuffle:
        rng=np.random.default_rng(seed); signs=rng.permutation(signs)
    return _trade(pair, pos, signs, hold_h, cost_mult=cost_mult)

def series_fix(pair, hour, hold_h, direction=1, cost_mult=1.0):
    df=H1(pair); pos=_hour_entries(df,hour)
    return _trade(pair, pos, np.full(len(pos),direction), hold_h, cost_mult=cost_mult)

def pooled(fn, *a, **k):
    """3ペアをプール（時刻indexで連結）。"""
    parts=[fn(p,*a,**k) for p in PAIRS]
    s=pd.concat(parts).sort_index()
    return s

# v7プロキシ（月曜04/06/08/10 LONG, 24h）→ 相関チェック用
def v7_proxy(pair):
    df=H1(pair); idx=df.index
    pos=np.where((idx.dayofweek==0)&(np.isin(idx.hour,[4,6,8,10])))[0]
    return _trade(pair, pos, np.ones(len(pos)), 24)

def _ann_for(hold_h):
    # 年あたりトレード数の概算（年次化係数）
    return {6:52, 24:52, 4:52*5}.get(hold_h, 52)

# ---------- 採点 ----------
def score(name, s, ann, placebo_ok, placebo_desc, cost_series):
    s=pd.Series(s).dropna()
    yrs=(s.index.max()-s.index.min()).days/365.25 if len(s)>1 else 0
    st=stat(s,ann); pp=perm_p(s); bonf=0.05/BONF_N[name]
    jk=jackknife(s); h=len(s)//2; IS=(1+s.iloc[:h]).prod()-1; OOS=(1+s.iloc[h:]).prod()-1
    wf=walkforward(s); dd=p95_maxdd(block_bootstrap(s,horizon=min(len(s),520) or 1))
    g8=(stat(cost_series,ann)["net"]>0)
    G={"G1_10y":yrs>=8.5,"G2":True,"G3_perm_bonf":pp<bonf,"G4_placebo":bool(placebo_ok),
       "G5_jackknife":(jk is not None and jk<=0.10),"G6_IS_OOS":(IS>0 and OOS>0),
       "G7_walkforward":wf>=4,"G8_cost":g8,"G9_DDfit":dd>=-10.0}
    core=[G["G3_perm_bonf"],G["G4_placebo"],G["G5_jackknife"],G["G6_IS_OOS"],
          G["G7_walkforward"],G["G8_cost"],G["G9_DDfit"]]
    grade=("ADOPT (v7同格)" if all(core) else
           "STRONG-LEAD (Bonf/JKのみ未達→デモで埋める)"
           if (G["G4_placebo"] and G["G6_IS_OOS"] and G["G7_walkforward"] and G["G8_cost"]) else "LEAD")
    return dict(name=name, grade=grade, stat=st, perm_p=round(pp,4), bonf_alpha=round(bonf,5),
                jackknife_max=jk, IS_pct=round(float(IS*100),1), OOS_pct=round(float(OOS*100),1),
                wf=f"{wf}/5", years=round(float(yrs),1), placebo=placebo_desc, dd_p95=dd, gates=G)

def corr_to_v7(s):
    v7=pooled(v7_proxy)
    a=s.resample("W").sum(); b=v7.resample("W").sum()
    j=pd.concat([a,b],axis=1).dropna()
    if len(j)<10: return None
    return round(float(j.iloc[:,0].corr(j.iloc[:,1])),2)

def run():
    print("="*72); print("edge10 — 10年H1 日中構造エッジ探索（事前登録 docs/72）"); print("="*72)
    selftest = os.environ.get("EDGE10_SELFTEST")=="1"
    if selftest: print("【SELFTEST】合成H1で実行（エンジン健全性のみ・実数値ではない）\n")

    results={}
    specs=[
        ("H1_gapfade6",  lambda: pooled(series_gapfade, 6),
                         lambda: perm_p(pooled(series_gapfade,6,shuffle=True))>0.05, "gap符号shuffleで消滅", 6),
        ("H2_gapfadeEOD",lambda: pooled(series_gapfade, 24),
                         lambda: perm_p(pooled(series_gapfade,24,shuffle=True))>0.05, "gap符号shuffleで消滅", 24),
        ("H3_tokyofix",  lambda: pooled(series_fix, 23, 4),
                         lambda: (perm_p(pooled(series_fix,21,4))>0.05 and perm_p(pooled(series_fix,1,4))>0.05),
                         "±2hずらしで消滅", 4),
        ("H4_londonfix", lambda: pooled(series_fix, 14, 4),
                         lambda: (perm_p(pooled(series_fix,12,4))>0.05 and perm_p(pooled(series_fix,16,4))>0.05),
                         "±2hずらしで消滅", 4),
    ]
    cost_builders={
        "H1_gapfade6":  lambda: pooled(series_gapfade, 6,  cost_mult=2.0),
        "H2_gapfadeEOD":lambda: pooled(series_gapfade, 24, cost_mult=2.0),
        "H3_tokyofix":  lambda: pooled(series_fix, 23, 4,  cost_mult=2.0),
        "H4_londonfix": lambda: pooled(series_fix, 14, 4,  cost_mult=2.0),
    }
    for name, sfn, plac_fn, plac_desc, hold in specs:
        s=sfn(); ann=_ann_for(hold)
        cost=cost_builders[name]()      # 2×コスト系列でG8を評価
        try: placebo_ok=plac_fn()
        except Exception as e: placebo_ok=False; print("placebo err",name,e)
        r=score(name, s, ann, placebo_ok, plac_desc, cost)
        r["corr_to_v7"]=corr_to_v7(s)
        results[name]=r
        g=r["gates"]; npass=sum(bool(v) for k,v in g.items())
        print(f"■ {name}  [{r['grade']}]  ρv7={r['corr_to_v7']}")
        print(f"   span{r['years']}y net{r['stat']['net']}% Sharpe{r['stat']['Sharpe']} "
              f"maxDD{r['stat']['maxDD']}% n={r['stat']['n']}  perm{r['perm_p']}<bonf{r['bonf_alpha']}:{g['G3_perm_bonf']}")
        print(f"   G4placebo:{g['G4_placebo']}({r['placebo']}) G5JK({r['jackknife_max']}):{g['G5_jackknife']} "
              f"G6IS/OOS({r['IS_pct']}/{r['OOS_pct']}):{g['G6_IS_OOS']} G7WF{r['wf']}:{g['G7_walkforward']} "
              f"G9DD(p95{r['dd_p95']}%):{g['G9_DDfit']}  → {npass}/9")
    # 探索スキャン（参考）
    print("\n--- 探索スキャン（時刻×方向, hold4h, 参考のみ・採否不使用, Bonferroni N=48）---")
    scan=[]
    for hr in range(24):
        for d in (1,-1):
            s=pooled(series_fix, hr, 4, direction=d)
            scan.append((hr,d,round(perm_p(s),4),stat(s,52)["net"]))
    scan.sort(key=lambda x:x[2])
    for hr,d,pp,net in scan[:8]:
        print(f"   hour{hr:02d}UTC dir{'L' if d>0 else 'S'} perm{pp} net{net}%  {'<0.00104(bonf48)' if pp<0.05/48 else ''}")
    return results

if __name__ == "__main__":
    res=run()
    print("\n(注) 実数値は Dukascopy 実行のみ。save_result('edge10_intraday_h1', metrics=res, inputs=[...]) で保存。")
