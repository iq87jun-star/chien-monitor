# -*- coding: utf-8 -*-
"""
policy_prune_symbols.py — PortfolioD銘柄間引きの検定【事前登録 docs/131】。
H24a: v4 9→6(K=3) / H24b: v7 3→2(K=1) / H24c: E5 4→2(K=2)。
方法: LOYO選別(各年を除いた9年の月次Sharpe下位Kを除外→除外年OOS) vs フルバスケット。
プラセボ: 同数除外の全組合せ(84/3/6)の全期間Sharpe分布。安定性: 除外セットのフォールド一致。
決定規則 c1-c4 は docs/131 §3 のとおり機械適用。窓: 2016-01〜2025-12(10フォールド)。
出力: results/policy_prune_symbols.json → docs/132
"""
import os, sys, json
from itertools import combinations
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from portfolio_daily_compare import load_daily, clip, rsi_w, atr_d, YEN, EMON, E5B, mon_daily
from parallel_vs_existing_compare import pip_size
from seasonal_optimize_loyo import sha256s

W0, W1 = pd.Timestamp("2016-01-01"), pd.Timestamp("2025-12-31")
YEARS = list(range(2016, 2026))
V4P = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]


def win(s):
    return s[(s.index >= W0) & (s.index <= W1)]


def v7_one(nm):
    df = load_daily(nm)
    cost = 2 * pip_size(nm) / df["open"]
    return win(clip((df[df["weekday"] == 0]["o2o"] - cost).dropna()))


def v4_one(p):
    df = load_daily(p)
    o = df["open"].values; hh = df["high"].values; ll = df["low"].values; c = df["close"].values
    idx = df.index; n = len(c); rsi = rsi_w(c); atr = atr_d(hh, ll, c); bb = 20
    cost = 2 * pip_size(p); acc = {}; i = bb + 2
    while i < n - 1:
        w_ = c[i - bb:i]; mean = w_.mean(); sd = w_.std(ddof=1)
        z = (c[i] - mean) / sd if sd > 0 else 0
        down = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
            else: break
        up = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
            else: break
        retd = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0
        buy = int(rsi[i] < 35) + int(z < -1.5) + int(down >= 3) + int(retd < -.005)
        sell = int(rsi[i] > 65) + int(z > 1.5) + int(up >= 3) + int(retd > .005)
        sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
        if sig == 0:
            i += 1; continue
        entry = o[i + 1]; sld = 1.5 * atr[i]; tpd = 1.2 * sld
        if sld <= 0 or entry <= 0:
            i += 1; continue
        sl = entry - sig * sld; tp = entry + sig * tpd; ex = None; j = i + 1; held = 0
        while j < n and held < 8:
            if sig > 0:
                if ll[j] <= sl: ex = sl; break
                if hh[j] >= tp: ex = tp; break
            else:
                if hh[j] >= sl: ex = sl; break
                if ll[j] <= tp: ex = tp; break
            j += 1; held += 1
        jx = min(j, n - 1)
        if ex is None: ex = c[jx]
        prev = entry
        for t in range(i + 1, jx + 1):
            px = ex if t == jx else c[t]
            r = sig * (px - prev) / entry
            if t == i + 1: r -= cost / entry
            acc[idx[t]] = acc.get(idx[t], 0.0) + r
            prev = px
        i = max(i + 1, j)
    return win(clip(pd.Series(acc).sort_index()))


def e5_basket(assets):
    """既存 e5_daily と同一ロジックを資産リストでパラメタ化(RP再構築)"""
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
    pw = (pos * w); pw.index = pw.index.to_period("M")
    daily = {}
    for nm in assets:
        s = load_daily(nm)["close"].pct_change().dropna()
        mkey = pd.PeriodIndex(pd.to_datetime(s.index), freq="M")
        daily[nm] = pd.Series(s.values * pw[nm].reindex(mkey).values, index=s.index)
    out = pd.DataFrame(daily).sum(axis=1, skipna=True)
    firsts = pd.Series(out.index, index=out.index).groupby(pd.PeriodIndex(out.index, freq="M")).min()
    out.loc[out.index.isin(firsts.values)] -= 5e-4
    return win(clip(out.dropna()))


def e5_one(nm):
    df = load_daily(nm)
    s = df["close"]; s.index = pd.to_datetime(df.index)
    mpx = s.resample("ME").last()
    comp = sum(np.sign(mpx.pct_change(L)) for L in (1, 3, 6, 12))
    pos = np.sign(comp).shift(1); pos.index = pos.index.to_period("M")
    d = s.pct_change().dropna()
    mk = pd.PeriodIndex(d.index, freq="M")
    out = pd.Series(d.values * pos.reindex(mk).values, index=d.index)
    firsts = pd.Series(out.index, index=out.index).groupby(pd.PeriodIndex(out.index, freq="M")).min()
    out.loc[out.index.isin(firsts.values)] -= 5e-4
    return win(clip(out.dropna()))


def monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({m: float((1 + s[mk == m]).prod() - 1) for m in mk.unique()}).sort_index()


def sharpe_m(m):
    m = m.dropna()
    return float(m.mean() / m.std() * np.sqrt(12)) if len(m) > 12 and m.std() > 0 else 0.0


def net_pct(m):
    return round((float((1 + m).prod()) - 1) * 100, 1)


def daily_matrix(per_sym):
    return pd.DataFrame(per_sym).fillna(0.0)


def combine(D, keep, how):
    return D[list(keep)].sum(axis=1) if how == "sum" else D[list(keep)].mean(axis=1)


