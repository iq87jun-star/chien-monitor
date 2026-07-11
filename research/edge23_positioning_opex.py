# -*- coding: utf-8 -*-
"""
edge23_positioning_opex.py — バッチ18(docs/126事前登録の実行)。
  H23a: JPY投機筋ポジショニング(COT net/OI 3年百分位)極端の翌週反転(USDJPY週次)
  H23b: v7のCOTゲート(pct≤50=円ショート混雑時のみ建てる) — 相対規則
  H23c: 金投機筋ポジショニング極端の翌週反転
  H23d: OpEx週(第3金曜を含む週)のUS500ロング(月1回)
9ゲート(docs/126 §3・α=0.0025)で採点。チューニング禁止・仮説追加禁止。
出力: results/edge23_positioning_opex.json(入力SHA-256付き) → docs/127へ転記。
事前準備: python3 research/fetch_data.py && python3 research/fetch_multiasset.py(G8/G9用スリーブ)
"""
import os, sys, json, csv, time, hashlib, calendar, urllib.request, urllib.parse, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)

MAIN = ("2016-01-01", "2025-12-31")
PRE_JPY = ("1996-01-01", "2015-12-31")
PRE_GOLD = ("2003-01-01", "2015-12-31")
PRE_SPX = ("1990-01-01", "2015-12-31")
ALPHA = 0.0025                       # Bonferroni 0.01/4(docs/126 §3)
PCT_WIN, PCT_MIN = 156, 104          # 3年百分位・最低104レポート
SEED = 23

SOC = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
COT_MARKETS = {
    "jpy": ["JAPANESE YEN - INTERNATIONAL MONETARY MARKET",
            "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"],
    "gold": ["GOLD - COMMODITY EXCHANGE INC."],
}
YAHOO_FULL = {"usdjpy_full": "USDJPY=X", "gold_full": "GC=F", "us500_full": "^GSPC"}


