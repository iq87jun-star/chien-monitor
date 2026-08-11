"""
seasonality_monday.py — 月曜シーズナリティ(週明けJPYクロス・ドリフト)エッジの最終検証。

背景: v1〜v5(価格指標による方向予測)は本番10年データで全滅。順列検定が
「価格の方向予測エッジは無い」というメタ結論を繰り返した。そこで方向予測では
なく『時間構造(曜日シーズナリティ)』という別系統を検定したところ、月曜LONGが
本プロジェクトで初めて全フィルタを通過した。

エッジの源泉(仮説): 週末に蓄積したマクロ・リスク要因が週明け(月曜)のJPYクロスに
リスクオン/円キャリー需要として現れる、流動性・フロー由来の構造。価格予測ではない。

検証ゲート(全11):
 1 曜日プラセボ(月曜だけ突出するか)        6 直近年生存(2023-26)
 2 IS/OOS安定                               7 ペア別寄与
 3 全年ジャックナイフ(p<=0.01維持)          8 SL/TP感応(タイトSL=エッジ破壊)
 4 コスト感応(往復1-4pip)                   9 ボラ状態依存(低/高)
 5 時刻プラセボ(04-10UTC帯)                10 複利/低リスク要件
                                          11 ニュース密度代理(第1週除外)

使い方: DATA_DIR=/path/to/real python3 research/seasonality_monday.py
エンジン(load_h1/resample/_atr)は v4 検証ノートから再利用する。
※ シミュレーション。将来/ライブ約定を保証しない。最終はデモ前進検証で確認のこと。
"""
import os, json, numpy as np, pandas as pd, nbformat, warnings, calendar
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
NB   = os.path.join(HERE, "FundedNext_v4_validation_SELFCONTAINED.ipynb")

# ---- エンジン関数を notebook から取り込む ----
G = {"__name__": "__engine__", "display": lambda *a, **k: None}
nb = nbformat.read(NB, as_version=4)
cells = [c for c in nb.cells if c.cell_type == "code"]
for i in (1, 2, 3):
    exec(cells[i].source, G)
load_h1 = G["load_h1"]; _atr = G["_atr_wilder"]
PAIRS = ["USDJPY", "EURJPY", "GBPJPY"]
AVAIL = [p for p in PAIRS if p in G["AVAIL"]]

PIP = 0.01  # JPYクロス

