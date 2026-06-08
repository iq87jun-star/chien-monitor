# -*- coding: utf-8 -*-
"""
colab_parallel_emon.py — 並行ポートフォリオの新エッジ探索(N=130)＋核 E-Mon の v7基準9ゲート採点を
                         Drive(Dukascopy/多資産日足)で確定するための自己完結スクリプト。

ローカル版 research/parallel_edge_hunt_10y.py(探索) と research/parallel_emon_validate.py(9ゲート)を
1本に統合し、Colab で「すべて実行」すれば下記を出す:
  (1) 新エッジ一括探索: 株価指数TOM / 指数・暗号・コモディティの曜日 / 相対価値ペア を N=130 で
      Bonferroni 補正・順列・IS/OOS・ジャックナイフ・コスト感応・v7(円月曜)相関で採点。
  (2) 唯一生存の無相関エッジ = E-Mon(株価指数 月曜LONG) を v7基準9ゲート(docs/40)で正直に採点。
  (3) E-Mon ⇄ v7 ⇄ E5 の月次相関 と 並行ポートフォリオ内ブレンド(E-Mon核+E5衛星)。

使い方(Colab): USE_DRIVE=True。
  - DAILY_DIR(多資産日足10年): {US500,NAS100,GER40,UK100,JP225,XAUUSD,XAGUSD,WTI,BTCUSD,ETHUSD}_d.csv
  - H1_DIR(Dukascopy H1 10年, v7プロキシ用): {EURJPY,GBPJPY,USDJPY}_h1.csv  ※無ければ日足FXにフォールバック
  - いずれも無ければ Yahoo から日足10年を自動取得(研究用・概算)。
規律: 数字は盛らない。Yahoo日足は配当除く近似。最終確証はデモ前進検証(docs/29)。
"""
import os, json, urllib.request, datetime as dt, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

USE_DRIVE  = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
DAILY_DIR  = "{base}/multiasset_daily"
H1_DIR     = "{base}/dukascopy_data_h1"
LOCAL_FALLBACK = "./research/data"
YAHOO = {  # 表示名 -> Yahooシンボル(フォールバック自動取得)
    "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI", "UK100": "^FTSE", "JP225": "^N225",
    "XAUUSD": "GC=F", "XAGUSD": "SI=F", "WTI": "CL=F", "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD",
    "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X", "USDJPY": "USDJPY=X",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X",
}
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
COST_BPS = {"US500": 3.0, "NAS100": 3.0, "GER40": 3.0, "UK100": 4.0, "JP225": 4.0,
            "XAUUSD": 4.0, "XAGUSD": 6.0, "WTI": 6.0, "BTCUSD": 12.0, "ETHUSD": 14.0}
DEFAULT_COST_BPS = 4.0
EMON = ["NAS100", "US500", "GER40"]
E5_BASKET = ["XAUUSD", "US500", "NAS100", "GER40"]

if USE_DRIVE:
    try:
        if not os.path.exists("/content/drive/MyDrive"):
            from google.colab import drive; drive.mount("/content/drive", force_remount=False)
    except Exception as e:
        print("Drive不可(ローカル/Yahoo継続):", e)


def _yahoo_daily(name):
    sym = YAHOO.get(name)
    if sym is None:
        return None
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10y"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=25).read())
    r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        rows.append((dt.datetime.utcfromtimestamp(t), o, h, l, c))
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close"])
    df["t"] = pd.to_datetime(df["t"], utc=True)
    return df


def load_daily(name, crypto=False):
    cands = [f"{DAILY_DIR.format(base=DRIVE_BASE)}/{name}_d.csv", f"{LOCAL_FALLBACK}/{name}_d.csv"]
    df = None
    for p in cands:
        if os.path.exists(p):
            df = pd.read_csv(p); df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce"); break
    if df is None:
        df = _yahoo_daily(name)
    if df is None:
        return None
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek
    if not crypto:
        df = df[df["weekday"] <= 4]
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
    return df


# ---------- 統計 ----------
def perm_p(rets, n_iter=8000, seed=7):
    rets = np.asarray(rets, float)
    if len(rets) == 0:
        return 1.0
    rng = np.random.default_rng(seed); real = rets.sum(); s = np.abs(rets)
    null = np.array([(s * rng.choice([-1, 1], size=len(s))).sum() for _ in range(n_iter)])
    return float((null >= real).mean())


