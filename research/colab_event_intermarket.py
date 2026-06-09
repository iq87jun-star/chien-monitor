# -*- coding: utf-8 -*-
"""
colab_event_intermarket.py — 第3並走ポート「未トライ土俵」新エッジ探索を Drive/Colab で確定する自己完結版。

research/event_intermarket_edge_10y.py を 1本に統合し、Colab で「すべて実行」すれば下記を出す:
  (1) マクロ・イベント・ドリフト(pre/post FOMC・pre/post NFP)× 指数4 × L/S
      + インターマーケット先行遅行(gold→AUD / oil→CAD / dxy→EUR / spx→JP225 / spx→GER40) × L/S
      + 低ボラ・レジーム × 指数4   を 事前登録 N で Bonferroni・順列・年次ブロックp・IS/OOS・JK・コスト感応で採点。
  (2) ★既存4成分すべて(v7 円月曜 / E-Mon 指数月曜 / E5 多資産TSMOM / v4 FX日足合議)との月次相関。
      = 第3の器(口座C)が 既存A(v7+v4+E5)・並走B(E-Mon+E5) の"両方"と低相関かを判定。
  (3) pre-FOMC 指数バスケット(E-Mon流の多ショット採点)。

使い方(Colab): そのまま「すべて実行」。
  - USE_DRIVE=True なら Drive の多資産日足/Dukascopyを優先。無ければ Yahoo 日足10年を自動取得(研究用・概算)。
  - ★FOMC日は定例会合のみ(下記表)。本番前に Fed 公式カレンダーで要照合。
規律: 数字は盛らない。出なければ「出ない」と書く。Yahoo日足は配当除く・OHLC概算・bps単純化。確定はデモ前進検証(docs/29)。
"""
import os, json, time, datetime as dt, urllib.request, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

USE_DRIVE = True
DRIVE_BASE = "/content/drive/MyDrive/forex_ml"
DAILY_DIR = "{base}/multiasset_daily"      # あれば優先(配当込/CFD近似が望ましい)
LOCAL_DIR = "./research/data"
CACHE_DIR = "./_im_cache"

YAHOO = {
    "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI", "JP225": "^N225",
    "XAUUSD": "GC=F", "WTI": "CL=F", "DXY": "DX-Y.NYB",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X", "NZDUSD": "NZDUSD=X",
    "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X", "USDJPY": "USDJPY=X",
}
COST_BPS = {"US500": 3.0, "NAS100": 3.0, "GER40": 3.0, "JP225": 4.0, "XAUUSD": 4.0, "WTI": 6.0, "DXY": 3.0}
DEFAULT_COST_BPS = 4.0
INDICES = ["US500", "NAS100", "GER40", "JP225"]
EMON_BASKET = ["NAS100", "US500", "GER40"]
E5_BASKET = ["XAUUSD", "US500", "NAS100", "GER40"]
YEN = ["EURJPY", "GBPJPY", "USDJPY"]
V4_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]

FOMC_DATES = [
    "2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15", "2016-07-27", "2016-09-21", "2016-11-02", "2016-12-14",
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26", "2017-09-20", "2017-11-01", "2017-12-13",
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01", "2018-09-26", "2018-11-08", "2018-12-19",
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31", "2019-09-18", "2019-10-30", "2019-12-11",
    "2020-01-29", "2020-03-18", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
]


# ---------------- データ取得(Drive優先 → ローカル → Yahoo) ----------------
def _yahoo(sym, tries=6):
    u = f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=10y"
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=25).read())
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            rows = []
            for i, t in enumerate(ts):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                if None in (o, h, l, c):
                    continue
                rows.append((dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
            return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])
        except Exception as e:
            last = e; time.sleep(2 ** k)
    raise last


def _read_csv(path):
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    ren = {}
    for need in ["timestamp", "open", "high", "low", "close"]:
        for c in df.columns:
            if c.lower().startswith(need[:4]) or c.lower() == need:
                ren[c] = need; break
    return df.rename(columns=ren)