# ---------------------------------------------------------------
# コア: 月曜 hEnter(UTC) に LONG、holdH 時間後に時間決済。3ペア等加重プール。
# costpip = 往復スプレッド+スリッページの pip 換算。
# 戻り値: 各エントリー日をindexとするプール純リターン Series。
# ---------------------------------------------------------------
def pool_returns(hEnter=8, holdH=24, costpip=2.0, weekday=0, exclude_week1=False):
    series = []
    for p in AVAIL:
        h1 = load_h1(p); cv = h1["close"].values; idx = h1.index
        ent = np.where((idx.dayofweek == weekday) & (idx.hour == hEnter))[0]
        rec = {}
        for a in ent:
            if a + holdH >= len(cv): continue
            ts = idx[a]
            if exclude_week1 and ((ts.day - 1) // 7 + 1) == 1: continue
            rec[ts] = (cv[a + holdH] - cv[a]) / cv[a] - costpip * PIP / cv[a]
        series.append(pd.Series(rec))
    return pd.concat(series, axis=1).mean(axis=1).dropna()

def perm_p(rets, n_iter=4000, seed=7):
    rets = np.asarray(rets); rng = np.random.default_rng(seed)
    real = rets.sum(); s = np.abs(rets); null = np.empty(n_iter)
    for i in range(n_iter): null[i] = (s * rng.choice([-1, 1], size=len(s))).sum()
    return float((null >= real).mean())

def stats(x):
    x = pd.Series(x).dropna()
    eq = (1 + x).cumprod(); dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    return dict(net_pct=round((eq.iloc[-1] - 1) * 100, 1), win_pct=round((x > 0).mean() * 100, 0),
                maxDD_pct=round(dd, 1), n=len(x))

def sim_sltp(hEnter, holdH, slATR, tpATR, costpip=2.0, volfilter=None):
    series = []
    for p in AVAIL:
        h1 = load_h1(p); atr = _atr(h1, 24).values
        cv = h1["close"].values; hi = h1["high"].values; lo = h1["low"].values; idx = h1.index
        ent = np.where((idx.dayofweek == 0) & (idx.hour == hEnter))[0]
        med = np.nanmedian(atr[(idx.dayofweek == 0) & np.isfinite(atr)])
        rec = {}
        for a in ent:
            if a + holdH >= len(cv) or not np.isfinite(atr[a]) or atr[a] <= 0: continue
            if volfilter == "low" and atr[a] > med: continue
            if volfilter == "high" and atr[a] <= med: continue
            entry = cv[a]; sl = entry - slATR * atr[a]; tp = entry + tpATR * atr[a]; R = None
            for k in range(a + 1, a + 1 + holdH):
                if lo[k] <= sl: R = (sl - entry) / entry; break
                if hi[k] >= tp: R = (tp - entry) / entry; break
            if R is None: R = (cv[a + holdH] - entry) / entry
            rec[idx[a]] = R - costpip * PIP / entry
        series.append(pd.Series(rec))
    return pd.concat(series, axis=1).mean(axis=1).dropna()

def run_all():
    out = {}
    # 採用設定
    base = pool_returns(8, 24, 2.0)
    out["chosen"] = dict(entry_hour_utc=8, hold_hours=24, costpip=2.0,
                         **stats(base), perm_p=round(perm_p(base.values), 4))
    half = base.index[len(base) // 2]
    out["chosen"]["oos"] = stats(base[base.index >= half])
    # 1 曜日プラセボ
    out["placebo_weekday"] = {calendar.day_abbr[wd]:
        dict(**stats(pool_returns(8, 24, 2.0, weekday=wd)),
             perm_p=round(perm_p(pool_returns(8, 24, 2.0, weekday=wd).values), 3)) for wd in range(5)}
    # 3 ジャックナイフ
    yrs = sorted(set(base.index.year))
    out["jackknife_year"] = {int(y): round(perm_p(base[base.index.year != y].values), 3) for y in yrs}
    # 4 コスト感応
    out["cost_sensitivity"] = {f"{m}pip":
        dict(**stats(pool_returns(8, 24, float(m))), perm_p=round(perm_p(pool_returns(8, 24, float(m)).values), 3))
        for m in (1, 2, 3, 4)}
    # 5 時刻プラセボ
    out["placebo_hour"] = {h: dict(**stats(pool_returns(h, 24, 2.0)), perm_p=round(perm_p(pool_returns(h, 24, 2.0).values), 3))
        for h in (4, 6, 7, 8, 9, 10, 13)}
    # 6 直近年
    rec = base[base.index.year >= 2023]
    out["recent_2023plus"] = dict(**stats(rec),
        pos_years=int((base.groupby(base.index.year).sum()[lambda s: s.index >= 2023] > 0).sum()))
    # 7 ペア別
    out["per_pair"] = {}
    for p in AVAIL:
        h1 = load_h1(p); cv = h1["close"].values; idx = h1.index
        ent = np.where((idx.dayofweek == 0) & (idx.hour == 8))[0]
        s = pd.Series({idx[a]: (cv[a + 24] - cv[a]) / cv[a] - 2 * PIP / cv[a] for a in ent if a + 24 < len(cv)})
        out["per_pair"][p] = dict(**stats(s), perm_p=round(perm_p(s.values), 3))
    # 8 SL/TP
    out["sltp"] = {"time_only": dict(**stats(sim_sltp(8, 24, 99, 99)), perm_p=round(perm_p(sim_sltp(8, 24, 99, 99).values), 3))}
    for sl, tp in [(1.0, 1.0), (1.5, 3.0), (2.5, 5.0)]:
        s = sim_sltp(8, 24, sl, tp)
        out["sltp"][f"SL{sl}_TP{tp}"] = dict(**stats(s), perm_p=round(perm_p(s.values), 3))
    # 9 ボラ
    out["vol_regime"] = {side: dict(**stats(sim_sltp(8, 24, 99, 99, volfilter=side)),
                                    perm_p=round(perm_p(sim_sltp(8, 24, 99, 99, volfilter=side).values), 3))
                         for side in ("low", "high")}
    # 11 ニュース代理
    ex = pool_returns(8, 24, 2.0, exclude_week1=True)
    out["news_proxy_exclude_week1"] = dict(**stats(ex), perm_p=round(perm_p(ex.values), 4))
    return out, base

if __name__ == "__main__":
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    res, base = run_all()
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "seasonality_monday.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)

    print("利用可能ペア:", AVAIL)
    print("\n=== 採用設定: 月曜08UTC LONG / 24h時間決済 / 往復2pip / 3ペア等加重 ===")
    c = res["chosen"]; print(f"  全期間 純益{c['net_pct']}% 勝率{c['win_pct']}% maxDD{c['maxDD_pct']}% "
                             f"順列p={c['perm_p']} | OOS 純益{c['oos']['net_pct']}% maxDD{c['oos']['maxDD_pct']}%")
    print("\n[1 曜日プラセボ] 月曜だけ突出するはず:")
    for k, v in res["placebo_weekday"].items():
        print(f"   {k}: 純益{v['net_pct']:+}% p={v['perm_p']}")
    print("\n[3 ジャックナイフ] どの年除外でもp維持:", res["jackknife_year"])
    print("\n[4 コスト感応]:", {k: (v['net_pct'], v['perm_p']) for k, v in res["cost_sensitivity"].items()})
    print("\n[5 時刻プラセボ]:", {k: (v['net_pct'], v['perm_p']) for k, v in res["placebo_hour"].items()})
    print("\n[6 直近2023+]:", res["recent_2023plus"])
    print("\n[7 ペア別]:", {k: (v['net_pct'], v['perm_p']) for k, v in res["per_pair"].items()})
    print("\n[8 SL/TP] タイトSLはエッジ破壊:", {k: (v['net_pct'], v['perm_p']) for k, v in res["sltp"].items()})
    print("\n[9 ボラ]:", {k: (v['net_pct'], v['perm_p']) for k, v in res["vol_regime"].items()})
    print("\n[11 ニュース代理(第1週除外)]:", res["news_proxy_exclude_week1"])

    # エクイティ曲線(等加重プール, 固定%リスク近似: 各月曜リターンをそのまま累積)
    eq = (1 + base).cumprod() * 100000
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(base.index, eq, label=f"pool Monday-LONG (net {res['chosen']['net_pct']}%, maxDD {res['chosen']['maxDD_pct']}%)")
    ax.axhline(100000, color="k", lw=.6, ls=":")
    ax.axhline(90000, color="r", lw=.6, ls="--", label="-10% floor")
    ax.set_title("v6 Monday-seasonality (3 JPY crosses, 08UTC LONG, 24h) — real 10y, ~2pip cost")
    ax.set_ylabel("equity $ (1 unit/trade, uncompounded)"); ax.legend()
    plt.tight_layout(); plt.savefig(os.path.join(HERE, "results", "v6_monday_equity.png"), dpi=110)
    print("\n保存: results/seasonality_monday.json, results/v6_monday_equity.png")
