# -*- coding: utf-8 -*-
"""
portfolio_F_topk.py — PortfolioF「トップレッグ抜粋」の検定【事前登録 docs/142】。
19レッグ(v4はバスケット1本・S-Jul通年は除外)からLOYOで上位K=6本を等ノーショナル合成。
ゲート: F1 プラセボp80 / F2 安定性≥5/6 / F3 中央3ヶ月でPD間引き版より失格%改善 / F4 重複ρ≤0.8。
出力: results/portfolio_F_topk.json → docs/143
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import (load_daily, clip, mon_daily, cc_daily, e5_daily, v4_daily,
                                     g3_daily, composite_daily, YEN, V7X, EMON, EMONX, FOMC)
from policy_prune_symbols import e5_one, v7_one as v7_one_ps
from median3_calibrate_compare import month_arrays, month_stats_at, simulate, calibrate_median3
from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS, sha256s

SEED, N_FINAL, K = 7, 20000, 6
YEARS = list(range(2016, 2026))
W0, W1 = pd.Timestamp("2016-01-01"), pd.Timestamp("2025-12-31")


def win(s): return s[(s.index >= W0) & (s.index <= W1)]


def mon_one(nm, idx_cost=None):
    from parallel_vs_existing_compare import pip_size
    df = load_daily(nm)
    cost = (idx_cost if idx_cost is not None else 2 * pip_size(nm) / df["open"])
    return win(clip((df[df["weekday"] == 0]["o2o"] - cost).dropna()))


def g3_unit():
    df = load_daily("US500"); c = df["close"].values
    dates = pd.DatetimeIndex(df.index); out = {}
    for d_ in FOMC:
        pos = dates.searchsorted(pd.Timestamp(d_))
        if pos < 2 or pos >= len(dates): continue
        out[dates[pos - 1]] = (c[pos - 1] / c[pos - 2] - 1.0) - 1e-4
    return win(clip(pd.Series(out).sort_index()))


def monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({m: float((1 + s[mk == m]).prod() - 1) for m in mk.unique()}).sort_index()


def sharpe_m(m):
    m = m.dropna()
    return float(m.mean() / m.std() * np.sqrt(12)) if len(m) > 12 and m.std() > 0 else 0.0


def main():
    print("[1/4] 19レッグ構築")
    legs = {}
    for p in YEN: legs[f"v7:{p}"] = mon_one(p)
    for p in V7X: legs[f"v7x:{p}"] = mon_one(p)
    for p in EMON: legs[f"EMon:{p}"] = mon_one(p, 3e-4)
    for p in EMONX: legs[f"EMonX:{p}"] = mon_one(p, 3e-4)
    for p in ["XAUUSD", "US500", "NAS100", "GER40"]: legs[f"E5:{p}"] = win(e5_one(p))
    legs["G3:US500"] = g3_unit()
    legs["v4:basket"] = win(v4_daily())
    names = list(legs.keys())
    D = pd.DataFrame(legs).fillna(0.0)
    msym = {k: monthly(legs[k]) for k in names}
    print(f"  {len(names)}レッグ")

    print("[2/4] LOYO選別(K=6)+感応(K=4,8)")
    res_k = {}
    for k_ in (K, 4, 8):
        oos, fold_sets = [], {}
        for y in YEARS:
            tr = {n: sharpe_m(msym[n][msym[n].index.year != y]) for n in names}
            top = sorted(sorted(tr, key=tr.get, reverse=True)[:k_])
            fold_sets[y] = top
            sd = D[top].mean(axis=1)
            oos.append(sd[sd.index.year == y])
        oos_m = monthly(pd.concat(oos).sort_index())
        full_sh = {n: sharpe_m(msym[n]) for n in names}
        full_top = sorted(sorted(full_sh, key=full_sh.get, reverse=True)[:k_])
        match = np.mean([len(set(fold_sets[y]) & set(full_top)) for y in YEARS])
        res_k[k_] = dict(oos_sharpe=round(sharpe_m(oos_m), 2), full_top=full_top,
                         avg_match=round(float(match), 1),
                         fold_sets={str(y): fold_sets[y] for y in YEARS})
        print(f"  K={k_}: OOS Sh {res_k[k_]['oos_sharpe']} 平均一致 {match:.1f}/{k_} top={full_top}")

    print("[3/4] プラセボ(無作為固定6本×400)")
    rng = np.random.default_rng(123)
    plc = []
    for _ in range(400):
        pick = list(rng.choice(names, size=K, replace=False))
        plc.append(sharpe_m(monthly(D[pick].mean(axis=1))))
    p80 = float(np.percentile(plc, 80))
    f1 = bool(res_k[K]["oos_sharpe"] > p80)
    f2 = bool(res_k[K]["avg_match"] >= 5.0)
    print(f"  p80={p80:.2f} F1={f1} F2={f2}")

    print("[4/4] 中央3ヶ月MC(全期間版セット)+重複ρ")
    top6 = res_k[K]["full_top"]
    base = D[top6].mean(axis=1)
    arrs = month_arrays(base)
    mult, _ = calibrate_median3(arrs, None, np.random.default_rng(SEED))
    mc = None
    f3 = False
    PD_REF = dict(fail_pct_optimistic=19.6, fail_pct_raw=26.7)  # docs/135
    if mult is not None:
        mc = dict(mult=mult, **simulate(month_stats_at(arrs, mult, None), N_FINAL,
                                        np.random.default_rng(SEED)))
        f3 = bool(mc["fail_pct_optimistic"] < PD_REF["fail_pct_optimistic"] and
                  mc["fail_pct_raw"] < PD_REF["fail_pct_raw"])
        print(f"  mult={mult} {mc}")

    # F4: 既存3器との月次ρ
    from policy_prune_symbols import e5_basket
    sl = dict(v7=mon_daily(["EURJPY", "GBPJPY"]), EMon=mon_daily(EMON, 3e-4),
              E5=win(e5_basket(["XAUUSD", "NAS100"])), v4=win(v4_daily()))
    PD_W = {m: {"v4": .30, "v7": .25, "EMon": .25, "E5": .20} for m in range(1, 13)}
    pdm = monthly(composite_daily(sl, PD_W))
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    R4 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}
    sl_full = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X), EMon=mon_daily(EMON, 3e-4),
                   EMonX=mon_daily(EMONX, 3e-4), E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]),
                   v4=win(v4_daily()))
    seasm = monthly(win(composite_daily(sl_full, R4)))
    pem = monthly(sl["E5"])
    fm = monthly(base)
    def rho(a, b):
        j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        return round(float(j["a"].corr(j["b"])), 2) if len(j) > 24 else None
    rhos = dict(vs_季節R4=rho(fm, seasm), vs_PD間引き=rho(fm, pdm), vs_PE_v2=rho(fm, pem))
    f4 = bool(all(r is None or abs(r) <= 0.8 for r in rhos.values()))
    print(f"  ρ={rhos} F4={f4}")

    passed = f1 and f2 and f3 and f4
    verdict = ("採用候補(Dukascopy確認→デモへ)" if passed
               else "REJECT(抜粋ポートフォリオは既存器を上回らない/選別に情報なし)")
    res = dict(meta=dict(prereg="docs/142", K=K, seed=SEED, n_paths=N_FINAL, inputs=sha256s()),
               loyo=res_k, placebo=dict(n=400, p80=round(p80, 2)),
               median3_mc=mc, pd_ref=PD_REF, rho=rhos,
               gates=dict(F1_placebo=f1, F2_stability=f2, F3_beats_PD=f3, F4_overlap=f4),
               verdict=verdict)
    with open(os.path.join(HERE, "results", "portfolio_F_topk.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("判定:", verdict)
    print("保存: research/results/portfolio_F_topk.json")


if __name__ == "__main__":
    main()
