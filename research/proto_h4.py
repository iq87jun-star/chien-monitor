"""
proto_h4.py — v4(H4化)の優位性プロトタイプ検証
  目的: v3の「多信号アンサンブル逆張り」をシグナル足 D1 -> H4 に降ろしたとき、
        取引頻度が上がり、かつ優位性(PF>1, OOS堅牢)が残るかを手元データで先に確認する。
        ここで芽が無ければEAを書く価値はない(誠実な足切り)。

  方法(v3検証ノートと同思想・簡易版):
    - H1 CSV(2015-2025) を H4 にリサンプル(00,04,08,12,16,20 UTC境界)。
    - 4条件をH4確定足[1]で評価 -> 翌H4始値で約定。
    - SL=AtrSLMult*ATR(H4), TP=SL*RR, MaxHoldBars(H4)で時間切れ。
    - 約定後はH1足でイントラバーSL/TP/時間切れを判定(同足はSL優先=保守)。
    - 固定スプレッド(pip*spread_mult)を往復コストとして計上。
    - 指標: PF, 取引/年, 勝率, BE勝率, Wilson下限, 全期間/IS75/OOS25。
  注意: 研究用簡易判定。最終判断はユーザーの実bid/askハーネスで再検証。
"""
import os, math
import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(__file__), "data")
PAIRS = ["USDJPY","EURJPY","GBPJPY","USDCHF","GBPUSD","EURUSD","AUDUSD","NZDUSD","USDCAD"]

# --- パラメータ(v3を踏襲、H4向けに保有/ストップ下限のみ調整) ---
P = dict(
    K=3,                 # H4は1本の情報量が小さいので全一致(4)は稀すぎ。まず3で広く見る
    RsiPeriod=14, RsiBuy=35.0, RsiSell=65.0,
    BBPeriod=20, BBZ=1.5,
    StreakBars=3, RetThresh=0.0025,   # H4リターン閾値はD1(0.5%)より小さく(0.25%)
    AtrPeriod=14, AtrSLMult=1.5, RR=1.2,
    MaxHoldBars=12,      # H4×12 = 2日相当
    MinStopPips=6.0, MaxStopPips=250.0,
    SpreadMult=1.0,      # 固定スプレッド = pip * これ
    SlipPips=0.2,
)

def pip_size(pair): return 0.01 if pair.endswith("JPY") else 0.0001

def load_h1(pair):
    df = pd.read_csv(os.path.join(DATA, f"{pair}_h1.csv"))
    tcol = "timestamp" if "timestamp" in df.columns else "time"
    df["time"] = pd.to_datetime(df[tcol], utc=True)
    df = df.dropna(subset=["time"]).set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df[["open","high","low","close"]].astype(float)

def resample_h4(h1):
    o = h1["open"].resample("4h").first()
    h = h1["high"].resample("4h").max()
    l = h1["low"].resample("4h").min()
    c = h1["close"].resample("4h").last()
    h4 = pd.concat([o,h,l,c], axis=1)
    h4.columns = ["open","high","low","close"]
    return h4.dropna()

def rsi_wilder(close, n):
    d = close.diff()
    up = d.clip(lower=0.0); dn = (-d).clip(lower=0.0)
    ru = up.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rd = dn.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = ru/rd.replace(0,np.nan)
    return 100 - 100/(1+rs)

