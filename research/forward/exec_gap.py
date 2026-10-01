# -*- coding: utf-8 -*-
"""docs/322 Q83: 執行差の測定装置 — 実口座(ops_inbox/<口座>/positions.csv)と紙上(同時刻の時間足・中値)の差をレグ別・月次に出す。
毎月 1 日に `cd research && python3 forward/exec_gap.py [YYYY-MM ...]`(既定 = 前月と当月)。結果: results/exec_gap_<月>.csv / exec_gap_trades.csv。

定義(1 取引あたり・bps・符号は取引方向込み):
  real_gross = sign*(close_price/open_price - 1)           実口座の値幅
  real_net   = real_gross + (commission+swap)/notional      実口座の純(notional = profit/real_gross。値幅ゼロの取引はレグ中央値で補完)
  paper_gross = sign*(mid[exit_hour]/mid[entry_hour] - 1)  同じ時刻(時間足の始値)で建てて同じ時刻で手仕舞った中値の値幅
  paper_model = paper_sched - model_cost                    研究系列の約束(予定の出口時刻 + モデル定数コスト)
  gap = real_net - paper_model = slip_in + slip_out + (real_cost - model_cost) + timing
    slip_in  = -sign*(open_price - mid_in)/mid_in            建て値の中値からの劣化(負 = 不利)
    slip_out = +sign*(close_price - mid_out)/mid_out         手仕舞い値の劣化
    real_cost = (commission+swap)/notional,  model_cost = 研究系列のコスト定数(FX 2pip / 指数 IDX_COST / XAU 5bps / 暗号 2pip≈0)
    timing   = paper_gross(実際の出口時刻) - paper_sched(予定の出口時刻)   SL・早期手仕舞い・遅延による差
  建て損ね率 = 1 - 実建て本数 / 予定本数(Mon の h4〜h10 = 月曜 × 4、Roll = 水曜 × 5、A案 S1/S2 = 月曜 × 1、S3 = 木曜 × 1。RSI2・v4・Hold は予定本数なし)
前提: サーバ時刻 = EET/EEST(FN / FTMO / Fintokei(AXSE)とも)。時間足は data_dukascopy → forward/q20_monitor_data → forward/exec_gap_data(Dukascopy 月次取得)→ Yahoo 1h(中値のみ・フラグ)。"""
import os, sys, re, glob, json, time, datetime as dt, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
import recentfit_screen as base
try: import dukascopy_fetch as dk
except Exception: dk = None
from zoneinfo import ZoneInfo
SERVER_TZ = ZoneInfo("EET"); CACHE = "forward/exec_gap_data"; os.makedirs(CACHE, exist_ok=True)
SYM_MAP = {"USOUSD": "WTI", "USOIL": "WTI", "GER40.cash": "GER40", "US500.cash": "US500", "NAS100.cash": "NAS100"}
YAHOO = {"ETHUSD": "ETH-USD", "BTCUSD": "BTC-USD", "UK100": "^FTSE", "WTI": "CL=F", "XAUUSD": "GC=F", "GER40": "^GDAXI", "US500": "ES=F", "NAS100": "NQ=F", "JP225": "NIY=F"}
DK_CODE = {"UK100": "GBRIDXGBP", "WTI": "LIGHTCMDUSD", "GER40": "DEUIDXEUR", "JP225": "JPNIDXJPY", "NAS100": "USATECHIDXUSD", "US500": "USA500IDXUSD"}
# 配備の予定表(docs/241 の台帳から転記・建て損ね率の分母。EA を切り替えたら since/until/skip を更新する)
SCHEDULE = {
    "14166201": [dict(fam="Mon", sym="ETHUSD", shots=4, since="2026-08-10"), dict(fam="Roll", sym="JPY5", shots=5, since="2026-09-28", skip=["2026-09-30", "2026-12-30", "2027-03-31", "2027-06-30"])],   # v1.30: Roll 5 本・9/30 は旧スキップ表で建てない
    "6104739":  [dict(fam="Roll", sym="JPY5", shots=5, since="2026-09-29", skip=["2026-12-30", "2027-03-31", "2027-06-30"]), dict(fam="Mon", sym="JPY4+ETH", shots=20, since="2026-09-29")],              # EA11 v1.10: Mon 5 レグ × 4 ショット・Roll 5 本(9/30 は解除・docs/308)
    "531343523": [dict(fam="S1", sym="GBPUSD", shots=1, since="2026-08-03", until="2026-09-28"), dict(fam="S2", sym="GBPJPY", shots=1, since="2026-08-03", until="2026-09-28"), dict(fam="S3", sym="USDCHF", shots=1, since="2026-08-03", until="2026-09-28")],   # RF5 は 9/28 14:45 停止
}
SCHED_HOURS = {"Mon": 24, "Roll": 4, "Sess": 4, "S1": 12, "S2": 12, "S3": 6}      # 予定保有時間(h)。無い族は実際の出口を使う
PER_WEEK = {"Mon": (0, None), "Roll": (2, None), "S1": (0, 1), "S2": (0, 1), "S3": (3, 1)}   # (曜日, 1 日あたり本数; None = ショット数を記録から数える)