# ---------------- データ取得(CSVキャッシュ+SHA) ----------------
def fetch_cot(key):
    p = os.path.join(DATA, f"cot_{key}.csv")
    if not os.path.exists(p):
        frames = []
        for mkt in COT_MARKETS[key]:
            params = {"$select": "report_date_as_yyyy_mm_dd,noncomm_positions_long_all,"
                                 "noncomm_positions_short_all,open_interest_all",
                      "$where": f"market_and_exchange_names='{mkt}'",
                      "$order": "report_date_as_yyyy_mm_dd", "$limit": "50000"}
            u = SOC + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            frames.append(pd.DataFrame(json.loads(urllib.request.urlopen(req, timeout=60).read())))
            time.sleep(0.5)
        df = pd.concat(frames, ignore_index=True)
        df["rd"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
        for c in ("noncomm_positions_long_all", "noncomm_positions_short_all", "open_interest_all"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = (df.dropna().sort_values(["rd", "open_interest_all"])
                .drop_duplicates("rd", keep="last"))  # 移行期の重複はOI大を採用
        df[["rd", "noncomm_positions_long_all", "noncomm_positions_short_all",
            "open_interest_all"]].to_csv(p, index=False)
    df = pd.read_csv(p, parse_dates=["rd"])
    df["net_oi"] = ((df["noncomm_positions_long_all"] - df["noncomm_positions_short_all"])
                    / df["open_interest_all"].replace(0, np.nan))
    return df.dropna(subset=["net_oi"]).set_index("rd").sort_index()


def fetch_yahoo_full(name, sym):
    p = os.path.join(DATA, f"{name}_d.csv")
    if not os.path.exists(p):
        u = (f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
             f"?interval=1d&period1=0&period2=1783295999")  # ..2026-07-05以降の直近まで
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=60).read())
        r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
        rows = []
        for i, t in enumerate(ts):
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            if None in (o, h, l, c) or o <= 0:
                continue
            rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None)
                         .strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
        with open(p, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["timestamp", "open", "high", "low", "close"]); w.writerows(rows)
    df = pd.read_csv(p)
    df["t"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["date"] = df["t"].dt.floor("D")
    df = df.groupby("date", as_index=True).last()[["open", "high", "low", "close"]]
    return df[df.index.dayofweek <= 4]


# ---------------- 共通部品 ----------------
def pct_rank(s, win=PCT_WIN, minp=PCT_MIN):
    """現在値含む過去win本の百分位(値≤現在の割合×100)"""
    return s.rolling(win, min_periods=minp).apply(
        lambda a: float((a <= a[-1]).mean()) * 100.0, raw=True)


def effective_monday(rd):
    """report_date(火)→金曜公表→翌月曜から有効。rd+6日以降の最初の月曜。"""
    e = rd + pd.Timedelta(days=6)
    return e + pd.Timedelta(days=(7 - e.weekday()) % 7)


def weekly_frame(daily):
    """週(月曜起点)ごとの 初営業日open と 週次リターン(今週初open→翌週初open)"""
    d = daily.copy()
    d["wk"] = d.index - pd.to_timedelta(d.index.dayofweek, unit="D")
    wko = d.groupby("wk")["open"].first()
    ret = wko.shift(-1) / wko - 1.0
    return pd.DataFrame({"open": wko, "ret": ret}).dropna()


def cot_weekly_signal(cot, weeks):
    """各週(月曜)に、その週から有効な最新レポートの百分位を割当(35日で失効)"""
    sig = cot[["net_oi"]].copy()
    sig["pct"] = pct_rank(sig["net_oi"])
    sig = sig.dropna(subset=["pct"]).reset_index()
    sig["eff"] = sig["rd"].map(effective_monday)
    sig = sig.sort_values("eff").drop_duplicates("eff", keep="last")
    wk = pd.DataFrame({"wk": weeks}).sort_values("wk")
    m = pd.merge_asof(wk, sig[["eff", "pct"]], left_on="wk", right_on="eff",
                      direction="backward", tolerance=pd.Timedelta(days=35))
    return m.set_index("wk")["pct"]


def clip(s, w):
    return s[(s.index >= pd.Timestamp(w[0])) & (s.index <= pd.Timestamp(w[1]))]


def perm_p(r, n=4000, seed=SEED):
    r = np.asarray(pd.Series(r).dropna(), float)
    if len(r) == 0 or np.abs(r).sum() == 0:
        return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a * rng.choice([-1, 1], size=len(a))).sum()
                            for _ in range(n)]) >= real).mean())


def metrics(s, ann):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return dict(net=0.0, sharpe=0.0, maxDD=0.0, n=0)
    eq = (1 + s).cumprod(); dd = float(((eq - eq.cummax()) / eq.cummax()).min()) * 100
    mu = s.mean() * ann; vol = s.std() * np.sqrt(ann)
    return dict(net=round(float((eq.iloc[-1] - 1) * 100), 1),
                sharpe=round(float(mu / vol) if vol > 0 else 0.0, 3),
                maxDD=round(dd, 1), n=int(len(s)))


def jackknife(s):
    years = sorted(set(s.index.year)); ps, nets = [], []
    for y in years:
        sub = s[s.index.year != y]
        ps.append(perm_p(sub.values, n=2000))
        nets.append(float((1 + sub).prod() - 1))
    return round(max(ps), 4), round(min(nets) * 100, 1)


def shuffle_placebo(pos, ret_series, cost_series, real_net, reps=2000, seed=SEED):
    """ドリフト保存: 主窓内でポジション列をシャッフル(ON比率・L/S構成保存・タイミング破壊)"""
    rng = np.random.default_rng(seed)
    p = pos.values.copy(); r = ret_series.values; c = cost_series.values
    nets = np.empty(reps)
    for i in range(reps):
        q = rng.permutation(p)
        strat = q * r - np.abs(q) * c
        nets[i] = float(np.prod(1 + strat) - 1)
    return dict(placebo_mean=round(float(nets.mean()) * 100, 1),
                placebo_p95=round(float(np.percentile(nets, 95)) * 100, 1),
                p_real_vs_placebo=round(float((nets >= real_net / 100).mean()), 4))


