# -*- coding: utf-8 -*-
"""
portfolio_E_durable.py — PortfolioE「耐久」(E5+G3)の校正・MC・相関【事前登録 docs/129】。
構成グリッド: PE0=E5単独 / PE1=E5+G3(event_risk1%) / PE2=E5+G3(2%)。
倍率=ガード逆算×0.8(docs/87)。チャレンジMC=median3_calibrate_compareのsimulate逐語再利用
(FNパネル: +8%/フロア-8%/日次-5% ・ FTMO近似パネル: +10%/フロア-10%/日次-5%)。
決定規則D1-D5は docs/129 §3 のとおり機械適用。窓2016-01〜2026-06(スリーブ側でclip)。
出力: results/portfolio_E_durable.json → docs/130
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import (mon_daily, cc_daily, e5_daily, v4_daily, g3_daily,
                                     composite_daily, worst_stats, calibrate, monthly_stats,
                                     M3, YEN, V7X, EMON, EMONX, load_daily)
import median3_calibrate_compare as m3c
from median3_calibrate_compare import month_arrays, month_stats_at, simulate
from seasonal_optimize_loyo import sha256s

N_FINAL = 20000
SEED = 7


def leg_sigma_pct(assets):
    """各レッグ寄与(w_i×pos_i×r_i)の月次σ%(1x)。EAのInpLegMonthlyRiskPct換算用。"""
    closes = {}
    for nm in assets:
        df = load_daily(nm); s = df["close"]; s.index = pd.to_datetime(df.index)
        closes[nm] = s.resample("ME").last()
    px = pd.DataFrame(closes).dropna(); ret = px.pct_change()
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12):
        sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    pos = np.sign(sig).shift(1)
    vol = ret.rolling(12).std().shift(1)
    w = (1 / vol).div((1 / vol).sum(axis=1), axis=0)
    pw = (pos.abs() * w); pw.index = pw.index.to_period("M")
    out = {}
    for nm in assets:
        s = load_daily(nm)["close"].pct_change().dropna()
        mkey = pd.PeriodIndex(pd.to_datetime(s.index), freq="M")
        leg = pd.Series(s.values * pw[nm].reindex(mkey).values, index=s.index).dropna()
        leg = leg[(leg.index >= "2016-01-01")]
        m = leg.groupby(pd.PeriodIndex(leg.index, freq="M")).sum()
        out[nm] = round(float(m.std()) * 100, 2)
    return out


def to_monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({m: float((1 + s[mk == m]).prod() - 1) for m in mk.unique()}).sort_index()


def corr_m(a, b):
    j = pd.concat([to_monthly(a).rename("a"), to_monthly(b).rename("b")], axis=1).dropna()
    j = j[(j.index >= "2016-01") & (j.index <= "2025-12")]
    return round(float(j["a"].corr(j["b"])), 2) if len(j) > 24 else None


def mc_panel(arrs, g3a, mults, target, floor, label):
    """simulateのモジュール定数を切替えて実行(終了後に復元)"""
    saved = (m3c.TARGET, m3c.FLOOR_OPT, m3c.FLOOR_RAW)
    m3c.TARGET, m3c.FLOOR_OPT, m3c.FLOOR_RAW = target, floor, floor
    out = {}
    try:
        for k, mult in mults.items():
            rng = np.random.default_rng(SEED)
            out[k] = dict(mult=mult, **simulate(month_stats_at(arrs, mult, g3a), N_FINAL, rng))
            print(f"  [{label}] {k}: {out[k]}")
    finally:
        m3c.TARGET, m3c.FLOOR_OPT, m3c.FLOOR_RAW = saved
    return out


def main():
    basket = None
    if len(sys.argv) > 1:                      # 例: python3 ... XAUUSD,NAS100 (docs/129 §6)
        basket = sys.argv[1].split(",")
    tag = "_v2" if basket else ""
    print(f"[1/4] スリーブ構築 basket={basket or 'E5現行4資産'}")
    if basket:
        from policy_prune_symbols import e5_basket
        e5 = e5_basket(basket)
    else:
        e5 = e5_daily()
    g3_1, g3_2 = g3_daily(0.01), g3_daily(0.02)
    print(f"  E5 {len(e5)}日 / G3イベント {len(g3_1)}")
    legsig = leg_sigma_pct(basket or ["XAUUSD", "US500", "NAS100", "GER40"])
    print(f"  レッグ月次σ%(1x): {legsig}")

    print("[2/4] 校正(ガード逆算×0.8)と構成比較")
    variants = {}
    series = {}
    for name, g3 in [("PE0_E5only", None), ("PE1_E5+G3_1pct", g3_1), ("PE2_E5+G3_2pct", g3_2)]:
        rec = calibrate(e5, g3)
        s = e5 * rec
        if g3 is not None:
            s = s.add(g3, fill_value=0.0)
        st = monthly_stats(s)
        wd, wdd = worst_stats(s)
        st["mult"] = rec
        st["worst_intramonth_DD"] = round(wdd * 100, 1)
        variants[name] = st
        series[name] = s
        print(f"  {name}: mult={rec} {st}")

    # 決定規則D1: PE1 vs PE0(等ガードテール=各自の校正倍率で比較)
    p0, p1, p2 = variants["PE0_E5only"], variants["PE1_E5+G3_1pct"], variants["PE2_E5+G3_2pct"]
    d1 = dict(
        c1_mean_month=bool(p1["mean_month"] > p0["mean_month"]),
        c2_maxDD=bool(p1["maxDD"] >= p0["maxDD"]),
        c3_worst_day=bool(p1["worst_day"] >= p0["worst_day"] - 0.2),
    )
    d1_pass = all(d1.values())
    chosen = "PE1_E5+G3_1pct" if d1_pass else "PE0_E5only"
    d2 = dict(applicable=bool(d1_pass),
              improves=bool(d1_pass and p2["mean_month"] > p1["mean_month"] and p2["worst_day"] >= -4.0))
    print(f"  D1: {d1} → 採用構成 = {chosen}")

    print("[3/4] チャレンジMC(日次ブロック・2万パス)")
    g3a = None
    use_g3 = chosen != "PE0_E5only"
    arrs = month_arrays(e5)
    if use_g3:
        g3s = g3_1.reindex(e5.index).fillna(0.0)
        mk = pd.PeriodIndex(e5.index, freq="M")
        g3a = [np.asarray(g3s[mk == m].values, float) for m in mk.unique()]
    rec = variants[chosen]["mult"]
    mults = {f"x{k}": round(rec * k, 2) for k in (1.0, 1.5, 2.0)}
    mc_fn = mc_panel(arrs, g3a, mults, 0.08, -0.08, "FN+8%")
    mc_ftmo = mc_panel(arrs, g3a, mults, 0.10, -0.10, "FTMO+10%")

    print("[4/4] 相関(vs PortfolioD / 季節M3)")
    sleeves = dict(v7=mon_daily(YEN), v7x=mon_daily(V7X),
                   EMon=mon_daily(EMON, 3e-4), EMonX=mon_daily(EMONX, 3e-4),
                   E5=e5, SJul=cc_daily(["US500", "NAS100"]), v4=v4_daily())
    pd_map = {m: {"v4": .30, "v7": .25, "EMon": .25, "E5": .20} for m in range(1, 13)}
    pd_comp = composite_daily(sleeves, pd_map)
    m3_comp = composite_daily(sleeves, M3)
    pe = series[chosen]
    rho = dict(vs_PortfolioD=corr_m(pe, pd_comp), vs_SeasonalM3=corr_m(pe, m3_comp))
    d4_limited = any(r is not None and abs(r) > 0.6 for r in rho.values())
    print(f"  ρ: {rho} → 分散価値{'限定的' if d4_limited else 'あり'}")

    res = dict(
        meta=dict(prereg="docs/129" + (" §6(E5間引き2資産)" if basket else ""), basket=basket or "4資産",
                  window="2016-01..2026-06(clip)", seed=SEED, n_paths=N_FINAL,
                  leg_sigma_monthly_pct_1x=legsig,
                  g3_note="G3は日足プロキシ=実測H1の約2割(docs/86 H14b)・控えめ側",
                  inputs=sha256s()),
        variants=variants,
        decision=dict(D1_gates=d1, D1_pass=bool(d1_pass), chosen=chosen, D2=d2,
                      D4_rho=rho, D4_diversification_limited=bool(d4_limited),
                      D5="本資金投入なし・デモ必須(docs/53 §5)"),
        challenge_mc=dict(FN_p1_8pct=mc_fn, FTMO_10pct=mc_ftmo,
                          note="楽観=日次-4%ガード完全執行/悲観(fail_pct_raw)=素の日次-5%踏抜き含む。"
                               "同月pass&failはfail優先"),
        reference=dict(PortfolioD="median-3標準: 中央3ヶ月/失格4.9%(Drive確定, docs/76)"))
    path = os.path.join(HERE, "results", f"portfolio_E_durable{tag}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
