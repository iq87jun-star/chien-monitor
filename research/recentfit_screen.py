# -*- coding: utf-8 -*-
"""
recentfit_screen.py — 【直近特化トラック】直近12/6ヶ月だけで伸びているセルを事前固定ルールで選抜。

ユーザー方針(2026-07-30):「過去1年(極論半年)だけ伸びているEAを、正攻法(10年検証・LOYO)とは
別トラックとして作る。本番口座到達で元が取れる非対称ペイオフに張る」。
docs/165(月別1位スクリーニング=LOYO崩壊で閉鎖)とは別系統であることに注意 —
本トラックは「LOYOで実力が出ない事は承知の上で、直近レジーム継続に有償の宝くじとして張る」
明示的なEVベットであり、耐久エッジの主張はしない(docs/174に設計・停止規則を事前登録)。

方法(全て実行前に固定・後知恵の再選抜はしない):
  1) データ: Yahoo日足 2016-01-01..2026-07-29(凍結窓)。FX13+指数6+金+暗号2。
  2) セル分解: Mon(月曜o2o 単銘柄) / Hold(連続保有 単銘柄) / TSMOM(月次E5型 単銘柄) /
     v4(日足k≥4合議 単ペア) — 全て既存スリーブ(docs/139系)と同一の構築式・同一コスト。
  3) 選抜ルール(固定): 直近12ヶ月スコア s=mean/std*sqrt(n)(活動日ベース)降順。
     フィルタ: 活動日≥15 / 12ヶ月累積>0 / 6ヶ月累積>0(=「直近も伸びている」)。
     Top-4。制約: 同一銘柄1セルまで・同一ファミリー2セルまで。加重: 逆ボラ(12m)・上限40%。
  4) 倍率校正(直近窓のみ): 0.8×max{m: 最悪単日×m≥−4% かつ 月中DD×m≥−8%}。速攻変種=1.5倍。
  5) MC: FN Stellar P1(+8%)→P2(+5%)。5日ブロックブートストラップ。
     直近12ヶ月サンプル(=レジーム継続の楽観)と全期間サンプル(=正直な悲観バウンド)を併記。
出力: results/recentfit_screen.json → docs/175
⚠ Yahoo日足近似。本トラックの数字は構造的に楽観(直近窓で選び直近窓で測る)。盛らずに両バウンド併記。
"""
import os, sys, json, time, csv, hashlib
import urllib.request
import datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

SEED = 7
N_MC = 10000
P1_TARGET, P2_TARGET = 0.08, 0.05
MAX_DD, DAY_GUARD = 0.10, 0.04          # 静的10% / EA balance基準−4%ガード(v1.44系)
# 凍結窓(再現性のため実行日基準を廃止)
P1_EPOCH, P2_EPOCH = 1451606400, 1785369599     # 2016-01-01 .. 2026-07-29 23:59:59 UTC
W_ALL0, W_ALL1 = pd.Timestamp("2016-01-01"), pd.Timestamp("2026-07-29")
W12_0 = pd.Timestamp("2025-08-01")               # 直近12ヶ月窓
W6_0 = pd.Timestamp("2026-02-01")                # 直近6ヶ月窓

YAHOO = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X",
    "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X", "NZDUSD": "NZDUSD=X",
    "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X", "AUDJPY": "AUDJPY=X", "NZDJPY": "NZDJPY=X",
    "CADJPY": "CADJPY=X", "CHFJPY": "CHFJPY=X",
    "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI",
    "JP225": "^N225", "UK100": "^FTSE", "FR40": "^FCHI",
    "XAUUSD": "GC=F", "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD",
}
CRYPTO = {"BTCUSD", "ETHUSD"}
IDX_COST = {"US500": 3e-4, "NAS100": 3e-4, "GER40": 3e-4, "UK100": 4e-4, "JP225": 4e-4,
            "FR40": 4e-4, "XAUUSD": 3e-4, "BTCUSD": 10e-4, "ETHUSD": 15e-4}
