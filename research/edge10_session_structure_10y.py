# -*- coding: utf-8 -*-
"""
edge10_session_structure_10y.py — 「日足OHLCで検定できる未踏のセッション構造」一括探索(10年)。

背景(これまでの土俵と、残っている穴):
  - docs/14/50/64 : カレンダー軸(曜日 / TOM / プレ祝日 / 年末年始 / 月別)は検定済み。
  - docs/27       : 日足の多資産トレンド/MR/リードラグ系は E1-E6 で検定済み(ADOPTゼロ)。
  - edge7/edge9   : FX の足内(H1)セッション・オーバーナイト継続・週末フローは検定済み。
  → だが全ての日足検定は o2o(open→翌open) の「1日まるごと」だった。日足OHLCは open と close を
    両方持つので、**1日をオーバーナイト(close→翌open)と日中(open→close)に分解した構造**は
    検定できるのに一度も検定していない(grep で overnight×指数 は皆無)。古典文献の本丸:
      O  指数オーバーナイト効果(Cooper et al. 2008): 株式リターンのほぼ全部が夜間に発生。
      D  日中(open→close)はゼロ近傍(Oの補集合)。
      G  寄付ギャップのフェード/フォロー(ギャップ埋め): |open/前close-1| > 0.5σ20 で o2c。
      W  週末オーバーナイト(金close→月open): 指数では未検定(edge9はFXのみ)。
      F  プレFOMCドリフト(Lucca-Moench 2015): FOMC声明日とその前日の c2c。日程はFed公式から取得。

トレード定義: O/W = close→次営業日open(夜間保有=スワップ控除あり)。D/G = open→当日close(同日)。
  F = c2c 1泊。往復コストbps控除はリポジトリ統一。**夜間保有はCFDファイナンシング(swap)を
  fin_bps/泊 で正直に控除**(これを怠ると夜間系は必ず盛れる)。

全候補は事前登録 → 合計 N で Bonferroni 補正。各候補に v1-v6/E-Mon を裁いた同じ二次ハーネス:
  順列検定 / IS-OOS(プール半割) / 全年ジャックナイフ / コスト感応(1x/2x/3x) / 夜間系はswap感応(0x/1x/2x) /
  既存エッジ相関(v7/E-Mon) / ★年次ブロックp。Oファミリには「夜間vs日中の対称性検定」も追加
  (単なる上昇相場ベータなら夜と昼で差が無い。差の符号反転順列pで"夜に偏る"ことを直接検定)。

データ: research/data/<NAME>_d.csv(Yahoo日足・**固定窓 2016-01-01..2025-12-31 に凍結**, docs/71)。
  無ければ本スクリプトが自動取得。FOMC日程: federalreserve.gov から取得し
  research/results/fomc_dates_2016_2025.json にコミット(再現性)。
規律: 数字を盛らない。出なければ「出ない」と書く。Yahoo日足は配当除く指数・現物指数の寄/引値で
  CFD(先物連動・~23h取引)の夜間ギャップの近似に過ぎない。採用候補は必ずデモ前進検証で実測。
"""
import os, json, re, csv, time, datetime as dt
import urllib.request
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RESULTS = os.path.join(HERE, "results")
os.makedirs(DATA, exist_ok=True); os.makedirs(RESULTS, exist_ok=True)

# 固定窓(docs/71): 2016-01-01 .. 2025-12-31 UTC
P1, P2 = 1451606400, 1767225599
YAHOO = {"US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI", "UK100": "^FTSE",
         "JP225": "^N225", "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X", "USDJPY": "USDJPY=X"}
INDICES = ["US500", "NAS100", "GER40", "UK100", "JP225"]

COST_BPS = {"US500": 3.0, "NAS100": 3.0, "GER40": 3.0, "UK100": 4.0, "JP225": 4.0}
DEFAULT_COST_BPS = 4.0
FIN_BPS_NIGHT = 1.8   # CFD夜間ファイナンシング/泊(≒(短期金利2%+マークアップ2.5%)/252)。L/S同額控除の保守側。
GAP_SIGMA = 0.5       # ギャップしきい値: |open/前close-1| > 0.5 × σ20(c2c)。事前登録・グリッド探索しない。


