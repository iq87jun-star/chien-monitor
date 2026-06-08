# -*- coding: utf-8 -*-
"""
p2_edge_search.py — 第2ポートフォリオ(P2)用 独立エッジ探索（商品ユニバース拡張・10年日足）。

目的: 既存P1(v7 円月曜 / v4 合議FX / E5 多資産モメンタム)と【低相関な別ポートフォリオ】を
      組むため、P1に無い土俵=追加FXクロス + 金属 + 株価指数 + 暗号 を、E5(モメンタム)と
      被らない機構=曜日(DOW) / 月末(TOM) / 短期平均回帰(REV) で全数検定する。

ハーネス(P1のv7基準と同思想・全候補一律):
  - ノールックアヘッド: シグナルは確定足(close[t])で生成、約定は翌足 open[t+1]。
  - 実コスト: FXはpipスプレッド+slip、金属/指数はbps、暗号はbps×2 を往復で控除。
  - 順列検定(符号シャッフル4000) / IS-OOS(前後半) / 全年ジャックナイフ /
    Bonferroni(本探索の全試行数で補正) / コスト2× / プラセボ(同数ランダム方向)。
  - ★相関: 各候補の月次P&Lと、既存P1(v7/v4/E5合成)月次との相関を測り「別物の分散源」かを判定。

データ: research/data/<NAME>_d.csv (Yahoo 10年, fetch_p2_universe.py / 既存committed)。
出力: research/results/p2_edge_search.json + コンソール。
注意: シミュレーション。Yahoo日足・指数=配当抜き・金=先物近月。最終確認はユーザーDukascopy/Colabで。誇張しない。
"""
import os, sys, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_backtester as rb
import ensemble_meanrev as em

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# ===== ユニバース定義 =====
FX_CROSS = ["EURGBP","AUDJPY","NZDJPY","CADJPY","CHFJPY","EURAUD","AUDNZD","EURCHF","GBPCHF","GBPAUD"]
METALS   = ["XAUUSD","XAGUSD"]
INDICES  = ["US500","NAS100","GER40","JP225","UK100"]
CRYPTO   = ["BTCUSD","ETHUSD"]
NONFX    = METALS + INDICES + CRYPTO
ALL      = FX_CROSS + NONFX
WD = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# 往復コスト(往復・return比)。FXはpip→price比、その他はbps。誇張せず保守側。
FX_SPREAD_PIPS = {"EURGBP":1.2,"AUDJPY":1.6,"NZDJPY":2.0,"CADJPY":2.0,"CHFJPY":2.0,
                  "EURAUD":1.8,"AUDNZD":2.2,"EURCHF":1.6,"GBPCHF":2.5,"GBPAUD":3.0}
SLIP_PIPS = 0.5
BPS = {**{m:5.0 for m in METALS}, **{i:5.0 for i in INDICES}, **{cc:10.0 for cc in CRYPTO}}

def is_fx(name): return name in FX_CROSS
def is_crypto(name): return name in CRYPTO
def pip_size(name): return 0.01 if name.endswith("JPY") else 0.0001

def cost_frac(name, open_price, mult=1.0):
    """往復コストを return 比で返す。"""
    if is_fx(name):
        pip = pip_size(name)
        return mult*(FX_SPREAD_PIPS.get(name,2.0) + 2*SLIP_PIPS)*pip/open_price
    return mult*BPS[name]/1e4

