# -*- coding: utf-8 -*-
"""
event_intermarket_edge_10y.py — 第3並走ポートフォリオ用「未トライ土俵」の新エッジ一括事前登録探索(10年)。

背景(これまで検定済みの土俵 = 再探索しない):
  - docs/14      : FX の 曜日(DOW) / 月末(TOM)              → 円月曜(v7)だけ生存。
  - docs/50      : 指数/暗号/コモディティの 曜日 / 指数TOM / 相対価値ペア(N=130) → 指数月曜(E-Mon)だけ生存。
  - docs/64      : プレ祝日 / 年末年始 / 月別シーズナリティ(N=164) → 指数7月(S-Jul)だけ SEASONAL-LEAD。
  - docs/28(edge7): H1足内セッション(ロンドン/NY ORB・フェード・初動継続・オーバーナイト・東京) Drive10年 → 全6 REJECT。
  → 「曜日・月末・月別・プレ祝日・年末年始・足内セッション」は出尽くし。本書はこれまで一度も検定していない
     2系統を、v1-v6/E-Mon/S-Jul を裁いたのと同一ハーネスで一括事前登録検定する:

  G  マクロ・イベント・ドリフト : 中央銀行/雇用統計の"イベント前後ドリフト"。曜日ラベルではなく
       「イベント日」で条件付ける=月曜効果(v7/E-Mon)と機序が直交。古典: Lucca & Moench(2015) pre-FOMC drift,
       Savor & Wilson(2013) announcement premium。
         G1 pre-FOMC drift   : FOMC公表"前営業日"に指数LONG → 公表当日寄付で決済(24h保有・年8回)。
         G2 pre-FOMC 2day    : FOMC公表 2営業日前から保有(前2日)。
         G3 post-FOMC drift  : FOMC公表"当日"建て→翌営業日寄付決済。
         G4 pre-NFP          : 雇用統計(第1金曜)"前営業日"に指数LONG → NFP当日寄付決済。
         G5 post-NFP         : NFP当日(第1金曜)建て→翌営業日寄付決済。

  L  インターマーケット先行遅行 : ある資産の前日リターン符号で別資産を建てる(クロスアセットのリードラグ)。
       カレンダーでも単一資産方向予測でもない第3系統(docs/14 選択肢3の未踏部分)。
         L1 gold→AUD   : 金(t-1)の符号で AUDUSD(t) を建てる(コモディティ通貨リンク)。
         L2 oil→CAD    : WTI(t-1)の符号で USDCAD(t) を"逆"に建てる(原油高=CAD高=USDCAD安)。
         L3 dxy→EUR    : ドル指数(t-1)の符号で EURUSD(t) を"逆"に建てる(USD先行)。
         L4 spx→JP225  : 米国(t-1)の符号で 日経(t) を建てる(オーバーナイト・スピルオーバー)。
         L5 spx→GER40  : 米国(t-1)の符号で 独DAX(t) を建てる(欧州への波及)。
         L6 volreg→idx : 指数20日実現ボラが低位(下位33%)の翌日に指数LONG(低ボラ持続=リスクオン)。

トレード定義(リポジトリ統一): trade_date の open でエントリ、翌 trade_date の open で決済(o2o, 1営業日保有)。
  pre-* は「イベント前営業日」=自動算出。L系は前日条件→当日 o2o。往復コストは bps 控除。

全候補は事前登録 → 合計 N で Bonferroni 補正。各候補に v1-v6/E-Mon/S-Jul を裁いたのと同じ二次ハーネス:
  順列検定(符号シャッフル) / ★年次ブロックp(年=独立サンプル) / IS-OOS(プール半割) / 全年ジャックナイフ /
  Bonferroni / コスト感応(1x/2x/3x) /
  ★★既存4成分すべてとの月次相関 = v7(円月曜)・E-Mon(指数月曜)・E5(多資産TSMOM)・v4(FX日足合議)。
  → 第3の器(口座C)は 既存A(v7+v4+E5)・並走B(E-Mon+E5) の"両方"と低相関でなければ並走の意味が無い。

データ: research/data/<NAME>_d.csv(Yahoo日足10年)。取得= research/fetch_calendar.py + research/fetch_intermarket.py。
  必要シンボル: US500,NAS100,GER40,JP225(指数) / XAUUSD,WTI(コモ) / DXY(ドル指数) /
                AUDUSD,USDCAD,EURUSD(+v4用 GBPUSD,USDCHF,NZDUSD,USDJPY) / EURJPY,GBPJPY,USDJPY(v7基準).
規律(docs/14,50,64の系譜): 数字を盛らない。出なければ「出ない」と書く。
  Yahoo日足は配当除く指数・OHLC概算・bps単純化。採用候補は必ず Drive(配当込/CFD近似)+デモ前進検証で実測。
  ★本サンドボックスは numpy/pandas・ネット非搭載のため一次値すら出せない=結果は空欄。確定は Colab/Drive で。
"""
import os, json, datetime as dt, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# 往復コスト(bps)。指数/金は数bps、原油やや高、FXは別途pipで。
COST_BPS = {"US500": 3.0, "NAS100": 3.0, "GER40": 3.0, "UK100": 4.0, "JP225": 4.0,
            "XAUUSD": 4.0, "WTI": 6.0, "DXY": 3.0}
