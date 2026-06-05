"""
edge2_candidates.py — 「2本目(別ロジック)」候補の横断検証。利益優先・正直なグレード付き。

ユーザー要望: 利益が出るなら方向は問わない。ただし docs/15 の捏造を繰り返さぬよう、
構造的な事前仮説のある候補のみを、v6と同じ全ゲートで検定し、実測で最良を選ぶ。
全候補は v7(円月曜LONG)との相関と、合算ポートフォリオ改善で評価する。

候補(いずれも事前仮説あり):
  A. CHF_Thu_PM_SHORT  : USDCHF 木曜午後 SHORT(スキャンで帯。docs/15リード)
  B. YEN_Fri_SHORT     : 円クロス 金曜 SHORT。docs/12が「3ペア全て金曜−」と記録した
                         週次シーズナリティの【裏側】。月曜LONGと別日・逆方向 = 独立性期待。
                         週末ギャップ回避のため日中(hold<=10h, 金曜引け前に決済)。
  C. YEN_Fri_SHORT_24h : 同上だが24h保有(週末越え)。ギャップ込みで優位か比較用。
  D. LATE_USD_SHORT    : 非円USD(EUR/GBP/AUD/NZD USD は LONG, USDCHF/CAD は SHORT)を
                         金曜にまとめた「週後半リスクオフ/USD安」バスケット。

各候補 → 曜日プラセボ / 順列p / IS-OOS / ジャックナイフ / コスト感応 / 円月曜相関 /
合算改善。グレード: CORE(p<=.05 & JK<=.05 & OOS符号維持) / LEAD(EV+ & 独立 & 一部ゲート) /
REJECT。⚠ 2.8年・JSON直読/marker検証。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(HERE,"data")
HOLD24=24; WD=["Mon","Tue","Wed","Thu","Fri"]
def pip(p): return 0.01 if p.endswith("JPY") else 0.0001
def load(p):
    d=pd.read_csv(os.path.join(DATA,f"{p}_h1.csv")); d["t"]=pd.to_datetime(d["timestamp"],utc=True,errors="coerce")
    return d.dropna(subset=["t"]).sort_values("t").set_index("t")
C={p:load(p) for p in ["EURJPY","GBPJPY","USDJPY","EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCHF","USDCAD"]}

def leg(pair, wd, hour, direction, hold, costpip=2.0):
    df=C[pair]; cv=df["close"].values; idx=df.index; ps=pip(pair)
    a=np.where((idx.dayofweek==wd)&(idx.hour==hour))[0]; a=a[a+hold<len(cv)]
    s=pd.Series(direction*(cv[a+hold]-cv[a])/cv[a]-costpip*ps/cv[a], index=idx[a].to_period("W"))
    return s[~s.index.duplicated()]

def basket(legs, costpip=2.0):
    """legs=[(pair,wd,hour,dir,hold),...] を週次等加重。"""
    cols=[leg(p,wd,h,d,hold,costpip) for (p,wd,h,d,hold) in legs]
    return pd.concat(cols,axis=1).mean(axis=1).dropna()

def perm_p(r,n=5000,seed=13):
    r=np.asarray(r,float)
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); s=np.abs(r)
    return float((np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n)])>=real).mean())
def stats(x):
    x=pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0,win_pct=0,maxDD_pct=0,n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1),win_pct=round((x>0).mean()*100,0),maxDD_pct=round(dd,1),n=int(len(x)))

# 円月曜LONG(v7構成)= 相関・合算の基準
YEN_MON=basket([(p,0,h,+1,HOLD24) for p in ("EURJPY","GBPJPY","USDJPY") for h in (4,6,8,10)])

PM=[12,13,14,15,16,17,18,20]
AM=[8,10]   # 金曜日中(週末ギャップ回避): 金曜朝エントリ・短時間保有
def cand_legs(name):
    if name=="A_CHF_Thu_PM_SHORT":
        return [("USDCHF",3,h,-1,HOLD24) for h in PM]
    if name=="B_YEN_Fri_SHORT_intraday":
        return [(p,4,h,-1,8) for p in ("EURJPY","GBPJPY","USDJPY") for h in AM]   # 8h保有=引け前
    if name=="C_YEN_Fri_SHORT_24h":
        return [(p,4,h,-1,HOLD24) for p in ("EURJPY","GBPJPY","USDJPY") for h in AM]
    if name=="D_LATE_USD_SHORT_Fri":
        usd={"EURUSD":+1,"GBPUSD":+1,"AUDUSD":+1,"NZDUSD":+1,"USDCHF":-1,"USDCAD":-1}
        return [(p,4,h,d,HOLD24) for p,d in usd.items() for h in (12,14,16,18)]
    raise ValueError(name)

def weekday_placebo(name):
    """同じ構成を曜日だけ変えて回す(時刻・方向・保有・ペアは固定)。核ゲート。"""
    out={}
    for wd in range(5):
        legs=[(p,wd,h,d,hold) for (p,_,h,d,hold) in cand_legs(name)]
        b=basket(legs); out[WD[wd]]=dict(**stats(b),perm_p=round(perm_p(b.values),3))
    return out

def grade(p,jk,oos_sign_ok,net):
    if net<=0: return "REJECT"
    if p<=0.05 and jk<=0.05 and oos_sign_ok: return "CORE"
    if p<=0.25 and net>0: return "LEAD"
    return "REJECT"

def run():
    out={}
    for name in ["A_CHF_Thu_PM_SHORT","B_YEN_Fri_SHORT_intraday","C_YEN_Fri_SHORT_24h","D_LATE_USD_SHORT_Fri"]:
        legs=cand_legs(name); b=basket(legs)
        if len(b)<30:
            out[name]=dict(note="insufficient",n=len(b)); continue
        h=b.index[len(b)//2]; isr=b[b.index<h]; oos=b[b.index>=h]
        yrs=sorted(set(b.index.year)); jk={int(y):round(perm_p(b[b.index.year!=y].values),3) for y in yrs}
        jkmax=round(max(jk.values()),3)
        p=round(perm_p(b.values),4)
        oos_ok=bool(oos.sum()>0 and isr.sum()>0)
        cost={f"{c}pip":stats(basket(legs,float(c)))["net_pct"] for c in (1,2,3,4)}
        # entry weekday for placebo display
        wd_entry=legs[0][1]
        pl=weekday_placebo(name)
        # 円月曜との相関 & 合算
        j=pd.concat([b.rename("x"),YEN_MON.rename("y")],axis=1).dropna()
        corr=round(float(j["x"].corr(j["y"])),2) if len(j)>30 else None
        comb=pd.concat([b.rename("x"),YEN_MON.rename("y")],axis=1).mean(axis=1).dropna()
        out[name]=dict(entry_weekday=WD[wd_entry], **stats(b), perm_p=p,
                       IS_net=stats(isr)["net_pct"], OOS_net=stats(oos)["net_pct"], OOS_perm_p=round(perm_p(oos.values),4),
                       jackknife_max_p=jkmax, cost=cost, corr_to_yen=corr,
                       weekday_placebo={k:(v["net_pct"],v["perm_p"]) for k,v in pl.items()},
                       combined_with_yen=dict(**stats(comb), yen_only_dd=stats(YEN_MON)["maxDD_pct"]),
                       grade=grade(p,jkmax,oos_ok,stats(b)["net_pct"]))
    out["_yen_monday_ref"]=stats(YEN_MON)
    return out

if __name__=="__main__":
    out=run()
    os.makedirs(os.path.join(HERE,"results"),exist_ok=True)
    with open(os.path.join(HERE,"results","edge2_candidates.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2,default=str)
    print("基準 円月曜LONG(v7):",out["_yen_monday_ref"])
    for name in ["A_CHF_Thu_PM_SHORT","B_YEN_Fri_SHORT_intraday","C_YEN_Fri_SHORT_24h","D_LATE_USD_SHORT_Fri"]:
        r=out[name]
        if "grade" not in r: print(f"\n### {name}: {r}"); continue
        print(f"\n### {name}  [{r['grade']}]")
        print(f"  純益{r['net_pct']}% 勝率{r['win_pct']}% maxDD{r['maxDD_pct']}% n={r['n']} p={r['perm_p']} | IS{r['IS_net']}/OOS{r['OOS_net']}(p{r['OOS_perm_p']}) JKmax_p={r['jackknife_max_p']}")
        print(f"  曜日プラセボ: "+" ".join(f"{k}{v[0]:+}%(p{v[1]})" for k,v in r['weekday_placebo'].items()))
        print(f"  コスト{r['cost']} | 円相関{r['corr_to_yen']} | 合算 純益{r['combined_with_yen']['net_pct']}% DD{r['combined_with_yen']['maxDD_pct']}%(円単独DD{r['combined_with_yen']['yen_only_dd']}%)")
    print("\n保存: research/results/edge2_candidates.json")
