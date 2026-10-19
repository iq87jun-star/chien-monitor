# -*- coding: utf-8 -*-
"""
colab_prune_dukascopy_check.py — 銘柄間引き(docs/131-132)のDukascopy最終確認【ユーザーColab用】。

目的: Yahoo日足LOYOで合格した H24a(v4 9→6: EURUSD/GBPUSD/USDJPY除外)と
      H24b(v7 3→2: USDJPY除外)を、実10年Dukascopyデータで再確認する。
      docs/132 §3-1 のとおり「Yahooの銘柄別ノイズで間引くのは危険」への最終関門。

使い方(Colab):
  1. Driveをマウントできる環境で本ファイルを実行(「すべて実行」)。
  2. DRIVE_BASE/dukascopy_data_h1/{PAIR}_h1.csv(10年・UTC)を自動で日足化して使用。
     日足 {PAIR}_d.csv が dukascopy_data_d にあればそちらを優先。無いペアはYahooで補完し出所を明示。
  3. 印字の「### 判定」ブロックとJSON(Drive保存)をそのまま結果docに転記。

判定規則(docs/131の趣旨をDukascopyに適用・固定):
  d1: 間引き後バスケットの月次Sharpe(2016-2025) > フル
  d2: 除外銘柄がDukascopyの銘柄別Sharpeでも下位に一致
      (v4: 除外3ペアが下位4以内 / v7: USDJPYが最下位)
  両方成立 → 合格(プリセット差替+デモへ)。不成立 → 間引き見送り(Yahoo固有ノイズと判定)。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
H1_DIR = f"{DRIVE_BASE}/dukascopy_data_h1"
D_DIR = f"{DRIVE_BASE}/dukascopy_data_d"
OUT_JSON = f"{DRIVE_BASE}/prune_dukascopy_check.json"

V4P = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
YEN = ["EURJPY", "GBPJPY", "USDJPY"]
V4_DROP = ["EURUSD", "GBPUSD", "USDJPY"]   # docs/132 固定セット
V7_DROP = ["USDJPY"]
W0, W1 = "2016-01-01", "2025-12-31"

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
    return df[[o, h, l, c]].astype(float).rename(columns={o: "open", h: "high", l: "low", c: "close"})


def _yahoo_daily(pair):
    import urllib.request
    sym = pair + "=X"
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&period1=1451606400&period2=1767225599"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=25).read())
    r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
    idx = (pd.to_datetime(ts, unit="s", utc=True) + pd.Timedelta(hours=2)).floor("D")
    df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close")}, index=idx).dropna()
    return df.groupby(df.index).last()


SRC = {}
def daily(pair):
    p_d = f"{D_DIR}/{pair}_d.csv"; p_h1 = f"{H1_DIR}/{pair}_h1.csv"
    if os.path.exists(p_d):
        df = _read(p_d); SRC[pair] = "dukascopy_d"
    elif os.path.exists(p_h1):
        h1 = _read(p_h1)
        g = h1.resample("1D")
        df = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                           "low": g["low"].min(), "close": g["close"].last()}).dropna()
        SRC[pair] = "dukascopy_h1→D"
    else:
        df = _yahoo_daily(pair); SRC[pair] = "yahoo(補完⚠)"
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    df = df[(df.index >= W0) & (df.index <= W1)]
    df = df[df.index.dayofweek <= 4]
    df["weekday"] = df.index.dayofweek
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
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


def v7_one(p):
    df = daily(p)
    cost = 2 * pip_size(p) / df["open"]
    return (df[df["weekday"] == 0]["o2o"] - cost).dropna()


def monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({m: float((1 + s[mk == m]).prod() - 1) for m in mk.unique()}).sort_index()


def sharpe_m(m):
    m = m.dropna()
    return round(float(m.mean() / m.std() * np.sqrt(12)), 2) if len(m) > 12 and m.std() > 0 else 0.0


def net_pct(m): return round((float((1 + m).prod()) - 1) * 100, 1)


def check(name, symbols, drop, builder, how):
    per = {s: builder(s) for s in symbols}
    D = pd.DataFrame(per).fillna(0.0)
    def comp(keep):
        return D[list(keep)].sum(axis=1) if how == "sum" else D[list(keep)].mean(axis=1)
    full_m = monthly(comp(symbols))
    pr_m = monthly(comp([s for s in symbols if s not in drop]))
    per_sh = {s: sharpe_m(monthly(per[s])) for s in symbols}
    order = sorted(per_sh, key=per_sh.get)
    d1 = bool(sharpe_m(pr_m) > sharpe_m(full_m))
    if name == "v4":
        d2 = bool(all(s in order[:4] for s in drop))
    else:
        d2 = bool(order[0] == drop[0])
    res = dict(per_symbol_sharpe=per_sh, sources={s: SRC.get(s) for s in symbols},
               full=dict(sharpe=sharpe_m(full_m), net=net_pct(full_m)),
               pruned=dict(sharpe=sharpe_m(pr_m), net=net_pct(pr_m)),
               drop=drop, d1_sharpe=d1, d2_rank=d2,
               verdict="合格(プリセット差替+デモへ)" if (d1 and d2) else "見送り(Yahooノイズと判定)")
    print(f"\n### 判定 {name}: {res['verdict']}")
    print(f"  full Sh {res['full']['sharpe']}/net {res['full']['net']}% → 間引き Sh {res['pruned']['sharpe']}/net {res['pruned']['net']}%")
    print(f"  銘柄別Sh: {per_sh}")
    print(f"  出所: {res['sources']}")
    return res


out = dict(H24a_v4=check("v4", V4P, V4_DROP, v4_one, "sum"),
           H24b_v7=check("v7", YEN, V7_DROP, v7_one, "mean"))
try:
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("\n保存:", OUT_JSON)
except Exception as e:
    print("JSON保存不可(印字を転記してください):", e)