DEFAULT_COST_BPS = 4.0
INDICES = ["US500", "NAS100", "GER40", "JP225"]
EMON_BASKET = ["NAS100", "US500", "GER40"]      # E-Mon 構成(docs/50)
E5_BASKET = ["XAUUSD", "US500", "NAS100", "GER40"]  # E5 構成(docs/23)
YEN = ["EURJPY", "GBPJPY", "USDJPY"]            # v7 構成
V4_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]


# ============================================================
# FOMC 公表日(2016-2025・定例8回/年・公表は会合2日目, 概ね水曜)。
#   出所: Federal Reserve 公式カレンダー(定例会合のみ。2020の緊急利下げは含めない)。
#   ★本番EA/確定検証では https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm で要照合。
# ============================================================
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


def load_daily(name, crypto=False):
    """日足を取引日へ正規化(リポジトリ統一の load_daily)。"""
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek
    if not crypto:
        df = df[df["weekday"] <= 4]
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0   # 当日open→翌取引日open(1営業日保有)
    df["c2c"] = df["close"].pct_change()
    return df


def have(name):
    return os.path.exists(os.path.join(DATA, f"{name}_d.csv"))


def pip_size(p):
    return 0.01 if p.endswith("JPY") else 0.0001


# ---------------- 統計ユーティリティ(既存ハーネスと同一) ----------------
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
    """年次合算リターンに対する符号反転順列検定(=年を独立ブロックとした正直な片側p)。"""
    y = yearly_returns(r).values
    if len(y) < 3:
        return 1.0, len(y)
    rng = np.random.default_rng(seed); real = y.sum(); a = np.abs(y)
    null = np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(n_iter)])
    return float((null >= real).mean()), len(y)


# ---------------- 既存4成分 月次プロキシ(無相関判定の基準) ----------------
def v7_monthly_ref():
    """v7 = 円3クロス 月曜LONG(open→翌open)等加重。"""
    acc = None
    for p in YEN:
        if not have(p):
            continue
        df = load_daily(p)
        m = to_monthly((df[df["weekday"] == 0]["o2o"] - 2 * pip_size(p) / df[df["weekday"] == 0]["open"]).dropna())
        acc = m if acc is None else acc.add(m, fill_value=0.0)
    return None if acc is None else (acc / 3.0).rename("v7")


def emon_monthly_ref():
    """E-Mon = 指数3つ 月曜LONG(open→翌open)等加重。"""
    parts = []
    for nm in EMON_BASKET:
        if not have(nm):
            continue
        df = load_daily(nm)
        c = COST_BPS.get(nm, DEFAULT_COST_BPS) / 1e4
        parts.append((df[df["weekday"] == 0]["o2o"] - c).rename(nm))
    if not parts:
        return None
    w = pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()
    return to_monthly(w).rename("emon")


def e5_monthly_ref():
    """E5 = 多資産 月次TSMOM(LB 1/3/6/12 合算符号・逆ボラ近似は等加重で簡略)。"""
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
    """v4 = FX9ペア 日足k>=4合議(SL=1.5ATR/RR1.2/8日)を日足OHLCで簡易再現。月次合算。docs/53。"""
    monthly = {}
    for p in V4_PAIRS:
        if not have(p):
            continue
        df = load_daily(p)
        o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
        idx = df.index; n = len(c)
        if n < 40:
            continue
        rsi = _rsi(c, 14); atr = _atr(h, l, c, 14); bbwin = 20; cost = 2 * pip_size(p)
        i = bbwin + 2
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
            ret = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0.0
            mv = 0.005
            buy = int(rsi[i] < 35) + int(zz < -1.5) + int(down >= 3) + int(ret < -mv)
            sell = int(rsi[i] > 65) + int(zz > 1.5) + int(up >= 3) + int(ret > mv)
            sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
            if sig == 0:
                i += 1; continue
            entry = o[i + 1]; sld = 1.5 * atr[i]; tpd = 1.2 * sld
            if sld <= 0:
                i += 1; continue
            sl = entry - sig * sld; tp = entry + sig * tpd
            exit_px = None; j = i + 1; held = 0
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