def gate_table(s_main, s_pre, s_cost2x, placebo, ann, corr=None, g9=None):
    m = metrics(s_main, ann); mp = metrics(s_pre, ann)
    p_main = perm_p(s_main.values); p_pre = perm_p(s_pre.values)
    jkmax, jkmin = jackknife(s_main)
    k = int(len(s_main) * 0.7)
    is_net = float((1 + s_main.iloc[:k]).prod() - 1) * 100
    oos_net = float((1 + s_main.iloc[k:]).prod() - 1) * 100
    m2x = metrics(s_cost2x, ann)
    gates = {
        "G1_econ": bool(m["net"] > 0 and m["sharpe"] >= 0.3),
        "G2_perm": bool(p_main < ALPHA),
        "G3_jk": bool(jkmax < 0.05 and jkmin > 0),
        "G4_placebo": bool(m["net"] > placebo["placebo_p95"]
                           and placebo["p_real_vs_placebo"] < 0.05),
        "G5_cost2x": bool(m2x["net"] > 0),
        "G6_isoos": bool(is_net > 0 and oos_net > 0),
        "G7_pre2016": bool(mp["net"] > 0 and p_pre < 0.05),
        "G8_corr": bool(corr is not None and all(abs(v) < 0.5 for v in corr.values())),
        "G9_port": bool(g9 is not None and g9["with_new"]["calmar"] > g9["base"]["calmar"]),
    }
    core = ["G1_econ", "G2_perm", "G3_jk", "G4_placebo", "G5_cost2x", "G6_isoos", "G8_corr"]
    if all(gates[g] for g in core):
        verdict = "ADOPT候補(長期構造)" if gates["G7_pre2016"] else "LEAD"
    else:
        verdict = "REJECT"
    return dict(main=m, perm_p=round(p_main, 4), pre2016=mp, perm_p_pre=round(p_pre, 4),
                jk_max_p=jkmax, jk_min_net=jkmin, is_net=round(is_net, 1),
                oos_net=round(oos_net, 1), cost2x=m2x, placebo=placebo,
                corr_existing=corr, g9=g9, gates=gates,
                gates_passed=f"{sum(gates.values())}/9", verdict=verdict)


def calmar_port(s, ann=12):
    s = pd.Series(s).dropna()
    eq = (1 + s).cumprod(); dd = float(((eq - eq.cummax()) / eq.cummax()).min())
    cagr = (eq.iloc[-1] ** (ann / len(s)) - 1) if eq.iloc[-1] > 0 else -1
    return dict(net=round(float((eq.iloc[-1] - 1) * 100), 1),
                calmar=round(float(cagr / abs(dd)), 2) if dd else 0.0,
                maxDD=round(dd * 100, 1))


def to_monthly(s):
    m = s.copy(); m.index = pd.to_datetime(m.index).to_period("M")
    return m.groupby(level=0).sum()