def norm_sym(s):
    s = str(s).strip()
    if s.endswith("p") and s[:-1].isupper(): s = s[:-1]          # Fintokei 接尾辞
    return SYM_MAP.get(s, s)


def classify(c):
    c = str(c)
    m = re.match(r"RF(Mon|Roll|Hold|v4|Sess)_([A-Za-z0-9.]+?)(?:_h(\d+))?$", c)
    if m: return m.group(1), norm_sym(m.group(2)), (int(m.group(3)) if m.group(3) else None)
    m = re.match(r"RF5-(S\d)", c)
    if m: return m.group(1), None, None
    return "other", None, None


def model_cost(fam, sym, price):
    if sym in base.IDX_COST: return base.IDX_COST[sym]
    if sym == "WTI": return 5e-4
    if sym == "XAUUSD": return 5e-4
    if fam in ("Hold",): return 0.0                                  # Hold は月初 5bps(月次)なので取引単位では 0
    return 2 * base.pip_size(sym) / price                             # FX(暗号は pip_size 0.0001 → ≈0・研究系列と同じ)


_HOURLY = {}
def hourly(sym, months):
    """UTC 時間足(open/close の中値)。bid/ask が両方あれば中値、無ければ bid。戻り: DataFrame[t(UTC naive) → open, close, src]"""
    key = sym
    if key in _HOURLY: return _HOURLY[key]
    frames = []
    for side in ("bid", "ask"):
        f = f"data_dukascopy/{sym}_hour{'' if side == 'bid' else '_ask'}.csv.gz"
        if os.path.exists(f):
            d = pd.read_csv(f); d["t"] = pd.to_datetime(d["timestamp"]); d = d.set_index("t")[["open", "close"]]; d.columns = [f"open_{side}", f"close_{side}"]; frames.append(d)
    out = pd.concat(frames, axis=1) if frames else pd.DataFrame()
    for (y, m) in months:
        for side in ("bid", "ask"):
            if len(out) and out.index.max() >= pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0) - pd.Timedelta(days=1): continue
            f = f"forward/q20_monitor_data/{sym}_{y}-{m:02d}_{side}.csv"
            if not os.path.exists(f): f = f"{CACHE}/{sym}_{y}-{m:02d}_{side}.csv"
            if not os.path.exists(f) and dk is not None:
                code = DK_CODE.get(sym, sym)
                st, data = dk.fetch(f"https://datafeed.dukascopy.com/datafeed/{code}/{y}/{m-1:02d}/{side.upper()}_candles_hour_1.bi5", tries=2)
                if st == 200 and data:
                    rows = dk.decode(data, code, y, m); pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume"]).set_index("t").to_csv(f)
            if os.path.exists(f):
                d = pd.read_csv(f, parse_dates=["t"]).set_index("t")[["open", "close"]]; d.columns = [f"open_{side}", f"close_{side}"]
                out = pd.concat([out, d]) if len(out) else d
    out = out[~out.index.duplicated(keep="last")].sort_index() if len(out) else out
    res = pd.DataFrame(index=out.index) if len(out) else pd.DataFrame()
    if len(out):
        if "open_ask" in out.columns and out["open_ask"].notna().any():
            res["open"] = out[["open_bid", "open_ask"]].mean(axis=1); res["close"] = out[["close_bid", "close_ask"]].mean(axis=1)
        else: res["open"] = out["open_bid"]; res["close"] = out["close_bid"]
        res["src"] = "dukascopy"
    # Yahoo 1h で不足月を補う(中値のみ)
    need = [(y, m) for (y, m) in months if not len(res) or (res.index <= pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)).sum() == 0 or res[(res.index.year == y) & (res.index.month == m)].shape[0] < 100]
    if need and sym in YAHOO or (need and len(sym) == 6):
        try:
            import yfinance as yf
            tk = YAHOO.get(sym, f"{sym}=X"); y0 = min(need); y1 = max(need)
            h = yf.download(tk, start=f"{y0[0]}-{y0[1]:02d}-01", end=(pd.Timestamp(y1[0], y1[1], 1) + pd.offsets.MonthEnd(0) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), interval="1h", progress=False, auto_adjust=False)
            if len(h):
                if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
                h.index = pd.DatetimeIndex(h.index).tz_convert("UTC").tz_localize(None) if h.index.tz is not None else pd.DatetimeIndex(h.index)
                h = h[["Open", "Close"]].rename(columns={"Open": "open", "Close": "close"}); h["src"] = "yahoo"
                h = h[[(t.year, t.month) in need for t in h.index]]
                res = pd.concat([res, h]) if len(res) else h; res = res[~res.index.duplicated(keep="first")].sort_index()
        except Exception as e: print(f"  [{sym}] yahoo 失敗 {e!r}")
    _HOURLY[key] = res; return res