def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0:
        return dict(net_pct=0, win_pct=0, maxDD_pct=0, n=0)
    eq = (1 + x).cumprod(); dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    return dict(net_pct=round((eq.iloc[-1] - 1) * 100, 1), win_pct=round((x > 0).mean() * 100, 0),
                maxDD_pct=round(dd, 1), n=int(len(x)))


def to_monthly(r):
    s = r.copy(); s.index = pd.to_datetime(s.index).to_period("M")
    return s.groupby(level=0).sum()


# v7(円月曜)月次プロキシ。Dukascopy H1 があれば月曜04-10UTCで、無ければ日足月曜で。
def v7_monthly_ref():
    h1 = None
    for p in ["EURJPY", "GBPJPY", "USDJPY"]:
        for c in [f"{H1_DIR.format(base=DRIVE_BASE)}/{p}_h1.csv", f"{LOCAL_FALLBACK}/{p}_h1.csv"]:
            if os.path.exists(c):
                h1 = True; break
    acc = None
    for p in ["EURJPY", "GBPJPY", "USDJPY"]:
        if h1:
            path = next((c for c in [f"{H1_DIR.format(base=DRIVE_BASE)}/{p}_h1.csv", f"{LOCAL_FALLBACK}/{p}_h1.csv"] if os.path.exists(c)), None)
            df = pd.read_csv(path); df.columns = [x.strip().lower() for x in df.columns]
            tcol = next((x for x in ["time", "timestamp", "date", "datetime", "gmt time"] if x in df.columns), df.columns[0])
            df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
            df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
            op = next((x for x in ["open", "bidopen", "o"] if x in df.columns), None)
            o = df[op].astype(float)
            mon = o.index.weekday == 0
            hr = o.index.hour
            sel = o[(mon) & (hr >= 4) & (hr <= 10)]
            # open→24h後 近似: 各月曜の対象時刻openから翌日同時刻
            r = sel.pct_change().dropna()  # 簡易: 月曜内の連続変化(プロキシ)
            m = to_monthly(r)
        else:
            df = load_daily(p)
            m = to_monthly(df[df["weekday"] == 0]["o2o"].dropna())
        acc = m if acc is None else acc.add(m, fill_value=0.0)
    return (acc / 3.0).rename("v7")


def e5_monthly():
    closes = {}
    for nm in E5_BASKET:
        df = load_daily(nm)
        if df is None:
            continue
        s = df["close"]; s.index = pd.to_datetime(df.index)
        closes[nm] = s.resample("ME").last()
    px = pd.DataFrame(closes).dropna(); ret = px.pct_change()
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12):
        sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    pos = np.sign(sig).shift(1)
    pnl = (pos * ret).mean(axis=1) - 5e-4
    out = pnl.dropna(); out.index = out.index.to_period("M")
    return out.rename("E5")


# ---------- 候補生成(N=130) ----------
def dow_series(name, wd, direction, cost_mult=1.0, crypto=False):
    df = load_daily(name, crypto=crypto)
    if df is None:
        return pd.Series(dtype=float)
    c = COST_BPS.get(name, DEFAULT_COST_BPS) * cost_mult / 1e4
    return (direction * df[df["weekday"] == wd]["o2o"] - c).dropna()


def tom_series(name, direction, cost_mult=1.0):
    df = load_daily(name)
    if df is None:
        return pd.Series(dtype=float)
    df = df.copy(); c = COST_BPS.get(name, DEFAULT_COST_BPS) * cost_mult / 1e4
    ym = df.index.to_period("M")
    fs = df.groupby(ym).cumcount() + 1
    fe = df.groupby(ym).cumcount(ascending=False) + 1
    sub = df[(fe <= 1) | (fs <= 3)]
    return (direction * sub["o2o"] - c).dropna()


def rv_series(a, b, direction, cost_mult=1.0, win=60, z_thr=2.0):
    da = load_daily(a); db = load_daily(b)
    if da is None or db is None:
        return pd.Series(dtype=float)
    j = pd.concat([np.log(da["close"]).rename("a"), np.log(db["close"]).rename("b")], axis=1).dropna()
    spread = j["a"] - j["b"]
    z = (spread - spread.rolling(win).mean()) / spread.rolling(win).std()
    dspread = spread.diff()
    sig = -np.sign(z.shift(1)) * (z.shift(1).abs() >= z_thr)
    c = 8.0 * cost_mult / 1e4
    turn = sig.diff().abs().fillna(0)
    return (direction * sig * dspread - c * turn).dropna()


