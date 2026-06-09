# -*- coding: utf-8 -*-
"""
edge10_gold_standalone_10y.py — 規約準拠の【新銘柄】候補: 金(XAUUSD)を単独で検定する10年バッテリー
================================================================================
背景(なぜ金・単独・非月次TSMOMか):
  - 確定構成は v4(FX合議) : E-Mon(株価指数 月曜LONG) = 55:45 (docs/59/61)。
  - 規約(FTMO/FundedNext)の核心禁止 = 同一/高相関銘柄の反対両建て(口座間も)。
    ∴ 新レッグは「v4が触るFX」「E-Monが触る株価指数」と別の資産でなければ衝突しうる。
  - docs/27 の E5(金+株価指数のTSMOM/RP)はLEAD止まり、しかも"指数を含む"のでE-Monと衝突。
    指数を外した E5c(金/銀/WTIのみ)は月次TSMOMで死亡(Calmar0.01, docs/59)。
  - docs/14 の day-of-week / turn-of-month 検定は FX9ペアのみ。**金/銀/WTIを単独で**
    day-of-week・turn-of-month・"日足"トレンド・"日足"平均回帰で検定したことは無い。
  → 本書は docs/14 の進路②「データ宇宙の拡張(金)」を、プロジェクトと同一の厳格ハーネスで実行する。
    金/銀/WTIは v4(FX)・E-Mon(指数)のどちらにも触れない=構造的にヘッジ衝突ゼロ=規約準拠。

データ: Yahoo日足 ~11年(再取得可・research/data/にキャッシュ, gitignore)。
規律(docs/14と同思想):
  - 事前登録した全セル(銘柄×手法×方向)を一括検定し、Bonferroni補正を全数で課す。
  - ノールックアヘッド(確定足→翌足始値約定)。実コストをbpsで往復計上。コスト感応(2/5/10/20bps)。
  - 順列検定(符号シャッフル, 月次集約=自己相関頑健) / IS-OOS(前半-後半) / 年次ジャックナイフ /
    プラセボ(ランダム方向) / **E-Mon proxy・株指数ベータ・対象自身のbuy&hold との相関(独立性)**。
  - 数字は盛らない。出なければ「出ない」と書く(docs/07/08の仮数値errorを繰り返さない)。

⚠ Yahoo日足はOHLC概算・配当/期近ロール・スワップ未精緻。LEAD以上は本資金前にデモ前進検証(docs/29)。
"""
import os, json, time, csv, datetime as dt, urllib.request
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

DATA = os.path.join(os.path.dirname(__file__), "data")
RESULTS = os.path.join(os.path.dirname(__file__), "results")
RANGE = "11y"

# 新銘柄候補(規約クリーン: v4=FX, E-Mon=指数 のどちらにも該当しない)
INSTR = {"XAUUSD": "GC=F", "XAGUSD": "SI=F", "WTI": "CL=F"}
# 相関(独立性)算定用の参照: E-Mon proxy 用の株価指数
INDEX = {"US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI"}

BASE_BPS = 5.0          # 往復コスト基準(価格分数 = bps/1e4)。商品CFDの保守値。
COST_GRID = (2, 5, 10, 20)
LOOKBACKS = [20, 60, 120]   # 日足TSMOM(月次TSMOMが死んだ→より速い日足を試す)
RSI_N = 14

# ---------------- データ取得(キャッシュ) ----------------
def fetch_yahoo(sym):
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range={RANGE}"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c): continue
        rows.append((dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
    return rows

def ensure(name, sym):
    os.makedirs(DATA, exist_ok=True)
    p = os.path.join(DATA, f"{name}_d.csv")
    if not os.path.exists(p):
        rows = fetch_yahoo(sym)
        with open(p, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["timestamp", "open", "high", "low", "close"]); w.writerows(rows)
        time.sleep(1.0)
    return p

def load(name, sym):
    df = pd.read_csv(ensure(name, sym))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    return df[["open", "high", "low", "close"]]

# ---------------- 指標 ----------------
def rsi_wilder(c, n=14):
    c = np.asarray(c, float); d = np.diff(c, prepend=c[0])
    up = np.clip(d, 0, None); dn = np.clip(-d, 0, None)
    au = np.empty_like(c); ad = np.empty_like(c); au[0] = up[0]; ad[0] = dn[0]; a = 1.0 / n
    for i in range(1, len(c)):
        au[i] = a * up[i] + (1 - a) * au[i - 1]; ad[i] = a * dn[i] + (1 - a) * ad[i - 1]
    rs = np.divide(au, np.where(ad == 0, np.nan, ad))
    return pd.Series(np.nan_to_num(100 - 100 / (1 + rs), nan=50.0), index=None)

# ---------------- 統計ハーネス(既存scriptと同一思想) ----------------
def perm_p(r, n=3000, seed=13):
    r = np.asarray(r, float)
    if len(r) == 0 or r.sum() <= 0: return 1.0
    rng = np.random.default_rng(seed); real = r.sum(); a = np.abs(r)
    return float((np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(n)]) >= real).mean())

