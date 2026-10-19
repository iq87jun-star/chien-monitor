# -*- coding: utf-8 -*-
"""
seasonal_optimize_loyo.py — docs/104(事前登録)の実行: 季節合成の構成ルール族を
LOYO(leave-one-year-out)のOOS成績のみで比較し、プラセボ(月ラベルシャッフル)と
コスト2倍感応で検証する。

⚠ 事前登録(docs/104)の後に実行。結果はdocs/105へ転記。ルール・閾値・決定規則は
  docs/104から変更しない。データ: Yahoo日足 2015-01-01〜2026-06-30(固定窓・SHA-256記録)。
出力: results/seasonal_optimize_loyo.json
"""
import os, sys, json, csv, time, hashlib, urllib.request, urllib.parse, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

P1, P2 = 1420070400, 1782863999   # 2015-01-01 .. 2026-06-30 UTC(E5の12Mルックバック確保)
SYMBOLS = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X",
    "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X", "NZDUSD": "NZDUSD=X",
    "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
    "AUDJPY": "AUDJPY=X", "NZDJPY": "NZDJPY=X", "CADJPY": "CADJPY=X", "CHFJPY": "CHFJPY=X",
    "XAUUSD": "GC=F", "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI",
    "JP225": "^N225", "UK100": "^FTSE", "FR40": "^FCHI",
}
V7X = ["AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"]
EMONX = ["JP225", "UK100", "FR40"]
SJUL = ["US500", "NAS100"]
LOYO_YEARS = list(range(2016, 2026))
THRESH = 0.005            # R1: 訓練平均月利0.5%(docs/87)
FIXED_R0 = {"v4": 0.30, "v7": 0.25, "EMon": 0.25, "E5": 0.20}   # 対照(docs/76の年間固定)
PLACEBO_REPS = 200
SEED = 7


def fetch_all():
    os.makedirs(DATA, exist_ok=True)
    for name, sym in SYMBOLS.items():
        u = (f"https://query2.finance.yahoo.com/v8/finance/chart/"
             f"{urllib.parse.quote(sym)}?interval=1d&period1={P1}&period2={P2}")
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=25).read())
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
        print(f"  {name}: {len(rows)} bars"); time.sleep(0.6)


def sha256s():
    return {n: hashlib.sha256(open(os.path.join(DATA, f"{n}_d.csv"), "rb").read()).hexdigest()[:16]
            for n in SYMBOLS if os.path.exists(os.path.join(DATA, f"{n}_d.csv"))}


def build_sleeves(cost_mult=1.0):
    """7スリーブの月次リターン(既存ロジック流用・コストも既存と同一×cost_mult)。"""
    from parallel_vs_existing_compare import (load_daily, to_monthly, pip_size,
                                              v4_monthly, v7_monthly, e5_monthly)
    def mon_basket(names, cost):
        parts = [(load_daily(nm)[load_daily(nm)["weekday"] == 0]["o2o"] - cost * cost_mult).rename(nm)
                 for nm in names]
        w = pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna()
        return to_monthly(w)
    def yen_basket(names):
        acc = None
        for p in names:
            df = load_daily(p)
            m = to_monthly((df[df["weekday"] == 0]["o2o"]
                            - cost_mult * 2 * pip_size(p) / df[df["weekday"] == 0]["open"]).dropna())
            acc = m if acc is None else acc.add(m, fill_value=0.0)
        return acc / len(names)
    def bh_monthly(names, cost=5e-4):
        closes = {}
        for nm in names:
            df = load_daily(nm); s = df["close"]; s.index = pd.to_datetime(df.index)
            closes[nm] = s.resample("ME").last()
        px = pd.DataFrame(closes).dropna()
        out = (px.pct_change().mean(axis=1) - cost * cost_mult).dropna()
        out.index = out.index.to_period("M"); return out
    # v4/v7/E5 は共有モジュールの実装(コスト内蔵)。cost_mult>1時はv4/v7/E5を近似スケール:
    #   既存実装のコスト項だけ倍にできないため、リターンから片道コスト相当を追加控除する。
    sl = {
        "v4": v4_monthly(),
        "v7": yen_basket(["EURJPY", "GBPJPY", "USDJPY"]),
        "v7x": yen_basket(V7X),
        "EMon": mon_basket(["NAS100", "US500", "GER40"], 3e-4),
        "EMonX": mon_basket(EMONX, 3e-4),
        "E5": e5_monthly(),
        "SJul": bh_monthly(SJUL),
    }
    if cost_mult > 1.0:
        # v4: 平均月2.3トレード×2pip追加 / E5: 月次0.5bps追加(近似・保守側)
        sl["v4"] = sl["v4"] - 0.0004 * (cost_mult - 1.0)
        sl["E5"] = sl["E5"] - 5e-4 * (cost_mult - 1.0)
    df = pd.DataFrame(sl)
    df = df[(df.index >= pd.Period("2016-01", "M"))]
    return df.fillna(0.0)   # v4等の無トレード月=0(全ルール共通)