def run_sleeve(name, symbols, per_sym, K, how, e5_mode=False):
    D = daily_matrix(per_sym)
    msym = {s: monthly(per_sym[s]) for s in symbols}
    full_daily = combine(D, symbols, how) if not e5_mode else e5_basket(symbols)
    full_m = monthly(full_daily)

    # LOYO: 各年を除いた9年のSharpe下位Kを除外 → その年のOOS
    oos, fold_drops = [], {}
    for y in YEARS:
        tr_sh = {s: sharpe_m(msym[s][msym[s].index.year != y]) for s in symbols}
        drop = sorted(sorted(tr_sh, key=tr_sh.get)[:K])
        keep = [s for s in symbols if s not in drop]
        fold_drops[y] = drop
        sd = (e5_basket(keep) if e5_mode else combine(D, keep, how))
        sd = sd[sd.index.year == y]
        oos.append(sd)
    oos_daily = pd.concat(oos).sort_index()
    oos_m = monthly(oos_daily)

    # vol-matched net(フルの月次σに揃える)
    scale = float(full_m.std() / oos_m.std()) if oos_m.std() > 0 else 1.0
    vmnet = net_pct(oos_m * scale)

    # プラセボ: 同数除外の全組合せ(固定)の全期間Sharpe分布
    dist = []
    for drop in combinations(symbols, K):
        keep = [s for s in symbols if s not in drop]
        m = monthly(e5_basket(keep) if e5_mode else combine(D, keep, how))
        dist.append(sharpe_m(m))
    p80 = float(np.percentile(dist, 80))

    # 安定性: 全期間選択セットとの一致
    full_sh = {s: sharpe_m(msym[s]) for s in symbols}
    full_drop = sorted(sorted(full_sh, key=full_sh.get)[:K])
    stable = sum(1 for y in YEARS if fold_drops[y] == full_drop)

    sh_full, sh_oos = sharpe_m(full_m), sharpe_m(oos_m)
    c1 = bool(sh_oos > sh_full and vmnet > net_pct(full_m))
    c2 = bool(sh_oos >= p80)
    c3 = bool(stable >= 8)
    return dict(full=dict(sharpe=round(sh_full, 2), net=net_pct(full_m)),
                loyo_pruned=dict(sharpe=round(sh_oos, 2), net_raw=net_pct(oos_m), net_volmatched=vmnet),
                fixed_posthoc_drop=full_drop,
                fold_drops={str(y): fold_drops[y] for y in YEARS},
                stability=f"{stable}/10",
                placebo=dict(n=len(dist), p80_sharpe=round(p80, 2),
                             dist=[round(x, 2) for x in sorted(dist)]),
                gates=dict(c1_oos=c1, c2_placebo=c2, c3_stability=c3))


def main():
    print("[H24a] v4 9→6")
    v4_sym = {p: v4_one(p) for p in V4P}
    ra = run_sleeve("v4", V4P, v4_sym, 3, "sum")
    print(f"  {ra['gates']} stability={ra['stability']}")

    print("[H24b] v7 3→2")
    v7_sym = {p: v7_one(p) for p in YEN}
    rb = run_sleeve("v7", YEN, v7_sym, 1, "mean")
    print(f"  {rb['gates']} stability={rb['stability']}")

    print("[H24c] E5 4→2(RP再構築)")
    e5_sym = {p: e5_one(p) for p in E5B}
    rc = run_sleeve("E5", E5B, e5_sym, 2, "mean", e5_mode=True)
    # c4: 間引き後E5 vs v7/E-Mon 相関
    keep_full = [s for s in E5B if s not in rc["fixed_posthoc_drop"]]
    pe = monthly(e5_basket(keep_full))
    v7m = monthly(win(mon_daily(YEN)))
    emonm = monthly(win(mon_daily(EMON, 3e-4)))
    rho_v7 = round(float(pd.concat([pe, v7m], axis=1).dropna().corr().iloc[0, 1]), 2)
    rho_em = round(float(pd.concat([pe, emonm], axis=1).dropna().corr().iloc[0, 1]), 2)
    rc["c4_rho"] = dict(vs_v7=rho_v7, vs_EMon=rho_em)
    rc["gates"]["c4_corr"] = bool(abs(rho_v7) <= 0.4 and abs(rho_em) <= 0.4)
    print(f"  {rc['gates']} stability={rc['stability']} ρ={rc['c4_rho']}")

    def verdict(r, need_c4=False):
        g = r["gates"]
        ok = g["c1_oos"] and g["c2_placebo"] and g["c3_stability"] and (g.get("c4_corr", True) if need_c4 else True)
        return "採用候補(Dukascopy再確認+デモへ)" if ok else "REJECT(現行維持)"

    out = dict(meta=dict(prereg="docs/131", window="2016-01..2025-12", folds=YEARS,
                         inputs=sha256s()),
               H24a_v4=dict(**ra, verdict=verdict(ra)),
               H24b_v7=dict(**rb, verdict=verdict(rb)),
               H24c_E5=dict(**rc, verdict=verdict(rc, need_c4=True)))
    path = os.path.join(HERE, "results", "policy_prune_symbols.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    for k in ("H24a_v4", "H24b_v7", "H24c_E5"):
        r = out[k]
        print(f"### {k} → {r['verdict']}")
        print(f"  full Sh {r['full']['sharpe']}/net {r['full']['net']}% | LOYO Sh {r['loyo_pruned']['sharpe']}"
              f"/vmnet {r['loyo_pruned']['net_volmatched']}% | placebo p80 {r['placebo']['p80_sharpe']}"
              f" | 安定 {r['stability']} | 事後固定除外 {r['fixed_posthoc_drop']}")
    print("保存:", path)


if __name__ == "__main__":
    main()
