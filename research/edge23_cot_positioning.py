# -*- coding: utf-8 -*-
"""
edge23_cot_positioning.py — docs/127 §1 の実行(W1: COTポジショニング宇宙・初検定)。
  C1: JPY投機筋ネット/OIの156週百分位 ≤10%→翌週LONG JPY / ≥90%→SHORT JPY(週次・5営業日保有)
  C2: C1と同ルールを6通貨(JPY/EUR/GBP/CHF/AUD/CAD)等ウェイト
  C3: v7(円3クロス月曜LONG)を「投機筋が円ネットショートの週」に限定するフィルタ
ルール・ゲート・αは docs/127 で固定済み。チューニング禁止。
出力: results/edge23_cot_positioning.json(入力SHA-256付き) → docs/128 へ転記。
"""
import os, sys, json, csv, glob, hashlib, urllib.request, urllib.parse, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
COT_DIR = os.path.join(DATA, "cot")
sys.path.insert(0, HERE)

ALPHA = 0.01 / 3                     # docs/127 §1-1
MAIN = ("2016-01-01", "2026-06-30")
PRE = ("1998-01-01", "2015-12-31")   # 実データ開始が遅い場合は実測窓を記録
IS_END, OOS_START = "2020-12-31", "2021-01-01"
PCTL_WIN, PCTL_MIN = 156, 100
LO, HI = 10.0, 90.0

# CFTC契約コード(docs/127 §0固定)
COT_CODE = {"JPY": "097741", "EUR": "099741", "GBP": "096742",
            "CHF": "092741", "AUD": "232741", "CAD": "090741"}
# 通貨→取引ペアと「その通貨ロング」の符号
PAIR_OF = {"JPY": ("USDJPY", -1), "EUR": ("EURUSD", +1), "GBP": ("GBPUSD", +1),
           "CHF": ("USDCHF", -1), "AUD": ("AUDUSD", +1), "CAD": ("USDCAD", -1)}
YAHOO = {"USDJPY": "USDJPY=X", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X",
         "USDCHF": "USDCHF=X", "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X",
         "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
         "US500": "%5EGSPC", "NAS100": "%5EIXIC", "GER40": "%5EGDAXI", "XAUUSD": "GC=F"}
P1, P2 = 788918400, 1782863999       # 1995-01-01 .. 2026-06-30


def fetch(name, sym):
    u = (f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?interval=1d&period1={P1}&period2={P2}")
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=60).read())
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


def ensure_data():
    os.makedirs(DATA, exist_ok=True)
    for name, sym in YAHOO.items():
        if sym is None:
            continue
        p = os.path.join(DATA, f"{name}_d.csv")
        if not os.path.exists(p):
            n = fetch(name, sym)
            print(f"  fetch {name}: {n} rows")


def load_cot():
    """legacy futures-only 全年 → {cur: DataFrame(asof, net_oi)}"""
    rows = []
    for path in sorted(glob.glob(os.path.join(COT_DIR, "deacot*.txt"))):
        with open(path, "r", errors="replace") as f:
            rdr = csv.reader(f)
            header = next(rdr)
            for r in rdr:
                if len(r) < 10:
                    continue
                code = r[3].strip()
                if code not in COT_CODE.values():
                    continue
                try:
                    oi = float(r[7]); nl = float(r[8]); ns = float(r[9])
                except ValueError:
                    continue
                if oi <= 0:
                    continue
                rows.append((r[2].strip(), code, (nl - ns) / oi))
    df = pd.DataFrame(rows, columns=["asof", "code", "net_oi"])
    df["asof"] = pd.to_datetime(df["asof"])
    out = {}
    for cur, code in COT_CODE.items():
        s = (df[df["code"] == code].groupby("asof")["net_oi"].mean()
             .sort_index())
        out[cur] = s
    return out