def get_raw(name):
    """name の生OHLC DataFrame(timestamp/open/high/low/close)を返す。"""
    if USE_DRIVE:
        for d in [DAILY_DIR.format(base=DRIVE_BASE)]:
            for fn in [f"{name}_d.csv", f"{name}.csv"]:
                p = os.path.join(d, fn)
                if os.path.exists(p):
                    return _read_csv(p)
    p = os.path.join(LOCAL_DIR, f"{name}_d.csv")
    if os.path.exists(p):
        return _read_csv(p)
    os.makedirs(CACHE_DIR, exist_ok=True)
    cp = os.path.join(CACHE_DIR, f"{name}_d.csv")
    if os.path.exists(cp):
        return _read_csv(cp)
    if name not in YAHOO:
        return None
    try:
        df = _yahoo(YAHOO[name]); df.to_csv(cp, index=False)
        time.sleep(2.0); return df
    except Exception as e:
        print(f"  [取得失敗] {name}: {type(e).__name__} {str(e)[:60]}")
        return None


_CACHE = {}


def load_daily(name, crypto=False):
    if name in _CACHE:
        return _CACHE[name]
    raw = get_raw(name)
    if raw is None:
        _CACHE[name] = None; return None
    df = raw.copy()
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek
    if not crypto:
        df = df[df["weekday"] <= 4]
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
    df["c2c"] = df["close"].pct_change()
    _CACHE[name] = df
    return df


def have(name):
    return load_daily(name) is not None


def pip_size(p):
    return 0.01 if p.endswith("JPY") else 0.0001


# ---------------- 統計(リポジトリ統一) ----------------
def perm_p(rets, n_iter=4000, seed=7):
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


def yearly_returns(r):
    s = pd.Series(r).dropna()
    if len(s) == 0:
        return pd.Series(dtype=float)
    return (1 + s).groupby(pd.to_datetime(s.index).year).prod() - 1.0


def yearly_block_p(r, n_iter=20000, seed=11):
    y = yearly_returns(r).values
    if len(y) < 3:
        return 1.0, len(y)
    rng = np.random.default_rng(seed); real = y.sum(); a = np.abs(y)
    null = np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(n_iter)])
    return float((null >= real).mean()), len(y)


# ---------------- 既存4成分 月次プロキシ ----------------
def v7_monthly_ref():
    acc = None
    for p in YEN:
        if not have(p):
            continue
        df = load_daily(p)
        m = to_monthly((df[df["weekday"] == 0]["o2o"] - 2 * pip_size(p) / df[df["weekday"] == 0]["open"]).dropna())
        acc = m if acc is None else acc.add(m, fill_value=0.0)
    return None if acc is None else (acc / 3.0).rename("v7")


def emon_monthly_ref():
    parts = []
    for nm in EMON_BASKET:
        if not have(nm):
            continue
        df = load_daily(nm); c = COST_BPS.get(nm, DEFAULT_COST_BPS) / 1e4
        parts.append((df[df["weekday"] == 0]["o2o"] - c).rename(nm))
    if not parts:
        return None
    w = pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()
    return to_monthly(w).rename("emon")


def e5_monthly_ref():
    closes = {}
    for nm in E5_BASKET:
        if not have(nm):
            continue
        df = load_daily(nm); s = df["close"].copy(); s.index = pd.to_datetime(df.index)
        closes[nm] = s.resample("ME").last()
    if not closes:
        return None
    px = pd.DataFrame(closes).dropna(); ret = px.pct_change()
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12):
        sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    pos = np.sign(sig).shift(1)
    out = ((pos * ret).mean(axis=1) - 5e-4).dropna(); out.index = out.index.to_period("M")
    return out.rename("e5")