# ============================================================
# イベント日 → "前営業日 / 当日" の trade_date を解決
# ============================================================
def _index_trade_dates():
    """指数(US500)の取引日インデックスを基準カレンダーに使う。"""
    df = load_daily("US500")
    return list(df.index)


def event_prevday_dates(event_dates, td_index, lag=1):
    """各イベント日の lag 営業日前の trade_date を返す(td_index=取引日の昇順リスト)。"""
    import bisect
    norm = [pd.Timestamp(d, tz="UTC").floor("D") for d in event_dates]
    out = []
    for ev in norm:
        # ev 以上で最小の取引日 = イベント当日(休場なら直後)。その lag 個手前が"前営業日"。
        pos = bisect.bisect_left(td_index, ev)
        if 0 <= pos - lag and pos - lag < len(td_index):
            out.append(td_index[pos - lag])
    return out


def event_sameday_dates(event_dates, td_index):
    """各イベント日に対応する取引日(休場なら直後の取引日)。"""
    import bisect
    norm = [pd.Timestamp(d, tz="UTC").floor("D") for d in event_dates]
    out = []
    for ev in norm:
        pos = bisect.bisect_left(td_index, ev)
        if pos < len(td_index):
            out.append(td_index[pos])
    return out


def nfp_dates(td_index):
    """雇用統計=各月第1金曜(自動算出)。例外的にずれる月はあるが標準ルールで近似。"""
    years = sorted(set(d.year for d in td_index))
    out = []
    for y in years:
        for m in range(1, 13):
            d = dt.date(y, m, 1)
            # 第1金曜
            offset = (4 - d.weekday()) % 7
            out.append(f"{y}-{m:02d}-{d.day + offset:02d}")
    return out


def _cost(name, cost_bps=None):
    return (COST_BPS.get(name, DEFAULT_COST_BPS) if cost_bps is None else cost_bps) / 1e4


# ============================================================
# 候補シリーズ生成
# ============================================================
def eventdrift_series(name, entry_dates, direction=+1, cost_bps=None):
    """entry_dates(=その日のopenで建て翌取引日openで決済)に限定した o2o リターン。"""
    df = load_daily(name)
    sel = df.index.isin(set(pd.DatetimeIndex(entry_dates)))
    sub = df[sel]
    return (direction * sub["o2o"] - _cost(name, cost_bps)).dropna()


def eventdrift_basket(names, entry_dates, direction=+1, cost_bps=None):
    acc = None
    for nm in names:
        if not have(nm):
            continue
        r = eventdrift_series(nm, entry_dates, direction, cost_bps)
        acc = r if acc is None else acc.add(r, fill_value=0.0)
        # 等加重: 各日付で在る分だけ平均する近似(欠損は fill_value=0)
    if acc is None:
        return pd.Series(dtype=float)
    return (acc / len(names)).dropna()


def leadlag_series(lead, follow, direction=+1, invert_signal=False, cost_bps=None):
    """lead(t-1)の c2c 符号で follow(t) を建て、follow の o2o を取る(1営業日保有)。
       invert_signal=True なら lead 符号を反転(例: oil↑→USDCAD↓)。"""
    if not (have(lead) and have(follow)):
        return pd.Series(dtype=float)
    dl = load_daily(lead); dfo = load_daily(follow)
    sig = np.sign(dl["c2c"].shift(1))            # 前日(=t-1)のリターン符号を当日適用
    if invert_signal:
        sig = -sig
    j = pd.concat([sig.rename("s"), dfo["o2o"].rename("r")], axis=1).dropna()
    j = j[j["s"] != 0]
    return (direction * j["s"] * j["r"] - _cost(follow, cost_bps)).dropna()


def volregime_series(name, lo_q=0.33, cost_bps=None):
    """name の20日実現ボラが下位 lo_q 分位の翌日に LONG(低ボラ持続=リスクオン)。"""
    if not have(name):
        return pd.Series(dtype=float)
    df = load_daily(name)
    vol = df["c2c"].rolling(20).std()
    thr = vol.quantile(lo_q)
    cond = (vol.shift(1) <= thr)                  # 前日までの低ボラ → 当日LONG
    sub = df[cond.fillna(False)]
    return (sub["o2o"] - _cost(name, cost_bps)).dropna()