def atr_wilder(df, n):
    h,l,c = df["high"],df["low"],df["close"]; pc=c.shift(1)
    tr = pd.concat([(h-l),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean()

def compute_signals(h4, P):
    c = h4["close"]
    rsi = rsi_wilder(c, P["RsiPeriod"])
    n = P["BBPeriod"]
    mean = c.shift(1).rolling(n).mean()
    std  = c.shift(1).rolling(n).std(ddof=1)
    z = (c-mean)/std
    down = (c < c.shift(1)).astype(int); up = (c > c.shift(1)).astype(int)
    def streak(flag):
        out=[]; run=0
        for v in flag.values:
            run = run+1 if v==1 else 0
            out.append(run)
        return pd.Series(out, index=flag.index)
    ds = streak(down); us = streak(up)
    ret = c.pct_change()
    bv = ((rsi<P["RsiBuy"]).astype(int) + (z<-P["BBZ"]).astype(int)
          + (ds>=P["StreakBars"]).astype(int) + (ret<-P["RetThresh"]).astype(int))
    sv = ((rsi>P["RsiSell"]).astype(int) + (z>P["BBZ"]).astype(int)
          + (us>=P["StreakBars"]).astype(int) + (ret>P["RetThresh"]).astype(int))
    K = P["K"]
    sig = pd.Series(0, index=c.index, dtype=int)
    sig[(bv>=K)&(bv>sv)] = 1
    sig[(sv>=K)&(sv>bv)] = -1
    out = pd.DataFrame({"signal":sig, "atr":atr_wilder(h4,P["AtrPeriod"])})
    return out

def backtest(pair, h1, h4, P):
    pip = pip_size(pair)
    sg = compute_signals(h4, P)
    spread = pip*P["SpreadMult"]; slip = pip*P["SlipPips"]
    # H1 numpy
    t1 = h1.index.values
    o1=h1["open"].values; h1h=h1["high"].values; l1=h1["low"].values; c1=h1["close"].values
    idx = list(sg.index); sigv=sg["signal"].values; atrv=sg["atr"].values
    Rs=[]; times=[]
    for i in range(len(idx)-1):
        s=sigv[i]; atr=atrv[i]
        if s==0 or not (atr==atr) or atr<=0: continue
        sd=P["AtrSLMult"]*atr
        if sd/pip < P["MinStopPips"] or sd/pip > P["MaxStopPips"]: continue
        t_next = idx[i+1]
        a = int(np.searchsorted(t1, np.datetime64(t_next), side="left"))
        if a>=len(t1): break
        # 約定 = 翌H4始値 = その時刻のH1始値
        mid = o1[a]
        if s>0: entry = mid + spread/2 + slip; sl=entry-sd; tp=entry+P["RR"]*sd
        else:   entry = mid - spread/2 - slip; sl=entry+sd; tp=entry-P["RR"]*sd
        until = t_next + np.timedelta64(P["MaxHoldBars"]*4, "h")
        b = int(np.searchsorted(t1, np.datetime64(until), side="right")); b=max(b,a+1)
        hh=h1h[a:b]; ll=l1[a:b]
        R=None
        for k in range(len(hh)):
            hi=hh[k]+spread/2; lo=ll[k]+spread/2  # askで判定(保守)
            if s>0:
                hit_sl = ll[k] <= sl; hit_tp = hh[k] >= tp
            else:
                hit_sl = hh[k] >= sl; hit_tp = ll[k] <= tp
            if hit_sl and hit_tp: R=-1.0; break   # 同足はSL優先
            if hit_sl: R=-1.0; break
            if hit_tp: R=P["RR"]; break
        if R is None:
            # 時間切れ: 窓末端の終値で評価
            last = c1[b-1] if b-1<len(c1) else c1[-1]
            diff = (last-entry) if s>0 else (entry-last)
            R = diff/sd
        Rs.append(R); times.append(pd.Timestamp(t_next))
    return pd.DataFrame({"time":times, "R":Rs})

def wilson_lower(w, n, z=1.96):
    if n==0: return float("nan")
    p=w/n; den=1+z*z/n; c=p+z*z/(2*n)
    adj=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)
    return (c-adj)/den

def stats(df, P, label):
    n=len(df)
    if n==0: return dict(label=label,n=0)
    R=df["R"].values
    gp=R[R>0].sum(); gl=-R[R<0].sum()
    pf = gp/gl if gl>0 else float("inf")
    w=int((R>0).sum()); wr=w/n
    be=1.0/(1.0+P["RR"])
    span=(df["time"].max()-df["time"].min()).days or 1
    tpy=n/(span/365.25)
    totR=R.sum()
    return dict(label=label,n=n,trades_yr=round(tpy,1),wr=round(wr*100,1),
                be=round(be*100,1),wilson_lo=round(wilson_lower(w,n)*100,1),
                PF=round(pf,2),totR=round(totR,2),exp_R=round(R.mean(),3))

def run():
    rows=[]; oos_rows=[]
    for pair in PAIRS:
        try:
            h1=load_h1(pair); h4=resample_h4(h1)
            df=backtest(pair,h1,h4,P)
            rows.append(stats(df,P,pair))
            if len(df)>0:
                cut=df["time"].quantile(0.75)
                is_=df[df["time"]<=cut]; oos=df[df["time"]>cut]
                s_is=stats(is_,P,f"{pair} IS"); s_oos=stats(oos,P,f"{pair} OOS")
                oos_rows.append(dict(pair=pair,
                    IS_n=s_is.get("n",0),IS_PF=s_is.get("PF"),IS_totR=s_is.get("totR"),
                    OOS_n=s_oos.get("n",0),OOS_PF=s_oos.get("PF"),OOS_totR=s_oos.get("totR")))
        except Exception as e:
            rows.append(dict(label=pair,n=-1,note=str(e)[:60]))
    print(f"\n=== H4 全期間ベースライン  K={P['K']} RR={P['RR']} hold={P['MaxHoldBars']}H4 ===")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n=== H4 Hold-Out 75/25 ===")
    print(pd.DataFrame(oos_rows).to_string(index=False))
    # プール(全ペア合算)
    allR=[]
    for pair in PAIRS:
        try:
            h1=load_h1(pair); h4=resample_h4(h1); d=backtest(pair,h1,h4,P)
            allR.append(d)
        except Exception: pass
    if allR:
        pool=pd.concat(allR).sort_values("time")
        print("\n=== プール(全ペア合算) ===")
        print(stats(pool,P,"POOL ALL"))
        cut=pool["time"].quantile(0.75)
        print(stats(pool[pool["time"]<=cut],P,"POOL IS"))
        print(stats(pool[pool["time"]>cut],P,"POOL OOS"))

if __name__=="__main__":
    run()