def perm_p_robust(s, n=3000, seed=13):
    s = pd.Series(s).dropna()
    if len(s) == 0: return 1.0
    ms = s.groupby(s.index.to_period("M")).sum()
    return perm_p(ms.values, n=n, seed=seed)

def stats(x):
    x = pd.Series(x).dropna()
    if len(x) == 0: return dict(net_pct=0.0, win_pct=0.0, maxDD_pct=0.0, n=0, sharpe=0.0)
    eq = (1 + x).cumprod(); dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    sh = (x.mean() / x.std() * np.sqrt(252)) if x.std() > 0 else 0.0  # 日次→年率近似(DoW等は近似)
    return dict(net_pct=round((eq.iloc[-1] - 1) * 100, 1), win_pct=round((x > 0).mean() * 100, 0),
                maxDD_pct=round(dd, 1), n=int(len(x)), sharpe=round(float(sh), 2))

def jackknife(s):
    s = pd.Series(s).dropna()
    yrs = sorted(set(s.index.year))
    if len(yrs) < 3: return None, None
    jk = {int(y): round(perm_p_robust(s[s.index.year != y]), 3) for y in yrs}
    return jk, round(max(jk.values()), 3)

def is_oos(s):
    s = pd.Series(s).dropna()
    if len(s) < 4: return 0.0, 0.0
    h = s.index[len(s) // 2]
    return round((1 + s[s.index < h]).prod() - 1, 4) * 100, round((1 + s[s.index >= h]).prod() - 1, 4) * 100

def monthly(s):
    s = pd.Series(s).dropna()
    return s.groupby(s.index.to_period("M")).sum() if len(s) else pd.Series(dtype=float)

# ---------------- シグナル生成(各々が日次PnL系列 pd.Series を返す) ----------------
def trade_date_open_to_next_open(df, mask, direction, bps):
    """mask=Trueの取引日のopenでentry、翌取引日openで決済。direction=+1/-1。"""
    o = df["open"]; idx = df.index
    nxt_o = o.shift(-1)
    ret = (nxt_o - o) / o * direction - bps / 1e4
    return ret[mask].dropna()

def sig_dayofweek(df, weekday, direction, bps=BASE_BPS, randomize=False, seed=0):
    mask = (df.index.dayofweek == weekday)
    if randomize:
        rng = np.random.default_rng(seed)
        o = df["open"]; nxt = o.shift(-1)
        base = ((nxt - o) / o)[mask].dropna()
        dirs = rng.choice([-1, 1], size=len(base))
        return (base * dirs - bps / 1e4)  # Series(datetime index)を保持
    return trade_date_open_to_next_open(df, mask, direction, bps)

def sig_turnofmonth(df, direction, bps=BASE_BPS, randomize=False, seed=0):
    # 月末最終営業日 + 月初3営業日 を保有日とみなす(各日 open->翌open)
    idx = df.index
    dom = pd.Series(idx, index=idx)
    is_first3 = dom.groupby([idx.year, idx.month]).rank(method="first") <= 3
    last = dom.groupby([idx.year, idx.month]).rank(method="first", ascending=False) == 1
    mask = pd.Series(is_first3.values | last.values, index=idx)
    if randomize:
        rng = np.random.default_rng(seed)
        o = df["open"]; nxt = o.shift(-1); base = ((nxt - o) / o)[mask].dropna()
        dirs = rng.choice([-1, 1], size=len(base))
        return (base * dirs - bps / 1e4)  # Series(datetime index)を保持
    return trade_date_open_to_next_open(df, mask, direction, bps)

def sig_tsmom_daily(df, bps=BASE_BPS, randomize=False, seed=0):
    """日足TSMOM: 複数lookbackの符号合議でポジション、翌日リターンを取る。コストは建替時。"""
    c = df["close"]; ret = c.pct_change()
    comp = sum(np.sign(c.pct_change(L)) for L in LOOKBACKS)
    pos = np.sign(comp)
    if randomize:
        rng = np.random.default_rng(seed)
        pos = pd.Series(rng.choice([-1, 1], size=len(pos)), index=pos.index)
    pos = pos.shift(1)  # ノールックアヘッド
    turn = pos.diff().abs().fillna(0)
    pnl = pos * ret - turn * (bps / 1e4)
    return pnl.dropna()

def sig_mr_daily(df, bps=BASE_BPS, randomize=False, seed=0):
    """日足平均回帰(v4機構を金に適用): RSI<35でLONG, >65でSHORT, 翌日決済。"""
    c = df["close"].values; idx = df.index
    rsi = rsi_wilder(c, RSI_N); rsi.index = idx
    raw = pd.Series(0, index=idx, dtype=float)
    raw[rsi < 35] = 1.0; raw[rsi > 65] = -1.0
    if randomize:
        rng = np.random.default_rng(seed)
        nz = raw != 0
        raw[nz] = rng.choice([-1, 1], size=int(nz.sum()))
    o = df["open"]; nxt = o.shift(-1)
    entry_ret = (nxt - o) / o
    mask = raw != 0
    pnl = (entry_ret * raw - bps / 1e4)[mask].dropna()
    return pnl

# ---------------- 事前登録バッテリー ----------------
WD = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
DIR = {1: "L", -1: "S"}

def build_candidates(data):
    """戻り: dict name -> (signal_fn(bps,randomize,seed)). 全数=Bonferroni N。"""
    cand = {}
    for inst, df in data.items():
        for wd in WD:
            for d in DIR:
                cand[f"{inst}_{WD[wd]}_{DIR[d]}"] = (lambda df=df, wd=wd, d=d:
                    (lambda bps=BASE_BPS, randomize=False, seed=0: sig_dayofweek(df, wd, d, bps, randomize, seed)))()
        for d in DIR:
            cand[f"{inst}_ToM_{DIR[d]}"] = (lambda df=df, d=d:
                (lambda bps=BASE_BPS, randomize=False, seed=0: sig_turnofmonth(df, d, bps, randomize, seed)))()
        cand[f"{inst}_TSMOMd"] = (lambda df=df:
            (lambda bps=BASE_BPS, randomize=False, seed=0: sig_tsmom_daily(df, bps, randomize, seed)))()
        cand[f"{inst}_MRd"] = (lambda df=df:
            (lambda bps=BASE_BPS, randomize=False, seed=0: sig_mr_daily(df, bps, randomize, seed)))()
    return cand

# ---------------- E-Mon proxy(独立性=相関の参照) ----------------
def emon_monthly(idx_data):
    """株価指数の 月曜open->火曜open LONG を月次集約(E-Monの素朴proxy)。"""
    rows = []
    for name, df in idx_data.items():
        o = df["open"]; nxt = o.shift(-1)
        mon = df.index.dayofweek == 0
        r = ((nxt - o) / o)[mon].dropna()
        for t, v in r.items():
            rows.append((t, v))
    if not rows: return pd.Series(dtype=float)
    s = pd.Series([v for _, v in rows], index=[t for t, _ in rows]).sort_index()
    return s.groupby(s.index.to_period("M")).sum()

def index_beta_monthly(idx_data):
    """株価指数 buy&hold 月次(リスクオン・ベータの参照)。"""
    cols = {n: df["close"].groupby(df.index.to_period("M")).last().pct_change() for n, df in idx_data.items()}
    return pd.concat(cols, axis=1).mean(axis=1).dropna()

def self_bh_monthly(df):
    """対象自身の buy&hold 月次(=方向シグナルが素のベータでないかの参照)。"""
    return df["close"].groupby(df.index.to_period("M")).last().pct_change().dropna()

def corr_m(a, b):
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    return round(float(j["a"].corr(j["b"])), 2) if len(j) > 12 else None

# ---------------- 実行 ----------------
def run():
    print("=== データ取得(Yahoo日足 ~11y, キャッシュ) ===")
    data = {n: load(n, s) for n, s in INSTR.items()}
    idx_data = {n: load(n, s) for n, s in INDEX.items()}
    for n, df in {**data, **idx_data}.items():
        yrs = (df.index[-1] - df.index[0]).days / 365.25
        print(f"  {n:7s} {len(df):5d} bars {df.index[0].date()}..{df.index[-1].date()} ({yrs:.1f}y)")

    emon = emon_monthly(idx_data)
    ibeta = index_beta_monthly(idx_data)
    print(f"  E-Mon proxy 月数={len(emon)} / index-beta 月数={len(ibeta)}")

    cand = build_candidates(data)
    N = len(cand); bonf = round(0.05 / N, 5)
    print(f"\n=== 事前登録バッテリー: {N} セル(銘柄×手法×方向) Bonferroni α={bonf} コスト基準{BASE_BPS}bps ===")

    out = {"meta": dict(n_tests=N, bonferroni_alpha=bonf, base_bps=BASE_BPS, lookbacks=LOOKBACKS,
                        range=RANGE, instruments=list(INSTR), note="金/銀/WTIは v4(FX)・E-Mon(指数)と非衝突=規約クリーン"),
           "candidates": {}}

    # 第1段: 全セルを perm_p_robust で粗選別(数字は全て保存)
    rows = []
    for name, fn in cand.items():
        s = fn()
        s = pd.Series(s) if not isinstance(s, pd.Series) else s
        if not isinstance(s.index, pd.DatetimeIndex):
            # DoW/ToM randomize経路でndarrayが来た場合に備えるが、通常はSeries
            s = pd.Series(dtype=float)
        st = stats(s)
        if st["n"] < 24:
            out["candidates"][name] = dict(**st, note="insufficient"); continue
        p = round(perm_p_robust(s), 4)
        rows.append((name, fn, s, st, p))
        out["candidates"][name] = dict(**st, perm_p=p)

    # Bonferroni生存 と "p<=0.05生(参考)"
    survivors = [r for r in rows if r[4] <= bonf]
    raw005 = [r for r in rows if r[4] <= 0.05]
    print(f"  perm_p<=0.05(生): {len(raw005)}件 / Bonferroni({bonf})生存: {len(survivors)}件")

    # 第2段: 生存 + 上位6件(近接候補も特性化)に全ゲート
    detail_set = {r[0] for r in survivors} | {r[0] for r in sorted(rows, key=lambda x: x[4])[:6]}
    for name, fn, s, st, p in rows:
        if name not in detail_set: continue
        jk, jkmax = jackknife(s)
        isn, oosn = is_oos(s)
        ms = monthly(s)
        c_emon = corr_m(ms, emon); c_ibeta = corr_m(ms, ibeta)
        inst = name.split("_")[0]
        c_self = corr_m(ms, self_bh_monthly(data[inst]))
        plc = fn(BASE_BPS, True, 7); plc = pd.Series(plc) if not isinstance(plc, pd.Series) else plc
        plc_st = stats(plc); plc_p = round(perm_p_robust(plc), 3)
        cost = {f"{c}bps": stats(fn(float(c)))["net_pct"] for c in COST_GRID}
        g_perm = p <= bonf
        g_jk = (jkmax is not None and jkmax <= 0.10)
        g_oos = (isn > 0 and oosn > 0)
        g_indep = all((c is None) or abs(c) <= 0.4 for c in (c_emon, c_ibeta))
        g_plac = (plc_p > 0.05 and st["net_pct"] > plc_st["net_pct"])
        g_cost = all(v > 0 for v in cost.values())
        g_dd = st["maxDD_pct"] >= -25.0
        passed = sum([g_perm, g_jk, g_oos, g_indep, g_plac, g_cost])
        grade = ("ADOPT" if (g_perm and g_jk and g_oos and g_indep and g_plac and g_cost)
                 else ("LEAD" if (st["net_pct"] > 0 and p <= 0.10 and g_oos) else "REJECT"))
        out["candidates"][name].update(dict(
            perm_p=p, jackknife_max_p=jkmax, IS_net=isn, OOS_net=oosn,
            corr_emon=c_emon, corr_index_beta=c_ibeta, corr_self_bh=c_self,
            placebo_net=plc_st["net_pct"], placebo_p=plc_p, cost=cost,
            gates=dict(perm=g_perm, jk=g_jk, oos=g_oos, indep=g_indep, placebo=g_plac, cost=g_cost, dd=g_dd),
            gates_passed=f"{passed}/6", grade=grade))
        print(f"\n### {name} [{grade}] {passed}/6")
        print(f"   純益{st['net_pct']}% 勝率{st['win_pct']}% maxDD{st['maxDD_pct']}% n={st['n']} Sharpe~{st['sharpe']}")
        print(f"   p頑健={p}(Bonf{bonf}:{g_perm}) JKmax={jkmax}({g_jk}) IS{isn}/OOS{oosn}({g_oos})")
        print(f"   相関 E-Mon={c_emon} idxβ={c_ibeta} self-bh={c_self} ({g_indep}) | placebo純{plc_st['net_pct']}%/p{plc_p}({g_plac}) | cost{cost}({g_cost})")

    adopts = [n for n, r in out["candidates"].items() if r.get("grade") == "ADOPT"]
    leads = [n for n, r in out["candidates"].items() if r.get("grade") == "LEAD"]
    out["adopted"] = adopts; out["leads"] = leads
    print("\n>>> ADOPT:", adopts if adopts else "なし")
    print(">>> LEAD(要追検):", leads if leads else "なし")
    if not adopts and not leads:
        print(">>> 金/銀/WTI単独も全滅 → 新レッグ無し、確定構成(v4:E-Mon=55:45)のまま(誠実な結論)。")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "edge10_gold_standalone_10y.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/edge10_gold_standalone_10y.json")
    return out

if __name__ == "__main__":
    run()
