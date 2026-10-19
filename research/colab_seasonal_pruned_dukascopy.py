# -*- coding: utf-8 -*-
"""
colab_seasonal_pruned_dukascopy.py — 季節R4+G3 間引きB案のDukascopy最終確認【ユーザーColab用・docs/140 §3】。

比較(全て中央3ヶ月校正・日次ブロックMC 2万パス・FN P1+8%):
  現行  = 配備中WR4テーブル + 現行スリーブ(v7 3クロス/E5 4資産)
  A     = 配備中WR4テーブル + 間引きスリーブ(参考)
  B     = 再導出テーブル(docs/140 §2の固定値) + 間引きスリーブ ← 判定対象
判定規則(docs/140 §3・固定): Bの失格%(楽観・悲観とも)が現行以下 → 合格(EA v1.40へ)。
  それ以外 → 見送り(現行テーブル維持)。

使い方(Colab): 「ランタイム」→「すべて実行」→ Driveマウント許可。
  FX/指数/金はDrive(dukascopy_data_h1等)優先・無い銘柄はYahoo補完(⚠表示。全変種共通なので
  相対比較は成立するが、v4ペアがYahoo補完の場合は信頼性低下と表示する)。
  終了後、「### 判定」ブロックとJSON(Drive保存)をClaude Codeセッションへ貼り付け。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
DIRS = [f"{DRIVE_BASE}/dukascopy_data_d", f"{DRIVE_BASE}/dukascopy_data_h1",
        f"{DRIVE_BASE}/multiasset_daily"]
OUT_JSON = f"{DRIVE_BASE}/seasonal_pruned_dukascopy_check.json"

V4P = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
YEN3, YEN2 = ["EURJPY", "GBPJPY", "USDJPY"], ["EURJPY", "GBPJPY"]
V7X = ["AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]
EMON, EMONX = ["US500", "NAS100", "GER40"], ["JP225", "UK100", "FR40"]
E5_4, E5_2 = ["XAUUSD", "US500", "NAS100", "GER40"], ["XAUUSD", "NAS100"]
SJUL = ["US500", "NAS100"]
YH = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X",
      "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X", "NZDUSD": "NZDUSD=X", "EURJPY": "EURJPY=X",
      "GBPJPY": "GBPJPY=X", "AUDJPY": "AUDJPY=X", "NZDJPY": "NZDJPY=X", "CADJPY": "CADJPY=X",
      "CHFJPY": "CHFJPY=X", "US500": "%5EGSPC", "NAS100": "%5EIXIC", "GER40": "%5EGDAXI",
      "JP225": "%5EN225", "UK100": "%5EFTSE", "FR40": "%5EFCHI", "XAUUSD": "GC=F"}
W0, W1 = "2016-01-01", "2026-06-30"
SEED, N_SEARCH, N_FINAL, MAXM = 7, 4000, 20000, 36
TARGET, FLOOR_OPT, DAY_FN, FLOOR_RAW = 0.08, -0.08, -0.05, -0.08

# 配備中WR4(EA v1.30焼き込み・docs/110)
WR4 = {1: {"EMon": .689, "SJul": .311}, 2: {"v4": 1.0},
       3: {"v4": .38, "E5": .217, "EMon": .403}, 4: {"EMon": .773, "SJul": .227},
       5: {"v4": .092, "EMon": .084, "EMonX": .114, "v7x": .270, "v7": .279, "SJul": .162},
       6: {"v4": .25, "E5": .332, "EMon": .173, "SJul": .245}, 7: {"SJul": 1.0},
       8: {"v4": .331, "E5": .328, "EMon": .206, "SJul": .135}, 9: {"v4": .483, "EMon": .517},
       10: {"EMon": .379, "EMonX": .437, "SJul": .184}, 11: {"EMonX": .181, "SJul": .819},
       12: {"v4": .406, "E5": .594}}
# B案テーブル(docs/140 §2・間引きスリーブ前提で再導出した固定値)
WR4B = {1: {"EMon": .689, "SJul": .311}, 2: {"v4": 1.0},
        3: {"v4": .247, "v7": .368, "EMon": .262, "E5": .123}, 4: {"EMon": .773, "SJul": .227},
        5: {"v4": .093, "v7": .27, "v7x": .274, "EMon": .085, "EMonX": .115, "SJul": .163},
        6: {"v4": .235, "EMon": .162, "E5": .373, "SJul": .23}, 7: {"E5": .257, "SJul": .743},
        8: {"v4": .318, "EMon": .198, "E5": .356, "SJul": .129},
        9: {"v4": .396, "EMon": .424, "E5": .18}, 10: {"EMon": .379, "EMonX": .437, "SJul": .184},
        11: {"EMonX": .151, "E5": .17, "SJul": .679}, 12: {"v4": .314, "E5": .686}}
FOMC = [
 "2016-01-27","2016-03-16","2016-04-27","2016-06-15","2016-07-27","2016-09-21","2016-11-02","2016-12-14",
 "2017-02-01","2017-03-15","2017-05-03","2017-06-14","2017-07-26","2017-09-20","2017-11-01","2017-12-13",
 "2018-01-31","2018-03-21","2018-05-02","2018-06-13","2018-08-01","2018-09-26","2018-11-08","2018-12-19",
 "2019-01-30","2019-03-20","2019-05-01","2019-06-19","2019-07-31","2019-09-18","2019-10-30","2019-12-11",
 "2020-01-29","2020-04-29","2020-06-10","2020-07-29","2020-09-16","2020-11-05","2020-12-16",
 "2021-01-27","2021-03-17","2021-04-28","2021-06-16","2021-07-28","2021-09-22","2021-11-03","2021-12-15",
 "2022-01-26","2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14",
 "2023-02-01","2023-03-22","2023-05-03","2023-06-14","2023-07-26","2023-09-20","2023-11-01","2023-12-13",
 "2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31","2024-09-18","2024-11-07","2024-12-18",
 "2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10",
 "2026-01-28","2026-03-18","2026-04-29"]

try:
    if not os.path.exists("/content/drive/MyDrive"):
        from google.colab import drive; drive.mount("/content/drive", force_remount=False)
except Exception as e:
    print("Drive不可:", e)


def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001


def _read(path):
    df = pd.read_csv(path); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time", "timestamp", "date", "datetime", "gmt time"] if c in df.columns), df.columns[0])
    df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t").set_index("t")
    def col(*n):
        for x in n:
            for c in df.columns:
                if c.lower() == x: return c
        return None
    o, h, l, c = col("open", "bidopen", "o"), col("high", "bidhigh", "h"), col("low", "bidlow", "l"), col("close", "bidclose", "c")
    if None in (o, h, l, c): return None
    out = df[[o, h, l, c]].astype(float).rename(columns={o: "open", h: "high", l: "low", c: "close"})
    if len(out) > 1 and (out.index[1] - out.index[0]) < pd.Timedelta(hours=23):
        g = out.resample("1D")
        out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                            "low": g["low"].min(), "close": g["close"].last()}).dropna()
    return out


def _yahoo_daily(name):
    import urllib.request
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{YH[name]}?interval=1d&period1=1420070400&period2=1782863999"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=25).read())
    r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
    idx = (pd.to_datetime(ts, unit="s", utc=True) + pd.Timedelta(hours=2)).floor("D")
    df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close")}, index=idx).dropna()
    return df.groupby(df.index).last()


SRC = {}
_CACHE = {}
def daily(name, full_hist=False):
    key = (name, full_hist)
    if key in _CACHE: return _CACHE[key]
    df = None
    for d_ in DIRS:
        for suf in ("_d", "_h1"):
            p = f"{d_}/{name}{suf}.csv"
            if os.path.exists(p):
                df = _read(p); SRC[name] = os.path.basename(d_) + suf
                break
        if df is not None: break
    if df is None:
        df = _yahoo_daily(name); SRC[name] = "yahoo(補完⚠)"
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    df = df[df.index <= W1]
    if not full_hist:
        df = df[df.index >= W0]
    df = df[df.index.dayofweek <= 4]
    df["weekday"] = df.index.dayofweek
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
    _CACHE[key] = df
    return df


def rsi_w(c, n=14):
    d = np.diff(c, prepend=c[0]); up = np.clip(d, 0, None); dn = np.clip(-d, 0, None)
    au = np.empty_like(c); ad = np.empty_like(c); au[0] = up[0]; ad[0] = dn[0]; a = 1 / n
    for i in range(1, len(c)):
        au[i] = a * up[i] + (1 - a) * au[i - 1]; ad[i] = a * dn[i] + (1 - a) * ad[i - 1]
    return 100 - 100 / (1 + au / np.where(ad == 0, 1e-12, ad))


def atr_d(hh, ll, cc, n=14):
    pc = np.roll(cc, 1); pc[0] = cc[0]
    tr = np.maximum(hh - ll, np.maximum(np.abs(hh - pc), np.abs(ll - pc)))
    o = np.empty_like(tr); o[0] = tr[0]; a = 1 / n
    for i in range(1, len(tr)):
        o[i] = a * tr[i] + (1 - a) * o[i - 1]
    return o


def v4_one(p):
    df = daily(p)
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
    return pd.Series(acc).sort_index()


def mon_sleeve(names, idx_cost=None):
    parts = []
    for nm in names:
        df = daily(nm)
        cost = (idx_cost if idx_cost is not None else 2 * pip_size(nm) / df["open"])
        parts.append((df[df["weekday"] == 0]["o2o"] - cost).rename(nm))
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()


def cc_sleeve(names):
    parts = [daily(nm)["close"].pct_change().rename(nm) for nm in names]
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()


def e5_sleeve(assets):
    closes = {}
    for nm in assets:
        s = daily(nm, full_hist=True)["close"]
        closes[nm] = s.resample("ME").last()
    px = pd.DataFrame(closes).dropna(); ret = px.pct_change()
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12):
        sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    pos = np.sign(sig).shift(1)
    vol = ret.rolling(12).std().shift(1)
    w = (1 / vol).div((1 / vol).sum(axis=1), axis=0)
    pw = (pos * w); pw.index = pw.index.to_period("M")
    parts = {}
    for nm in assets:
        s = daily(nm, full_hist=True)["close"].pct_change().dropna()
        mkey = pd.PeriodIndex(s.index, freq="M")
        parts[nm] = pd.Series(s.values * pw[nm].reindex(mkey).values, index=s.index)
    out = pd.DataFrame(parts).sum(axis=1, skipna=True)
    firsts = pd.Series(out.index, index=out.index).groupby(pd.PeriodIndex(out.index, freq="M")).min()
    out.loc[out.index.isin(firsts.values)] -= 5e-4
    out = out.dropna()
    return out[(out.index >= W0) & (out.index <= W1)]


def g3_overlay(event_risk=0.01):
    df = daily("US500")
    c = df["close"].values
    atr = atr_d(df["high"].values, df["low"].values, c)
    dates = pd.DatetimeIndex(df.index); out = {}
    for d_ in FOMC:
        T = pd.Timestamp(d_)
        pos = dates.searchsorted(T)
        if pos < 2 or pos >= len(dates): continue
        i1, i2 = pos - 1, pos - 2
        af = atr[i2] / c[i2]
        noty = min(event_risk / max(af, 1e-4), 1.5)
        out[dates[i1]] = noty * (c[i1] / c[i2] - 1.0) - 1e-4
    return pd.Series(out).sort_index()


def composite(sleeves, wmap):
    idx = sorted(set().union(*[set(s.index) for s in sleeves.values()]))
    idx = [t for t in idx if pd.Timestamp(W0) <= t <= pd.Timestamp(W1)]
    vals = [sum(wmap[t.month].get(k, 0.0) * float(sleeves[k].get(t, 0.0)) for k in sleeves) for t in idx]
    return pd.Series(vals, index=pd.DatetimeIndex(idx))


def month_arrays(d):
    mk = pd.PeriodIndex(d.index, freq="M")
    return [np.asarray(d[mk == m].values, float) for m in mk.unique()], list(mk.unique())


def month_stats_at(arrs, mult, g3a):
    out = []
    for i, a in enumerate(arrs):
        d = a * mult
        if g3a is not None: d = d + g3a[i]
        dc = np.maximum(d, -0.04)
        eq = np.cumprod(1 + dc)
        out.append(dict(ret=eq[-1] - 1, trough=eq.min() - 1, peak=eq.max() - 1,
                        raw_min_day=d.min(), raw_trough=np.cumprod(1 + d).min() - 1))
    return out


def simulate(ms, n_paths, rng):
    n = len(ms); pass_m = []; fail_o = fail_r = undone = 0
    for _ in range(n_paths):
        e = 1.0; failed_o = failed_r = done = False
        for t in range(1, MAXM + 1):
            s = ms[rng.integers(0, n)]
            if not failed_r and (s["raw_min_day"] <= DAY_FN or e * (1 + s["raw_trough"]) <= 1 + FLOOR_RAW):
                failed_r = True
            if e * (1 + s["trough"]) <= 1 + FLOOR_OPT:
                failed_o = True; done = True
            elif e * (1 + s["peak"]) >= 1 + TARGET:
                pass_m.append(t); done = True
            e *= (1 + s["ret"])
            if done: break
        if failed_o: fail_o += 1
        if failed_r: fail_r += 1
        if not done: undone += 1
    med = float(np.median(pass_m)) if pass_m else np.nan
    return dict(median_months=med, pass_pct=round(100 * len(pass_m) / n_paths, 1),
                fail_pct_optimistic=round(100 * fail_o / n_paths, 1),
                fail_pct_raw=round(100 * fail_r / n_paths, 1),
                undone_pct=round(100 * undone / n_paths, 1))


def calibrate_median3(arrs, g3a, rng):
    best = best_m = None
    for mult in np.arange(0.4, 4.01, 0.2):
        st = simulate(month_stats_at(arrs, mult, g3a), N_SEARCH, rng)
        if not np.isnan(st["median_months"]) and st["median_months"] <= 3.0:
            best_m = mult; break
    if best_m is None: return None
    for mult in np.arange(max(0.4, best_m - 0.2), best_m + 0.201, 0.05):
        st = simulate(month_stats_at(arrs, mult, g3a), N_SEARCH, rng)
        d = abs((st["median_months"] or 99) - 3.0)
        if best is None or d < best[0] or (d == best[0] and mult < best[1]):
            best = (d, mult)
    return round(best[1], 2)


print("スリーブ構築(Drive優先・Yahoo補完は⚠表示)")
common = dict(v4=pd.concat([v4_one(p) for p in V4P], axis=1).fillna(0.0).sum(axis=1),
              v7x=mon_sleeve(V7X), EMon=mon_sleeve(EMON, 3e-4), EMonX=mon_sleeve(EMONX, 3e-4),
              SJul=cc_sleeve(SJUL))
sl_cur = dict(common); sl_cur["v7"] = mon_sleeve(YEN3); sl_cur["E5"] = e5_sleeve(E5_4)
sl_prn = dict(common); sl_prn["v7"] = mon_sleeve(YEN2); sl_prn["E5"] = e5_sleeve(E5_2)
g3 = g3_overlay()
print("出所:", SRC)
if any("yahoo" in SRC.get(p, "") for p in V4P):
    print("⚠ v4ペアにYahoo補完あり=判定の信頼性低下")

out = {}
for name, sl, wmap in [("現行R4+G3", sl_cur, WR4), ("A_テーブル据置+間引き", sl_prn, WR4),
                        ("B_再導出+間引き", sl_prn, WR4B)]:
    base = composite(sl, wmap)
    arrs, months = month_arrays(base)
    g3s = g3.reindex(base.index).fillna(0.0)
    mk = pd.PeriodIndex(base.index, freq="M")
    g3a = [np.asarray(g3s[mk == m].values, float) for m in months]
    mult = calibrate_median3(arrs, g3a, np.random.default_rng(SEED))
    if mult is None:
        out[name] = dict(note="校正不可"); print(f"  {name}: 校正不可"); continue
    st = simulate(month_stats_at(arrs, mult, g3a), N_FINAL, np.random.default_rng(SEED))
    out[name] = dict(mult=mult, **st)
    print(f"  {name}: mult={mult} {st}")

b0, bB = out.get("現行R4+G3", {}), out.get("B_再導出+間引き", {})
ok = ("mult" in b0 and "mult" in bB
      and bB["fail_pct_optimistic"] <= b0["fail_pct_optimistic"]
      and bB["fail_pct_raw"] <= b0["fail_pct_raw"])
verdict = "B合格(EA v1.40テーブル差替+デモへ)" if ok else "見送り(現行テーブル維持)"
print(f"\n### 判定: {verdict}")
print(json.dumps(out, ensure_ascii=False, indent=1))
try:
    with open(OUT_JSON, "w") as f:
        json.dump(dict(sources=SRC, variants=out, verdict=verdict), f, ensure_ascii=False, indent=1)
    print("保存:", OUT_JSON)
except Exception as e:
    print("JSON保存不可(印字を転記してください):", e)