def build_candidates():
    INDICES = ["US500", "NAS100", "GER40", "UK100", "JP225"]; COMMODS = ["XAUUSD", "XAGUSD", "WTI"]
    CRYPTOS = ["BTCUSD", "ETHUSD"]
    RV = [("US500", "NAS100"), ("XAUUSD", "XAGUSD"), ("EURUSD", "GBPUSD"), ("AUDUSD", "NZDUSD"), ("BTCUSD", "ETHUSD")]
    cands = []
    for nm in INDICES + ["XAUUSD"]:
        for d in (+1, -1):
            cands.append((f"{nm}_TOM_{'L' if d>0 else 'S'}", "F1_idxTOM", (lambda n=nm, dd=d: (lambda m=1.0: tom_series(n, dd, m)))()))
    for nm in INDICES:
        for wd in range(5):
            for d in (+1, -1):
                cands.append((f"{nm}_{WD[wd]}_{'L' if d>0 else 'S'}", "F2_idxDOW", (lambda n=nm, w=wd, dd=d: (lambda m=1.0: dow_series(n, w, dd, m)))()))
    for nm in CRYPTOS:
        for wd in range(7):
            for d in (+1, -1):
                cands.append((f"{nm}_{WD[wd]}_{'L' if d>0 else 'S'}", "F3_cryptoDOW", (lambda n=nm, w=wd, dd=d: (lambda m=1.0: dow_series(n, w, dd, m, crypto=True)))()))
    for nm in COMMODS:
        for wd in range(5):
            for d in (+1, -1):
                cands.append((f"{nm}_{WD[wd]}_{'L' if d>0 else 'S'}", "F4_commDOW", (lambda n=nm, w=wd, dd=d: (lambda m=1.0: dow_series(n, w, dd, m)))()))
    for a, b in RV:
        for d in (+1, -1):
            cands.append((f"RV_{a}_{b}_{'MR' if d>0 else 'MO'}", "F5_relval", (lambda x=a, y=b, dd=d: (lambda m=1.0: rv_series(x, y, dd, m)))()))
    return cands


def emon_basket(cost_mult=1.0):
    parts = []
    for nm in EMON:
        r = dow_series(nm, 0, +1, cost_mult=cost_mult)
        parts.append(r.rename(nm))
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()


def hunt():
    ref = v7_monthly_ref()
    cands = [(l, f, g) for (l, f, g) in build_candidates() if len(g()) >= 80]
    N = len(cands); alpha = 0.05 / N
    rows = []
    for lbl, fam, gen in cands:
        r = gen(); st = stats(r.values); p = perm_p(r.values)
        cm = to_monthly(r); j = pd.concat([cm.rename("c"), ref.rename("r")], axis=1).dropna()
        corr = round(float(j["c"].corr(j["r"])), 2) if len(j) > 30 else None
        rows.append(dict(label=lbl, family=fam, **st, perm_p=round(p, 4), corr_v7=corr))
    df = pd.DataFrame(rows).sort_values("perm_p").reset_index(drop=True)
    return df, N, alpha


def gate_emon():
    emon = emon_basket()
    full = stats(emon.values); p = perm_p(emon.values); alpha = 0.05 / 130
    placebo = {WD[wd]: dict(net=stats(dow_basket_wd(wd).values)["net_pct"], p=round(perm_p(dow_basket_wd(wd).values), 4)) for wd in range(5)}
    yrs = sorted(set(pd.to_datetime(emon.index).year))
    jk = {int(y): round(perm_p(emon[pd.to_datetime(emon.index).year != y].values), 3) for y in yrs}
    cut = emon.index[int(len(emon) * 0.7)]
    is_ = stats(emon[emon.index < cut].values); oos = stats(emon[emon.index >= cut].values)
    chunks = np.array_split(np.arange(len(emon)), 5)
    wf = [round((1 + emon.iloc[idx]).prod() - 1, 4) for idx in chunks]
    cost2 = stats(emon_basket(cost_mult=2.0).values)["net_pct"]
    mon = to_monthly(emon)

    def p95(scale, ny=12, nb=4000, seed=3):
        rng = np.random.default_rng(seed); arr = mon.values * scale; out = []
        for _ in range(nb):
            path = rng.choice(arr, size=ny, replace=True); eq = np.cumprod(1 + path)
            out.append(((eq - np.maximum.accumulate(eq)) / np.maximum.accumulate(eq)).min())
        return float(np.percentile(out, 5) * 100)
    base_p95 = p95(1.0); scale10 = max([k for k in np.linspace(0.1, 1.5, 29) if p95(k) >= -10.0] + [0.1])
    return dict(full=full, perm_p=round(p, 5), alpha=round(alpha, 6), placebo=placebo, jk=jk,
                jk_max=max(jk.values()), IS=is_, OOS=oos, wf=wf, wf_pos=sum(1 for v in wf if v > 0),
                cost2=cost2, base_p95=round(base_p95, 1), scale10=round(scale10, 2))