# ---------------- データ取得(凍結窓・キャッシュ) ----------------
def _fetch_yahoo(sym, tries=6):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?period1={P1}&period2={P2}&interval=1d")
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
                d_ = dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None)
                rows.append((d_.strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c))
            return rows
        except Exception as e:
            last = e; time.sleep(2 ** k)
    raise last


def ensure_data():
    for name, sym in YAHOO.items():
        p = os.path.join(DATA, f"{name}_d.csv")
        if os.path.exists(p):
            continue
        rows = _fetch_yahoo(sym)
        with open(p, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["timestamp", "open", "high", "low", "close"]); w.writerows(rows)
        print(f"  fetch {name}: {len(rows)} bars {rows[0][0][:10]}..{rows[-1][0][:10]}")
        time.sleep(1.5)


def load_daily(name):
    df = pd.read_csv(os.path.join(DATA, f"{name}_d.csv"))
    df["t"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    df["trade_date"] = (df["t"] + pd.Timedelta(hours=2)).dt.floor("D")
    df = df.groupby("trade_date", as_index=True).last()
    df["weekday"] = df.index.dayofweek
    df = df[df["weekday"] <= 4]
    df["o2o"] = df["open"].shift(-1) / df["open"] - 1.0
    df["o2c"] = df["close"] / df["open"] - 1.0                     # 日中
    df["c2o_next"] = df["open"].shift(-1) / df["close"] - 1.0      # 当日close→翌営業日open(夜間)
    df["c2c"] = df["close"] / df["close"].shift(1) - 1.0
    df["nights"] = (df.index.to_series().shift(-1) - df.index.to_series()).dt.days  # 夜間保有の暦泊数
    df["sigma20"] = df["c2c"].rolling(20).std().shift(1)
    df["gap"] = df["open"] / df["close"].shift(1) - 1.0
    return df


# ---------------- FOMC日程(Fed公式・スケジュール会合のみ) ----------------
_MON = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"])}


def _decision_date(year, month_label, day_label):
    """'January'/'April/May' × '26-27' / '31-1' → 決定日(レンジ最終日)。月跨ぎは後側の月。"""
    months = [m for m in month_label.split("/") if m in _MON]
    if not months:
        return None
    days = re.findall(r"\d+", day_label)
    if not days:
        return None
    last_day = int(days[-1])
    mo = _MON[months[-1]]
    if len(days) >= 2 and int(days[-1]) < int(days[0]):  # 31-1 のような月跨ぎ
        mo = _MON[months[-1]] if len(months) > 1 else (_MON[months[0]] % 12 + 1)
    yr = year + 1 if (mo == 1 and _MON[months[0]] == 12) else year
    try:
        return dt.date(yr, mo, last_day)
    except ValueError:
        return None


def fetch_fomc_dates():
    cache = os.path.join(RESULTS, "fomc_dates_2016_2025.json")
    if os.path.exists(cache):
        with open(cache) as f:
            return [dt.date.fromisoformat(s) for s in json.load(f)["decision_dates"]]

    def get(u):
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")

    dates = []
    # 2016-2020: historical pages。'January 26-27 Meeting - 2016' 形式。unscheduled/notation は除外。
    for y in range(2016, 2021):
        h = get(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm")
        for m in re.findall(r"<h5[^>]*>([^<]*?Meeting[^<]*)</h5>", h):
            if "unscheduled" in m.lower() or "notation" in m.lower() or "cancelled" in m.lower():
                continue
            mm = re.match(r"([A-Za-z/]+)\s+([\d/–\-]+)\s+Meeting", m.strip())
            if mm:
                d = _decision_date(y, mm.group(1), mm.group(2))
                if d:
                    dates.append(d)
    # 2021-2025: カレンダーページ(年パネルごとに month/date div)。
    h = get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    panels = re.split(r"(20\d\d) FOMC Meetings", h)
    for i in range(1, len(panels) - 1, 2):
        y = int(panels[i]); body = panels[i + 1]
        if not (2021 <= y <= 2025):
            continue
        for mon, day in re.findall(
                r"fomc-meeting__month[^>]*>\s*<strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<",
                body, re.S):
            if "cancelled" in day.lower() or "unscheduled" in day.lower():
                continue
            d = _decision_date(y, mon, day.strip().rstrip("*"))
            if d:
                dates.append(d)
    dates = sorted(set(d for d in dates if dt.date(2016, 1, 1) <= d <= dt.date(2025, 12, 31)))
    with open(cache, "w") as f:
        json.dump(dict(source="federalreserve.gov fomchistorical{2016..2020}.htm + fomccalendars.htm",
                       fetched_window="2016-01-01..2025-12-31", scheduled_only=True,
                       n=len(dates), decision_dates=[d.isoformat() for d in dates]), f, indent=1)
    return dates


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
    y = yearly_returns(r).values
    if len(y) < 3:
        return 1.0, len(y)
    rng = np.random.default_rng(seed); real = y.sum(); a = np.abs(y)
    null = np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(n_iter)])
    return float((null >= real).mean()), len(y)