def px(h, t, col="open"):
    """t(UTC)の時間足始値(col=open)。その時間の足が無ければ直前の足の終値で代用。"""
    if h is None or not len(h): return np.nan, ""
    t0 = t.floor("h")
    if t0 in h.index: return float(h.at[t0, col]), str(h.at[t0, "src"])
    prev = h.index[h.index <= t0]
    if len(prev) and (t0 - prev[-1]) <= pd.Timedelta(hours=3): return float(h.at[prev[-1], "close"]), str(h.at[prev[-1], "src"])
    return np.nan, ""


def load_positions():
    rows = []
    for f in sorted(glob.glob("ops_inbox/*/positions.csv")):
        acct = os.path.basename(os.path.dirname(f))
        if not acct.isdigit(): continue
        try: d = pd.read_csv(f)
        except Exception: continue
        if not len(d): continue
        d["account"] = acct; rows.append(d)
    if not rows: return pd.DataFrame()
    d = pd.concat(rows, ignore_index=True)
    for c in ("open_time", "close_time"): d[c] = pd.to_datetime(d[c].astype(str).str.strip(), format="%Y.%m.%d %H:%M:%S", errors="coerce")
    d = d[d["close_time"].notna()].copy()
    for c in ("open_time", "close_time"):
        d[c + "_utc"] = d[c].dt.tz_localize(SERVER_TZ, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC").dt.tz_localize(None)
    cls = d["comment"].map(classify); d["fam"] = [c[0] for c in cls]; d["sym"] = [c[1] or norm_sym(s) for c, s in zip(cls, d["symbol"])]; d["shot"] = [c[2] for c in cls]
    d["sign"] = np.where(d["type"].str.lower().str.startswith("sell"), -1.0, 1.0)
    d["sl_hit"] = d.get("sl_hit", False).astype(str).str.lower().eq("true") if "sl_hit" in d.columns else False
    return d


def measure(months):
    d = load_positions()
    if not len(d): print("positions なし"); return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    d = d[[(t.year, t.month) in months for t in d["open_time_utc"]]].copy()     # 建てた月で集計(予定本数と揃える)
    recs = []
    for _, r in d.iterrows():
        h = hourly(r["sym"], months)
        mid_in, src_in = px(h, r["open_time_utc"]); mid_out, src_out = px(h, r["close_time_utc"])
        sched_h = SCHED_HOURS.get(r["fam"])
        t_sched = r["open_time_utc"].floor("h") + pd.Timedelta(hours=sched_h) if sched_h else r["close_time_utc"]
        mid_sched, _ = px(h, t_sched)
        s = r["sign"]; op, cp = float(r["open_price"]), float(r["close_price"])
        real_gross = s * (cp / op - 1) if op else np.nan
        notional = (float(r["profit"]) / real_gross) if (real_gross and abs(real_gross) > 1e-6) else np.nan
        cost_real = ((float(r["commission"]) + float(r["swap"])) / notional) if notional and notional > 0 else np.nan
        paper_gross = s * (mid_out / mid_in - 1) if mid_in and mid_out else np.nan
        paper_sched = s * (mid_sched / mid_in - 1) if mid_in and mid_sched else np.nan
        mc = model_cost(r["fam"], r["sym"], op)
        recs.append(dict(account=r["account"], month=f"{r['open_time_utc'].year}-{r['open_time_utc'].month:02d}", fam=r["fam"], sym=r["sym"], shot=r["shot"], leg=f"{r['fam']}_{r['sym']}" + (f"_h{int(r['shot'])}" if pd.notna(r["shot"]) and r["shot"] is not None else ""),
                         open_utc=r["open_time_utc"], close_utc=r["close_time_utc"], sl_hit=bool(r["sl_hit"]), volume=r["volume"], profit=r["profit"], comm_swap=float(r["commission"]) + float(r["swap"]),
                         notional=notional, real_gross=real_gross, cost_real=cost_real, mid_in=mid_in, mid_out=mid_out, mid_sched=mid_sched, paper_gross=paper_gross, paper_sched=paper_sched, model_cost=mc,
                         slip_in=(-s * (op - mid_in) / mid_in) if mid_in else np.nan, slip_out=(s * (cp - mid_out) / mid_out) if mid_out else np.nan, src=src_in or src_out))
    t = pd.DataFrame(recs)
    if not len(t): return t, pd.DataFrame(), pd.DataFrame()
    # コスト補完(値幅ゼロの取引): レグ中央値
    t["cost_real"] = t.groupby(["account", "leg"])["cost_real"].transform(lambda x: x.fillna(x.median()))
    t["real_net"] = t["real_gross"] + t["cost_real"].fillna(0)
    t["paper_model"] = t["paper_sched"] - t["model_cost"]
    t["timing"] = t["paper_gross"] - t["paper_sched"]
    t["cost_diff"] = t["cost_real"].fillna(0) + t["model_cost"]       # real_cost(負)− model_cost(正の定数を引く) → real_cost + model_cost
    t["gap"] = t["real_net"] - t["paper_model"]
    for c in ("real_gross", "real_net", "cost_real", "paper_gross", "paper_sched", "paper_model", "model_cost", "slip_in", "slip_out", "timing", "cost_diff", "gap"): t[c + "_bps"] = t[c] * 1e4
    # 予定本数(建て損ね): SCHEDULE(配備の予定表)から月ごとに数える。0 本のレグも行として出す
    exp_rows = []
    for acct, legs in SCHEDULE.items():
        for lg in legs:
            dow = PER_WEEK[lg["fam"]][0]; since = pd.Timestamp(lg["since"]); until = pd.Timestamp(lg.get("until", "2099-12-31")); skip = set(pd.to_datetime(lg.get("skip", [])))
            for (y, m) in months:
                days = pd.date_range(f"{y}-{m:02d}-01", pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0), freq="D")
                n_days = sum(1 for dd in days if dd.dayofweek == dow and since <= dd <= until and dd not in skip)
                exp_rows.append(dict(account=acct, month=f"{y}-{m:02d}", fam=lg["fam"], sym=lg["sym"], n_expected=n_days * lg["shots"]))
    exp = pd.DataFrame(exp_rows)
    agg = t.groupby(["account", "month", "fam", "sym"]).agg(n=("gap", "size"), sl_rate=("sl_hit", "mean"), real_net_bps=("real_net_bps", "mean"), paper_model_bps=("paper_model_bps", "mean"), gap_bps=("gap_bps", "mean"),
                                                            slip_in_bps=("slip_in_bps", "mean"), slip_out_bps=("slip_out_bps", "mean"), cost_real_bps=("cost_real_bps", "mean"), model_cost_bps=("model_cost_bps", "mean"), timing_bps=("timing_bps", "mean"),
                                                            profit=("profit", "sum"), comm_swap=("comm_swap", "sum"), src=("src", lambda x: ",".join(sorted(set(x))))).reset_index()
    # 予定表のレグ名(JPY5 等の束)は実レグ(個別通貨)と束ねて照合する
    fam_tot = agg.groupby(["account", "month", "fam"])["n"].sum().reset_index().rename(columns={"n": "n_fam"})
    exp = exp.merge(fam_tot, on=["account", "month", "fam"], how="left"); exp["n_fam"] = exp["n_fam"].fillna(0).astype(int)
    exp["miss_rate"] = np.where(exp["n_expected"] > 0, 1 - exp["n_fam"] / exp["n_expected"].replace(0, np.nan), np.nan)
    agg["decomp"] = np.where(agg["fam"].isin(["Mon", "Roll", "Sess", "S1", "S2", "S3"]), "ok", "参考(分単位の出口)")
    return t, agg, exp




