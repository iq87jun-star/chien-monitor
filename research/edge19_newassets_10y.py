# -*- coding: utf-8 -*-
"""
edge19_newassets_10y.py — 探索再開バッチ17(docs/106事前登録の実行)。
新資産クラス(商品・債券先物12・Yahoo継続足日足)に対する:
  H19a: E5逐語レシピのTSMOM(月次1/3/6/12符号合議・逆ボラ・5bp/月)
  H19b: 既存E5(4資産)+新12=16資産版E5 の既存E5比較
9ゲート(docs/106 §3)で採点。チューニング禁止・仮説追加禁止。
出力: results/edge19_newassets_10y.json(入力SHA-256付き) → docs/107へ転記。
"""
import os, sys, json, csv, time, hashlib, urllib.request, urllib.parse, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)

P1, P2 = 946684800, 1782863999   # 2000-01-01 .. 2026-06-30
NEW = {"ZW": "ZW=F", "ZC": "ZC=F", "ZS": "ZS=F", "NG": "NG=F", "CL": "CL=F",
       "HG": "HG=F", "SI": "SI=F", "PL": "PL=F", "ZN": "ZN=F", "ZB": "ZB=F",
       "SB": "SB=F", "KC": "KC=F"}
E5_OLD = ["XAUUSD", "US500", "NAS100", "GER40"]   # 既存E5(research/dataに取得済み・2015-)
COST_M = 5e-4                                     # 月次コスト(E5と同一)
ALPHA = 0.005                                     # Bonferroni(2仮説)
MAIN = ("2016-01", "2025-12")
PRE = ("2000-01", "2015-12")


def fetch(name, sym):
    u = (f"https://query2.finance.yahoo.com/v8/finance/chart/"
         f"{urllib.parse.quote(sym)}?interval=1d&period1={P1}&period2={P2}")
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None)
                     .strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
    p = os.path.join(DATA, f"{name}_d.csv")
    with open(p, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["timestamp", "open", "high", "low", "close"]); w.writerows(rows)
    return len(rows)


def monthly_close(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    return df["close"].resample("ME").last().dropna()


def tsmom_positions(px):
    """E5逐語: 1/3/6/12ヶ月リターン符号の合議(月末判定→翌月適用)"""
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12):
        sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    return np.sign(sig).shift(1)


def tsmom_monthly(px, cost=COST_M, invvol=True):
    ret = px.pct_change()
    pos = tsmom_positions(px)
    if invvol:
        vol = ret.rolling(12).std().shift(1)
        w = (1.0 / vol).div((1.0 / vol).sum(axis=1), axis=0)
        gross = (pos * w * ret).sum(axis=1)   # 逆ボラ加重(E5実装と同じ加重平均型)
        out = gross - cost * (pos.abs().mean(axis=1))
    else:
        out = (pos * ret).mean(axis=1) - cost
    out = out.dropna(); out.index = out.index.to_period("M")
    return out, pos


def clip_window(s, w):
    return s[(s.index >= pd.Period(w[0], "M")) & (s.index <= pd.Period(w[1], "M"))]


def perm_p(r, n=4000, seed=7):
    r = np.asarray(r, float)
    if len(r) == 0:
        return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(n)]) >= real).mean())


def metrics(s):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return dict(net=0, sharpe=0, maxDD=0, calmar=0, n=0)
    eq = (1 + s).cumprod(); dd = float(((eq - eq.cummax()) / eq.cummax()).min()) * 100
    mu = s.mean() * 12; vol = s.std() * np.sqrt(12)
    cagr = (eq.iloc[-1] ** (12 / len(s)) - 1) * 100 if eq.iloc[-1] > 0 else -100
    return dict(net=round(float((eq.iloc[-1] - 1) * 100), 1), sharpe=round(float(mu / vol) if vol > 0 else 0, 3),
                maxDD=round(dd, 1), calmar=round(float(cagr / abs(dd)), 2) if dd else 0.0, n=int(len(s)))


def jackknife(s):
    years = sorted(set(s.index.year))
    ps, nets = [], []
    for y in years:
        sub = s[s.index.year != y]
        ps.append(perm_p(sub.values, n=2000))
        nets.append(float((1 + sub).prod() - 1))
    return round(max(ps), 4), round(min(nets) * 100, 1)


