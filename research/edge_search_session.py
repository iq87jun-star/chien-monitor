"""
edge_search_session.py — 「生きたエッジ(v6)」の抽象化拡張: (曜日 × セッション時刻)スキャン。

抽象化: v6で生き残ったエッジ = 「特定の(曜日×セッション時刻)セルに集中する、
価格予測ではないフロー由来の方向ドリフト」。円月曜08UTCはその1例。docs/14の日足
スキャンは1日を平均して時刻情報を潰したため非JPYで何も出なかった。本スクリプトは
H1で 全9ペア × 曜日5 × 時刻24 × 方向 を走査し、同型のエッジが他ペア/他時刻に
無いかを探す。

⚠ データは committed H1 = 2.8年のみ(実10年H1はこの環境に無い)。よって本結果は
「発見・リード」段階であり、要・10年H1での追認。短期データの偽陽性に対する防御として:
  (1) 順列検定 p
  (2) 前後半で符号一致(安定性ゲート)
  (3) 隣接時刻も同方向(帯で出る= v6の04-10帯と同じ頑健性)
  (4) 陽性対照: EURJPY 月曜 朝 が検出されること(手法の妥当性確認)
を全候補に課す。ホールドは v6 同様 24h、往復2pip控除。シミュレーション。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PAIRS = ["EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCAD","USDCHF","USDJPY","EURJPY","GBPJPY"]
WD = ["Mon","Tue","Wed","Thu","Fri"]
HOLD = 24
COST = 2.0

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001

def load_h1(pair):
    df = pd.read_csv(os.path.join(DATA, f"{pair}_h1.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    return df

def perm_p(rets, n_iter=2000, seed=7):
    rets = np.asarray(rets, float)
    if len(rets) == 0: return 1.0
    rng = np.random.default_rng(seed); real = rets.sum(); s = np.abs(rets)
    null = np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n_iter)])
    return float((null >= real).mean())

def cell_rets(close, idx, wd, hr, direction, pip):
    """(曜日wd×時刻hr)で entry, HOLD後 exit の方向別純リターン配列。"""
    a = np.where((idx.dayofweek==wd) & (idx.hour==hr))[0]
    a = a[a + HOLD < len(close)]
    if len(a)==0: return np.array([])
    raw = (close[a+HOLD] - close[a]) / close[a]
    return direction*raw - COST*pip/close[a]

def net_pct(r):
    if len(r)==0: return 0.0
    return float(((1+pd.Series(r)).prod()-1)*100)

def run():
    rows = []
    cache = {}
    for pair in PAIRS:
        df = load_h1(pair); cache[pair] = df
        close = df["close"].values; idx = df.index; pip = pip_size(pair)
        for wd in range(5):
            for hr in range(24):
                rL = cell_rets(close, idx, wd, hr, +1, pip)
                if len(rL) < 80: continue
                h = len(rL)//2; h1, h2 = rL[:h].sum(), rL[h:].sum()
                # 方向は前後半合算の符号で決める(LONG/SHORT)
                direction = +1 if rL.sum() >= 0 else -1
                r = direction*rL  # 符号をエッジ方向へ
                hh1, hh2 = r[:h].sum(), r[h:].sum()
                stable = (hh1 > 0) and (hh2 > 0)              # 安定性ゲート
                rows.append(dict(pair=pair, wd=WD[wd], hr=hr,
                                 dir=("L" if direction>0 else "S"),
                                 n=len(r), net_pct=round(net_pct(r),1),
                                 stable=stable, _r=r))
    df = pd.DataFrame(rows)
    n_cells = len(df)
    # 一次プレスクリーン: 安定 & 純益>0
    pre = df[df.stable & (df.net_pct > 0)].copy()
    # 順列検定(プレスクリーン通過のみ)
    pre["perm_p"] = pre["_r"].apply(lambda r: round(perm_p(np.asarray(r)),4))
    alpha_bonf = 0.05 / n_cells
    pre = pre.sort_values("perm_p").reset_index(drop=True)

    # 隣接時刻バンド: 同(pair,wd,dir)で hr±1 も陽性(stable&net>0)か
    posset = set((row.pair,row.wd,row.dir,row.hr) for row in pre.itertuples())
    def band(row):
        return ((row.pair,row.wd,row.dir,(row.hr-1)%24) in posset) or \
               ((row.pair,row.wd,row.dir,(row.hr+1)%24) in posset)
    pre["band"] = pre.apply(band, axis=1)

    return df, pre, n_cells, alpha_bonf, cache

if __name__ == "__main__":
    pd.set_option("display.width",220); pd.set_option("display.max_columns",30); pd.set_option("display.max_rows",80)
    df, pre, n_cells, alpha_bonf, cache = run()
    show = pre.drop(columns=["_r"])

    print(f"全セル数={n_cells}  Bonferroni α={alpha_bonf:.5f}  (データ=2.8年H1, ホールド{HOLD}h, 往復{COST}pip)")
    # 陽性対照
    ctrl = show[(show.pair=="EURJPY") & (show.wd=="Mon")]
    print("\n[陽性対照] EURJPY 月曜(朝帯が低pで出れば手法妥当):")
    print(ctrl.sort_values("hr").to_string() if len(ctrl) else "  検出なし")

    print(f"\n===== 安定(前後半とも+) & 順列 p<=0.05 の上位 =====")
    top = show[show.perm_p <= 0.05]
    print(top.head(40).to_string() if len(top) else "  なし")

    # 本命: 非JPY かつ 帯で出る かつ p<=0.01
    lead = show[(~show.pair.str.endswith("JPY")) & (show.band) & (show.perm_p <= 0.01)]
    print(f"\n===== ★リード候補(非JPY・帯・p<=0.01): {len(lead)}件 =====")
    print(lead.sort_values("perm_p").to_string() if len(lead) else "  なし(非JPYには同型エッジ検出されず)")

    bonf = show[show.perm_p <= alpha_bonf]
    print(f"\nBonferroni 生存(p<=α): {len(bonf)}件")
    print(bonf.to_string() if len(bonf) else "  なし")

    os.makedirs(os.path.join(HERE,"results"), exist_ok=True)
    out = dict(n_cells=n_cells, alpha_bonf=round(alpha_bonf,5), data="committed H1 2.8y", hold=HOLD, cost=COST,
               control_EURJPY_Mon=ctrl.to_dict("records"),
               sig_p05=show[show.perm_p<=0.05].drop(columns=["band"]).to_dict("records"),
               leads_nonJPY=lead.to_dict("records"),
               bonferroni_survivors=bonf.to_dict("records"))
    with open(os.path.join(HERE,"results","edge_search_session.json"),"w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/edge_search_session.json")