def corr_and_g9(strat_weekly):
    """G8/G9: 既存4スリーブ(月次)との相関と15%追加のポート寄与"""
    from parallel_vs_existing_compare import v7_monthly, v4_monthly, e5_monthly
    os.environ["RG_ALLOW_YAHOO"] = "0"
    import edge_regime_gate_10y as RG
    def tm(w):
        s = w.copy(); s.index = pd.to_datetime(s.index).to_period("M")
        return s.groupby(level=0).sum()
    sleeves = dict(v4=v4_monthly(), v7=v7_monthly(),
                   EMon=tm(RG.emon_weekly_gated("riskoff")), E5=e5_monthly())
    new_m = to_monthly(strat_weekly)
    new_m = new_m[(new_m.index >= pd.Period("2016-01", "M"))
                  & (new_m.index <= pd.Period("2025-12", "M"))]
    corr = {}
    for k, v in sleeves.items():
        j = pd.concat([new_m.rename("a"), v.rename("b")], axis=1).dropna()
        corr[k] = round(float(j["a"].corr(j["b"])), 3) if len(j) > 12 else 0.0
    def z(s):
        v = s.std(); return s * (0.01 / v) if v > 0 else s
    base_w = dict(v4=.30, v7=.25, EMon=.25, E5=.20)
    zdf = pd.concat([z(v[(v.index >= pd.Period("2016-01", "M"))
                         & (v.index <= pd.Period("2025-12", "M"))]).rename(k)
                     for k, v in sleeves.items()] + [z(new_m).rename("NEW")], axis=1).dropna()
    port0 = sum(zdf[k] * w for k, w in base_w.items())
    port1 = sum(zdf[k] * w * 0.85 for k, w in base_w.items()) + zdf["NEW"] * 0.15
    return corr, dict(base=calmar_port(port0), with_new=calmar_port(port1))


# ---------------- H23a/H23c: COT極端の翌週反転 ----------------
def cot_extreme_strategy(cot, wf, side_asset, cost_fn, lo=20, hi=80):
    """side_asset='jpy': pct≤20→円ロング(=USDJPYショート=-1)/pct≥80→+1(USDJPYロング)
       side_asset='gold': pct≤20→金ロング(+1)/pct≥80→金ショート(-1)"""
    pct = cot_weekly_signal(cot, wf.index)
    if side_asset == "jpy":
        pos = pd.Series(np.where(pct <= lo, -1.0, np.where(pct >= hi, 1.0, 0.0)),
                        index=wf.index)  # USDJPY建玉方向(円ロング=-1)
    else:
        pos = pd.Series(np.where(pct <= lo, 1.0, np.where(pct >= hi, -1.0, 0.0)),
                        index=wf.index)
    cost = cost_fn(wf)
    strat = pos * wf["ret"] - pos.abs() * cost
    return strat.dropna(), pos, cost


def run_standalone(tag, cot, wf, side, cost_fn, pre_win, ann=52):
    strat, pos, cost = cot_extreme_strategy(cot, wf, side, cost_fn)
    s_main = clip(strat, MAIN); s_pre = clip(strat, pre_win)
    strat2x, _, _ = cot_extreme_strategy(cot, wf, side,
                                         lambda w: cost_fn(w) * 2.0)
    s2x = clip(strat2x, MAIN)
    pm = pos.reindex(s_main.index); rm = wf["ret"].reindex(s_main.index)
    cm = cost.reindex(s_main.index)
    real_net = metrics(s_main, ann)["net"]
    placebo = shuffle_placebo(pm, rm, cm, real_net)
    corr, g9 = corr_and_g9(s_main)
    res = gate_table(s_main, s_pre, s2x, placebo, ann, corr, g9)
    res["on_ratio_main"] = round(float((pm != 0).mean()), 3)
    print(f"  {tag}: main {res['main']} p={res['perm_p']} | pre {res['pre2016']} "
          f"p={res['perm_p_pre']} | placebo {placebo} | {res['gates_passed']} {res['verdict']}")
    return res


# ---------------- H23b: v7のCOTゲート ----------------
def v7_weekly():
    from parallel_vs_existing_compare import load_daily, pip_size, YEN
    parts = []
    for p in YEN:
        df = load_daily(p)
        mon = df[df["weekday"] == 0]
        r = (mon["o2o"] - 2 * pip_size(p) / mon["open"]).dropna().rename(p)
        r.index = pd.to_datetime(r.index)
        if r.index.tz is not None:
            r.index = r.index.tz_localize(None)
        parts.append(r)
    w = pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()
    w.index = w.index - pd.to_timedelta(w.index.dayofweek, unit="D")  # 週キー=月曜
    return w