def v7_monthly_ref():
    acc = None
    for p in ["EURJPY", "GBPJPY", "USDJPY"]:
        m = to_monthly(load_daily(p).query("weekday==0")["o2o"].dropna())
        acc = m if acc is None else acc.add(m, fill_value=0.0)
    return (acc / 3.0).rename("v7")


def emon_monthly_ref():
    acc = None
    for nm in ["US500", "NAS100", "GER40"]:
        c = COST_BPS.get(nm, DEFAULT_COST_BPS) / 1e4
        m = to_monthly((load_daily(nm).query("weekday==0")["o2o"] - c).dropna())
        acc = m if acc is None else acc.add(m, fill_value=0.0)
    return (acc / 3.0).rename("emon")


# ---------------- 候補シリーズ生成 ----------------
def _cost(name, cost_bps):
    return (COST_BPS.get(name, DEFAULT_COST_BPS) if cost_bps is None else cost_bps) / 1e4


def overnight_series(name, direction, cost_bps=None, fin_mult=1.0):
    """O: 毎営業日 close→翌営業日 open。夜間保有=暦泊数×fin控除。"""
    df = load_daily(name)
    fin = FIN_BPS_NIGHT * fin_mult / 1e4
    r = direction * df["c2o_next"] - _cost(name, cost_bps) - fin * df["nights"]
    return r.dropna()


def intraday_series(name, direction, cost_bps=None, fin_mult=1.0):
    """D: 毎営業日 open→close(同日・夜間保有なし)。"""
    df = load_daily(name)
    return (direction * df["o2c"] - _cost(name, cost_bps)).dropna()


def gap_series(name, mode, cost_bps=None, fin_mult=1.0):
    """G: |gap| > 0.5σ20 の日のみ open→close。fade=ギャップ逆方向 / follow=順方向。"""
    df = load_daily(name)
    sel = df[(df["gap"].abs() > GAP_SIGMA * df["sigma20"]) & df["sigma20"].notna()]
    sgn = -np.sign(sel["gap"]) if mode == "fade" else np.sign(sel["gap"])
    return (sgn * sel["o2c"] - _cost(name, cost_bps)).dropna()


def weekend_series(name, direction, cost_bps=None, fin_mult=1.0):
    """W: 金曜 close→次営業日 open(通常は月曜寄付・3泊のfin控除)。"""
    df = load_daily(name)
    sel = df[df["weekday"] == 4]
    fin = FIN_BPS_NIGHT * fin_mult / 1e4
    r = direction * sel["c2o_next"] - _cost(name, cost_bps) - fin * sel["nights"]
    return r.dropna()