def load_daily(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df = df[df.index.dayofweek <= 4]
    return df


def weekly_open_returns(pair):
    """月曜open→翌月曜open のリターン。index=当該月曜。月曜欠損週は火曜開始で代替しない(週を落とす)。"""
    df = load_daily(pair)
    opens = df["open"]
    mondays = opens[opens.index.dayofweek == 0]
    idx = mondays.index
    rets = {}
    for i in range(len(idx) - 1):
        d0, d1 = idx[i], idx[i + 1]
        if 5 <= (d1 - d0).days <= 9:                 # 祝日で8-9日となる週まで許容
            rets[d0] = float(mondays.iloc[i + 1] / mondays.iloc[i] - 1.0)
    return pd.Series(rets).sort_index()


def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001


def weekly_cost(pair):
    """往復2pip(docs/14系)を代表価格で率換算。"""
    df = load_daily(pair)
    return float(2 * pip_size(pair) / df["open"].median())


def signal_weeks(cot_s):
    """as-of火曜のレポート → 有効になる『翌週月曜』の日付にマップし、百分位を返す。
    公表は金曜15:30 ET(as-of+3日)なので as-of+6日の月曜から有効 = look-ahead なし。"""
    pct = cot_s.rolling(PCTL_WIN, min_periods=PCTL_MIN).apply(
        lambda w: (w[:-1] <= w[-1]).mean() * 100.0 if len(w) > 1 else np.nan, raw=True)
    eff = {}
    for asof, v in pct.items():
        if np.isnan(v):
            continue
        mon = asof + pd.Timedelta(days=(7 - asof.dayofweek) % 7)
        if mon == asof:
            mon += pd.Timedelta(days=7)
        # as-of火曜(dayofweek=1)→翌月曜= +6日。火曜以外のas-of(祝日ずれ)も翌週月曜に丸める
        eff[mon] = v
    return pd.Series(eff).sort_index()


def clip(s, a, b):
    return s[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]


def metrics(r):
    r = r.dropna()
    act = r[r != 0]
    eq = (1 + r).cumprod()
    peak = eq.cummax(); dd = (eq / peak - 1).min() if len(eq) else 0.0
    ann = r.mean() * 52
    vol = r.std() * np.sqrt(52)
    return dict(net=round(float(eq.iloc[-1] - 1) * 100, 2) if len(eq) else 0.0,
                maxdd=round(float(dd) * 100, 2),
                sharpe=round(float(ann / vol), 2) if vol > 0 else 0.0,
                n_weeks=int(len(r)), n_active=int(len(act)),
                winrate=round(float((act > 0).mean()) * 100, 1) if len(act) else 0.0)


def perm_p(r, n=4000, seed=7):
    """符号シャッフル順列検定(edge_search系と同一): アクティブ週の符号をランダム反転。"""
    r = r.dropna()
    rng = np.random.default_rng(seed)
    actual = float(r.sum())
    av = r[r != 0].values
    if len(av) == 0:
        return 1.0
    cnt = 0
    for _ in range(n):
        s = (av * rng.choice([-1, 1], size=len(av))).sum()
        if s >= actual:
            cnt += 1
    return round((cnt + 1) / (n + 1), 5)


def jackknife(r):
    yrs = sorted(set(r.index.year))
    outs = {}
    for y in yrs:
        outs[int(y)] = round(float(r[r.index.year != y].sum()) * 100, 2)
    pos = sum(1 for v in outs.values() if v > 0)
    return outs, pos, len(yrs)


def run_c(currencies, window, cost_mult=1.0):
    """C1(1通貨)/C2(6通貨)の合成週次リターンと素材を返す。"""
    legs = {}
    for cur in currencies:
        pair, sgn = PAIR_OF[cur]
        wret = weekly_open_returns(pair)
        cost = weekly_cost(pair) * cost_mult
        pct = signal_weeks(COT[cur])
        aligned = pct.reindex(wret.index).ffill(limit=1)
        pos = pd.Series(0.0, index=wret.index)
        pos[aligned <= LO] = +1.0
        pos[aligned >= HI] = -1.0
        legs[cur] = (wret, pos, sgn, cost)
    idx = sorted(set().union(*[set(l[0].index) for l in legs.values()]))
    total = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for cur, (wret, pos, sgn, cost) in legs.items():
        rr = (pos * wret * sgn - (pos != 0) * cost).reindex(total.index).fillna(0.0)
        total = total + rr / len(legs)
    return clip(total, *window), legs


def v7_weekly():
    """v7週次PnL(3クロス月曜LONG o2o・往復2pip)。index=月曜。"""
    acc = None
    for p in ["EURJPY", "GBPJPY", "USDJPY"]:
        df = load_daily(p)
        df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
        mon = df[df.index.dayofweek == 0]
        r = (mon["o2o"] - 2 * pip_size(p) / mon["open"]).dropna()
        acc = r if acc is None else acc.add(r, fill_value=0.0)
    return (acc / 3.0).sort_index()


def main():
    global COT
    t0 = dt.datetime.now(dt.timezone.utc).isoformat()
    print("[1/6] データ準備(Yahoo日足+COT32年)")
    ensure_data()
    COT = load_cot()
    for cur, s in COT.items():
        print(f"  COT {cur}: {len(s)}週 {s.index.min().date()}..{s.index.max().date()}")

    R = {"meta": dict(started=t0, alpha=ALPHA, spec="docs/127 §1",
                      cot_weeks={c: int(len(s)) for c, s in COT.items()})}

    # ---------- C1 / C2 ----------
    for cid, curs in (("C1", ["JPY"]), ("C2", list(PAIR_OF))):
        print(f"[2/6] {cid} 本窓")
        r_main, legs = run_c(curs, MAIN)
        m = metrics(r_main)
        p = perm_p(r_main)
        jk, jk_pos, jk_n = jackknife(r_main)
        r_2x, _ = run_c(curs, MAIN, cost_mult=2.0)
        m2 = metrics(r_2x)
        r_is = clip(r_main, MAIN[0], IS_END); r_oos = clip(r_main, OOS_START, MAIN[1])
        pre, _ = run_c(curs, PRE)
        mpre = metrics(pre); ppre = perm_p(pre)
        # プラセボ
        actual = float(r_main.sum())
        rng = np.random.default_rng(11)
        nets = []
        for _ in range(500):
            net = 0.0
            for cur in legs:
                wret, pos, sgn, cost = legs[cur]
                w = clip(wret, *MAIN); po = pos.reindex(w.index).fillna(0.0).values.copy()
                rng.shuffle(po)
                net += float((po * w.values * sgn - (po != 0) * cost).sum()) / len(legs)
            nets.append(net)
        nets = np.asarray(nets)
        plc_p95 = round(float(np.quantile(nets, 0.95)) * 100, 2)
        plc_p = round(float((nets >= actual).mean()), 4)
        gates = dict(
            G1_econ=m["net"] > 0,
            G2_perm=p < ALPHA,
            G3_jk=(jk_pos / jk_n) >= 0.9,
            G4_placebo=m["net"] > plc_p95,
            G5_cost2x=m2["net"] > 0,
            G6_isoos=(float(r_is.sum()) > 0 and float(r_oos.sum()) > 0),
        )
        R[cid] = dict(main=m, perm_p=p, jackknife=jk, jk_pass=f"{jk_pos}/{jk_n}",
                      cost2x=m2, is_net=round(float(r_is.sum()) * 100, 2),
                      oos_net=round(float(r_oos.sum()) * 100, 2),
                      placebo_p95=plc_p95, placebo_p=plc_p,
                      pre2016=dict(**mpre, perm_p=ppre,
                                   window=[str(pre.index.min().date()) if len(pre) else None,
                                           str(pre.index.max().date()) if len(pre) else None]),
                      gates=gates, gates_passed=sum(gates.values()),
                      verdict="ADOPT候補(G8確認へ)" if all(gates.values()) else "REJECT")
        print(f"  {cid}: net={m['net']}% p={p} 有効={m['n_active']}週 "
              f"ゲート{sum(gates.values())}/6 → {R[cid]['verdict']}")

    # ---------- C3 ----------
    print("[3/6] C3 v7×COT機序")
    v7w = v7_weekly()
    # 直近公表済みレポートの生net/OI(百分位でなく符号・docs/127 C3)
    eff_net = {}
    for asof, v in COT["JPY"].items():
        mon = asof + pd.Timedelta(days=(7 - asof.dayofweek) % 7)
        if mon == asof:
            mon += pd.Timedelta(days=7)
        eff_net[mon] = v
    eff_net = pd.Series(eff_net).sort_index()
    al = eff_net.reindex(v7w.index).ffill(limit=1)
    v7m = clip(v7w, *MAIN); alm = al.reindex(v7m.index)
    short_w = v7m[alm < 0]; long_w = v7m[alm >= 0]
    unfiltered = float(v7m.sum())
    filtered = float(short_w.sum())
    # 分割差の順列検定: ラベルシャッフル
    rng = np.random.default_rng(23)
    obs = short_w.mean() - long_w.mean()
    lab = alm.dropna(); vv = v7m.reindex(lab.index).values; ls = (lab < 0).values.copy()
    cnt = 0
    for _ in range(4000):
        rng.shuffle(ls)
        d = vv[ls].mean() - vv[~ls].mean()
        if d >= obs:
            cnt += 1
    c3_p = round((cnt + 1) / 4001, 5)
    c3 = dict(n_short_weeks=int(len(short_w)), n_long_weeks=int(len(long_w)),
              v7_unfiltered_net=round(unfiltered * 100, 2),
              v7_filtered_net=round(filtered * 100, 2),
              mean_bps_shortweeks=round(float(short_w.mean()) * 1e4, 1),
              mean_bps_longweeks=round(float(long_w.mean()) * 1e4, 1),
              split_perm_p=c3_p,
              gates=dict(filter_improves=filtered > unfiltered, split_p=c3_p < ALPHA))
    c3["verdict"] = ("フィルタ採用候補" if all(c3["gates"].values())
                     else "REJECT(v7は素通し維持)")
    R["C3"] = c3
    print(f"  C3: 素通し={c3['v7_unfiltered_net']}% フィルタ={c3['v7_filtered_net']}% "
          f"p={c3_p} → {c3['verdict']}")

    # ---------- G8 相関(ADOPT候補のみ必要だが常に記録) ----------
    print("[4/6] G8 既存エッジ相関")
    try:
        from parallel_vs_existing_compare import v7_monthly, v4_monthly, e5_monthly, emon_monthly
        sleeves = dict(v4=v4_monthly(), v7=v7_monthly(), EMon=emon_monthly(), E5=e5_monthly())
        for cid in ("C1", "C2"):
            r_main, _ = run_c(["JPY"] if cid == "C1" else list(PAIR_OF), MAIN)
            cm = r_main.copy(); cm.index = cm.index.to_period("M"); cm = cm.groupby(level=0).sum()
            cc = {}
            for k, s in sleeves.items():
                j = pd.concat([cm.rename("c"), s.rename("s")], axis=1).dropna()
                cc[k] = round(float(j["c"].corr(j["s"])), 3) if len(j) > 12 else None
            R[cid]["G8_corr"] = cc
            R[cid]["gates"]["G8"] = all(v is None or abs(v) < 0.4 for v in cc.values())
        print("  corr:", {c: R[c]["G8_corr"] for c in ("C1", "C2")})
    except Exception as e:
        print("  G8 skip:", e)

    # ---------- 入力ハッシュ ----------
    print("[5/6] 入力SHA-256")
    hashes = {}
    for f in sorted(glob.glob(os.path.join(COT_DIR, "deacot*.txt")))[:40]:
        hashes[os.path.basename(f)] = hashlib.sha256(open(f, "rb").read()).hexdigest()[:16]
    for n in YAHOO:
        p = os.path.join(DATA, f"{n}_d.csv")
        if os.path.exists(p):
            hashes[f"{n}_d.csv"] = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    R["input_sha256"] = hashes

    out = os.path.join(HERE, "results", "edge23_cot_positioning.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(R, open(out, "w"), indent=1, ensure_ascii=False, default=str)
    print("[6/6] saved:", out)


if __name__ == "__main__":
    main()
