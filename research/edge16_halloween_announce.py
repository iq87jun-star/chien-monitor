"""
edge16_halloween_announce.py — ハロウィーン効果 & マクロ発表日プレミアム【事前登録 docs/90】。
H16a: 冬半年(11-4月)株LONG vs 夏半年 — 主検定=冬夏スプレッドの符号順列 p<=0.025。
H16b: 発表日(雇用統計=第1金曜+FOMC声明日)のみUS500保有 — 主検定=ラベル順列 p<=0.025。
"""
import os, json, importlib.util
import numpy as np, pandas as pd

spec = importlib.util.spec_from_file_location("e13", "research/edge13_longhistory_confirm.py")
e13 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e13)
spec14 = importlib.util.spec_from_file_location("e14", "research/edge14_breadth_durability.py")
e14 = importlib.util.module_from_spec(spec14); spec14.loader.exec_module(e14)

EQ = ["US500", "NAS100", "GER40"]
ALPHA = 0.025
RNG = np.random.default_rng(13)

def perm_p_sign(v, n=3000, seed=13):
    v = np.asarray(v, float)
    rng = np.random.default_rng(seed); real = v.sum(); a = np.abs(v)
    return float((np.array([(a*rng.choice([-1,1], size=len(a))).sum() for _ in range(n)]) >= real).mean())

# ---------- H16a ハロウィーン ----------
def half_year_returns():
    rows = {}
    for a in EQ:
        s = e13.daily(a); mclose = s.groupby(s.index.to_period("M")).last()
        for y in sorted(set(p.year for p in mclose.index)):
            try:
                oct_prev = mclose[pd.Period(f"{y-1}-10")]
                apr      = mclose[pd.Period(f"{y}-04")]
                octc     = mclose[pd.Period(f"{y}-10")]
            except KeyError: continue
            w = apr/oct_prev - 1.0 - 5e-4          # 冬: 前年10月末→4月末
            su = octc/apr - 1.0                    # 夏: 4月末→10月末(保有しない=比較用)
            rows.setdefault(y, []).append((w, su))
    W = pd.Series({y: np.mean([t[0] for t in v]) for y, v in rows.items() if len(v) >= 2}).sort_index()
    S = pd.Series({y: np.mean([t[1] for t in v]) for y, v in rows.items() if len(v) >= 2}).sort_index()
    return W, S

def h16a():
    W, S = half_year_returns()
    D = (W - S).dropna()
    netW = (np.prod(1+W.values)-1)*100
    p = round(perm_p_sign(D.values), 4)
    pre, post = D[D.index < 2016], D[D.index >= 2016]
    g_dir = netW > 0
    g_spread = p <= ALPHA
    g_split = (pre.mean() > 0 and post.mean() > 0)
    # 診断: 対B&H
    bh = pd.DataFrame({a: e13.daily(a).pct_change() for a in EQ}).mean(axis=1).dropna()
    bh = bh[bh.index >= "1986-10-31"]
    bh_eq = (1+bh).cumprod(); bh_net = (float(bh_eq.iloc[-1])-1)*100
    bh_dd = float(((bh_eq-bh_eq.cummax())/bh_eq.cummax()).min())*100
    strat = bh.copy(); mask = ~bh.index.month.isin([11,12,1,2,3,4]); strat[mask] = 0.0
    st_eq = (1+strat).cumprod(); st_net = (float(st_eq.iloc[-1])-1)*100
    st_dd = float(((st_eq-st_eq.cummax())/st_eq.cummax()).min())*100
    verdict = "LEAD" if (g_dir and g_spread and g_split) else ("参考(G_spread未達)" if (g_dir and g_split) else "REJECT")
    res = dict(n_years=len(D), winter_net=round(netW,1), winter_mean=round(float(W.mean())*100,2),
        summer_mean=round(float(S.mean())*100,2), spread_mean=round(float(D.mean())*100,2),
        spread_perm_p=p, pre2016_spread=round(float(pre.mean())*100,2), post2016_spread=round(float(post.mean())*100,2),
        spread_win=f"{int((D>0).sum())}/{len(D)}",
        diag_bh=dict(bh_net=round(bh_net,0), bh_maxDD=round(bh_dd,1), strat_net=round(st_net,0), strat_maxDD=round(st_dd,1)),
        gates=dict(dir=bool(g_dir), spread=bool(g_spread), split=bool(g_split)), verdict=verdict)
    print(f"### H16a ハロウィーン → {verdict}")
    print(f"  n={len(D)}年 冬平均{res['winter_mean']}% 夏平均{res['summer_mean']}% スプレッド{res['spread_mean']}%/年(勝率{res['spread_win']}) p={p}(α{ALPHA})")
    print(f"  スプレッド pre2016 {res['pre2016_spread']}% / 2016+ {res['post2016_spread']}%")
    print(f"  診断 対B&H: 戦略net{res['diag_bh']['strat_net']}% DD{res['diag_bh']['strat_maxDD']}% vs B&H net{res['diag_bh']['bh_net']}% DD{res['diag_bh']['bh_maxDD']}%(市場滞在は半分)")
    return res

