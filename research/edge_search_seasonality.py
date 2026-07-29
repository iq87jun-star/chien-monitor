"""
edge_search_seasonality.py — 無相関のカレンダー系エッジ探索(日足10年×9ペア)。

目的: v6(円の月曜シーズナリティ)は本物だが3ペア相関0.5-0.68の「1現象」。
真のポートフォリオには『v6と無相関の別エッジ』が要る。本スクリプトは
曜日 × ペア × 方向(LONG/SHORT)を全数スキャンし、v1〜v5を葬った同じ厳格ハーネス
(順列検定 / IS-OOS / 全年ジャックナイフ / Bonferroni / コスト感応)に通す。
さらに各候補について v6基準(EURJPY月曜LONG)との相関を測り、無相関のものだけ拾う。

データ: research/data/<PAIR>_d.csv(committed, 2016-2026の日足9ペア)。
日足は 23:00/00:00 混在(セッション境界)。trade_date=(t+2h).floor('D') で
取引日に正規化してから曜日を取る。曜日バランス(各~520, 週末~0)を sanity gate にする。

トレード定義: trade_date の open でエントリ、翌 trade_date の open で決済(~1営業日保有)。
往復コストは pip 換算で控除。シミュレーションであり将来約定を保証しない。
"""
import os, json, itertools, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PAIRS = ["EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCAD","USDCHF","USDJPY","EURJPY","GBPJPY"]
WD = ["Mon","Tue","Wed","Thu","Fri"]

def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001