MON_FX = ["EURJPY", "GBPJPY", "USDJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]
MON_IDX = ["NAS100", "US500", "GER40", "JP225", "UK100", "FR40"]
HOLD_SYMS = ["US500", "NAS100", "GER40", "JP225", "XAUUSD", "BTCUSD"]
TSMOM_SYMS = ["XAUUSD", "US500", "NAS100", "GER40", "BTCUSD", "ETHUSD"]
V4_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
E5B = ["XAUUSD", "US500", "NAS100", "GER40"]

TOP_K = 4
MAX_PER_FAMILY = 2
W_CAP = 0.40
MIN_ACTIVE_12M = 15


# ---------------- データ ----------------
def fetch(name):
    path = os.path.join(DATA, f"{name}_rf.csv")
    if os.path.exists(path):
        return path
    sym = urllib.request.quote(YAHOO[name], safe="=-")
    u = (f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?interval=1d&period1={P1_EPOCH}&period2={P2_EPOCH}")
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=25).read())
    r = d["chart"]["result"][0]
    ts = r["timestamp"]; q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None)
                     .strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["timestamp", "open", "high", "low", "close"]); w.writerows(rows)
    time.sleep(0.6)
    return path


def load_daily(name):
    df = pd.read_csv(fetch(name))
    df["t"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek
    if name not in CRYPTO:
        df = df[df["weekday"] <= 4]
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
    return df


def pip_size(p): return 0.01 if p.endswith("JPY") else 0.0001


def clip(s, a=None, b=None):
    """⚠2026-09-01修正: 旧実装は `a=W_ALL0, b=W_ALL1` と既定引数で受けていた。
    既定引数はモジュール定義時に一度だけ評価されるため、呼び出し側が
    `base.W_ALL1 = ...` で窓をロールしても**セル構築は旧窓のまま truncate されていた**。
    影響を受けたのは W_ALL1 を再代入する `recentfit_short_rescreen_202609.py`(docs/184)のみ
    (docs/174-182の各スクリプトは再代入していないため数値は不変)。詳細と再実行結果は docs/192。
    再代入しない呼び出しでは挙動は完全に同一である。"""
    a = W_ALL0 if a is None else a
    b = W_ALL1 if b is None else b
    s = pd.Series(np.asarray(s.values, float), index=pd.DatetimeIndex(s.index))
    return s[(s.index >= a) & (s.index <= b)].dropna()


# ---------------- セル構築(既存スリーブと同一式) ----------------
def mon_cell(nm):
    df = load_daily(nm)
    cost = IDX_COST.get(nm, None)
    c = (cost if cost is not None else 2 * pip_size(nm) / df["open"])
    return clip((df[df["weekday"] == 0]["o2o"] - c).dropna())


def hold_cell(nm):
    df = load_daily(nm)
    s = df["close"].pct_change().dropna()
    s = clip(s)
    firsts = pd.Series(s.index, index=s.index).groupby(pd.PeriodIndex(s.index, freq="M")).min()
    s.loc[s.index.isin(firsts.values)] -= 5e-4
    return s


def tsmom_cell(nm):
    df = load_daily(nm)
    px = df["close"].resample("ME").last().dropna()
    sig = sum(np.sign(px.pct_change(lb)) for lb in (1, 3, 6, 12))
    pos = np.sign(sig).shift(1)
    pos.index = pos.index.to_period("M")
    s = df["close"].pct_change().dropna()
    mkey = pd.PeriodIndex(pd.DatetimeIndex(s.index), freq="M")
    coef = pos.reindex(mkey).fillna(0.0).values
    out = pd.Series(s.values * coef, index=s.index)
    out = clip(out)
    firsts = pd.Series(out.index, index=out.index).groupby(pd.PeriodIndex(out.index, freq="M")).min()
    out.loc[out.index.isin(firsts.values)] -= 5e-4
    return out


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


def v4_cell(p):
    df = load_daily(p)
    o = df["open"].values; hh = df["high"].values; ll = df["low"].values; c = df["close"].values
    idx = df.index; n = len(c); rsi = rsi_w(c); atr = atr_d(hh, ll, c); bb = 20
    cost = 2 * pip_size(p); acc = {}; i = bb + 2
    while i < n - 1:
        win = c[i - bb:i]; mean = win.mean(); sd = win.std(ddof=1)
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
    return clip(pd.Series(acc).sort_index())


def e5_composite():
    closes = {}
    for nm in E5B:
        closes[nm] = load_daily(nm)["close"].resample("ME").last()
    px = pd.DataFrame(closes).dropna(); ret = px.pct_change()
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for lb in (1, 3, 6, 12):
        sig = sig.add(np.sign(px.pct_change(lb)), fill_value=0)
    pos = np.sign(sig).shift(1)
    vol = ret.rolling(12).std().shift(1)
    w = (1 / vol).div((1 / vol).sum(axis=1), axis=0)
    pw = (pos * w); pw.index = pw.index.to_period("M")
    daily = {}
    for nm in E5B:
        s = load_daily(nm)["close"].pct_change().dropna()
        mkey = pd.PeriodIndex(pd.DatetimeIndex(s.index), freq="M")
        coef = pw[nm].reindex(mkey).values
        daily[nm] = pd.Series(s.values * coef, index=s.index)
    out = pd.DataFrame(daily).sum(axis=1, skipna=True)
    firsts = pd.Series(out.index, index=out.index).groupby(pd.PeriodIndex(out.index, freq="M")).min()
    out.loc[out.index.isin(firsts.values)] -= 5e-4
    return clip(out.dropna())


# ---------------- 統計・選抜 ----------------
def win(s, a, b=None):
    # clip()と同じ既定引数の問題を回避(呼び出し時にモジュール値を読む)
    b = W_ALL1 if b is None else b
    return s[(s.index >= a) & (s.index <= b)]


def cell_stats(s):
    """活動日ベースの直近12/6ヶ月統計"""
    s12 = win(s, W12_0); s6 = win(s, W6_0)
    a12 = s12[s12 != 0.0]; a6 = s6[s6 != 0.0]
    n12 = int(len(a12))
    std = float(a12.std()) if n12 > 2 else float("nan")
    score = float(a12.mean() / std * np.sqrt(n12)) if (n12 > 2 and std > 0) else float("-inf")
    cum12 = float((1 + s12).prod() - 1); cum6 = float((1 + s6).prod() - 1)
    sall = s[s != 0.0]
    return dict(n_active_12m=n12, cum_12m=round(cum12 * 100, 2), cum_6m=round(cum6 * 100, 2),
                score_12m=round(score, 2) if np.isfinite(score) else None,
                std_active_12m=round(std * 100, 3) if np.isfinite(std) else None,
                worst_day_12m=round(float(s12.min()) * 100, 2) if len(s12) else None,
                cum_full=round(float((1 + sall).prod() - 1) * 100, 1))


def select_cells(table):
    """事前固定ルール: score降順→フィルタ→銘柄1・ファミリー2制約→Top4→逆ボラ加重(cap40%)
    注(2026-08-08レビュー): capは一回適用→再正規化のため、最終加重はcapを僅かに超え得る
    (例: 2026-08-06非FX選抜のHold_UK100=41.3%)。事前登録済み規則の事後変更を避けるため
    実装は変更しない。次回スクリーニングでcapを厳密化する場合はdocsに変更を事前登録すること。"""
    ok = [(k, v) for k, v in table.items()
          if v["stats"]["n_active_12m"] >= MIN_ACTIVE_12M
          and v["stats"]["cum_12m"] > 0 and v["stats"]["cum_6m"] > 0
          and v["stats"]["score_12m"] is not None]
    ok.sort(key=lambda kv: kv[1]["stats"]["score_12m"], reverse=True)
    picked, fam_ct, sym_used = [], {}, set()
    for k, v in ok:
        fam, sym = v["family"], v["symbol"]
        if sym in sym_used or fam_ct.get(fam, 0) >= MAX_PER_FAMILY:
            continue
        picked.append(k); sym_used.add(sym); fam_ct[fam] = fam_ct.get(fam, 0) + 1
        if len(picked) == TOP_K:
            break
    iv = {k: 1.0 / (table[k]["stats"]["std_active_12m"] / 100) for k in picked}
    tot = sum(iv.values())
    w = {k: iv[k] / tot for k in picked}
    over = {k: min(v, W_CAP) for k, v in w.items()}
    tot2 = sum(over.values())
    return {k: round(v / tot2, 3) for k, v in over.items()}


# ---------------- 校正・MC ----------------
def worst_stats(daily):
    wd = float(daily.min())
    mk = pd.PeriodIndex(daily.index, freq="M")
    wdd = 0.0
    for m in mk.unique():
        eq = (1 + daily[mk == m]).cumprod()
        wdd = min(wdd, float(((eq - eq.cummax()) / eq.cummax()).min()))
    return wd, wdd


def calibrate(base, day_cap=DAY_GUARD, floor_cap=0.08):
    best = 0.05
    for m in np.arange(0.05, 6.01, 0.05):
        wd, wdd = worst_stats(base * m)
        if wd >= -day_cap and wdd >= -floor_cap:
            best = m
        else:
            break
    return round(0.8 * best, 2)


def mc_challenge(daily, mult, rng, n=N_MC, block=5, max_days=250):
    """FN Stellar 2段階: P1+8%→P2+5% / 静的DD−10% / EAガードで日次−4%クリップ。
    5日ブロックブートストラップ。返り値: 到達率・失格率・所要日数分位。"""
    r = np.clip(np.asarray(daily.values, float) * mult, -DAY_GUARD, None)
    nb = len(r) - block + 1
    # v2026-08-08修正: 旧実装は max_days//block+2=52ブロック=260日分しか生成せず、
    # P2判定が意図(max_days*2=500日)の半分強で打ち切られていた(funded率が下振れ=保守側)。
    starts = rng.integers(0, nb, size=(n, (max_days * 2) // block + 1))
    paths = r[(starts[:, :, None] + np.arange(block)[None, None, :])].reshape(n, -1)[:, :max_days * 2]
    eq = np.cumprod(1 + paths, axis=1)
    p1_days = np.full(n, -1); p2_days = np.full(n, -1); failed = np.zeros(n, bool)
    for i in range(n):
        e = eq[i]; base_i = 1.0
        # P1
        hit = np.where(e / base_i - 1 >= P1_TARGET)[0]
        dq = np.where(e / base_i - 1 <= -MAX_DD)[0]
        if len(dq) and (not len(hit) or dq[0] < hit[0]):
            failed[i] = True; continue
        if not len(hit) or hit[0] >= max_days:
            continue
        p1_days[i] = hit[0] + 1
        # P2 (通過翌日から・基準リセット)
        b2 = e[hit[0]]
        e2 = e[hit[0] + 1:] / b2
        hit2 = np.where(e2 - 1 >= P2_TARGET)[0]
        dq2 = np.where(e2 - 1 <= -MAX_DD)[0]
        if len(dq2) and (not len(hit2) or dq2[0] < hit2[0]):
            failed[i] = True; continue
        if len(hit2) and hit2[0] + hit[0] + 1 < max_days * 2:
            p2_days[i] = p1_days[i] + hit2[0] + 1
    okP1 = p1_days > 0; okP2 = p2_days > 0
    def q(a, p): return int(np.percentile(a, p)) if len(a) else None
    return dict(p1_pass=round(float(okP1.mean()) * 100, 1),
                funded=round(float(okP2.mean()) * 100, 1),
                fail=round(float(failed.mean()) * 100, 1),
                p1_days_med=q(p1_days[okP1], 50), p1_days_p90=q(p1_days[okP1], 90),
                funded_days_med=q(p2_days[okP2], 50), funded_days_p90=q(p2_days[okP2], 90))


def sha256s():
    out = {}
    for f in sorted(os.listdir(DATA)):
        if f.endswith("_rf.csv"):
            with open(os.path.join(DATA, f), "rb") as fh:
                out[f.replace("_rf.csv", "")] = hashlib.sha256(fh.read()).hexdigest()[:16]
    return out


def series_pack(s):
    """月次リターン表(直近13ヶ月)"""
    mk = pd.PeriodIndex(s.index, freq="M")
    m = pd.Series({str(k): round(float((1 + s[mk == k]).prod() - 1) * 100, 2) for k in mk.unique()})
    return dict(list(m.sort_index().items())[-13:])


def main():
    rng = np.random.default_rng(SEED)
    print("[1/5] データ取得(凍結窓 2016-01-01..2026-07-29)")
    for nm in YAHOO:
        try:
            fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:60]}")
    print("  取得済:", len(sha256s()), "銘柄")

    print("[2/5] セル構築")
    cells = {}
    for nm in MON_FX + MON_IDX:
        cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=mon_cell(nm))
    for nm in HOLD_SYMS:
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=hold_cell(nm))
    for nm in TSMOM_SYMS:
        cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=tsmom_cell(nm))
    for p in V4_PAIRS:
        cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=v4_cell(p))

    print("[3/5] 直近統計とランキング")
    table = {}
    for k, v in cells.items():
        st = cell_stats(v["s"])
        table[k] = dict(family=v["family"], symbol=v["symbol"], stats=st)
    ranked = sorted([k for k in table if table[k]["stats"]["score_12m"] is not None],
                    key=lambda k: table[k]["stats"]["score_12m"], reverse=True)
    for k in ranked[:12]:
        print(f"  {k:16s} {table[k]['stats']}")

    weights = select_cells(table)
    print("  選抜:", weights)

    print("[4/5] 合成・校正・MC")
    idx = sorted(set().union(*[set(cells[k]["s"].index) for k in weights]))
    comp = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, w in weights.items():
        comp = comp.add(cells[k]["s"].reindex(comp.index).fillna(0.0) * w, fill_value=0.0)
    comp12 = win(comp, W12_0)
    mult_std = calibrate(comp12)
    mult_fast = round(mult_std * 1.5, 2)
    variants = {}
    for tag, mult in (("standard", mult_std), ("fast_1.5x", mult_fast)):
        mc_recent = mc_challenge(comp12, mult, np.random.default_rng(SEED))
        mc_full = mc_challenge(comp, mult, np.random.default_rng(SEED))
        s = comp12 * mult
        wd, wdd = worst_stats(s)
        variants[tag] = dict(
            mult=mult, recent12m=mc_recent, full_history=mc_full,
            recent_worst_day=round(wd * 100, 2), recent_worst_intramonth_dd=round(wdd * 100, 2),
            recent_monthly=series_pack(s))
        print(f"  {tag}: mult={mult} 直近={mc_recent} 全期間={mc_full}")

    # 参考: 現行(正攻法)構成の直近12ヶ月成績 — 同じ物差しで併記
    print("[5/5] 参考系列(現行スリーブの直近12ヶ月)")
    refs = {}
    ref_defs = {
        "v7(円月曜3)": lambda: sum(mon_cell(n) for n in ["EURJPY", "GBPJPY", "USDJPY"]) / 3,
        "EMon(指数月曜3)": lambda: sum(mon_cell(n) for n in ["NAS100", "US500", "GER40"]) / 3,
        "E5(4資産TSMOM)": e5_composite,
    }
    for name, fn in ref_defs.items():
        try:
            s = clip(fn())
            refs[name] = dict(cum_12m=round(float((1 + win(s, W12_0)).prod() - 1) * 100, 2),
                              cum_6m=round(float((1 + win(s, W6_0)).prod() - 1) * 100, 2))
            print(f"  {name}: {refs[name]}")
        except Exception as e:
            refs[name] = dict(error=f"{type(e).__name__}: {str(e)[:80]}")

    res = dict(
        meta=dict(
            purpose="直近特化トラック(docs/174)の事前固定スクリーニング。耐久エッジの主張はしない",
            window_all="2016-01-01..2026-07-29", window_12m=str(W12_0.date()),
            window_6m=str(W6_0.date()), seed=SEED, n_mc=N_MC,
            selection_rule=f"score=mean/std*sqrt(n)(活動日) Top{TOP_K} / 銘柄1・ファミリー{MAX_PER_FAMILY} / "
                           f"逆ボラ加重cap{int(W_CAP*100)}% / フィルタ: 活動日≥{MIN_ACTIVE_12M}・12m>0・6m>0",
            mult_rule="0.8×max{m: 直近12m最悪単日×m≥−4% ∧ 月中DD×m≥−8%} / fast=1.5倍",
            mc_rule="FN Stellar P1+8%→P2+5%・静的DD−10%・日次はEAガードで−4%クリップ・5日ブロックBS",
            caveat="直近窓で選び直近窓で測る=構造的に楽観。full_historyが正直な悲観バウンド。"
                   "Yahoo日足近似・配当除く。実運用はデモ/本番で別途確認",
            inputs=sha256s()),
        ranking={k: table[k] for k in ranked},
        selected=weights, variants=variants, reference_recent=refs)
    path = os.path.join(HERE, "results", "recentfit_screen.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