# ===== データ =====
def load(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date").last()
    df["weekday"] = df.index.dayofweek
    if not is_crypto(name):
        df = df[df["weekday"] <= 4]          # FX/指数/金属は平日のみ
    df["o2o"] = df["open"].shift(-1)/df["open"] - 1.0   # open[t]→open[t+1]
    df["ret"] = df["close"].pct_change()
    df["rsi2"] = rb.rsi_wilder(df["close"].values, 2)
    return df

DF = {name: load(name) for name in ALL}

# ===== 候補リターン系列(index=entry trade_date, 値=往復コスト後 return) =====
def dow_series(name, wd, direction, mult=1.0):
    df = DF[name]; sub = df[df["weekday"]==wd].dropna(subset=["o2o"])
    return (direction*sub["o2o"] - cost_frac(name, sub["open"], mult)).dropna()

def tom_series(name, direction, mult=1.0, last_n=1, first_n=3):
    df = DF[name].dropna(subset=["o2o"]).copy()
    ym = df.index.to_period("M")
    fs = df.groupby(ym).cumcount()+1
    fe = df.groupby(ym).cumcount(ascending=False)+1
    sub = df[(fe<=last_n) | (fs<=first_n)]
    return (direction*sub["o2o"] - cost_frac(name, sub["open"], mult)).dropna()

def rev_series(name, mode, mult=1.0, lo=10.0, hi=90.0):
    """短期平均回帰/順張り: RSI(2)は close[t] で確定 → 約定 open[t+1] → 決済 open[t+2]。
       ノールックアヘッドのため戦略リターンは o2o の1本シフト(open[t+1]→open[t+2])を使う。
       mode='fade' 売られすぎLONG/買われすぎSHORT(逆張り), 'follow' その逆(順張り)。"""
    df = DF[name].copy()
    df["o2o_next"] = df["o2o"].shift(-1)          # open[t+1]→open[t+2]
    df["entry_open"] = df["open"].shift(-1)        # 約定する翌足始値
    df = df.dropna(subset=["o2o_next","entry_open","rsi2"])
    sig = np.where(df["rsi2"]<lo, +1, np.where(df["rsi2"]>hi, -1, 0))
    if mode=="follow": sig = -sig
    sub = df[sig!=0]; d = sig[sig!=0]
    r = d*sub["o2o_next"].values - cost_frac(name, sub["entry_open"].values, mult)
    return pd.Series(r, index=sub.index).dropna()

# ===== 統計 =====
def eq_stats(x):
    x = pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0.0, win_pct=0.0, maxDD_pct=0.0, n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1), win_pct=round(float((x>0).mean())*100,1),
                maxDD_pct=round(float(dd),1), n=int(len(x)))

def perm_p(x, n_iter=4000, seed=7):
    x=np.asarray(x,float)
    if len(x)<10: return 1.0
    rng=np.random.default_rng(seed); real=x.sum(); a=np.abs(x).astype(np.float32)
    signs=rng.choice(np.array([-1,1],np.float32), size=(n_iter,len(a)))
    null=(signs*a).sum(axis=1)
    return float((null>=real).mean())

def monthly(x):
    x=pd.Series(x).dropna()
    if len(x)==0: return pd.Series(dtype=float)
    g=x.groupby(x.index.to_period("M")).sum()
    return g

# ===== 既存P1の月次プロキシ(相関の基準) =====
def p1_v7_monthly():
    tot=None
    for p in ["EURJPY","GBPJPY","USDJPY"]:
        df=pd.read_csv(os.path.join(DATA,f"{p}_d.csv"))
        df["t"]=pd.to_datetime(df["timestamp"],utc=True,errors="coerce")
        df=df.dropna(subset=["t"]).sort_values("t")
        df["trade_date"]=(df["t"]+pd.Timedelta(hours=2)).dt.floor("D")
        df=df.groupby("trade_date").last(); df["weekday"]=df.index.dayofweek
        df=df[df["weekday"]<=4]; df["o2o"]=df["open"].shift(-1)/df["open"]-1.0
        sub=df[df["weekday"]==0].dropna(subset=["o2o"])
        pip=0.01; cost=(2.0+2*0.5)*pip/sub["open"]
        r=(sub["o2o"]-cost); m=monthly(r)
        tot=m if tot is None else tot.add(m,fill_value=0)
    return tot/3.0