# ---------- H16b 発表日プレミアム ----------
def first_fridays(idx):
    """各月の第1金曜(取引日ベース近似)。"""
    out = set()
    df = pd.Series(1, index=idx)
    for (y, m), grp in df.groupby([idx.year, idx.month]):
        fri = [d for d in grp.index if d.dayofweek == 4]
        if fri: out.add(fri[0].date())
    return out

def h16b():
    s = e13.daily("US500"); r = s.pct_change().dropna()
    nfp = first_fridays(r.index)
    fomc = set(pd.Timestamp(d).date() for d in (e14.FOMC_PRE + e14.FOMC_POST))
    is_a = np.array([(d.date() in nfp) or (d.date() in fomc) for d in r.index])
    cost = 1e-4
    a_days = r[is_a] - cost; n_days = r[~is_a]
    net = (np.prod(1+a_days.values)-1)*100
    delta = float(a_days.mean() - n_days.mean())
    vals = r.values; nA = int(is_a.sum()); n = len(vals); ge = 0
    for _ in range(3000):
        pick = RNG.choice(n, size=nA, replace=False)
        mask = np.zeros(n, bool); mask[pick] = True
        if (vals[mask].mean() - vals[~mask].mean()) >= delta: ge += 1
    p = round(ge/3000, 4)
    pre_a, pre_n = a_days[a_days.index < "2016-01-01"], n_days[n_days.index < "2016-01-01"]
    post_a, post_n = a_days[a_days.index >= "2016-01-01"], n_days[n_days.index >= "2016-01-01"]
    d_pre = float(pre_a.mean()-pre_n.mean()); d_post = float(post_a.mean()-post_n.mean())
    g_dir = net > 0; g_label = p <= ALPHA; g_split = (d_pre > 0 and d_post > 0)
    only_nfp = r[[d.date() in nfp for d in r.index]]; only_fomc = r[[d.date() in fomc for d in r.index]]
    verdict = "LEAD" if (g_dir and g_label and g_split) else ("参考(G_label未達)" if (g_dir and g_split) else "REJECT")
    res = dict(n_adays=int(nA), net_pct=round(net,1), aday_mean_bps=round(float(a_days.mean())*1e4,2),
        nonaday_mean_bps=round(float(n_days.mean())*1e4,2), delta_bps=round(delta*1e4,2), label_perm_p=p,
        pre2016_delta_bps=round(d_pre*1e4,2), post2016_delta_bps=round(d_post*1e4,2),
        diag=dict(nfp_mean_bps=round(float(only_nfp.mean())*1e4,2), fomc_mean_bps=round(float(only_fomc.mean())*1e4,2)),
        gates=dict(dir=bool(g_dir), label=bool(g_label), split=bool(g_split)), verdict=verdict)
    print(f"\n### H16b 発表日プレミアム → {verdict}")
    print(f"  発表日n={nA} net{res['net_pct']}% 発表日平均{res['aday_mean_bps']}bps vs 非発表日{res['nonaday_mean_bps']}bps Δ={res['delta_bps']}bps p={p}(α{ALPHA})")
    print(f"  Δ pre2016 {res['pre2016_delta_bps']}bps / 2016+ {res['post2016_delta_bps']}bps | 分解: NFP {res['diag']['nfp_mean_bps']}bps / FOMC {res['diag']['fomc_mean_bps']}bps")
    return res

out = {"H16a_HALLOWEEN": h16a(), "H16b_ANNOUNCE_DAY": h16b()}
os.makedirs("research/results", exist_ok=True)
with open("research/results/edge16_halloween_announce.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\n保存: research/results/edge16_halloween_announce.json")