def run_v7_gate(cot_jpy):
    v7w = clip(v7_weekly(), MAIN)
    pct = cot_weekly_signal(cot_jpy, v7w.index)
    gate = (pct <= 50).astype(float)
    gated = v7w * gate
    def shp(s):
        s = pd.Series(s).dropna()
        return float(s.mean() / s.std() * np.sqrt(52)) if s.std() > 0 else 0.0
    n = len(v7w); b = n // 3
    blocks = [(v7w.iloc[i * b:(i + 1) * b if i < 2 else n],
               gated.iloc[i * b:(i + 1) * b if i < 2 else n]) for i in range(3)]
    block_res = [dict(ungated=round(shp(u), 3), gated=round(shp(g), 3),
                      win=bool(shp(g) > shp(u))) for u, g in blocks]
    rng = np.random.default_rng(SEED)
    on = int(gate.sum()); real = shp(gated)
    sims = np.empty(2000)
    for i in range(2000):
        mask = np.zeros(n); mask[rng.choice(n, size=on, replace=False)] = 1.0
        sims[i] = shp(v7w.values * mask)
    p_pl = float((sims >= real).mean())
    ok = all(r["win"] for r in block_res) and p_pl < 0.05
    res = dict(on_ratio=round(float(gate.mean()), 3),
               full=dict(ungated=dict(**metrics(v7w, 52), sharpe_w=round(shp(v7w), 3)),
                         gated=dict(**metrics(gated, 52), sharpe_w=round(shp(gated), 3))),
               blocks=block_res, placebo_p=round(p_pl, 4),
               verdict="LEAD(デモ前提)" if ok else "REJECT(現行v7維持)")
    print(f"  H23b: on={res['on_ratio']} blocks={[r['win'] for r in block_res]} "
          f"placebo_p={p_pl:.4f} → {res['verdict']}")
    return res


# ---------------- H23d: OpEx週 ----------------
def month_weeks(daily, y, m):
    """当月の週(月曜キー)→(初営業日open, 最終営業日close)。週は月内営業日のみで構成"""
    d = daily[(daily.index.year == y) & (daily.index.month == m)]
    out = {}
    for wk, g in d.groupby(d.index - pd.to_timedelta(d.index.dayofweek, unit="D")):
        out[wk] = (float(g["open"].iloc[0]), float(g["close"].iloc[-1]), len(g))
    return out


def opex_week_monday(y, m):
    c = calendar.Calendar()
    fridays = [d for d in c.itermonthdates(y, m) if d.month == m and d.weekday() == 4]
    tf = fridays[2]
    return pd.Timestamp(tf) - pd.Timedelta(days=4)


def run_opex(spx, cost=3e-4):
    rows, candidates = [], []
    y0, m0 = spx.index.min().year, spx.index.min().month
    y1, m1 = spx.index.max().year, spx.index.max().month
    cur = pd.Timestamp(y0, m0, 1)
    end = pd.Timestamp(y1, m1, 1)
    while cur <= end:
        y, m = cur.year, cur.month
        wks = month_weeks(spx, y, m)
        opx = opex_week_monday(y, m)
        if opx in wks and wks[opx][2] >= 3:
            o, c_, _ = wks[opx]
            rows.append((opx, c_ / o - 1.0 - cost))
            alts = [c2 / o2 - 1.0 - cost for w, (o2, c2, nd) in wks.items()
                    if w != opx and nd >= 3]
            candidates.append(alts)
        cur += pd.offsets.MonthBegin(1)
    strat = pd.Series(dict(rows)).sort_index()
    return strat, candidates