def _rsi(c, n=14):
    d = np.diff(c, prepend=c[0]); up = np.clip(d, 0, None); dn = np.clip(-d, 0, None)
    au = np.empty_like(c); ad = np.empty_like(c); au[0] = up[0]; ad[0] = dn[0]; a = 1.0 / n
    for i in range(1, len(c)):
        au[i] = a * up[i] + (1 - a) * au[i - 1]; ad[i] = a * dn[i] + (1 - a) * ad[i - 1]
    rs = au / np.where(ad == 0, 1e-12, ad); return 100 - 100 / (1 + rs)


def _atr(h, l, c, n=14):
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.empty_like(tr); out[0] = tr[0]; a = 1.0 / n
    for i in range(1, len(tr)):
        out[i] = a * tr[i] + (1 - a) * out[i - 1]
    return out


def v4_monthly_ref():
    monthly = {}
    for p in V4_PAIRS:
        if not have(p):
            continue
        df = load_daily(p)
        o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
        idx = df.index; n = len(c)
        if n < 40:
            continue
        rsi = _rsi(c, 14); atr = _atr(h, l, c, 14); bbwin = 20; cost = 2 * pip_size(p); i = bbwin + 2
        while i < n - 1:
            win = c[i - bbwin:i]; mean = win.mean(); sd = win.std(ddof=1)
            zz = (c[i] - mean) / sd if sd > 0 else 0.0
            down = 0
            for k in range(0, 12):
                if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]:
                    down += 1
                else:
                    break
            up = 0
            for k in range(0, 12):
                if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]:
                    up += 1
                else:
                    break
            ret = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0.0; mv = 0.005
            buy = int(rsi[i] < 35) + int(zz < -1.5) + int(down >= 3) + int(ret < -mv)
            sell = int(rsi[i] > 65) + int(zz > 1.5) + int(up >= 3) + int(ret > mv)
            sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
            if sig == 0:
                i += 1; continue
            entry = o[i + 1]; sld = 1.5 * atr[i]; tpd = 1.2 * sld
            if sld <= 0:
                i += 1; continue
            sl = entry - sig * sld; tp = entry + sig * tpd; exit_px = None; j = i + 1; held = 0
            while j < n and held < 8:
                hi = h[j]; lo = l[j]
                if sig > 0:
                    if lo <= sl:
                        exit_px = sl; break
                    if hi >= tp:
                        exit_px = tp; break
                else:
                    if hi >= sl:
                        exit_px = sl; break
                    if lo <= tp:
                        exit_px = tp; break
                j += 1; held += 1
            if exit_px is None:
                exit_px = c[min(j, n - 1)]
            r = sig * (exit_px / entry - 1.0) - cost / entry
            mkey = pd.Period(idx[min(j, n - 1)], freq="M")
            monthly[mkey] = monthly.get(mkey, 0.0) + r
            i = max(i + 1, j)
    if not monthly:
        return None
    return pd.Series(monthly).sort_index().rename("v4")


# ---------------- イベント日解決 ----------------
def _index_trade_dates():
    df = load_daily("US500")
    return list(df.index) if df is not None else []


def event_prevday_dates(event_dates, td_index, lag=1):
    import bisect
    norm = [pd.Timestamp(d, tz="UTC").floor("D") for d in event_dates]
    out = []
    for ev in norm:
        pos = bisect.bisect_left(td_index, ev)
        if 0 <= pos - lag < len(td_index):
            out.append(td_index[pos - lag])
    return out


def event_sameday_dates(event_dates, td_index):
    import bisect
    norm = [pd.Timestamp(d, tz="UTC").floor("D") for d in event_dates]
    out = []
    for ev in norm:
        pos = bisect.bisect_left(td_index, ev)
        if pos < len(td_index):
            out.append(td_index[pos])
    return out


def nfp_dates(td_index):
    years = sorted(set(d.year for d in td_index))
    out = []
    for y in years:
        for m in range(1, 13):
            d = dt.date(y, m, 1); offset = (4 - d.weekday()) % 7
            out.append(f"{y}-{m:02d}-{d.day + offset:02d}")
    return out


