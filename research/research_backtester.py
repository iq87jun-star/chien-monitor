# -*- coding: utf-8 -*-
"""
research_backtester.py
======================
ユーザーの厳密ハーネス(Lv1-Lv5)と同思想の研究用バックテスタ。
目的: 「押し目RSI反転」がエッジ無しと判明したため、白紙から複数戦略タイプを
      実データで正直に検定し、本物のエッジ(OOSで有意なPF>1)が出るか確認する。

原則:
  - ノールックアヘッド: シグナルは確定足(t-1まで)で生成し、t本目の始値で約定。
  - 実コスト: スプレッド/2 + スリッページ を往復で計上(pips)。
  - 評価: 全期間/イン-アウト(70:30)/ブートストラップでPF<=1確率。
  - 誇張しない: 出なければ「出ない」と表示。

データ: research/data/{pair}_d.csv (日足10年, Yahoo)。
注意: Yahoo日足はOHLCが概算でスプレッドも単純化。最終判断はユーザーのMT5/Dukascopyで。
"""
import os, csv, math, json
import numpy as np

DATA = os.path.join(os.path.dirname(__file__), "data")

# 実コスト(pips, 片道はhalf)。日足戦略は保有が長くコスト影響は相対的に小さい。
SPREAD_PIPS = {"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,
               "USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
DEFAULT_SPREAD = 1.5
SLIPPAGE_PIPS = 0.5


def pip_size(pair): return 0.01 if pair.endswith("JPY") else 0.0001


def load_daily(pair):
    path = os.path.join(DATA, f"{pair}_d.csv")
    ts=[]; o=[]; h=[]; l=[]; c=[]
    with open(path) as f:
        r=csv.DictReader(f)
        for row in r:
            ts.append(row["timestamp"])
            o.append(float(row["open"])); h.append(float(row["high"]))
            l.append(float(row["low"]));  c.append(float(row["close"]))
    return (np.array(ts), np.array(o), np.array(h), np.array(l), np.array(c))


# ---------- 指標 ----------
def ema(x, n):
    a=2.0/(n+1.0); out=np.empty_like(x); out[0]=x[0]
    for i in range(1,len(x)): out[i]=a*x[i]+(1-a)*out[i-1]
    return out

def sma(x, n):
    out=np.full_like(x, np.nan)
    cs=np.cumsum(np.insert(x,0,0.0))
    out[n-1:]=(cs[n:]-cs[:-n])/n
    return out

def rsi_wilder(c, n=14):
    d=np.diff(c, prepend=c[0]); up=np.clip(d,0,None); dn=np.clip(-d,0,None)
    au=np.empty_like(c); ad=np.empty_like(c); au[0]=up[0]; ad[0]=dn[0]; a=1.0/n
    for i in range(1,len(c)):
        au[i]=a*up[i]+(1-a)*au[i-1]; ad[i]=a*dn[i]+(1-a)*ad[i-1]
    rs=np.divide(au, np.where(ad==0,np.nan,ad)); return np.nan_to_num(100-100/(1+rs), nan=50.0)

def atr_wilder(h,l,c,n=14):
    pc=np.roll(c,1); pc[0]=c[0]
    tr=np.maximum.reduce([h-l, np.abs(h-pc), np.abs(l-pc)])
    out=np.empty_like(c); out[0]=tr[0]; a=1.0/n
    for i in range(1,len(c)): out[i]=a*tr[i]+(1-a)*out[i-1]
    return out

def rolling_max(x,n):
    out=np.full_like(x,np.nan)
    for i in range(n,len(x)): out[i]=np.max(x[i-n:i])
    return out

def rolling_min(x,n):
    out=np.full_like(x,np.nan)
    for i in range(n,len(x)): out[i]=np.min(x[i-n:i])
    return out


# ---------- 汎用シミュレータ(ロング/ショート, ATR-SL, RR-TP, ノールックアヘッド) ----------
def simulate(pair, o,h,l,c, entry_sig, exit_sig=None, sl_atr=2.0, rr=2.0,
             atr_n=14, max_hold=20, direction_arr=None):
    """entry_sig[i]=+1/-1/0 は『i本目の確定足で出たシグナル』。約定は i+1本目の始値。
       SL=ATR*sl_atr, TP=SL*rr。exit_sigやmax_holdでも手仕舞い。"""
    pip=pip_size(pair)
    atr=atr_wilder(h,l,c,atr_n)
    half=(SPREAD_PIPS.get(pair,DEFAULT_SPREAD)/2.0+SLIPPAGE_PIPS)*pip
    R=[]; pos=None; n=len(c)
    for i in range(1, n):
        # 手仕舞い判定(保有中)
        if pos is not None:
            dirn=pos["dir"]; entry=pos["entry"]; sl=pos["sl"]; tp=pos["tp"]
            hi=h[i]; lo=l[i]; exit_p=None
            if dirn>0:
                if lo-half<=sl: exit_p=sl
                elif hi-half>=tp: exit_p=tp
            else:
                if hi+half>=sl: exit_p=sl
                elif lo+half<=tp: exit_p=tp
            hold=i-pos["i"]
            force = (exit_sig is not None and exit_sig[i-1]==-dirn) or (hold>=max_hold)
            if exit_p is None and force:
                exit_p=o[i]+(half if dirn<0 else -half)  # 翌足始値で成行手仕舞い(コスト方向)
            if exit_p is not None:
                r=((exit_p-entry) if dirn>0 else (entry-exit_p))/pos["risk"]
                R.append(r); pos=None
        # 新規(ノールックアヘッド: i-1のシグナルでi本目始値約定)
        if pos is None:
            s=entry_sig[i-1]
            if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                entry=o[i]+(half if s>0 else -half)
                risk=atr[i-1]*sl_atr
                if s>0: sl=entry-risk; tp=entry+rr*risk
                else:   sl=entry+risk; tp=entry-rr*risk
                pos={"dir":s,"entry":entry,"sl":sl,"tp":tp,"risk":risk,"i":i}
    return np.array(R, float)


# ---------- 統計 ----------
def bootstrap_pf_le1(R, n_boot=5000, seed=42):
    if len(R)<10: return float("nan")
    rng=np.random.default_rng(seed); n=len(R); cnt=0
    for _ in range(n_boot):
        s=R[rng.integers(0,n,n)]; gp=s[s>0].sum(); gl=-s[s<0].sum()
        pf=gp/gl if gl>0 else 1e9
        if pf<=1.0: cnt+=1
    return cnt/n_boot

def stats(R, label=""):
    n=len(R)
    if n<10: return {"label":label,"n":n,"note":"too few"}
    wins=int((R>0).sum()); wr=wins/n
    gp=R[R>0].sum(); gl=-R[R<0].sum(); pf=gp/gl if gl>0 else float("inf")
    exp=R.mean(); sh=R.mean()/R.std(ddof=1) if R.std(ddof=1)>0 else float("nan")
    return {"label":label,"n":n,"win_rate":round(wr,3),"PF":round(pf,3),
            "expectancy_R":round(exp,4),"sharpe_trade":round(sh,3),
            "boot_P_PF<=1":round(bootstrap_pf_le1(R),4)}


def split_is_oos(R_full_idx, c_len, frac=0.7):
    """インデックスベースで前70%=IS, 後30%=OOS の境界本数を返す。"""
    return int(c_len*frac)