def load_daily(pair):
    df = pd.read_csv(os.path.join(DATA, f"{pair}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    # 取引日へ正規化(23:00→翌日, 00:00→当日)。同一取引日が複数あれば最後を採用。
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek
    df = df[df["weekday"] <= 4]                      # 平日のみ
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0   # 当日open→翌営業日open
    return df.dropna(subset=["o2o"])

# --- 統計ユーティリティ ---
def perm_p(rets, n_iter=4000, seed=7):
    rets = np.asarray(rets, float)
    if len(rets) == 0: return 1.0
    rng = np.random.default_rng(seed); real = rets.sum(); s = np.abs(rets)
    null = np.array([(s*rng.choice([-1,1],size=len(s))).sum() for _ in range(n_iter)])
    return float((null >= real).mean())     # 片側(LONG/SHORTは符号込みで渡す)

def stats(x):
    x = pd.Series(x).dropna()
    if len(x)==0: return dict(net_pct=0,win_pct=0,maxDD_pct=0,n=0)
    eq=(1+x).cumprod(); dd=((eq-eq.cummax())/eq.cummax()).min()*100
    return dict(net_pct=round((eq.iloc[-1]-1)*100,1), win_pct=round((x>0).mean()*100,0),
                maxDD_pct=round(dd,1), n=int(len(x)))

def candidate_series(pair, wd, direction, costpip):
    """指定 (pair, weekday, dir) の週次トレード純リターン Series(index=trade_date)。"""
    df = load_daily(pair); pip = pip_size(pair)
    sub = df[df["weekday"]==wd]
    r = direction * sub["o2o"] - costpip*pip/sub["open"]
    return r.dropna()

def tom_series(pair, direction, costpip, last_n=1, first_n=3):
    """ターン・オブ・マンス: 各月の最終 last_n 営業日 + 月初 first_n 営業日に
    エントリ(1営業日保有)。曜日系とは機序が独立(月末リバランス・フロー)。"""
    df = load_daily(pair).copy(); pip = pip_size(pair)
    ym = df.index.to_period("M")
    df["from_start"] = df.groupby(ym).cumcount() + 1                 # 1=月初第1営業日
    df["from_end"]   = df.groupby(ym).cumcount(ascending=False) + 1  # 1=月末最終営業日
    mask = (df["from_end"] <= last_n) | (df["from_start"] <= first_n)
    sub = df[mask]
    r = direction * sub["o2o"] - costpip*pip/sub["open"]
    return r.dropna()

def run():
    REF = candidate_series("EURJPY", 0, +1, 2.0)    # v6基準: EURJPY月曜LONG
    ref_wk = REF.copy(); ref_wk.index = REF.index.to_period("W")
    ref_wk = ref_wk[~ref_wk.index.duplicated()]

    # 候補 = (label, family, regen(costpip)->Series)。曜日 + ターン・オブ・マンスの2系統。
    cands = []
    for pair in PAIRS:
        for wd in range(5):
            for direction in (+1,-1):
                lbl = f"{pair}_{WD[wd]}_{'L' if direction>0 else 'S'}"
                gen = (lambda p=pair,w=wd,d=direction: (lambda c: candidate_series(p,w,d,c)))()
                if len(gen(2.0)) >= 100: cands.append((lbl, "DOW", gen))
    for pair in PAIRS:
        for direction in (+1,-1):
            lbl = f"{pair}_TOM_{'L' if direction>0 else 'S'}"
            gen = (lambda p=pair,d=direction: (lambda c: tom_series(p,d,c)))()
            if len(gen(2.0)) >= 100: cands.append((lbl, "TOM", gen))
    n_tests = len(cands)
    alpha_bonf = 0.05 / n_tests
    print(f"全候補数(=多重検定試行数): {n_tests}  Bonferroni α = {alpha_bonf:.5f}")

    rows = []; GEN = {}
    for lbl, fam, gen in cands:
        GEN[lbl] = gen
        r = gen(2.0)
        p = perm_p(r.values)
        st = stats(r.values)
        # 相関(同週でv6基準と): 候補の週リターン vs EURJPY月曜
        cw = r.copy(); cw.index = r.index.to_period("W"); cw = cw[~cw.index.duplicated()]
        j = pd.concat([cw.rename("c"), ref_wk.rename("r")], axis=1).dropna()
        corr = float(j["c"].corr(j["r"])) if len(j) > 30 else np.nan
        rows.append(dict(label=lbl, family=fam, **st, perm_p=round(p,4),
                         corr_v6=round(corr,2) if corr==corr else None))
    df = pd.DataFrame(rows).sort_values("perm_p").reset_index(drop=True)

    # 一次通過: 順列 p <= 0.05
    sig = df[df.perm_p <= 0.05].copy()
    # Bonferroni 生存
    surv = sig[sig.perm_p <= alpha_bonf].copy()

    # 二次ハーネス: Bonferroni生存が無くても、p<=0.05 かつ |v6相関|<=0.5 の
    # 「無相関候補」には二次ゲートを当てて将来の追試対象を可視化する。
    targets = pd.concat([surv, sig[(sig.corr_v6.abs() <= 0.5)]]).drop_duplicates("label")
    detail = {}
    for _, row in targets.iterrows():
        lbl = row["label"]; r = GEN[lbl](2.0)
        half = r.index[len(r)//2]
        oos = stats(r[r.index >= half].values); oos_p = perm_p(r[r.index >= half].values)
        yrs = sorted(set(r.index.year))
        jk = {int(y): round(perm_p(r[r.index.year != y].values),3) for y in yrs}
        cost = {f"{c}pip": stats(GEN[lbl](float(c)).values)["net_pct"] for c in (1,2,3,4)}
        detail[lbl] = dict(
            full=dict(net_pct=row["net_pct"], win_pct=row["win_pct"], maxDD_pct=row["maxDD_pct"],
                      n=int(row["n"]), perm_p=row["perm_p"], corr_v6=row["corr_v6"]),
            bonferroni_survivor=bool(row["perm_p"] <= alpha_bonf),
            oos=dict(**oos, perm_p=round(oos_p,4)),
            jackknife_max_p=round(max(jk.values()),3), jackknife=jk, cost_net=cost)

    out = dict(n_tests=n_tests, alpha_bonf=round(alpha_bonf,5),
               sig_count=int(len(sig)), bonferroni_survivors=int(len(surv)),
               all_significant=sig.to_dict("records"), detail=detail)
    return df, sig, surv, out

if __name__ == "__main__":
    pd.set_option("display.width",200); pd.set_option("display.max_columns",30); pd.set_option("display.max_rows",100)
    df, sig, surv, out = run()

    # sanity: 曜日バランス
    bal = load_daily("EURUSD")["weekday"].value_counts().sort_index()
    print("\n[sanity] EURUSD 曜日件数(各~500/週末0なら正規化OK):", dict(zip([WD[i] for i in bal.index], bal.values)))

    print(f"\n===== 順列 p<=0.05 の候補({len(sig)}/{out['n_tests']}) =====")
    print(sig.to_string())
    print(f"\n===== ★Bonferroni 生存(p<=α={out['alpha_bonf']}): {len(surv)}件 =====")
    print(surv.to_string() if len(surv) else "  なし")

    print("\n===== 生存候補の二次ハーネス =====")
    for k, d in out["detail"].items():
        f, o = d["full"], d["oos"]
        print(f"\n[{k}] 全期間 純益{f['net_pct']}% 勝率{f['win_pct']}% DD{f['maxDD_pct']}% p={f['perm_p']} "
              f"v6相関={f['corr_v6']}")
        print(f"   OOS後半 純益{o['net_pct']}% DD{o['maxDD_pct']}% p={o['perm_p']} | "
              f"JKmax_p={d['jackknife_max_p']} | コスト{d['cost_net']}")

    os.makedirs(os.path.join(HERE,"results"), exist_ok=True)
    with open(os.path.join(HERE,"results","edge_search_seasonality.json"),"w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/edge_search_seasonality.json")