def _cost(name, cost_bps=None):
    return (COST_BPS.get(name, DEFAULT_COST_BPS) if cost_bps is None else cost_bps) / 1e4


# ---------------- 候補シリーズ ----------------
def eventdrift_series(name, entry_dates, direction=+1, cost_bps=None):
    df = load_daily(name)
    if df is None:
        return pd.Series(dtype=float)
    sub = df[df.index.isin(set(pd.DatetimeIndex(entry_dates)))]
    return (direction * sub["o2o"] - _cost(name, cost_bps)).dropna()


def eventdrift_basket(names, entry_dates, direction=+1, cost_bps=None):
    acc = None; k = 0
    for nm in names:
        if not have(nm):
            continue
        r = eventdrift_series(nm, entry_dates, direction, cost_bps)
        acc = r if acc is None else acc.add(r, fill_value=0.0); k += 1
    return (acc / max(k, 1)).dropna() if acc is not None else pd.Series(dtype=float)


def leadlag_series(lead, follow, direction=+1, invert_signal=False, cost_bps=None):
    if not (have(lead) and have(follow)):
        return pd.Series(dtype=float)
    dl = load_daily(lead); dfo = load_daily(follow)
    sig = np.sign(dl["c2c"].shift(1))
    if invert_signal:
        sig = -sig
    j = pd.concat([sig.rename("s"), dfo["o2o"].rename("r")], axis=1).dropna()
    j = j[j["s"] != 0]
    return (direction * j["s"] * j["r"] - _cost(follow, cost_bps)).dropna()


def volregime_series(name, lo_q=0.33, cost_bps=None):
    if not have(name):
        return pd.Series(dtype=float)
    df = load_daily(name); vol = df["c2c"].rolling(20).std(); thr = vol.quantile(lo_q)
    sub = df[(vol.shift(1) <= thr).fillna(False)]
    return (sub["o2o"] - _cost(name, cost_bps)).dropna()


def build_candidates(td_index):
    fomc_prev1 = event_prevday_dates(FOMC_DATES, td_index, 1)
    fomc_prev2 = event_prevday_dates(FOMC_DATES, td_index, 2)
    fomc_same = event_sameday_dates(FOMC_DATES, td_index)
    nfp = nfp_dates(td_index)
    nfp_prev1 = event_prevday_dates(nfp, td_index, 1)
    nfp_same = event_sameday_dates(nfp, td_index)
    cands = []
    event_specs = [("PreFOMC1", "G_preFOMC", fomc_prev1), ("PreFOMC2", "G_preFOMC", fomc_prev2),
                   ("PostFOMC", "G_postFOMC", fomc_same), ("PreNFP", "G_preNFP", nfp_prev1),
                   ("PostNFP", "G_postNFP", nfp_same)]
    for nm in INDICES:
        for ev_tag, fam, dates in event_specs:
            for d in (+1, -1):
                tag = "L" if d > 0 else "S"
                cands.append((f"{nm}_{ev_tag}_{tag}", fam,
                              (lambda n=nm, dts=dates, dd=d: (lambda c=None: eventdrift_series(n, dts, dd, c)))()))
    leadlag_specs = [("L1_gold2AUD", "XAUUSD", "AUDUSD", False), ("L2_oil2CAD", "WTI", "USDCAD", True),
                     ("L3_dxy2EUR", "DXY", "EURUSD", True), ("L4_spx2JP", "US500", "JP225", False),
                     ("L5_spx2GER", "US500", "GER40", False)]
    for lbl, lead, follow, inv in leadlag_specs:
        for d in (+1, -1):
            tag = "L" if d > 0 else "S"
            cands.append((f"{lbl}_{tag}", "L_leadlag",
                          (lambda le=lead, fo=follow, iv=inv, dd=d: (lambda c=None: leadlag_series(le, fo, dd, iv, c)))()))
    for nm in INDICES:
        cands.append((f"{nm}_VolRegimeLo_L", "L_volregime",
                      (lambda n=nm: (lambda c=None: volregime_series(n, 0.33, c)))()))
    return cands