def fomc_series(name, leg, fomc_dates, cost_bps=None, fin_mult=1.0):
    """F: leg='pre'=決定前日のc2c(close[D-2]→close[D-1]) / leg='day'=決定日のc2c。LONGのみ(文献方向)。1泊。"""
    df = load_daily(name)
    dset = set(pd.Timestamp(d, tz="UTC") for d in fomc_dates)
    pos = {d: i for i, d in enumerate(df.index)}
    fin = FIN_BPS_NIGHT * fin_mult / 1e4
    idx, vals = [], []
    for d in sorted(dset):
        if d not in pos:                                   # 決定日が休場なら直近の前営業日に丸める
            prev = df.index[df.index <= d]
            if len(prev) == 0:
                continue
            d = prev[-1]
        i = pos[d]
        j = i - 1 if leg == "pre" else i
        if j < 1:
            continue
        idx.append(df.index[j]); vals.append(df["c2c"].iloc[j])
    r = pd.Series(vals, index=idx).dropna()
    return r - _cost(name, cost_bps) - fin


# ---------------- 候補レジストリ(事前登録 N=44) ----------------
def build_candidates(fomc_dates):
    cands = []
    for nm in INDICES:
        for d, tag in ((+1, "L"), (-1, "S")):
            cands.append((f"{nm}_Overnight_{tag}", "O_overnight",
                          (lambda n=nm, dd=d: (lambda c=None, f=1.0: overnight_series(n, dd, c, f)))()))
            cands.append((f"{nm}_Intraday_{tag}", "D_intraday",
                          (lambda n=nm, dd=d: (lambda c=None, f=1.0: intraday_series(n, dd, c, f)))()))
            cands.append((f"{nm}_Weekend_{tag}", "W_weekendON",
                          (lambda n=nm, dd=d: (lambda c=None, f=1.0: weekend_series(n, dd, c, f)))()))
        for mode in ("fade", "follow"):
            cands.append((f"{nm}_Gap{mode.capitalize()}", "G_gap",
                          (lambda n=nm, m=mode: (lambda c=None, f=1.0: gap_series(n, m, c, f)))()))
    for nm in ["US500", "NAS100"]:
        for leg in ("pre", "day"):
            cands.append((f"{nm}_FOMC_{leg}_L", "F_fomc",
                          (lambda n=nm, l=leg: (lambda c=None, f=1.0: fomc_series(n, l, fomc_dates, c, f)))()))
    return cands


def overnight_vs_intraday_p(name, n_iter=10000, seed=13):
    """夜昼対称性検定: d_t = c2o_next − o2c の符号反転順列p(片側: 夜>昼)。ベータでは説明できない偏りの直接検定。"""
    df = load_daily(name)
    d = (df["c2o_next"] - df["o2c"]).dropna().values
    rng = np.random.default_rng(seed); real = d.sum(); a = np.abs(d)
    null = np.array([(a * rng.choice([-1, 1], size=len(a))).sum() for _ in range(n_iter)])
    return float((null >= real).mean())


