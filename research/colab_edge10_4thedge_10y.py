"""
colab_edge10_4thedge_10y.py — 4本目エッジ事前登録(docs/47)の【10年H1 Dukascopy 確定版】。

目的: 手元Yahoo H1 ~2年の予備(docs/48)で3候補とも REJECT だった C1/C2/C3 を、ユーザーの
  10年H1 Dukascopy で正式に確定する（NEGATIVE を記録に残す / 万一 2年では見えなかった候補が
  10年で浮上しないかの最終確認）。**パラメータは docs/47 で固定済み——本ファイルで変更しない。**

判定（v7基準9ゲート + R1相関）:
  ADOPT       = G3(プールOOS perm_p < α_family=0.0167)・G4プラセボ・G5 JK・G6 IS/OOS両+・
                G7 WF≥4/5・G8 コスト2×・G9 −10%適合・R1 |月次相関|≤0.3(v7/v4/E5全て) を全合格
  STRONG-LEAD = G4・G6・G7・G8・R1 合格で G3 か G5 が未達
  LEAD/REJECT = それ未満

使い方(Colab):
  USE_DRIVE=True。H1_DIR に {9ペア}_h1.csv（10年, Dukascopy由来, columns: timestamp,open,high,low,close, UTC）。
  既存戦略の月次リターン系列（相関R1用）があれば V_SERIES_DIR に v7_monthly.csv / v4_monthly.csv /
  e5_monthly.csv（columns: month,ret）を置く（無ければ R1 はスキップし WARN）。
  「すべて実行」。出力 = results/edge10_4thedge_10y.json。

⚠ 数字は盛らない。出なければ「出ない(REJECT)」と表示する。確証はデモ前進検証(docs/29)で。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR     = "{base}/dukascopy_data_h1"
V_SERIES_DIR = "{base}/strategy_monthly"
LOCAL_FALLBACK = "./research/data"

PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"]
SPREAD_PIPS = {"USDJPY":1.2,"EURJPY":1.6,"GBPJPY":2.0,"EURUSD":0.8,"GBPUSD":1.2,
               "USDCHF":1.4,"USDCAD":1.4,"AUDUSD":1.2,"NZDUSD":1.5}
SLIP=0.5; VOLWIN=24; SEED=11
ALPHA_FAMILY=0.0167; ALPHA_STRICT=0.05/27
NPERM=4000

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル継続):", e)
DRIVE_OK=os.path.exists("/content/drive/MyDrive")

def _dir(tmpl):
    return tmpl.format(base=DRIVE_BASE) if (USE_DRIVE and DRIVE_OK) else LOCAL_FALLBACK
def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def cost_frac(p,px): return (SPREAD_PIPS.get(p,1.5)+2*SLIP)*pip_size(p)/np.asarray(px)

def load_h1(p):
    path=os.path.join(_dir(H1_DIR), f"{p}_h1.csv")
    if not os.path.exists(path): path=os.path.join(LOCAL_FALLBACK, f"{p}_h1.csv")
    df=pd.read_csv(path); df["timestamp"]=pd.to_datetime(df["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)

def atr_pct(O, win=VOLWIN):
    r=np.abs(np.diff(O)/O[:-1]); out=np.full(len(O),np.nan)
    for i in range(win,len(O)): out[i]=np.median(r[i-win:i])
    return out

# ---- 候補（docs/47 固定パラメータ。edge10_4thedge.py と同一ロジック） ----
def gen_trades(df, kind):
    T=df["timestamp"].to_numpy(); O=df["open"].to_numpy(float); H=df["high"].to_numpy(float)
    L=df["low"].to_numpy(float); C=df["close"].to_numpy(float); ap=atr_pct(O)
    hours=df["timestamp"].dt.hour.to_numpy(); dates=df["timestamp"].dt.date.to_numpy()
    p=df.attrs.get("pair","EURUSD"); out=[]
    if kind in ("C1_fade","C1_cont"):
        theta=2.0;Hh=4;SLk=2.0;n=len(O)
        for i in range(1,n-1):
            if not(8<=hours[i]<=17): continue
            a=ap[i]
            if not np.isfinite(a): continue
            pr=(O[i]-O[i-1])/O[i-1]
            if abs(pr)<theta*a: continue
            d=(-1 if kind=="C1_fade" else 1)*np.sign(pr)
            ent=O[i];sl=SLk*a*ent;ex=None
            for k in range(i,min(i+Hh,n-1)+1):
                if dates[k]!=dates[i] or hours[k]>20: break
                if d>0 and L[k]<=ent-sl: ex=ent-sl;break
                if d<0 and H[k]>=ent+sl: ex=ent+sl;break
                if k==i+Hh or hours[k]==20: ex=C[k];break
            if ex is None: ex=C[min(i+Hh,n-1)]
            out.append((T[i], float(d*(ex-ent)/ent - cost_frac(p,ent))))
    elif kind=="C2_breakout":
        byday={}
        for i in range(len(O)): byday.setdefault(dates[i],{})[hours[i]]=i
        for day,hrs in byday.items():
            if not all(h in hrs for h in [1,7,16]): continue
            idx=[hrs[h] for h in range(1,8) if h in hrs]
            if len(idx)<4: continue
            hi=max(H[j] for j in idx);lo=min(L[j] for j in idx);rng=hi-lo
            i0=hrs[1];a=ap[i0]
            if not np.isfinite(a): continue
            if rng>=0.5*(a*O[i0]*6.0): continue
            ent=None;d=0;ej=None
            for h in [7,8,9,10]:
                if h not in hrs: continue
                j=hrs[h]
                if H[j]>=hi: ent=hi;d=1;ej=j;break
                if L[j]<=lo: ent=lo;d=-1;ej=j;break
            if ent is None: continue
            cl=hrs[16];sl=lo if d>0 else hi;ex=C[cl]
            for j in range(ej,cl+1):
                if d>0 and L[j]<=sl: ex=sl;break
                if d<0 and H[j]>=sl: ex=sl;break
            out.append((T[ej], float(d*(ex-ent)/ent - cost_frac(p,ent))))
    elif kind in ("C3_rev","C3_cont"):
        byday={}
        for i in range(len(O)): byday.setdefault(dates[i],{})[hours[i]]=i
        for day,hrs in byday.items():
            if not all(h in hrs for h in [0,7,13]): continue
            i0=hrs[0];i7=hrs[7];i13=hrs[13];a=ap[i7]
            if not np.isfinite(a): continue
            asia=(O[i7]-O[i0])/O[i0]
            if abs(asia)<0.4*(a*7.0): continue
            d=(-1 if kind=="C3_rev" else 1)*np.sign(asia)
            ent=O[i7];sl=2.0*a*ent;ex=C[i13]
            for j in range(i7,i13+1):
                if d>0 and L[j]<=ent-sl: ex=ent-sl;break
                if d<0 and H[j]>=ent+sl: ex=ent+sl;break
            out.append((T[i7], float(d*(ex-ent)/ent - cost_frac(p,ent))))
    return out

# ---- 統計 ----
def block_boot_p(r,nboot=NPERM,block=5,seed=SEED):
    r=np.asarray(r,float);n=len(r)
    if n<15: return float("nan")
    rng=np.random.default_rng(seed);cnt=0;nblk=int(np.ceil(n/block))
    for _ in range(nboot):
        s=rng.integers(0,n,size=nblk)
        samp=np.concatenate([r[x:x+block] if x+block<=n else np.concatenate([r[x:],r[:x+block-n]]) for x in s])[:n]
        if samp.mean()<=0: cnt+=1
    return cnt/nboot

def desc(r):
    r=np.asarray(r,float)
    if len(r)==0: return dict(n=0)
    eq=np.cumsum(r);pk=np.maximum.accumulate(eq);gp=r[r>0].sum();gl=-r[r<0].sum()
    return dict(n=int(len(r)),net=float(eq[-1]),mean=float(r.mean()),
                win=float((r>0).mean()),pf=float(gp/gl) if gl>0 else float("inf"),
                maxdd=float((eq-pk).min()))

def yearly_jk(trades):
    """年次ジャックナイフ: 各年を抜いた残りで boot_p。max_p を返す。"""
    if not trades: return float("nan")
    yrs=sorted(set(t.astype('datetime64[Y]').astype(int)+1970 for t,_ in [(np.datetime64(t),r) for t,r in trades]))
    mp=0.0
    for y in yrs:
        rr=[r for t,r in trades if (np.datetime64(t).astype('datetime64[Y]').astype(int)+1970)!=y]
        p=block_boot_p(rr)
        if np.isfinite(p): mp=max(mp,p)
    return mp

def wf(trades,k=5):
    if len(trades)<k*5: return "n/a"
    seg=np.array_split(np.arange(len(trades)),k);pos=0
    for s in seg:
        if sum(trades[i][1] for i in s)>0: pos+=1
    return f"{pos}/{k}"

def load_strategy_monthly():
    out={}
    for name in ["v7","v4","e5"]:
        path=os.path.join(_dir(V_SERIES_DIR), f"{name}_monthly.csv")
        if os.path.exists(path):
            d=pd.read_csv(path); out[name]=d.set_index(d.columns[0])[d.columns[1]]
    return out

def monthly_series(trades):
    if not trades: return pd.Series(dtype=float)
    s=pd.Series({pd.Timestamp(t).to_period("M"):r for t,r in trades})
    return s.groupby(level=0).sum()

def main():
    strat=load_strategy_monthly()
    primary={"C1":"C1_fade","C2":"C2_breakout","C3":"C3_rev"}
    placebo={"C1":"C1_cont","C3":"C3_cont"}
    raw={}
    for p in PAIRS:
        df=load_h1(p); df.attrs["pair"]=p
        for kind in ["C1_fade","C1_cont","C2_breakout","C3_rev","C3_cont"]:
            raw.setdefault(kind,[]).extend(gen_trades(df,kind))
    res={"meta":{"source":"Dukascopy H1 10y (or local fallback)","alpha_family":ALPHA_FAMILY,
                 "alpha_strict":ALPHA_STRICT,"preregistered":"docs/47","note":"numbers are real run outputs only"},
         "candidates":{}}
    for cid,kind in primary.items():
        tr=sorted(raw[kind],key=lambda x:x[0]); rets=[r for _,r in tr]
        k=int(len(tr)*0.7); IS=[r for _,r in tr[:k]]; OOS=[r for _,r in tr[k:]]
        d_full=desc(rets); d_full["boot_p"]=block_boot_p(rets)
        d_oos=desc(OOS); d_oos["boot_p"]=block_boot_p(OOS)
        jk=yearly_jk(tr)
        ph=None
        if cid in placebo:
            pl=[r for _,r in raw[placebo[cid]]]; ph={**desc(pl),"boot_p":block_boot_p(pl)}
        # R1 相関
        corr={}
        if strat:
            ms=monthly_series(tr)
            for name,s in strat.items():
                s2=s.copy(); s2.index=pd.PeriodIndex(s2.index,freq="M") if not isinstance(s2.index,pd.PeriodIndex) else s2.index
                j=pd.concat([ms.rename("c"),s2.rename("s")],axis=1).dropna()
                corr[name]=float(j["c"].corr(j["s"])) if len(j)>=12 else None
        # 判定
        g3 = (np.isfinite(d_oos["boot_p"]) and d_oos["boot_p"]<ALPHA_FAMILY)
        g5 = (np.isfinite(jk) and jk<=0.10)
        g6 = (desc(IS)["net"]>0 and d_oos["net"]>0)
        g7v = wf(tr); g7 = g7v not in("n/a",) and int(g7v.split("/")[0])>=4
        r1 = all((c is None) or abs(c)<=0.3 for c in corr.values()) if corr else None
        if g3 and g5 and g6 and g7 and (r1 is True): grade="ADOPT"
        elif g6 and g7 and (r1 in (True,None)): grade="STRONG-LEAD" if (g3 or g5) else "LEAD"
        else: grade="REJECT"
        res["candidates"][cid]={"kind":kind,"full":d_full,"IS":desc(IS),"OOS":d_oos,
                                "yearly_jk_maxp":jk,"wf":g7v,"placebo":ph,"corr_v7v4e5":corr,
                                "gates":{"G3":bool(g3),"G5":bool(g5),"G6":bool(g6),"G7":bool(g7),"R1":r1},
                                "grade":grade}
    os.makedirs("research/results",exist_ok=True)
    with open("research/results/edge10_4thedge_10y.json","w") as f:
        json.dump(res,f,indent=2,default=str)
    print("="*72)
    for cid,c in res["candidates"].items():
        f=c["full"];o=c["OOS"]
        print(f"\n[{cid} {c['kind']}] n={f['n']} net={f['net']*100:+.1f}% PF={f['pf']:.3f} win={f['win']*100:.1f}% maxDD={f['maxdd']*100:.1f}%")
        print(f"  OOS n={o['n']} net={o['net']*100:+.1f}% boot_p={o['boot_p']:.4f}(α={ALPHA_FAMILY}) JKmax={c['yearly_jk_maxp']} WF={c['wf']} corr={c['corr_v7v4e5']}")
        print(f"  gates={c['gates']}  →  {c['grade']}")
    print("\n出所: research/results/edge10_4thedge_10y.json  ／ STRONG-LEAD以上のみ v11 EA化を検討（docs/47 §6）")

if __name__=="__main__":
    main()
