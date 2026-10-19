"""
edge2_chf_lateweek.py — 第2エッジ候補「週後半 USDCHF SHORT(CHF高/USD安ドリフト)」の厳格検証。

背景: docs/15 のセッション・スキャン生出力で、円月曜とは別系統で唯一帯で出た非JPY候補が
  USDCHF SHORT。木曜12-20UTC + 金曜早朝に p<=0.05 が連続(帯)。docs/15では「孤立セル」と
  退けたが、再確認すると【単発でなく週後半に広がる帯】であり、v6を本物と判断した時と同じ
  『帯で出る』頑健性を持つ。ペアが非円・曜日が違う・方向がSHORT → 円月曜と無相関なら真の
  分散先(2本目)になり得る。本スクリプトで v6 と同じ全ゲートにかけ、本物か偶然かを判定する。

最重要ゲート = 曜日プラセボ:
  単なる2.8年のドル安トレンドなら【全曜日】でUSDCHF SHORTが出るはず(=偽)。
  木/金の週後半だけに局在するなら【構造】(=真)。これで regime-artifact を切り分ける。

全ゲート(v6 seasonality_monday.py と同型):
  G1 曜日プラセボ(週後半だけ突出か / トレンドの全曜日一様でないか) ★判定の核
  G2 時刻局在(午後帯に集中か / ランダム時刻では出ないか)
  G3 IS/OOS 安定(前半後半で符号維持 = レジーム・アーティファクトでない)
  G4 全年ジャックナイフ(特定年依存でない)
  G5 コスト感応(往復1-4pip)
  G6 順列 p / Bonferroni(スキャン1061セルを試行数とみなす)
  G7 円月曜エッジとの相関(<=0.4 なら分散先)

⚠ data = committed H1 = 2.8年のみ。USDCHFは1ペアで分散内蔵なし。よって本結果は「2本目の
  リード」で、10年H1追認(colab)を経てから採用。数値は JSON直読/marker検証。
"""
import os, json, numpy as np, pandas as pd, warnings, calendar
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PIP_CHF = 0.0001
HOLD = 24
WD = ["Mon","Tue","Wed","Thu","Fri"]

def load(p):
    d = pd.read_csv(os.path.join(DATA, f"{p}_h1.csv"))
    d["t"] = pd.to_datetime(d["timestamp"], utc=True, errors="coerce")
    return d.dropna(subset=["t"]).sort_values("t").set_index("t")

CHF = load("USDCHF")

def cell(weekday, hour, costpip=2.0, direction=-1):
    """USDCHF をその(曜日×時刻)で direction(-1=SHORT)・24h保有・コスト後。週index。"""
    cv = CHF["close"].values; idx = CHF.index
    a = np.where((idx.dayofweek==weekday) & (idx.hour==hour))[0]; a = a[a+HOLD < len(cv)]
    raw = (cv[a+HOLD]-cv[a])/cv[a]
    s = pd.Series(direction*raw - costpip*PIP_CHF/cv[a], index=idx[a])
    s.index = s.index.to_period("W"); return s[~s.index.duplicated()]

def band(weekday, hours, costpip=2.0, direction=-1):
    """複数時刻を等加重した『その曜日の午後帯バスケット』。週次。"""
    cols = [cell(weekday,h,costpip,direction) for h in hours]
    return pd.concat(cols, axis=1).mean(axis=1).dropna()

def perm_p(r, n_iter=5000, seed=13):
    r = np.asarray(r, float)
    if len(r)==0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); s = np.abs(r)
    return float((np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n_iter)])>=real).mean())

def stats(x):
    x = pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0,win_pct=0,maxDD_pct=0,n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1), win_pct=round((x>0).mean()*100,0),
                maxDD_pct=round(dd,1), n=int(len(x)))

# 円月曜バスケット(相関用) — v7と同じ構成
def yen_monday():
    cols=[]
    for p in ("EURJPY","GBPJPY","USDJPY"):
        d=load(p); cv=d["close"].values; idx=d.index
        for h in (4,6,8,10):
            a=np.where((idx.dayofweek==0)&(idx.hour==h))[0]; a=a[a+HOLD<len(cv)]
            s=pd.Series((cv[a+HOLD]-cv[a])/cv[a]-2*0.01/cv[a], index=idx[a].to_period("W"))
            cols.append(s[~s.index.duplicated()])
    return pd.concat(cols,axis=1).mean(axis=1).dropna()

AFTERNOON = [12,13,14,15,16,17,18,20]   # スキャンで木曜に帯で出た午後帯