def run():
    ensure_data()
    fomc = fetch_fomc_dates()
    refs = {"v7": v7_monthly_ref(), "emon": emon_monthly_ref()}
    cands = [(l, f, g) for (l, f, g) in build_candidates(fomc) if len(g()) >= 60]
    n_tests = len(cands)
    alpha = 0.05 / n_tests

    rows = []; GEN = {}
    for lbl, fam, gen in cands:
        GEN[lbl] = gen
        r = gen()
        p = perm_p(r.values); st = stats(r.values); cm = to_monthly(r)
        cc = {}
        for k, ref in refs.items():
            j = pd.concat([cm.rename("c"), ref.rename("r")], axis=1).dropna()
            cc[f"corr_{k}"] = round(float(j["c"].corr(j["r"])), 2) if len(j) > 30 else None
        rows.append(dict(label=lbl, family=fam, **st, perm_p=round(p, 4), **cc))
    df = pd.DataFrame(rows).sort_values("perm_p").reset_index(drop=True)

    sig = df[df.perm_p <= 0.05].copy()
    surv = sig[sig.perm_p <= alpha].copy()

    def _ok(v):
        return v is None or (isinstance(v, float) and np.isnan(v)) or abs(v) <= 0.3
    targets = pd.concat([surv, sig[sig.apply(lambda r: _ok(r.get("corr_v7")) and _ok(r.get("corr_emon")), axis=1)]]
                        ).drop_duplicates("label")
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
        fin = {f"{m}x": stats(GEN[lbl](None, float(m)).values)["net_pct"] for m in (0, 1, 2)}
        yb_p, yb_n = yearly_block_p(r); yr = yearly_returns(r)
        detail[lbl] = dict(
            full=dict(net_pct=row["net_pct"], win_pct=row["win_pct"], maxDD_pct=row["maxDD_pct"],
                      n=int(row["n"]), perm_p=row["perm_p"], corr_v7=row.get("corr_v7"), corr_emon=row.get("corr_emon")),
            bonferroni_survivor=bool(row["perm_p"] <= alpha),
            yearly_block_p=round(yb_p, 4), yearly_n=int(yb_n),
            yearly_pos_pct=round(float((yr > 0).mean()) * 100, 0) if len(yr) else None,
            IS=is_, oos=dict(**oos, perm_p=round(oos_p, 4)),
            jackknife_max_p=round(max(jk.values()), 3), jackknife=jk,
            cost_net=cost, fin_net=fin)

    sym = {nm: round(overnight_vs_intraday_p(nm), 4) for nm in INDICES}

    out = dict(n_tests=n_tests, alpha_bonf=round(alpha, 6),
               sig_count=int(len(sig)), bonferroni_survivors=int(len(surv)),
               span=[str(refs["v7"].index.min()), str(refs["v7"].index.max())],
               fomc_n=len(fomc), gap_sigma=GAP_SIGMA, fin_bps_night=FIN_BPS_NIGHT,
               overnight_vs_intraday_p=sym,
               all_significant=sig.to_dict("records"), detail=detail)
    return df, sig, surv, out


if __name__ == "__main__":
    pd.set_option("display.width", 240); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 300)
    df, sig, surv, out = run()

    d0 = load_daily("US500")
    print("[sanity] US500 平日件数:", dict(d0["weekday"].value_counts().sort_index()))
    print(f"[sanity] US500 夜間泊数分布(1=平日泊,3=週末泊): {dict(d0['nights'].value_counts().sort_index().head(5))}")
    print(f"[sanity] FOMC決定日数(2016-2025, scheduled): {out['fomc_n']} (8回/年×10年=80が目安)")

    print(f"\n全候補数(多重検定試行数) N = {out['n_tests']}   Bonferroni α = {out['alpha_bonf']}")
    print("\n===== 夜昼対称性検定(片側p: 夜>昼。ベータで説明できない夜偏りの直接検定) =====")
    print(" ", out["overnight_vs_intraday_p"])
    print(f"\n===== 順列 p<=0.05 の候補 ({len(sig)}/{out['n_tests']}) =====")
    print(sig.to_string() if len(sig) else "  なし")
    print(f"\n===== ★Bonferroni 生存 (p<=α={out['alpha_bonf']}): {len(surv)}件 =====")
    print(surv.to_string() if len(surv) else "  なし")

    print("\n===== 追検対象(Bonferroni生存 + 既存2エッジと無相関|corr|<=0.3)の二次ハーネス =====")
    for k, d in out["detail"].items():
        f, o, i = d["full"], d["oos"], d["IS"]
        flag = "★BONF生存" if d["bonferroni_survivor"] else ""
        print(f"\n[{k}] {flag} 全:純益{f['net_pct']}% 勝率{f['win_pct']}% DD{f['maxDD_pct']}% n={f['n']} 日次p={f['perm_p']} "
              f"v7相関={f['corr_v7']} Emon相関={f['corr_emon']}")
        print(f"   ★年次ブロックp={d['yearly_block_p']} (年数={d['yearly_n']}, 陽性年{d['yearly_pos_pct']}%) | "
              f"IS純益{i['net_pct']}% / OOS純益{o['net_pct']}% p={o['perm_p']} | JKmax_p={d['jackknife_max_p']}")
        print(f"   コスト感応{d['cost_net']} | swap感応(夜間系のみ意味){d['fin_net']}")

    with open(os.path.join(RESULTS, "edge10_session_structure_10y.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2, default=str)
    print("\n保存: research/results/edge10_session_structure_10y.json")