# ============================================================
# 候補レジストリ(事前登録)
# ============================================================
def build_candidates(td_index):
    """(label, family, generator(cost_bps=None)->Series) を返す。事前登録 = 実行前に固定。"""
    fomc_prev1 = event_prevday_dates(FOMC_DATES, td_index, lag=1)
    fomc_prev2 = event_prevday_dates(FOMC_DATES, td_index, lag=2)
    fomc_same = event_sameday_dates(FOMC_DATES, td_index)
    nfp = nfp_dates(td_index)
    nfp_prev1 = event_prevday_dates(nfp, td_index, lag=1)
    nfp_same = event_sameday_dates(nfp, td_index)

    cands = []
    # --- 単一指数 × イベント × 方向(L/S) ---
    event_specs = [
        ("PreFOMC1", "G_preFOMC", fomc_prev1),
        ("PreFOMC2", "G_preFOMC", fomc_prev2),
        ("PostFOMC", "G_postFOMC", fomc_same),
        ("PreNFP", "G_preNFP", nfp_prev1),
        ("PostNFP", "G_postNFP", nfp_same),
    ]
    for nm in INDICES:
        for ev_tag, fam, dates in event_specs:
            for d in (+1, -1):
                tag = "L" if d > 0 else "S"
                cands.append((f"{nm}_{ev_tag}_{tag}", fam,
                              (lambda n=nm, dts=dates, dd=d: (lambda c=None: eventdrift_series(n, dts, dd, c)))()))

    # --- インターマーケット先行遅行(L/S) ---
    leadlag_specs = [
        ("L1_gold2AUD", "L_leadlag", "XAUUSD", "AUDUSD", False),
        ("L2_oil2CAD", "L_leadlag", "WTI", "USDCAD", True),    # 原油高→USDCAD安=invert
        ("L3_dxy2EUR", "L_leadlag", "DXY", "EURUSD", True),    # ドル高→EURUSD安=invert
        ("L4_spx2JP", "L_leadlag", "US500", "JP225", False),
        ("L5_spx2GER", "L_leadlag", "US500", "GER40", False),
    ]
    for lbl, fam, lead, follow, inv in leadlag_specs:
        for d in (+1, -1):
            tag = "L" if d > 0 else "S"
            cands.append((f"{lbl}_{tag}", fam,
                          (lambda le=lead, fo=follow, iv=inv, dd=d: (lambda c=None: leadlag_series(le, fo, dd, iv, c)))()))

    # --- 低ボラ・レジーム(指数のみ・LONG) ---
    for nm in INDICES:
        cands.append((f"{nm}_VolRegimeLo_L", "L_volregime",
                      (lambda n=nm: (lambda c=None: volregime_series(n, 0.33, c)))()))

    return cands


def run():
    td_index = _index_trade_dates()
    refs = {}
    for k, fn in [("v7", v7_monthly_ref), ("emon", emon_monthly_ref),
                  ("e5", e5_monthly_ref), ("v4", v4_monthly_ref)]:
        ref = fn()
        if ref is not None:
            refs[k] = ref

    cands = [(l, f, g) for (l, f, g) in build_candidates(td_index) if len(g()) >= 60]
    n_tests = len(cands)
    alpha = 0.05 / max(n_tests, 1)

    rows = []; GEN = {}
    for lbl, fam, gen in cands:
        GEN[lbl] = gen
        r = gen()
        p = perm_p(r.values); st = stats(r.values); cm = to_monthly(r)
        cc = {}
        for k, ref in refs.items():
            j = pd.concat([cm.rename("c"), ref.rename("r")], axis=1).dropna()
            cc[f"corr_{k}"] = round(float(j["c"].corr(j["r"])), 2) if len(j) > 24 else None
        rows.append(dict(label=lbl, family=fam, **st, perm_p=round(p, 4), **cc))
    df = pd.DataFrame(rows).sort_values("perm_p").reset_index(drop=True)

    sig = df[df.perm_p <= 0.05].copy()
    surv = sig[sig.perm_p <= alpha].copy()

    # 二次ハーネス対象: Bonferroni生存 + (p<=0.05 かつ 既存4成分すべてと |相関|<=0.3 の無相関候補)
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
            jackknife_max_p=round(max(jk.values()), 3) if jk else None, jackknife=jk, cost_net=cost)

    # バスケット採点(E-Mon流: 1イベント現象を多指数でサンプル)。最有力=pre-FOMC指数バスケット。
    fomc_prev1 = event_prevday_dates(FOMC_DATES, td_index, lag=1)
    fomc_prev2 = event_prevday_dates(FOMC_DATES, td_index, lag=2)
    baskets = {
        "EFOMC(US500+NAS100+GER40 preFOMC1 L)": eventdrift_basket(["US500", "NAS100", "GER40"], fomc_prev1, +1),
        "EFOMC2(US500+NAS100+GER40 preFOMC2 L)": eventdrift_basket(["US500", "NAS100", "GER40"], fomc_prev2, +1),
    }
    basket_out = {}
    for bname, br in baskets.items():
        if len(br) < 10:
            continue
        yb_p, yb_n = yearly_block_p(br); yr = yearly_returns(br); bm = to_monthly(br)
        cc = {}
        for k, ref in refs.items():
            j = pd.concat([bm.rename("c"), ref.rename("r")], axis=1).dropna()
            cc[f"corr_{k}"] = round(float(j["c"].corr(j["r"])), 2) if len(j) > 8 else None
        basket_out[bname] = dict(
            **stats(br.values), daily_perm_p=round(perm_p(br.values), 4),
            yearly_block_p=round(yb_p, 4), yearly_n=int(yb_n),
            yearly_pos_pct=round(float((yr > 0).mean()) * 100, 0),
            yearly_mean_pct=round(float(yr.mean()) * 100, 2), yearly_min_pct=round(float(yr.min()) * 100, 2),
            **cc)

    out = dict(n_tests=n_tests, alpha_bonf=round(alpha, 6),
               sig_count=int(len(sig)), bonferroni_survivors=int(len(surv)),
               refs_available=list(refs.keys()),
               span=[str(td_index[0]), str(td_index[-1])] if td_index else None,
               all_significant=sig.to_dict("records"), detail=detail, baskets=basket_out)
    return df, sig, surv, out