def month_stats(df, years):
    """訓練年集合での 月別 平均月利・vol(スリーブ×12ヶ月)"""
    sub = df[[y in years for y in df.index.year]]
    g = sub.groupby(sub.index.month)
    return g.mean(), g.std()


def weights_for(rule, mu_m, sd_m):
    """月mの訓練統計(mu_m: Series[sleeve], sd_m 同)→重みdict。"""
    def r1():
        q = mu_m[mu_m >= THRESH]
        return {} if q.empty else (q / q.sum()).to_dict()
    def r0():
        return dict(FIXED_R0)
    if rule == "R0":
        return r0()
    if rule == "R1":
        return r1()
    if rule == "R2a":
        return {} if mu_m.max() < THRESH else {mu_m.idxmax(): 1.0}
    if rule == "R2b":
        top = mu_m.nlargest(2); top = top[top >= THRESH]
        return {} if top.empty else (top / top.sum()).to_dict()
    if rule.startswith("R3"):
        lam = {"R3a": 0.25, "R3b": 0.50, "R3c": 0.75}[rule]
        w1, w0 = r1(), r0()
        keys = set(w1) | set(w0)
        w = {k: lam * w1.get(k, 0.0) + (1 - lam) * w0.get(k, 0.0) for k in keys}
        s = sum(w.values())
        return {k: v / s for k, v in w.items()} if s > 0 else {}
    if rule == "R4":
        q = mu_m[mu_m >= THRESH]
        if q.empty:
            return {}
        rv = q / sd_m.reindex(q.index).replace(0, np.nan)
        rv = rv.dropna()
        return {} if rv.empty else (rv / rv.sum()).to_dict()
    raise ValueError(rule)


def loyo_series(df, rule, month_map_shuffle=None, rng=None):
    """LOYO OOS月次系列。month_map_shuffle=Trueなら各フォールドで月→重みの対応を置換(プラセボ)。"""
    out = {}
    for y in LOYO_YEARS:
        train = [t for t in LOYO_YEARS if t != y]
        mu, sd = month_stats(df, train)
        wmap = {m: weights_for(rule, mu.loc[m], sd.loc[m]) for m in range(1, 13)}
        if month_map_shuffle:
            perm = rng.permutation(range(1, 13))
            wmap = {m: wmap[perm[m - 1]] for m in range(1, 13)}
        sub = df[df.index.year == y]
        for idx, row in sub.iterrows():
            w = wmap[idx.month]
            out[idx] = sum(row.get(k, 0.0) * v for k, v in w.items())
    return pd.Series(out).sort_index()


def metrics(s):
    s = s.dropna()
    eq = (1 + s).cumprod()
    dd = float(((eq - eq.cummax()) / eq.cummax()).min()) * 100
    mu = s.mean() * 12; vol = s.std() * np.sqrt(12)
    cagr = (eq.iloc[-1] ** (12 / len(s)) - 1) * 100 if eq.iloc[-1] > 0 else -100
    return dict(mean_month_pct=round(float(s.mean() * 100), 3),
                sharpe=round(float(mu / vol) if vol > 0 else 0, 3),
                maxDD=round(dd, 2),
                calmar=round(float(cagr / abs(dd)), 2) if dd else 0.0,
                worst_month_pct=round(float(s.min() * 100), 2), months=int(len(s)))