def run_h23d(spx):
    strat, cands = run_opex(spx)
    strat2x, _ = run_opex(spx, cost=6e-4)
    s_main = clip(strat, MAIN); s_pre = clip(strat, PRE_SPX)
    # プラセボ: 各月、OpEx週以外のランダム週(月1週ON保存)
    idx = [i for i, d in enumerate(strat.index)
           if pd.Timestamp(MAIN[0]) <= d <= pd.Timestamp(MAIN[1])]
    rng = np.random.default_rng(SEED)
    nets = np.empty(2000)
    for r in range(2000):
        tot = 1.0
        for i in idx:
            alts = cands[i]
            tot *= 1 + (alts[rng.integers(len(alts))] if alts else 0.0)
        nets[r] = tot - 1
    real_net = metrics(s_main, 12)["net"]
    placebo = dict(placebo_mean=round(float(nets.mean()) * 100, 1),
                   placebo_p95=round(float(np.percentile(nets, 95)) * 100, 1),
                   p_real_vs_placebo=round(float((nets >= real_net / 100).mean()), 4))
    corr, g9 = corr_and_g9(s_main)
    res = gate_table(s_main, s_pre, clip(strat2x, MAIN), placebo, 12, corr, g9)
    print(f"  H23d: main {res['main']} p={res['perm_p']} | pre {res['pre2016']} "
          f"p={res['perm_p_pre']} | placebo {placebo} | {res['gates_passed']} {res['verdict']}")
    return res


def main():
    os.makedirs(DATA, exist_ok=True)
    print("[1/6] COT取得(Socrata 6dca-aqww)")
    cot_jpy = fetch_cot("jpy"); cot_gold = fetch_cot("gold")
    print(f"  jpy: {len(cot_jpy)} reports {cot_jpy.index.min().date()}..{cot_jpy.index.max().date()}")
    print(f"  gold: {len(cot_gold)} reports {cot_gold.index.min().date()}..{cot_gold.index.max().date()}")

    print("[2/6] 価格取得(Yahoo全歴史)")
    usdjpy = fetch_yahoo_full("usdjpy_full", YAHOO_FULL["usdjpy_full"])
    gold = fetch_yahoo_full("gold_full", YAHOO_FULL["gold_full"])
    spx = fetch_yahoo_full("us500_full", YAHOO_FULL["us500_full"])
    print(f"  usdjpy {usdjpy.index.min().date()}.. / gold {gold.index.min().date()}.. "
          f"/ spx {spx.index.min().date()}..")
    hashes = {f: hashlib.sha256(open(os.path.join(DATA, f), "rb").read()).hexdigest()[:16]
              for f in ["cot_jpy.csv", "cot_gold.csv", "usdjpy_full_d.csv",
                        "gold_full_d.csv", "us500_full_d.csv"]}

    print("[3/6] H23a: JPY COT極端の翌週反転(USDJPY)")
    wf_jpy = weekly_frame(usdjpy)
    h23a = run_standalone("H23a", cot_jpy, wf_jpy, "jpy",
                          lambda w: 2 * 0.01 / w["open"], PRE_JPY)

    print("[4/6] H23b: v7のCOTゲート(pct≤50)")
    h23b = run_v7_gate(cot_jpy)

    print("[5/6] H23c: 金COT極端の翌週反転")
    wf_gold = weekly_frame(gold)
    h23c = run_standalone("H23c", cot_gold, wf_gold, "gold",
                          lambda w: pd.Series(5e-4, index=w.index), PRE_GOLD)

    print("[6/6] H23d: OpEx週US500ロング")
    h23d = run_h23d(spx)

    out = dict(prereg="docs/126", alpha=ALPHA, input_sha256=hashes,
               h23a=h23a, h23b=h23b, h23c=h23c, h23d=h23d)
    path = os.path.join(HERE, "results", "edge23_positioning_opex.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("\n判定: H23a", h23a["verdict"], "| H23b", h23b["verdict"],
          "| H23c", h23c["verdict"], "| H23d", h23d["verdict"])
    print("保存:", path)


if __name__ == "__main__":
    main()
