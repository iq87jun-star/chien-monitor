# -*- coding: utf-8 -*-
"""
colab_v4share_dukascopy.py — v4配分(30/15/0%)のDukascopy最終判定【ユーザーColab用・docs/136-137】。

目的: Yahoo土俵で合格した「v4削減」を、v4が正しく測れる実データで最終判定する。
      Yahooはv4を系統的に過小評価するため(docs/137 §2)、この確認なしに配分変更しない。

使い方(Colab): 「ランタイム」→「すべて実行」→ Driveマウント許可。
  FXはDrive dukascopy_data_h1/{PAIR}_h1.csv(または _d)を日足化。指数/金もDriveにあれば使用、
  無ければYahoo補完(出所を⚠付きで明示=v4以外の品質は両変種共通なので比較は成立)。
  終了後、最後の「### 判定」ブロックとJSON(Drive保存)をClaude Codeセッションへ貼り付け。

判定規則(docs/137 §2・固定): 中央3ヶ月校正で失格%(楽観・悲観)がともに基準(v4 30%)より
  改善した変種のみ採用。改善なし → v4 30%維持。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
DIRS = [f"{DRIVE_BASE}/dukascopy_data_d", f"{DRIVE_BASE}/dukascopy_data_h1",
        f"{DRIVE_BASE}/multiasset_daily"]
OUT_JSON = f"{DRIVE_BASE}/v4share_dukascopy_check.json"

V4P = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
V7_2 = ["EURJPY", "GBPJPY"]
EMON = ["US500", "NAS100", "GER40"]
E5_2 = ["XAUUSD", "NAS100"]
YH = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X",
      "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X", "NZDUSD": "NZDUSD=X", "EURJPY": "EURJPY=X",
      "GBPJPY": "GBPJPY=X", "US500": "%5EGSPC", "NAS100": "%5EIXIC", "GER40": "%5EGDAXI", "XAUUSD": "GC=F"}
W0, W1 = "2016-01-01", "2025-12-31"
SEED, N_SEARCH, N_FINAL, MAXM = 7, 4000, 20000, 36
TARGET, FLOOR_OPT, DAY_FN, FLOOR_RAW = 0.08, -0.08, -0.05, -0.08

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
    if (out.index[1] - out.index[0]) < pd.Timedelta(hours=23):
        g = out.resample("1D")
        out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                            "low": g["low"].min(), "close": g["close"].last()}).dropna()
    return out


def _yahoo_daily(name):
    import urllib.request
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{YH[name]}?interval=1d&period1=1420070400&period2=1767225599"
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
    if not full_hist:
        df = df[(df.index >= W0) & (df.index <= W1)]
    else:
        df = df[df.index <= W1]
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
    out_parts = {}
    for nm in assets:
        s = daily(nm, full_hist=True)["close"].pct_change().dropna()
        mkey = pd.PeriodIndex(s.index, freq="M")
        out_parts[nm] = pd.Series(s.values * pw[nm].reindex(mkey).values, index=s.index)
    out = pd.DataFrame(out_parts).sum(axis=1, skipna=True)
    firsts = pd.Series(out.index, index=out.index).groupby(pd.PeriodIndex(out.index, freq="M")).min()
    out.loc[out.index.isin(firsts.values)] -= 5e-4
    out = out.dropna()
    return out[(out.index >= W0) & (out.index <= W1)]


def month_arrays(d):
    mk = pd.PeriodIndex(d.index, freq="M")
    return [np.asarray(d[mk == m].values, float) for m in mk.unique()]


def month_stats_at(arrs, mult):
    out = []
    for a in arrs:
        d = a * mult
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


def calibrate_median3(arrs, rng):
    best = best_m = None
    for mult in np.arange(0.4, 4.01, 0.2):
        st = simulate(month_stats_at(arrs, mult), N_SEARCH, rng)
        if not np.isnan(st["median_months"]) and st["median_months"] <= 3.0:
            best_m = mult; break
    if best_m is None: return None
    for mult in np.arange(max(0.4, best_m - 0.2), best_m + 0.201, 0.05):
        st = simulate(month_stats_at(arrs, mult), N_SEARCH, rng)
        d = abs((st["median_months"] or 99) - 3.0)
        if best is None or d < best[0] or (d == best[0] and mult < best[1]):
            best = (d, mult)
    return round(best[1], 2)


print("スリーブ構築(v4はDukascopy必須・他はDrive優先/Yahoo補完可)")
sleeves = dict(v4=pd.concat([v4_one(p) for p in V4P], axis=1).fillna(0.0).sum(axis=1),
               v7=mon_sleeve(V7_2), EMon=mon_sleeve(EMON, 3e-4), E5=e5_sleeve(E5_2))
print("出所:", SRC)
if any("yahoo" in SRC.get(p, "") for p in V4P):
    print("⚠ v4ペアにYahoo補完あり=判定の信頼性低下。Dukascopyデータを揃えて再実行推奨")

idx = sorted(set().union(*[set(s.index) for s in sleeves.values()]))
idx = [t for t in idx if pd.Timestamp(W0) <= t <= pd.Timestamp(W1)]
out = {}
for x in (0.30, 0.15, 0.0):
    k = (1.0 - x) / 0.70
    w = {"v4": x, "v7": .25 * k, "EMon": .25 * k, "E5": .20 * k}
    comp = pd.Series([sum(w[s] * float(sleeves[s].get(t, 0.0)) for s in sleeves) for t in idx],
                     index=pd.DatetimeIndex(idx))
    arrs = month_arrays(comp)
    mult = calibrate_median3(arrs, np.random.default_rng(SEED))
    if mult is None:
        out[f"v4_{int(x*100)}pct"] = dict(note="校正不可"); continue
    st = simulate(month_stats_at(arrs, mult), N_FINAL, np.random.default_rng(SEED))
    out[f"v4_{int(x*100)}pct"] = dict(mult=mult, **st)
    print(f"  v4={int(x*100)}%: mult={mult} {st}")

b = out["v4_30pct"]
winners = [k for k in ("v4_15pct", "v4_0pct") if "mult" in out[k]
           and out[k]["fail_pct_optimistic"] < b["fail_pct_optimistic"]
           and out[k]["fail_pct_raw"] < b["fail_pct_raw"]]
verdict = (f"{min(winners, key=lambda k: out[k]['fail_pct_optimistic'])} 採用(デモへ)" if winners
           else "v4 30%維持(削減は実データで改善せず)")
print(f"\n### 判定: {verdict}")
print(json.dumps(out, ensure_ascii=False, indent=1))
try:
    with open(OUT_JSON, "w") as f:
        json.dump(dict(sources=SRC, variants=out, verdict=verdict), f, ensure_ascii=False, indent=1)
    print("保存:", OUT_JSON)
except Exception as e:
    print("JSON保存不可(印字を転記してください):", e)
