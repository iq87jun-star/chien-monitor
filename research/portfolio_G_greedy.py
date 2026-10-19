# -*- coding: utf-8 -*-
"""
portfolio_G_greedy.py — PortfolioG「検証通過型の上位抜粋」【事前登録 docs/144】。
貪欲選択: 訓練Sharpe降順に走査し、合成の訓練Sharpeを+0.02以上改善するレッグのみ採用(上限10)。
LOYO検証+プラセボ+安定性(Jaccard)+中央3ヶ月でPD間引き比較。
出力: results/portfolio_G_greedy.json → docs/145
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import mon_daily, e5_daily, v4_daily, composite_daily, YEN, V7X, EMON, EMONX
from portfolio_F_topk import mon_one, g3_unit, monthly, sharpe_m, win
from policy_prune_symbols import e5_one, e5_basket
from median3_calibrate_compare import month_arrays, month_stats_at, simulate, calibrate_median3
from seasonal_optimize_loyo import build_sleeves, month_stats, weights_for, LOYO_YEARS, sha256s

SEED, N_FINAL = 7, 20000
YEARS = list(range(2016, 2026))
DELTA, CAP = 0.02, 10
PD_REF = dict(fail_pct_optimistic=19.6, fail_pct_raw=26.7)  # docs/135


def greedy(D, msym, names, year_mask=None):
    """訓練Sharpe降順走査・合成Sharpe+DELTA改善のみ採用(等ノーショナル平均・上限CAP)。"""
    def tr_m(n):
        m = msym[n]
        return m[year_mask(m)] if year_mask else m
    order = sorted(names, key=lambda n: sharpe_m(tr_m(n)), reverse=True)
    sel = []
    cur_sh = -9.9
    for n in order:
        if len(sel) >= CAP: break
        cand = sel + [n]
        comp = D[cand].mean(axis=1)
        m = monthly(comp)
        if year_mask: m = m[year_mask(m)]
        sh = sharpe_m(m)
        if sh >= cur_sh + DELTA:
            sel = cand; cur_sh = sh
    return sel, round(cur_sh, 2)


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
    D = D[(D.index.year >= 2016) & (D.index.year <= 2025)]
    msym = {k: monthly(legs[k]) for k in names}

    print("[2/4] LOYO貪欲選択")
    oos, fold_sets = [], {}
    for y in YEARS:
        mask = lambda m, y=y: m.index.year != y
        sel, _ = greedy(D, msym, names, year_mask=mask)
        fold_sets[y] = sel
        sd = D[sel].mean(axis=1)
        oos.append(sd[sd.index.year == y])
        print(f"  {y}除外: {len(sel)}本 {sel}")
    oos_m = monthly(pd.concat(oos).sort_index())
    oos_sh = round(sharpe_m(oos_m), 2)

    full_sel, full_tr_sh = greedy(D, msym, names)
    jac = np.mean([len(set(fold_sets[y]) & set(full_sel)) / len(set(fold_sets[y]) | set(full_sel))
                   for y in YEARS])
    print(f"  全期間セット({len(full_sel)}本): {full_sel} 訓練Sh {full_tr_sh}")
    print(f"  LOYO-OOS Sh {oos_sh} / 平均Jaccard {jac:.2f}")

    print("[3/4] プラセボ(同本数の無作為固定セット×400)")
    rng = np.random.default_rng(123)
    plc = [sharpe_m(monthly(D[list(rng.choice(names, size=len(full_sel), replace=False))].mean(axis=1)))
           for _ in range(400)]
    p80 = float(np.percentile(plc, 80))
    g1, g2 = bool(oos_sh > p80), bool(jac >= 0.6)
    print(f"  p80={p80:.2f} G1={g1} G2={g2}")

    print("[4/4] 中央3ヶ月MC+重複ρ")
    base = D[full_sel].mean(axis=1)
    arrs = month_arrays(base)
    mult, _ = calibrate_median3(arrs, None, np.random.default_rng(SEED))
    mc, g3_ok = None, False
    if mult is not None:
        mc = dict(mult=mult, **simulate(month_stats_at(arrs, mult, None), N_FINAL,
                                        np.random.default_rng(SEED)))
        g3_ok = bool(mc["fail_pct_optimistic"] < PD_REF["fail_pct_optimistic"] and
                     mc["fail_pct_raw"] < PD_REF["fail_pct_raw"])
        print(f"  mult={mult} {mc}")
    else:
        print("  中央3ヶ月に到達不可(≤4x)")

    sl_pd = dict(v7=mon_daily(["EURJPY", "GBPJPY"]), EMon=mon_daily(EMON, 3e-4),
                 E5=win(e5_basket(["XAUUSD", "NAS100"])), v4=win(v4_daily()))
    PD_W = {m: {"v4": .30, "v7": .25, "EMon": .25, "E5": .20} for m in range(1, 13)}
    pdm = monthly(win(composite_daily(sl_pd, PD_W)))
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    mu, sd = month_stats(dfm, LOYO_YEARS)
    R4 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}
    from portfolio_daily_compare import cc_daily
    sl_full = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X), EMon=mon_daily(EMON, 3e-4),
                   EMonX=mon_daily(EMONX, 3e-4), E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]),
                   v4=win(v4_daily()))
    seasm = monthly(win(composite_daily(sl_full, R4)))
    pem = monthly(win(e5_basket(["XAUUSD", "NAS100"])))
    fm = monthly(base)
    def rho(a, b):
        j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        return round(float(j["a"].corr(j["b"])), 2) if len(j) > 24 else None
    rhos = dict(vs_季節R4=rho(fm, seasm), vs_PD間引き=rho(fm, pdm), vs_PE_v2=rho(fm, pem))
    g4 = bool(all(r is None or abs(r) <= 0.8 for r in rhos.values()))
    print(f"  ρ={rhos} G4={g4}")

    passed = g1 and g2 and g3_ok and g4
    verdict = ("採用候補(Dukascopy確認→デモへ)" if passed
               else "REJECT(現行3器を維持)")
    res = dict(meta=dict(prereg="docs/144", delta=DELTA, cap=CAP, seed=SEED, n_paths=N_FINAL,
                         inputs=sha256s()),
               full_set=full_sel, full_train_sharpe=full_tr_sh,
               loyo=dict(oos_sharpe=oos_sh, jaccard=round(float(jac), 2),
                         fold_sets={str(y): fold_sets[y] for y in YEARS}),
               placebo=dict(n=400, p80=round(p80, 2)),
               median3_mc=mc, pd_ref=PD_REF, rho=rhos,
               gates=dict(G1_placebo=g1, G2_stability=g2, G3_beats_PD=g3_ok, G4_overlap=g4),
               verdict=verdict)
    with open(os.path.join(HERE, "results", "portfolio_G_greedy.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("判定:", verdict)
    print("保存: research/results/portfolio_G_greedy.json")


if __name__ == "__main__":
    main()