if __name__ == "__main__":
    pd.set_option("display.width", 240); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
    df, sig, surv, out = run()

    print(f"基準成分(再構築できた既存エッジ) = {out['refs_available']}")
    print(f"全候補数(多重検定試行数) N = {out['n_tests']}   Bonferroni α = {out['alpha_bonf']}")
    print(f"\n===== 順列 p<=0.05 の候補 ({len(sig)}/{out['n_tests']}) =====")
    print(sig.to_string() if len(sig) else "  なし")
    print(f"\n===== ★Bonferroni 生存 (p<=α={out['alpha_bonf']}): {len(surv)}件 =====")
    print(surv.to_string() if len(surv) else "  なし")

    print("\n===== 追検対象(Bonferroni生存 + 既存4成分すべてと無相関|corr|<=0.3)の二次ハーネス =====")
    print("(★年次ブロックp = 年を独立サンプルとした正直な片側p。イベント系は年8回×10年≒80標本でも"
          "年=独立観測は10ゆえ年次pを最重視)")
    for k, d in out["detail"].items():
        f, o, i = d["full"], d["oos"], d["IS"]
        flag = "★BONF生存" if d["bonferroni_survivor"] else ""
        print(f"\n[{k}] {flag} 全:純益{f['net_pct']}% 勝率{f['win_pct']}% DD{f['maxDD_pct']}% n={f['n']} 日次p={f['perm_p']}")
        print(f"   相関 v7={f.get('corr_v7')} Emon={f.get('corr_emon')} E5={f.get('corr_e5')} v4={f.get('corr_v4')}")
        print(f"   ★年次ブロックp={d['yearly_block_p']}(年数{d['yearly_n']}, 陽性年{d['yearly_pos_pct']}%) | "
              f"IS純益{i['net_pct']}% / OOS純益{o['net_pct']}% p={o['perm_p']} | JKmax_p={d['jackknife_max_p']} | コスト{d['cost_net']}")

    print("\n===== バスケット採点(E-Mon流: pre-FOMC を多指数でサンプル) =====")
    for bname, b in out["baskets"].items():
        print(f"\n[{bname}] 純益{b['net_pct']}% 勝率{b['win_pct']}% DD{b['maxDD_pct']}% n={b['n']}")
        print(f"   日次p={b['daily_perm_p']} | ★年次ブロックp={b['yearly_block_p']}(年数{b['yearly_n']}, 陽性年{b['yearly_pos_pct']}%, "
              f"年平均{b['yearly_mean_pct']}%, 最悪年{b['yearly_min_pct']}%)")
        print(f"   相関 v7={b.get('corr_v7')} Emon={b.get('corr_emon')} E5={b.get('corr_e5')} v4={b.get('corr_v4')}")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "event_intermarket_edge_10y.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/event_intermarket_edge_10y.json")