def main():
    args = sys.argv[1:]
    if not args:
        today = dt.date.today(); prev = (pd.Timestamp(today) - pd.offsets.MonthBegin(1)).to_period("M"); args = [str(prev), today.strftime("%Y-%m")]
    months = [tuple(map(int, a.split("-"))) for a in args]
    t, agg, exp = measure(months)
    if not len(t): return
    os.makedirs("results", exist_ok=True)
    t.to_csv("results/exec_gap_trades.csv", index=False)
    for mo in sorted(agg["month"].unique()):
        a = agg[agg["month"] == mo].copy(); a.to_csv(f"results/exec_gap_{mo}.csv", index=False)
        print(f"\n== {mo} 口座 × レグ(bps/取引・平均)==")
        cols = ["account", "fam", "sym", "n", "sl_rate", "real_net_bps", "paper_model_bps", "gap_bps", "slip_in_bps", "slip_out_bps", "cost_real_bps", "model_cost_bps", "timing_bps", "profit", "decomp", "src"]
        print(a[cols].round(2).to_string(index=False))
        e = exp[exp["month"] == mo]
        if len(e):
            e.to_csv(f"results/exec_gap_expected_{mo}.csv", index=False)
            print(f"-- {mo} 建て損ね(予定表 SCHEDULE)--"); print(e[["account", "fam", "sym", "n_expected", "n_fam", "miss_rate"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