def run():
    td_index = _index_trade_dates()
    if not td_index:
        raise SystemExit("US500 日足が取得できませんでした。Drive配置 or ネットワークを確認してください。")
    refs = {}
    for k, fn in [("v7", v7_monthly_ref), ("emon", emon_monthly_ref), ("e5", e5_monthly_ref), ("v4", v4_monthly_ref)]:
        ref = fn()
        if ref is not None:
            refs[k] = ref
    cands = [(l, f, g) for (l, f, g) in build_candidates(td_index) if len(g()) >= 60]
    n_tests = len(cands); alpha = 0.05 / max(n_tests, 1)
    rows = []; GEN = {}
    for lbl, fam, gen in cands:
        GEN[lbl] = gen; r = gen()
        p = perm_p(r.values); st = stats(r.values); cm = to_monthly(r); cc = {}
        for k, ref in refs.items():
            j = pd.concat([cm.rename("c"), ref.rename("r")], axis=1).dropna()
            cc[f"corr_{k}"] = round(float(j["c"].corr(j["r"])), 2) if len(j) > 24 else None
        rows.append(dict(label=lbl, family=fam, **st, perm_p=round(p, 4), **cc))
    df = pd.DataFrame(rows).sort_values("perm_p").reset_index(drop=True)
    sig = df[df.perm_p <= 0.05].copy(); surv = sig[sig.perm_p <= alpha].copy()

    def _ok(v):
        return v is None or (isinstance(v, float) and np.isnan(v)) or abs(v) <= 0.3

    def uncorr(row):
        return all(_ok(row.get(f"corr_{k}")) for k in refs.keys())

    targets = pd.concat([surv, sig[sig.apply(uncorr, axis=1)]]).drop_duplicates("label")
    detail = {}
    for _, row in targets.iterrows():
        lbl = row["label"]; r = GEN[lbl]()
        half = r.index[len(r) // 2]
        is_ = stats(r[r.index < half].values); oos = stats(r[r.index >= half].values)
        oos_p = perm_p(r[r.index >= half].values)
        yrs = sorted(set(pd.to_datetime(r.index).year))
        jk = {int(y): round(perm_p(r[pd.to_datetime(r.index).year != y].values), 3) for y in yrs}
        base_c = COST_BPS.get(lbl.split("_")[0], DEFAULT_COST_BPS)
        cost = {f"{m}x": stats(GEN[lbl](base_c * m).values)["net_pct"] for m in (1, 2, 3)}
        yb_p, yb_n = yearly_block_p(r); yr = yearly_returns(r)
        detail[lbl] = dict(
            full={k: row.get(k) for k in ("net_pct", "win_pct", "maxDD_pct", "n", "perm_p",
                                          "corr_v7", "corr_emon", "corr_e5", "corr_v4")},
            bonferroni_survivor=bool(row["perm_p"] <= alpha),
            yearly_block_p=round(yb_p, 4), yearly_n=int(yb_n),
            yearly_pos_pct=round(float((yr > 0).mean()) * 100, 0) if len(yr) else None,
            IS=is_, oos=dict(**oos, perm_p=round(oos_p, 4)),
            jackknife_max_p=round(max(jk.values()), 3) if jk else None, cost_net=cost)
    fomc_prev1 = event_prevday_dates(FOMC_DATES, td_index, 1)
    fomc_prev2 = event_prevday_dates(FOMC_DATES, td_index, 2)
    baskets = {"EFOMC(US500+NAS100+GER40 preFOMC1 L)": eventdrift_basket(["US500", "NAS100", "GER40"], fomc_prev1, +1),
               "EFOMC2(US500+NAS100+GER40 preFOMC2 L)": eventdrift_basket(["US500", "NAS100", "GER40"], fomc_prev2, +1)}
    basket_out = {}
    for bname, br in baskets.items():
        if len(br) < 10:
            continue
        yb_p, yb_n = yearly_block_p(br); yr = yearly_returns(br); bm = to_monthly(br); cc = {}
        for k, ref in refs.items():
            j = pd.concat([bm.rename("c"), ref.rename("r")], axis=1).dropna()
            cc[f"corr_{k}"] = round(float(j["c"].corr(j["r"])), 2) if len(j) > 8 else None
        basket_out[bname] = dict(**stats(br.values), daily_perm_p=round(perm_p(br.values), 4),
                                 yearly_block_p=round(yb_p, 4), yearly_n=int(yb_n),
                                 yearly_pos_pct=round(float((yr > 0).mean()) * 100, 0),
                                 yearly_mean_pct=round(float(yr.mean()) * 100, 2),
                                 yearly_min_pct=round(float(yr.min()) * 100, 2), **cc)
    return df, sig, surv, dict(n_tests=n_tests, alpha_bonf=round(alpha, 6), refs_available=list(refs.keys()),
                               sig_count=int(len(sig)), bonferroni_survivors=int(len(surv)),
                               span=[str(td_index[0]), str(td_index[-1])],
                               all_significant=sig.to_dict("records"), detail=detail, baskets=basket_out)


if __name__ == "__main__":
    if USE_DRIVE:
        try:
            from google.colab import drive
            drive.mount("/content/drive")
        except Exception:
            print("[info] Colab Drive 未マウント(ローカル/Yahooで継続)")
    pd.set_option("display.width", 240); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
    df, sig, surv, out = run()
    print(f"基準成分 = {out['refs_available']} / span={out['span']}")
    print(f"N = {out['n_tests']}   Bonferroni α = {out['alpha_bonf']}")
    print(f"\n===== 順列 p<=0.05 ({len(sig)}/{out['n_tests']}) =====")
    print(sig.to_string() if len(sig) else "  なし")
    print(f"\n===== ★Bonferroni 生存: {len(surv)}件 =====")
    print(surv.to_string() if len(surv) else "  なし")
    print("\n===== 追検対象(生存 + 既存4成分すべてと無相関)の二次ハーネス =====")
    for k, d in out["detail"].items():
        f, o, i = d["full"], d["oos"], d["IS"]
        flag = "★BONF生存" if d["bonferroni_survivor"] else ""
        print(f"\n[{k}] {flag} 純益{f['net_pct']}% 勝率{f['win_pct']}% DD{f['maxDD_pct']}% n={f['n']} 日次p={f['perm_p']}")
        print(f"   相関 v7={f.get('corr_v7')} Emon={f.get('corr_emon')} E5={f.get('corr_e5')} v4={f.get('corr_v4')}")
        print(f"   ★年次ブロックp={d['yearly_block_p']}(年数{d['yearly_n']},陽性年{d['yearly_pos_pct']}%) | "
              f"IS{i['net_pct']}%/OOS{o['net_pct']}% p={o['perm_p']} | JKmax={d['jackknife_max_p']} | コスト{d['cost_net']}")
    print("\n===== pre-FOMC 指数バスケット =====")
    for bname, b in out["baskets"].items():
        print(f"\n[{bname}] 純益{b['net_pct']}% 勝率{b['win_pct']}% DD{b['maxDD_pct']}% n={b['n']}")
        print(f"   日次p={b['daily_perm_p']} ★年次p={b['yearly_block_p']}(年{b['yearly_n']},陽性{b['yearly_pos_pct']}%,"
              f"平均{b['yearly_mean_pct']}%,最悪{b['yearly_min_pct']}%) 相関 v7={b.get('corr_v7')} Emon={b.get('corr_emon')} E5={b.get('corr_e5')} v4={b.get('corr_v4')}")
    os.makedirs("./_im_out", exist_ok=True)
    with open("./_im_out/event_intermarket_edge_10y.json", "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: ./_im_out/event_intermarket_edge_10y.json")