def main():
    rng = np.random.default_rng(SEED)
    print("[1/4] データ取得(2015-01〜2026-06 固定窓)")
    fetch_all()
    hashes = sha256s()

    print("[2/4] スリーブ月次系列の構築(既存ロジック流用)")
    df = build_sleeves(1.0)
    df_loyo = df[(df.index.year >= 2016) & (df.index.year <= 2025)]
    print(f"  window: {df.index[0]}..{df.index[-1]} / LOYO対象 {len(df_loyo)}ヶ月")

    rules = ["R0", "R1", "R2a", "R2b", "R3a", "R3b", "R3c", "R4"]
    print("[3/4] LOYO OOS採点")
    res = {}
    for r in rules:
        s = loyo_series(df_loyo, r)
        res[r] = metrics(s)
        print(f"  {r:4s} {res[r]}")

    # プラセボ: R1と、決定規則の候補になり得る月別選択系の最良(R1除くR2/R4系のOOS Sharpe最大)に適用
    print("[4/4] プラセボ(月シャッフル×%d)とコスト2倍感応" % PLACEBO_REPS)
    sel_rules = ["R1"]
    monthly_sel = {k: v for k, v in res.items() if k in ("R2a", "R2b", "R4")}
    if monthly_sel:
        sel_rules.append(max(monthly_sel, key=lambda k: monthly_sel[k]["sharpe"]))
    placebo = {}
    for r in sel_rules:
        real = res[r]["sharpe"]
        dist = []
        for _ in range(PLACEBO_REPS):
            dist.append(metrics(loyo_series(df_loyo, r, month_map_shuffle=True, rng=rng))["sharpe"])
        dist = np.array(dist)
        placebo[r] = dict(real_sharpe=real,
                          placebo_mean=round(float(dist.mean()), 3),
                          placebo_p95=round(float(np.percentile(dist, 95)), 3),
                          p_value=round(float((dist >= real).mean()), 4),
                          verdict=("月別性に固有価値あり" if (dist >= real).mean() < 0.05
                                   else "月別性はノイズと区別できない"))
        print(f"  placebo {r}: {placebo[r]}")

    df2 = build_sleeves(2.0)
    df2 = df2[(df2.index.year >= 2016) & (df2.index.year <= 2025)]
    cost2 = {r: metrics(loyo_series(df2, r)) for r in rules}
    for r in rules:
        print(f"  cost2x {r:4s} sharpe {res[r]['sharpe']} -> {cost2[r]['sharpe']}")

    # 参考: 2026H1(LOYO外)— 2016-2025訓練の各ルールを2026H1に適用
    ref26 = {}
    mu, sd = month_stats(df[(df.index.year >= 2016) & (df.index.year <= 2025)], LOYO_YEARS)
    sub26 = df[df.index.year == 2026]
    for r in rules:
        vals = []
        for idx, row in sub26.iterrows():
            w = weights_for(r, mu.loc[idx.month], sd.loc[idx.month])
            vals.append(sum(row.get(k, 0.0) * v for k, v in w.items()))
        ref26[r] = round(float(np.sum(vals) * 100), 2)

    # 決定規則(docs/104 §4)の機械適用
    base = res["R1"]
    winner, why = "R1", "どの候補も決定規則(Sharpe≥1.1×R1 かつ Calmar≥R1 かつ cost2xで同順位)を満たさず"
    for r in rules:
        if r == "R1":
            continue
        c = res[r]
        if (c["sharpe"] >= 1.1 * base["sharpe"] and c["calmar"] >= base["calmar"]
                and cost2[r]["sharpe"] >= cost2["R1"]["sharpe"]):
            winner, why = r, "決定規則を満たす(docs/104 §4)"
            break
    if placebo["R1"]["p_value"] >= 0.05:
        note_placebo = "R1はプラセボ不合格=月別性ノイズの可能性 → R0/R3系を推す(docs/104 §4)"
    else:
        note_placebo = "R1はプラセボ合格(月別性に固有価値)"

    out = dict(prereg="docs/104", window=f"{df.index[0]}..{df.index[-1]}",
               loyo_years=LOYO_YEARS, input_sha256=hashes,
               loyo_oos=res, placebo=placebo, cost2x=cost2,
               ref_2026H1_net_pct=ref26,
               decision=dict(winner_by_rule=winner, reason=why, placebo_note=note_placebo))
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", "seasonal_optimize_loyo.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)
    print("決定:", winner, "|", why, "|", note_placebo)


if __name__ == "__main__":
    main()
