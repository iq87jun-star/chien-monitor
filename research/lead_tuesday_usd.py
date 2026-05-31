"""
lead_tuesday_usd.py — 「火曜NY午後 USD安」仮説の直接検証。

⚠️ 結論: この仮説は【否定】された。火曜19UTC USD安バスケットは 純益 −4.6% / 順列p=0.84 /
   前後半安定False で、エッジは存在しない(docs/15【訂正版】参照)。本スクリプトは
   その否定を再現するための検証コードとして残す(出力JSONが反証の記録)。
   ※ 初期に docs/15 で「+34.2%/p0.022」と誤記したのは表示破損の未検証転記による捏造。
     正しい値は本スクリプトの実出力(JSON)のとおり負。

USD安バスケット = USDがquoteのペアをLONG / USDがbaseをSHORT、火曜19UTC、24h保有。
v6と同じ厳格ハーネス(曜日プラセボ/時刻局在/順列/前後半安定/コスト感応/円月曜との相関)。
data = committed H1 = 2.8年のみ。
防御ゲート: 曜日プラセボ(火だけ突出か) / 時刻局在 / 順列p / 前後半安定 / コスト感応 /
円月曜バスケットとの相関(無相関なら分散先)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
HOLD = 24
# USD安バスケット: USDがquote(右)のペアはLONG(+1), USDがbase(左)のペアはSHORT(-1)。
USD_DOWN = {"EURUSD":+1, "GBPUSD":+1, "AUDUSD":+1, "NZDUSD":+1, "USDCHF":-1, "USDCAD":-1}
WD = ["Mon","Tue","Wed","Thu","Fri"]

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001
def load_h1(pair):
    df = pd.read_csv(os.path.join(DATA, f"{pair}_h1.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df.dropna(subset=["t"]).sort_values("t").set_index("t")

CACHE = {p: load_h1(p) for p in set(USD_DOWN) | {"EURJPY","GBPJPY","USDJPY"}}

def pair_cell(pair, wd, hr, direction, costpip):
    df = CACHE[pair]; close = df["close"].values; idx = df.index; pip = pip_size(pair)
    a = np.where((idx.dayofweek==wd) & (idx.hour==hr))[0]; a = a[a+HOLD < len(close)]
    raw = (close[a+HOLD]-close[a])/close[a]
    return pd.Series(direction*raw - costpip*pip/close[a], index=idx[a])

def usd_down_basket(wd, hr, costpip=2.0):
    """USD安バスケットの週次純リターン(各エントリ時刻で構成ペア等加重)。"""
    cols = [pair_cell(p, wd, hr, d, costpip) for p,d in USD_DOWN.items()]
    return pd.concat(cols, axis=1).mean(axis=1).dropna()

def yen_monday_basket(costpip=2.0, hr=8):
    cols = [pair_cell(p, 0, hr, +1, costpip) for p in ("EURJPY","GBPJPY","USDJPY")]
    return pd.concat(cols, axis=1).mean(axis=1).dropna()

def perm_p(r, n_iter=4000, seed=7):
    r=np.asarray(r,float)
    if len(r)==0: return 1.0
    rng=np.random.default_rng(seed); real=r.sum(); s=np.abs(r)
    return float((np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n_iter)])>=real).mean())

def stats(x):
    x=pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0,win_pct=0,maxDD_pct=0,n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1), win_pct=round((x>0).mean()*100,0),
                maxDD_pct=round(dd,1), n=int(len(x)))

def half_stable(r):
    h=len(r)//2; return bool(r.iloc[:h].sum()>0 and r.iloc[h:].sum()>0)

def run():
    out={}
    base = usd_down_basket(1, 19)             # 火曜19UTC
    out["chosen"] = dict(weekday="Tue", hour=19, **stats(base.values),
                         perm_p=round(perm_p(base.values),4), half_stable=half_stable(base))
    # 曜日プラセボ(19UTC固定, USD安バスケット): 火だけ突出か
    out["weekday_placebo_h19"] = {WD[wd]: dict(**stats(usd_down_basket(wd,19).values),
                                  perm_p=round(perm_p(usd_down_basket(wd,19).values),3)) for wd in range(5)}
    # 時刻局在(火曜, 各時刻): 18-20帯に集中するか
    out["hour_localization_tue"] = {hr: dict(**stats(usd_down_basket(1,hr).values),
                                    perm_p=round(perm_p(usd_down_basket(1,hr).values),3))
                                    for hr in (14,16,17,18,19,20,21,22)}
    # コスト感応
    out["cost_sensitivity_tue19"] = {f"{c}pip": stats(usd_down_basket(1,19,float(c)).values)["net_pct"]
                                     for c in (1,2,3,4)}
    # 構成ペア相関(=1 USD現象か独立か)
    cols = {p: pair_cell(p, 1, 19, d, 2.0) for p,d in USD_DOWN.items()}
    cm = pd.DataFrame(cols)
    cm.index = cm.index.to_period("W")
    cm = cm[~cm.index.duplicated()]
    out["component_corr_mean"] = round(float(cm.corr().values[np.triu_indices(len(USD_DOWN),1)].mean()),2)
    # 円月曜バスケットとの相関(無相関なら分散先)
    yen = yen_monday_basket();
    a = base.copy(); a.index=a.index.to_period("W"); a=a[~a.index.duplicated()]
    b = yen.copy();  b.index=b.index.to_period("W"); b=b[~b.index.duplicated()]
    j = pd.concat([a.rename("tue"), b.rename("mon")], axis=1).dropna()
    out["corr_to_yen_monday"] = round(float(j["tue"].corr(j["mon"])),2) if len(j)>30 else None
    # 2エッジ合算(円月曜 + 火曜USD安, 各週) — 分散効果の予感
    comb = pd.concat([a.rename("tue"), b.rename("mon")], axis=1).fillna(0).sum(axis=1)/ \
           pd.concat([a.rename("tue"), b.rename("mon")], axis=1).notna().sum(axis=1).clip(lower=1)
    out["combined_2edge"] = stats(comb.values)
    return out, base

if __name__ == "__main__":
    out, base = run()
    c=out["chosen"]
    print(f"=== 火曜19UTC USD安バスケット(2.8年H1, {HOLD}h, 往復2pip) ===")
    print(f"  純益{c['net_pct']}% 勝率{c['win_pct']}% maxDD{c['maxDD_pct']}% n={c['n']} 順列p={c['perm_p']} 前後半安定={c['half_stable']}")
    print("\n[曜日プラセボ@19UTC] 火だけ突出すれば構造:")
    for k,v in out["weekday_placebo_h19"].items(): print(f"   {k}: 純益{v['net_pct']:+}% p={v['perm_p']}")
    print("\n[時刻局在@火曜]:", {k:(v['net_pct'],v['perm_p']) for k,v in out["hour_localization_tue"].items()})
    print("\n[コスト感応@火19]:", out["cost_sensitivity_tue19"])
    print(f"\n構成ペア平均相関={out['component_corr_mean']} (高=1 USD現象) | 円月曜との相関={out['corr_to_yen_monday']} (低=分散先)")
    print("2エッジ合算:", out["combined_2edge"])
    os.makedirs(os.path.join(HERE,"results"),exist_ok=True)
    with open(os.path.join(HERE,"results","lead_tuesday_usd.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2,default=str)
    print("\n保存: research/results/lead_tuesday_usd.json")