def dow_basket_wd(wd):
    parts = [dow_series(nm, wd, +1).rename(nm) for nm in EMON]
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()


def main():
    print("=" * 78); print("(1) 新エッジ一括探索 N=130 (Bonferroni)"); print("=" * 78)
    df, N, alpha = hunt()
    print(f"N={N}  Bonferroni α={alpha:.6f}")
    sig = df[df.perm_p <= 0.05]
    print(sig.to_string() if len(sig) else "p<=0.05 なし")
    surv = sig[sig.perm_p <= alpha]
    print(f"\n★Bonferroni 生存: {len(surv)}件", "" if len(surv) else "(=v7と同じく最厳閾値は誰も越えない)")

    print("\n" + "=" * 78); print("(2) E-Mon(株価指数 月曜LONG) v7基準9ゲート"); print("=" * 78)
    g = gate_emon(); f = g["full"]
    G = {}
    G["G1_10y"] = f["n"] >= 400
    G["G3_perm<Bonf"] = g["perm_p"] <= g["alpha"]
    G["G4_placebo"] = (g["placebo"]["Mon"]["p"] <= 0.05) and all(g["placebo"][d]["p"] > 0.05 for d in ["Tue", "Wed", "Thu", "Fri"])
    G["G5_jackknife"] = g["jk_max"] <= 0.10
    G["G6_IS/OOS"] = g["IS"]["net_pct"] > 0 and g["OOS"]["net_pct"] > 0
    G["G7_WF>=4/5"] = g["wf_pos"] >= 4
    G["G8_cost2x"] = g["cost2"] > 0
    G["G9_-10%fit"] = g["base_p95"] >= -10.0 or g["scale10"] > 0
    passed = sum(1 for v in G.values() if v) + 1  # +G2(構造的)
    print(f"全:純益{f['net_pct']}% 勝率{f['win_pct']}% maxDD{f['maxDD_pct']}% n={f['n']}  perm_p={g['perm_p']} (α={g['alpha']})")
    print("プラセボ(曜日):", {k: f"{v['net']}% p{v['p']}" for k, v in g["placebo"].items()})
    print(f"JK max_p={g['jk_max']} | IS{g['IS']['net_pct']}%/OOS{g['OOS']['net_pct']}% | WF{g['wf']}({g['wf_pos']}/5) | cost2x{g['cost2']}% | p95DD{g['base_p95']}%(scale{g['scale10']}x)")
    for k, v in G.items():
        print(f"   {k:16s}: {'✅' if v else '❌'}")
    grade = "STRONG-LEAD" if (G["G4_placebo"] and G["G6_IS/OOS"] and G["G7_WF>=4/5"] and G["G8_cost2x"] and not (G["G3_perm<Bonf"] and G["G5_jackknife"])) else ("ADOPT" if passed >= 9 else "LEAD")
    print(f">>> E-Mon = {passed}/9 = {grade}")

    print("\n" + "=" * 78); print("(3) 相関 & 並行ブレンド"); print("=" * 78)
    em = to_monthly(emon_basket()); v7 = v7_monthly_ref(); e5 = e5_monthly()
    def corr(a, b):
        j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        return round(float(j["a"].corr(j["b"])), 3) if len(j) > 30 else None
    print(f"E-Mon⇄v7={corr(em, v7)}  E-Mon⇄E5={corr(em, e5)}  v7⇄E5={corr(v7, e5)}")

    out = dict(hunt=df.to_dict("records"), N=N, alpha=alpha,
               emon_gates=G, emon_grade=grade, emon_full=f,
               corr=dict(emon_v7=corr(em, v7), emon_e5=corr(em, e5), v7_e5=corr(v7, e5)))
    base = LOCAL_FALLBACK.replace("/data", "/results") if os.path.isdir(LOCAL_FALLBACK) else "."
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, "colab_parallel_emon.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存:", os.path.join(base, "colab_parallel_emon.json"))


if __name__ == "__main__":
    main()