def run():
    out = {}
    base = band(3, AFTERNOON)            # 木曜・午後帯 SHORT バスケット
    out["chosen"] = dict(weekday="Thu", hours=AFTERNOON, direction="SHORT",
                         **stats(base), perm_p=round(perm_p(base.values),4))
    h = base.index[len(base)//2]
    # G1 曜日プラセボ(同じ午後帯SHORTを各曜日で)★核
    out["G1_weekday_placebo"] = {WD[wd]: dict(**stats(band(wd,AFTERNOON)),
                                  perm_p=round(perm_p(band(wd,AFTERNOON).values),3)) for wd in range(5)}
    # G2 時刻局在(木曜・各時刻 単独SHORT)
    out["G2_hour_localization_thu"] = {hh: dict(**stats(cell(3,hh)),
                                       perm_p=round(perm_p(cell(3,hh).values),3)) for hh in range(24)}
    # G3 IS/OOS
    out["G3_oos"] = dict(IS=stats(base[base.index<h]), OOS=stats(base[base.index>=h]),
                         OOS_perm_p=round(perm_p(base[base.index>=h].values),4))
    # G4 ジャックナイフ
    yrs = sorted(set(base.index.year))
    jk = {int(y): round(perm_p(base[base.index.year!=y].values),3) for y in yrs}
    out["G4_jackknife"] = jk; out["G4_max_p"] = round(max(jk.values()),3)
    # G5 コスト感応
    out["G5_cost"] = {f"{c}pip": stats(band(3,AFTERNOON,float(c)))["net_pct"] for c in (1,2,3,4)}
    # G6 Bonferroni(スキャン規模1061を試行数とみなす)
    out["G6_bonferroni"] = dict(alpha=round(0.05/1061,6), chosen_p=out["chosen"]["perm_p"],
                                survives=bool(out["chosen"]["perm_p"] <= 0.05/1061))
    # G7 円月曜との相関
    a=base.copy(); b=yen_monday()
    j=pd.concat([a.rename("chf"), b.rename("yen")],axis=1).dropna()
    out["G7_corr_to_yen"] = round(float(j["chf"].corr(j["yen"])),2) if len(j)>30 else None
    # 2エッジ合算(円月曜 + 木CHF, 週次等加重)
    comb=pd.concat([a.rename("chf"), b.rename("yen")],axis=1)
    cw=comb.mean(axis=1).dropna()
    out["combined_2edge"] = dict(**stats(cw),
                                 yen_only=stats(b), chf_only=stats(a))
    return out, base

if __name__ == "__main__":
    out, base = run()
    os.makedirs(os.path.join(HERE,"results"), exist_ok=True)
    with open(os.path.join(HERE,"results","edge2_chf_lateweek.json"),"w") as f:
        json.dump(out,f,ensure_ascii=False,indent=2,default=str)
    c=out["chosen"]
    print(f"=== 木曜 午後帯 USDCHF SHORT バスケット(2.8年H1, 24h, 往復2pip) ===")
    print(f"  純益{c['net_pct']}% 勝率{c['win_pct']}% maxDD{c['maxDD_pct']}% n={c['n']} 順列p={c['perm_p']}")
    print("\n[G1 曜日プラセボ] ★週後半だけ突出ならエッジ / 全曜日ならトレンド:")
    for k,v in out["G1_weekday_placebo"].items(): print(f"   {k}: 純益{v['net_pct']:+}% p={v['perm_p']}")
    print("\n[G2 時刻局在@木] 午後帯に集中?:")
    for hh in (6,8,10,12,13,14,15,16,17,18,20,22):
        v=out["G2_hour_localization_thu"][hh]; print(f"   {hh:02d}UTC 純益{v['net_pct']:+}% p={v['perm_p']}")
    o=out["G3_oos"]; print(f"\n[G3 IS/OOS] IS{o['IS']['net_pct']}% / OOS{o['OOS']['net_pct']}% OOS_p={o['OOS_perm_p']}")
    print(f"[G4 ジャックナイフ] max_p={out['G4_max_p']}")
    print(f"[G5 コスト感応] {out['G5_cost']}")
    g6=out["G6_bonferroni"]; print(f"[G6 Bonferroni] α={g6['alpha']} p={g6['chosen_p']} 生存={g6['survives']}")
    print(f"[G7 円月曜との相関] {out['G7_corr_to_yen']} (<=0.4で分散先)")
    cb=out["combined_2edge"]; print(f"[2エッジ合算] 純益{cb['net_pct']}% maxDD{cb['maxDD_pct']}% "
          f"(円のみDD{cb['yen_only']['maxDD_pct']}% / CHFのみDD{cb['chf_only']['maxDD_pct']}%)")
    print("\n保存: research/results/edge2_chf_lateweek.json")