def drift_placebo(px, real_net, cost=COST_M, reps=2000, seed=11):
    """ドリフト保存プラセボ: 各資産のポジション列を資産内シャッフル(構成比保存・タイミング破壊)"""
    ret = px.pct_change()
    pos = tsmom_positions(px)
    vol = ret.rolling(12).std().shift(1)
    w = (1.0 / vol).div((1.0 / vol).sum(axis=1), axis=0)
    rng = np.random.default_rng(seed)
    valid = pos.dropna(how="all").index
    nets = []
    for _ in range(reps):
        pp = pos.copy()
        for c in pp.columns:
            v = pp[c].loc[valid].values.copy()
            rng.shuffle(v)
            pp.loc[valid, c] = v
        g = (pp * w * ret).sum(axis=1) - cost * (pp.abs().mean(axis=1))
        g = g.dropna(); g.index = g.index.to_period("M")
        g = clip_window(g, MAIN)
        nets.append(float((1 + g).prod() - 1))
    nets = np.array(nets)
    return dict(placebo_mean=round(float(nets.mean()) * 100, 1),
                placebo_p95=round(float(np.percentile(nets, 95)) * 100, 1),
                p_real_vs_placebo=round(float((nets >= real_net / 100).mean()), 4))


def main():
    os.makedirs(DATA, exist_ok=True)
    print("[1/5] 新12資産の取得(2000-01〜2026-06)")
    for n, s in NEW.items():
        try:
            print(f"  {n}: {fetch(n, s)} bars")
        except Exception as e:
            print(f"  {n}: ERR {type(e).__name__} {str(e)[:60]}")
        time.sleep(0.6)
    hashes = {n: hashlib.sha256(open(os.path.join(DATA, f"{n}_d.csv"), "rb").read()).hexdigest()[:16]
              for n in NEW if os.path.exists(os.path.join(DATA, f"{n}_d.csv"))}

    print("[2/5] 月次終値パネル構築")
    px_new = pd.DataFrame({n: monthly_close(n) for n in NEW}).dropna(how="all")
    have = [c for c in px_new.columns if px_new[c].dropna().index.min() <= pd.Timestamp("2003-01-31")]
    print(f"  2003年以前から存在: {len(have)}/{len(NEW)} 資産 {have}")
    px_old = pd.DataFrame({n: monthly_close(n) for n in E5_OLD}).dropna()

    print("[3/5] H19a: 新12資産TSMOM")
    s_new, _ = tsmom_monthly(px_new)
    main_s = clip_window(s_new, MAIN); pre_s = clip_window(s_new, PRE)
    m_main = metrics(main_s); m_pre = metrics(pre_s)
    p_main = perm_p(main_s.values); p_pre = perm_p(pre_s.values)
    jkmax, jkmin_net = jackknife(main_s)
    k = int(len(main_s) * 0.7)
    is_net = float((1 + main_s.iloc[:k]).prod() - 1) * 100
    oos_net = float((1 + main_s.iloc[k:]).prod() - 1) * 100
    s_new2x, _ = tsmom_monthly(px_new, cost=2 * COST_M)
    m_2x = metrics(clip_window(s_new2x, MAIN))
    placebo = drift_placebo(px_new, m_main["net"])
    print(f"  main {m_main} p={p_main:.4f} | pre2016 {m_pre} p={p_pre:.4f}")
    print(f"  JKmax={jkmax} JKmin_net={jkmin_net}% IS/OOS={is_net:.1f}/{oos_net:.1f} cost2x_net={m_2x['net']}")
    print(f"  placebo: {placebo}")

    print("[4/5] 相関とポートフォリオ寄与(G8/G9)")
    from parallel_vs_existing_compare import v7_monthly, v4_monthly, e5_monthly
    import edge_regime_gate_10y as RG
    os.environ["RG_ALLOW_YAHOO"] = "0"
    def to_m(w):
        s = w.copy(); s.index = pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()
    sleeves = dict(v4=v4_monthly(), v7=v7_monthly(),
                   EMon=to_m(RG.emon_weekly_gated("riskoff")), E5=e5_monthly())
    corr = {}
    for k2, v in sleeves.items():
        j = pd.concat([clip_window(s_new, MAIN).rename("a"), v.rename("b")], axis=1).dropna()
        corr[k2] = round(float(j["a"].corr(j["b"])), 3)
    print("  corr:", corr)
    # G9: 新スリーブ15%(既存×0.85)・vol1%正規化
    def z(s):
        v = s.std(); return s * (0.01 / v) if v > 0 else s
    base_w = dict(v4=.30, v7=.25, EMon=.25, E5=.20)
    zdf = pd.concat([z(clip_window(v, MAIN)).rename(k2) for k2, v in sleeves.items()]
                    + [z(clip_window(s_new, MAIN)).rename("NEW")], axis=1).dropna()
    port0 = sum(zdf[k2] * w for k2, w in base_w.items())
    port1 = sum(zdf[k2] * w * 0.85 for k2, w in base_w.items()) + zdf["NEW"] * 0.15
    g9 = dict(base=metrics(port0), with_new=metrics(port1))
    print("  G9:", g9)

    print("[5/5] H19b: 16資産版E5 vs 既存E5(共通窓)")
    common0 = max(px_old.index.min(), px_new.index.min())
    px16 = pd.concat([px_old, px_new], axis=1)[lambda d: d.index >= common0]
    s16, _ = tsmom_monthly(px16)
    s4, _ = tsmom_monthly(px_old)
    w16 = clip_window(s16, MAIN); w4 = clip_window(s4, MAIN)
    j = pd.concat([w16.rename("e16"), w4.rename("e4")], axis=1).dropna()
    h19b = dict(e5_old=metrics(j["e4"]), e5_16=metrics(j["e16"]),
                p_16=perm_p(j["e16"].values),
                corr_old_new=round(float(j["e16"].corr(j["e4"])), 3))
    s16_2x, _ = tsmom_monthly(px16, cost=2 * COST_M)
    h19b["e5_16_cost2x"] = metrics(clip_window(s16_2x, MAIN).reindex(j.index).dropna())
    print("  ", h19b)

    # ゲート採点(docs/106 §3)
    gates_a = {
        "G1_econ": bool(m_main["net"] > 0 and m_main["sharpe"] >= 0.3),
        "G2_perm": bool(p_main < ALPHA),
        "G3_jk": bool(jkmax < 0.05 and jkmin_net > 0),
        "G4_placebo": bool(m_main["net"] > placebo["placebo_p95"] and placebo["p_real_vs_placebo"] < 0.05),
        "G5_cost2x": bool(m_2x["net"] > 0),
        "G6_isoos": bool(is_net > 0 and oos_net > 0),
        "G7_pre2016": bool(m_pre["net"] > 0 and p_pre < 0.05),
        "G8_corr": bool(all(abs(v) < 0.5 for v in corr.values())),
        "G9_port": bool(g9["with_new"]["calmar"] > g9["base"]["calmar"]),
    }
    core = ["G1_econ", "G2_perm", "G3_jk", "G4_placebo", "G5_cost2x", "G6_isoos", "G8_corr"]
    n_pass = sum(gates_a.values())
    if all(gates_a[g] for g in core):
        verdict_a = "ADOPT候補(長期構造)" if gates_a["G7_pre2016"] else "LEAD"
    else:
        verdict_a = "REJECT"
    gates_b = dict(
        improves=bool(h19b["e5_16"]["sharpe"] > h19b["e5_old"]["sharpe"]
                      and h19b["e5_16"]["calmar"] > h19b["e5_old"]["calmar"]),
        sig=bool(h19b["p_16"] < ALPHA),
        cost2x=bool(h19b["e5_16_cost2x"]["net"] > 0))
    verdict_b = "E5拡張を提案(承認+デモ前提)" if all(gates_b.values()) else "拡張見送り"

    out = dict(prereg="docs/106", input_sha256=hashes,
               universe=list(NEW.keys()), long_history_assets=have,
               h19a=dict(main=m_main, perm_p=round(p_main, 4), pre2016=m_pre, perm_p_pre=round(p_pre, 4),
                         jk_max_p=jkmax, jk_min_net=jkmin_net,
                         is_net=round(is_net, 1), oos_net=round(oos_net, 1),
                         cost2x=m_2x, placebo=placebo, corr_existing=corr, g9=g9,
                         gates=gates_a, gates_passed=f"{n_pass}/9", verdict=verdict_a),
               h19b=dict(**h19b, gates=gates_b, verdict=verdict_b),
               ref_2026H1_net_pct=round(float((1 + s_new[s_new.index >= pd.Period('2026-01', 'M')]).prod() - 1) * 100, 2))
    path = os.path.join(HERE, "results", "edge19_newassets_10y.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("\n判定 H19a:", verdict_a, f"({n_pass}/9)", "| H19b:", verdict_b)
    print("保存:", path)


if __name__ == "__main__":
    main()