def p1_v4_monthly():
    PAIRS=["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
    from collections import defaultdict
    mo=defaultdict(float)
    for p in PAIRS:
        ts,o,h,l,c=rb.load_daily(p); sig=em.signals_confluence(o,h,l,c,k_required=4)
        pip=rb.pip_size(p); atr=rb.atr_wilder(h,l,c,14)
        half=(rb.SPREAD_PIPS.get(p,rb.DEFAULT_SPREAD)/2.0+rb.SLIPPAGE_PIPS)*pip; pos=None
        for i in range(1,len(c)):
            if pos is not None:
                dirn=pos["dir"];e=pos["entry"];slv=pos["sl"];tp=pos["tp"];hi=h[i];lo=l[i];ex=None
                if dirn>0:
                    if lo-half<=slv: ex=slv
                    elif hi-half>=tp: ex=tp
                else:
                    if hi+half>=slv: ex=slv
                    elif lo+half<=tp: ex=tp
                if ex is None and (i-pos["i"])>=8: ex=o[i]+(half if dirn<0 else -half)
                if ex is not None:
                    r=((ex-e) if dirn>0 else (e-ex))/pos["risk"]; mo[str(ts[pos["i"]])[:7]]+=r; pos=None
            if pos is None:
                s=sig[i-1]
                if s!=0 and not np.isnan(atr[i-1]) and atr[i-1]>0:
                    e=o[i]+(half if s>0 else -half); risk=atr[i-1]*1.5
                    slv=e-risk if s>0 else e+risk; tp=e+1.2*risk if s>0 else e-1.2*risk
                    pos={"dir":s,"entry":e,"sl":slv,"tp":tp,"risk":risk,"i":i}
    s=pd.Series(mo); s.index=pd.PeriodIndex(s.index,freq="M"); return s.sort_index()

def p1_e5_monthly():
    """E5プロキシ: 多資産バスケットの月次TSMOM(1/3/6/12ヶ月符号多数決→翌月方向,1ヶ月保有,等加重)。"""
    basket=["XAUUSD","US500","NAS100","GER40","BTCUSD","ETHUSD"]
    mret={}
    for a in basket:
        df=pd.read_csv(os.path.join(DATA,f"{a}_d.csv"))
        df["t"]=pd.to_datetime(df["timestamp"],utc=True,errors="coerce")
        df=df.dropna(subset=["t"]).sort_values("t").set_index("t")
        m=df["close"].resample("ME").last(); mret[a]=m.pct_change()
    idx=sorted(set().union(*[set(s.index) for s in mret.values()]))
    out=pd.Series(0.0,index=pd.PeriodIndex([i.to_period("M") for i in idx],freq="M"))
    for a,s in mret.items():
        s=s.reindex(idx)
        for k in range(13,len(idx)):
            votes=sum(np.sign(s.iloc[k-lb:k].sum()) for lb in (1,3,6,12))
            d=np.sign(votes)
            if d!=0 and not np.isnan(s.iloc[k]):
                out.iloc[k]+= d*s.iloc[k]/len(basket) - 5/1e4
    return out

def build_p1():
    v7=p1_v7_monthly(); v4=p1_v4_monthly(); e5=p1_e5_monthly()
    def z(s):
        s=s.dropna(); sd=s.std()
        return s/sd if sd>0 else s
    j=pd.concat([z(v7).rename("v7"),z(v4).rename("v4"),z(e5).rename("e5")],axis=1).dropna()
    p1=0.4*j["v7"]+0.4*j["v4"]+0.2*j["e5"]
    return p1, {"v7":v7,"v4":v4,"e5":e5}, j

def corr_to(series_monthly, p1_monthly):
    a=series_monthly.dropna(); b=p1_monthly.dropna()
    j=pd.concat([a.rename("a"),b.rename("b")],axis=1).dropna()
    return (round(float(j["a"].corr(j["b"])),3), len(j)) if len(j)>=24 else (None,len(j))

# ===== メイン探索 =====
def run():
    P1, legs, _ = build_p1()
    print(f"[P1基準] 月次合成(40:40:20, vol正規化) 期間 {P1.index.min()}..{P1.index.max()} n={len(P1)}")

    cands=[]   # (label, family, gen) gen(mult)->Series
    for name in ALL:
        wdays = range(7) if is_crypto(name) else range(5)
        for w in wdays:
            for d in (+1,-1):
                lbl=f"{name}_{WD[w]}_{'L' if d>0 else 'S'}"
                cands.append((lbl,"DOW",(lambda n=name,w=w,d=d:(lambda m=1.0:dow_series(n,w,d,m)))()))
    for name in ALL:
        for d in (+1,-1):
            lbl=f"{name}_TOM_{'L' if d>0 else 'S'}"
            cands.append((lbl,"TOM",(lambda n=name,d=d:(lambda m=1.0:tom_series(n,d,m)))()))
    for name in ALL:
        for mode in ("fade","follow"):
            lbl=f"{name}_REV_{mode}"
            cands.append((lbl,"REV",(lambda n=name,mo=mode:(lambda m=1.0:rev_series(n,mo,m)))()))

    # 最低標本 n>=80 のみ採用
    cands=[(l,f,g) for (l,f,g) in cands if len(g(1.0))>=80]
    N=len(cands); alpha=0.05/N
    print(f"全候補(=多重検定試行数) N={N}  Bonferroni α={alpha:.6f}\n")

    rows=[]; GEN={}
    for lbl,fam,gen in cands:
        GEN[lbl]=gen; r=gen(1.0); st=eq_stats(r.values); p=perm_p(r.values)
        cm=monthly(r); cc,nm=corr_to(cm,P1)
        rows.append(dict(label=lbl,family=fam,**st,perm_p=round(p,4),corr_P1=cc,corr_n=nm))
    df=pd.DataFrame(rows).sort_values("perm_p").reset_index(drop=True)

    sig=df[(df.perm_p<=0.05)&(df.net_pct>0)].copy()
    surv=sig[sig.perm_p<=alpha].copy()

    # 二次ハーネス: Bonferroni生存 ＋「p<=0.01 かつ |corr_P1|<=0.3 の低相関候補」
    targets=pd.concat([surv, sig[(sig.perm_p<=0.01)&(sig.corr_P1.abs()<=0.3)]]).drop_duplicates("label")
    detail={}
    for _,row in targets.iterrows():
        lbl=row["label"]; r=GEN[lbl](1.0)
        half=r.index[len(r)//2]
        Ris=r[r.index<half]; Roos=r[r.index>=half]
        oos=eq_stats(Roos.values); oosp=perm_p(Roos.values); isp=perm_p(Ris.values)
        yrs=sorted(set(r.index.year))
        jk={int(y):round(perm_p(r[r.index.year!=y].values),3) for y in yrs}
        wf=0
        for s in range(5):
            a=r.index[int(len(r)*s/5)]; b=r.index[min(len(r)-1,int(len(r)*(s+1)/5))]
            seg=r[(r.index>=a)&(r.index<b)]
            if eq_stats(seg.values)["net_pct"]>0: wf+=1
        cost2=eq_stats(GEN[lbl](2.0).values)
        rp=GEN[lbl](1.0)
        plac=[]
        for sd in range(20):
            rng=np.random.default_rng(100+sd); flip=rng.choice([-1,1],size=len(rp))
            plac.append((rp.values*flip).sum())
        plac_mean=float(np.mean(plac))
        detail[lbl]=dict(
            full=dict(net_pct=row["net_pct"],win_pct=row["win_pct"],maxDD_pct=row["maxDD_pct"],
                      n=int(row["n"]),perm_p=row["perm_p"],corr_P1=row["corr_P1"],corr_n=int(row["corr_n"])),
            bonferroni_survivor=bool(row["perm_p"]<=alpha),
            is_=dict(net_pct=eq_stats(Ris.values)["net_pct"],perm_p=round(isp,4)),
            oos=dict(**oos,perm_p=round(oosp,4)),
            g_is_oos=bool(Ris.sum()>0 and Roos.sum()>0),
            jk_max_p=round(max(jk.values()),3), jk=jk,
            g_jk=bool(max(jk.values())<=0.10),
            wf=f"{wf}/5", g_wf=bool(wf>=4),
            cost2x=cost2, g_cost=bool(cost2["net_pct"]>0),
            g_placebo=bool(row["net_pct"]/100.0 > plac_mean),  # 実net > プラセボ平均
        )
    out=dict(span=[str(P1.index.min()),str(P1.index.max())], N_tests=N, alpha_bonf=round(alpha,6),
             p1_leg_corr={"v7_v4":round(float(legs_corr(legs,'v7','v4')),3),
                          "v7_e5":round(float(legs_corr(legs,'v7','e5')),3),
                          "v4_e5":round(float(legs_corr(legs,'v4','e5')),3)},
             sig_count=int(len(sig)), bonferroni_survivors=int(len(surv)),
             all_significant=sig.to_dict("records"), detail=detail)
    return df, sig, surv, out

def legs_corr(legs,a,b):
    j=pd.concat([legs[a].rename("a"),legs[b].rename("b")],axis=1).dropna()
    return j["a"].corr(j["b"]) if len(j)>=24 else float("nan")

if __name__=="__main__":
    pd.set_option("display.width",220); pd.set_option("display.max_columns",30); pd.set_option("display.max_rows",200)
    df,sig,surv,out=run()
    # sanity
    bal=DF["EURGBP"]["weekday"].value_counts().sort_index()
    print("[sanity] EURGBP 曜日件数:",dict(zip([WD[i] for i in bal.index],bal.values)))
    bal2=DF["BTCUSD"]["weekday"].value_counts().sort_index()
    print("[sanity] BTCUSD 曜日件数(7日):",dict(zip([WD[i] for i in bal2.index],bal2.values)))
    print(f"\nP1脚間相関(参考): {out['p1_leg_corr']}")
    print(f"\n===== 順列 p<=0.05 & net>0 の候補({len(sig)}/{out['N_tests']}) =====")
    print(sig.head(40).to_string())
    print(f"\n===== ★Bonferroni生存(p<=α={out['alpha_bonf']}): {len(surv)}件 =====")
    print(surv.to_string() if len(surv) else "  なし")
    print("\n===== 生存/低相関候補の二次ハーネス(9ゲート) =====")
    for k,d in out["detail"].items():
        f=d["full"]
        gates=[d["bonferroni_survivor"],d["g_placebo"],d["g_jk"],d["g_is_oos"],d["g_wf"],d["g_cost"]]
        npass=sum(gates)
        print(f"\n[{k}] net{f['net_pct']}% 勝率{f['win_pct']}% DD{f['maxDD_pct']}% n={f['n']} "
              f"p={f['perm_p']} corrP1={f['corr_P1']}")
        print(f"   OOS net{d['oos']['net_pct']}% p={d['oos']['perm_p']} | IS net{d['is_']['net_pct']}% | "
              f"JKmax_p={d['jk_max_p']}({d['g_jk']}) WF{d['wf']}({d['g_wf']}) cost2x net{d['cost2x']['net_pct']}%({d['g_cost']}) "
              f"plac({d['g_placebo']}) Bonf({d['bonferroni_survivor']}) → {npass}/6")
    os.makedirs(os.path.join(HERE,"results"),exist_ok=True)
    with open(os.path.join(HERE,"results","p2_edge_search.json"),"w") as fp:
        json.dump(out,fp,ensure_ascii=False,indent=2,default=str)
    print("\n保存: research/results/p2_edge_search.json")
