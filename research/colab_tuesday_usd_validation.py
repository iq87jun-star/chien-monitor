"""
colab_tuesday_usd_validation.py — 「火曜NY午後 USD安ドリフト」第2エッジ候補の10年H1追認。

⚠️ 注記: 「火曜USD安」仮説は committed 2.8年H1では【否定】された(純益−4.6%/p0.84,
   docs/15【訂正版】)。本スクリプトは(a)その否定を10年H1で追認する、(b)任意の
   (曜日×時刻)セル+バスケットを同じハーネスで検証する再利用テンプレ、として残す。
   entry_hour / USD_DOWN / weekday を書き換えれば別仮説の検証にも使える。

位置づけ: 任意の(曜日×セッション時刻)フロー・ドリフト仮説を、ユーザーの Colab 環境
(実10年H1)で本検証ハーネスに通すための自己完結スクリプト。
v6独立検証ノートと同じ厳格さ(順列 / 曜日プラセボ / 時刻帯 / IS-OOS / 全年ジャックナイフ /
Bonferroni / コスト感応 / 構成相関 / 円月曜との相関 / 2エッジ合算DD)。

判定の眼目(2.8年で見えた構造が10年でも残るか):
  G1 曜日プラセボ: 火曜だけ有意、他曜日 非有意
  G2 時刻帯: 18-19(-20)UTC に局在(13-15のロンドン/NY重複ボラ帯とは別)
  G3 IS/OOS: 後半でも符号・有意維持(レジーム・アーティファクトでない)
  G4 全年ジャックナイフ: どの年を除いても有意維持(特定年依存でない)
  G5 Bonferroni: 多重検定補正後も生存(2.8年では生存ゼロだった)
  G6 円月曜との相関 <= 0.4(分散先たりうる)
全通過 → 第2エッジ認定 → ポートフォリオEA化へ。1つでも崩れたら破棄(docs/14と同じ規律)。

使い方(Colab):
  USE_DRIVE=True, DRIVE_BASE と H1_DIR を自分の {PAIR}_h1.csv 置き場に合わせる。
  必要ペア: EURUSD GBPUSD AUDUSD NZDUSD USDCHF USDCAD + EURJPY GBPJPY USDJPY。
※ シミュレーション。将来/ライブ約定を保証しない。最終はデモ前進検証で確認のこと。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

# === ユーザー設定(Colabで編集) ===
USE_DRIVE      = True
DRIVE_BASE     = "/content/drive/MyDrive/forex_ml"
H1_DIR         = "{base}/dukascopy_data_h1"      # {PAIR}_h1.csv
LOCAL_FALLBACK = "./research/data"               # ローカル実行時(2.8年)フォールバック

HOLD = 24                                        # 保有時間(h) = v6と同じ
DEFAULT_COST_PIP = 2.0                           # 往復(スプレッド+スリッページ)
USD_DOWN = {"EURUSD":+1,"GBPUSD":+1,"AUDUSD":+1,"NZDUSD":+1,"USDCHF":-1,"USDCAD":-1}
YEN = ["EURJPY","GBPJPY","USDJPY"]
WD  = ["Mon","Tue","Wed","Thu","Fri"]

if USE_DRIVE:
    try:
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive マウント不可(ローカル実行?):", e); USE_DRIVE=False

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001

def _resolve(pair):
    cands = []
    if USE_DRIVE:
        base = H1_DIR.format(base=DRIVE_BASE)
        cands += [f"{base}/{pair}_h1.csv", f"{base}/{pair}.csv"]
    cands += [f"{LOCAL_FALLBACK}/{pair}_h1.csv"]
    for c in cands:
        if os.path.exists(c): return c
    raise FileNotFoundError(f"{pair}: H1 CSV が見つからない。探索: {cands}")

def load_h1(pair):
    df = pd.read_csv(_resolve(pair))
    tcol = None
    for cand in ("time","timestamp","date","datetime","gmt time","local time"):
        m = [c for c in df.columns if c.lower()==cand]
        if m: tcol = m[0]; break
    if tcol is None: tcol = df.columns[0]
    df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def pick(*names):
        for n in names:
            for c in df.columns:
                if c.lower()==n: return c
        return None
    cc = pick("close","bidclose","bid_close","c")
    out = pd.DataFrame(index=df.index); out["close"] = df[cc].astype(float)
    return out.dropna()

CACHE = {}
def H1(p):
    if p not in CACHE: CACHE[p] = load_h1(p)
    return CACHE[p]

# ---- コア ----
def pair_cell(pair, wd, hr, direction, costpip):
    df = H1(pair); close = df["close"].values; idx = df.index; pip = pip_size(pair)
    a = np.where((idx.dayofweek==wd) & (idx.hour==hr))[0]; a = a[a+HOLD < len(close)]
    raw = (close[a+HOLD]-close[a])/close[a]
    return pd.Series(direction*raw - costpip*pip/close[a], index=idx[a])

def usd_down_basket(wd, hr, costpip=DEFAULT_COST_PIP):
    cols = [pair_cell(p, wd, hr, d, costpip) for p,d in USD_DOWN.items()]
    return pd.concat(cols, axis=1).mean(axis=1).dropna()

def yen_monday_basket(hr=8, costpip=DEFAULT_COST_PIP):
    cols = [pair_cell(p, 0, hr, +1, costpip) for p in YEN]
    return pd.concat(cols, axis=1).mean(axis=1).dropna()

def perm_p(r, n_iter=5000, seed=20260531):
    r = np.asarray(r, float)
    if len(r)==0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); s = np.abs(r)
    null = np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n_iter)])
    return float((null >= real).mean())

def stats(x):
    x = pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0,win_pct=0,maxDD_pct=0,n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1), win_pct=round((x>0).mean()*100,0),
                maxDD_pct=round(dd,1), n=int(len(x)))

def to_week(s):
    z = s.copy(); z.index = s.index.to_period("W"); return z[~z.index.duplicated()]

# ---- 検証 ----
def validate(entry_hour=19):
    res = {}
    base = usd_down_basket(1, entry_hour)
    res["chosen"] = dict(weekday="Tue", hour=entry_hour, **stats(base.values),
                         perm_p=round(perm_p(base.values),4))
    # G1 曜日プラセボ
    res["G1_weekday_placebo"] = {WD[wd]: dict(**stats(usd_down_basket(wd,entry_hour).values),
                                 perm_p=round(perm_p(usd_down_basket(wd,entry_hour).values),3)) for wd in range(5)}
    # G2 時刻局在(火曜・全時刻)
    res["G2_hour_localization"] = {hr: dict(**stats(usd_down_basket(1,hr).values),
                                   perm_p=round(perm_p(usd_down_basket(1,hr).values),3)) for hr in range(24)}
    # G3 IS/OOS
    half = base.index[len(base)//2]
    res["G3_oos"] = dict(IS=stats(base[base.index<half].values),
                         OOS=stats(base[base.index>=half].values),
                         OOS_perm_p=round(perm_p(base[base.index>=half].values),4))
    # G4 全年ジャックナイフ
    yrs = sorted(set(base.index.year))
    res["G4_jackknife"] = {int(y): round(perm_p(base[base.index.year!=y].values),3) for y in yrs}
    res["G4_jackknife_max_p"] = round(max(res["G4_jackknife"].values()),3)
    # G5 Bonferroni(発見スキャンの規模 9ペア×5曜日×24時刻=1080 を試行数とみなす)
    n_tests = 9*5*24
    res["G5_bonferroni"] = dict(alpha=round(0.05/n_tests,6), chosen_p=res["chosen"]["perm_p"],
                                survives=bool(res["chosen"]["perm_p"] <= 0.05/n_tests))
    # G6 円月曜との相関 + 構成相関
    comp = pd.DataFrame({p: pair_cell(p,1,entry_hour,d,DEFAULT_COST_PIP) for p,d in USD_DOWN.items()})
    comp.index = comp.index.to_period("W"); comp = comp[~comp.index.duplicated()]
    res["component_corr_mean"] = round(float(comp.corr().values[np.triu_indices(len(USD_DOWN),1)].mean()),2)
    a, b = to_week(base), to_week(yen_monday_basket())
    j = pd.concat([a.rename("tue"), b.rename("mon")], axis=1).dropna()
    res["G6_corr_to_yen_monday"] = round(float(j["tue"].corr(j["mon"])),2) if len(j)>30 else None
    # コスト感応
    res["cost_sensitivity"] = {f"{c}pip": stats(usd_down_basket(1,entry_hour,float(c)).values)["net_pct"]
                               for c in (1,2,3,4)}
    # 2エッジ合算ポートフォリオ(等加重・週次)
    p2 = pd.concat([a.rename("tue"), b.rename("mon")], axis=1)
    comb = p2.mean(axis=1).dropna()
    res["combined_portfolio"] = dict(**stats(comb.values),
                                     yen_only=stats(b.values), tue_only=stats(a.values))
    return res

if __name__ == "__main__":
    R = validate(19)
    c = R["chosen"]
    print(f"=== 火曜{c['hour']}UTC USD安バスケット(10年H1想定 / {HOLD}h / 往復{DEFAULT_COST_PIP}pip) ===")
    print(f"  純益{c['net_pct']}% 勝率{c['win_pct']}% maxDD{c['maxDD_pct']}% n={c['n']} 順列p={c['perm_p']}")
    print("\n[G1 曜日プラセボ] 火だけ有意なら合格:")
    for k,v in R["G1_weekday_placebo"].items(): print(f"   {k}: 純益{v['net_pct']:+}% p={v['perm_p']}")
    print("\n[G2 時刻局在] 18-19(-20)に集中なら合格:")
    for hr in (15,16,17,18,19,20,21,22):
        v=R["G2_hour_localization"][hr]; print(f"   {hr:02d}UTC: 純益{v['net_pct']:+}% p={v['perm_p']}")
    o=R["G3_oos"]; print(f"\n[G3 IS/OOS] IS純益{o['IS']['net_pct']}% / OOS純益{o['OOS']['net_pct']}% OOS_p={o['OOS_perm_p']}")
    print(f"[G4 ジャックナイフ] max_p={R['G4_jackknife_max_p']} (<=0.05 で合格)")
    g5=R["G5_bonferroni"]; print(f"[G5 Bonferroni] α={g5['alpha']} chosen_p={g5['chosen_p']} → 生存={g5['survives']}")
    print(f"[G6 相関] 円月曜との相関={R['G6_corr_to_yen_monday']} (<=0.4で分散先) / 構成内部相関={R['component_corr_mean']}")
    print(f"[コスト感応] {R['cost_sensitivity']}")
    cp=R["combined_portfolio"]
    print(f"\n[2エッジ合算] 純益{cp['net_pct']}% maxDD{cp['maxDD_pct']}% "
          f"(円のみ DD{cp['yen_only']['maxDD_pct']}% / 火USDのみ DD{cp['tue_only']['maxDD_pct']}%)")
    gates = [R["G1_weekday_placebo"]["Tue"]["perm_p"]<=0.05,
             max(R["G2_hour_localization"][h]["perm_p"] for h in (18,19))<=0.05,
             o["OOS_perm_p"]<=0.05, R["G4_jackknife_max_p"]<=0.05,
             g5["survives"], (R["G6_corr_to_yen_monday"] or 1) <= 0.4]
    print(f"\n>>> 総合: 6ゲート中 {sum(gates)} 通過。", "★第2エッジ認定→EA化へ" if all(gates) else "未達ゲートあり→保留/破棄")
    try:
        out = H1_DIR.format(base=DRIVE_BASE) + "/tuesday_usd_validation.json" if USE_DRIVE else "research/results/tuesday_usd_validation.json"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out,"w") as f: json.dump(R,f,ensure_ascii=False,indent=2,default=str)
        print("保存:", out)
    except Exception as e:
        print("JSON保存スキップ:", e)
