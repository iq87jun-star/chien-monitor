"""
edge20_cot.py — CFTC CoT建玉批次【事前登録 docs/104】。
CoT legacy(1986〜)の投機筋ネット÷OI(火曜時点・金曜公表)→ 公表金曜終値で建て翌週金曜まで保有。
H20a SPEC-CONTRA: 156週分位≥90%→SHORT/≤10%→LONG(ON市場等ウェイト)
H20b POS-MOM   : 13週変化の符号に順張り(全市場等ウェイト1/7)
ゲート: dir/円環シフトプラセボp≤0.05(Bonf 0.025)/pre-2016と2016+両+/2×コスト/保有5%年/対ベータ/DD≥−20%
"""
import os, io, json, time, lzma, struct, hashlib, zipfile, urllib.request
import numpy as np, pandas as pd

LOCAL, OUT = "./research/data", "./research/results/edge20_cot.json"
COST1, HOLD_STRESS, PERM_N, SEED = 0.0005, 0.05, 2000, 20
CODES = {"097741": "JPY", "099741": "EUR", "096742": "GBP", "232741": "AUD",
         "090741": "CAD", "092741": "CHF", "067651": "WTI"}
# docs/104 修正1: 価格はDukascopy日足BID。-1=逆数(外貨ロングに揃える)。バンドはスケール自動判定用
DUKA = {"JPY": ("USDJPY", -1, (50, 400)), "EUR": ("EURUSD", +1, (0.5, 2.5)),
        "GBP": ("GBPUSD", +1, (0.8, 3.0)), "AUD": ("AUDUSD", +1, (0.3, 2.0)),
        "CAD": ("USDCAD", -1, (0.9, 2.0)), "CHF": ("USDCHF", -1, (0.5, 3.0)),
        "WTI": ("LIGHTCMDUSD", +1, (5, 250))}

def _get(url, path):
    if not os.path.exists(path):
        for k in range(5):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                d = urllib.request.urlopen(req, timeout=120).read()
                open(path, "wb").write(d); break
            except Exception:
                if k == 4: raise
                time.sleep(2 ** k)
    return path

def cot():
    files = [_get("https://www.cftc.gov/files/dea/history/deacot1986_2016.zip",
                  f"{LOCAL}/deacot1986_2016.zip")]
    for y in range(2017, 2027):
        files.append(_get(f"https://www.cftc.gov/files/dea/history/deacot{y}.zip",
                          f"{LOCAL}/deacot{y}.zip"))
    frames = []
    for f in files:
        z = zipfile.ZipFile(f)
        name = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
        df = pd.read_csv(io.BytesIO(z.read(name)), dtype=str, low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        col = {c.lower(): c for c in df.columns}
        code = col[[c for c in col if "contract market code" in c][0]]
        date = col[[c for c in col if "yyyy-mm-dd" in c][0]]
        ncl = col[[c for c in col if c.startswith("noncommercial positions-long (all)")][0]]
        ncs = col[[c for c in col if c.startswith("noncommercial positions-short (all)")][0]]
        oi = col[[c for c in col if c.startswith("open interest (all)")][0]]
        d = df[[code, date, ncl, ncs, oi]].copy()
        d.columns = ["code", "date", "ncl", "ncs", "oi"]
        d["code"] = d["code"].str.strip()
        d = d[d["code"].isin(CODES)]
        frames.append(d)
    d = pd.concat(frames)
    d["date"] = pd.to_datetime(d["date"].str.strip())
    for c in ("ncl", "ncs", "oi"):
        d[c] = pd.to_numeric(d[c].str.strip(), errors="coerce")
    d = d.dropna().drop_duplicates(["code", "date"], keep="last")
    d["spec"] = (d["ncl"] - d["ncs"]) / d["oi"]
    out = {}
    for c, sym in CODES.items():
        s = d[d["code"] == c].set_index("date")["spec"].sort_index()
        out[sym] = s
    return out

def duka_daily(inst, band):
    """Dukascopy日足BID終値(年ファイル・[t,o,c,l,h,v] big-endian・スケール自動判定)"""
    vals = {}
    for y in range(1990, 2027):
        path = f"{LOCAL}/duka_{inst}_{y}.bi5"
        if not os.path.exists(path):
            try:
                req = urllib.request.Request(
                    f"https://datafeed.dukascopy.com/datafeed/{inst}/{y}/BID_candles_day_1.bi5",
                    headers={"User-Agent": "Mozilla/5.0"})
                open(path, "wb").write(urllib.request.urlopen(req, timeout=60).read())
            except Exception:
                open(path, "wb").write(b"")
            time.sleep(0.15)
        raw = open(path, "rb").read()
        if not raw: continue
        try:
            b = lzma.decompress(raw)
        except Exception:
            continue
        for i in range(0, len(b), 24):
            t, o, c, lo, hi, v = struct.unpack(">5If", b[i:i+24])
            vals[pd.Timestamp(f"{y}-01-01") + pd.Timedelta(seconds=t)] = c
    s = pd.Series(vals).sort_index()
    med = s.median()
    for scale in (1e5, 1e3, 1e2, 1.0):
        if band[0] <= med / scale <= band[1]:
            s = s / scale; break
    else:
        raise ValueError(f"{inst}: scale判定不能 median={med}")
    s = s[s > 0]
    return s[s != s.shift()]  # 週末/休日のフラット複製行を除去

def prices():
    out = {}
    for sym, (inst, sign, band) in DUKA.items():
        s = duka_daily(inst, band)
        out[sym] = (1.0 / s) if sign < 0 else s
        print(f"  price {sym}({inst}): {s.index[0].date()}〜{s.index[-1].date()} {len(s)}日")
    return out

def weekly_frames():
    spec, px = cot(), prices()
    rows = {}
    for sym in CODES.values():
        s, p = spec[sym], px[sym]
        ent, sv = [], []
        for t, v in s.items():
            rel = t + pd.Timedelta(days=3)              # 火曜→金曜公表
            idx = p.index[p.index >= rel]
            if len(idx) == 0: continue
            ent.append(idx[0]); sv.append(v)
        f = pd.DataFrame({"entry": ent, "spec": sv}).drop_duplicates("entry").set_index("entry")
        f["px"] = p.reindex(f.index)
        f["ret_next"] = f["px"].shift(-1) / f["px"] - 1  # 今週金曜→翌週金曜
        f["pct156"] = f["spec"].rolling(156).rank(pct=True)
        f["mom13"] = f["spec"] - f["spec"].shift(13)
        rows[sym] = f
    return rows

def portfolio(rows, hid):
    idx = sorted(set().union(*[f.index for f in rows.values()]))
    W = pd.DataFrame(0.0, index=idx, columns=list(rows))
    R = pd.DataFrame(np.nan, index=idx, columns=list(rows))
    for sym, f in rows.items():
        if hid == "H20a":
            w = pd.Series(0.0, index=f.index)
            w[f["pct156"] >= 0.90] = -1.0
            w[f["pct156"] <= 0.10] = +1.0
        else:
            w = np.sign(f["mom13"]).fillna(0.0)
        W.loc[f.index, sym] = w.values
        R.loc[f.index, sym] = f["ret_next"].values
    if hid == "H20a":
        n_on = (W != 0).sum(axis=1)
        W = W.div(n_on.replace(0, np.nan), axis=0).fillna(0.0)
    else:
        W = W / len(rows)
    W[R.isna()] = 0.0
    return W, R.fillna(0.0)

def evaluate(W, R, rng):
    dates = W.index
    gross_w = (W * R).sum(axis=1)
    gross = float(gross_w.sum())
    turn = float(W.diff().abs().sum().sum())
    expo = float(W.abs().sum(axis=1).mean())
    net = gross - turn * COST1
    net2x = gross - turn * COST1 * 2
    hold = net - expo * HOLD_STRESS / 52 * len(dates)
    sims = np.empty(PERM_N)
    Wv, Rv = W.values, R.values
    for i in range(PERM_N):
        g = 0.0
        for j in range(Wv.shape[1]):
            k = rng.integers(1, len(dates))
            g += float((np.roll(Wv[:, j], k) * Rv[:, j]).sum())
        sims[i] = g
    pval = float((sims >= gross).mean())
    beta = float(sum(Wv[:, j].mean() * Rv[:, j].sum() for j in range(Wv.shape[1])))
    excess = gross - beta
    pre = dates < pd.Timestamp("2016-01-01")
    def _net(msk):
        g = float(gross_w[msk].sum())
        t = float(W[msk].diff().abs().sum().sum())
        return g - t * COST1
    net_pre, net_post = _net(pre), _net(~pre)
    cost_w = W.diff().abs().sum(axis=1).fillna(W.abs().sum(axis=1)) * COST1
    eq = (1 + gross_w - cost_w).cumprod()
    maxdd = float((eq / eq.cummax() - 1).min())
    gates = {"G_dir": net > 0, "G_p": pval <= 0.05, "G_p_bonf": pval <= 0.025,
             "G_split_pre2016": net_pre > 0, "G_split_2016plus": net_post > 0,
             "G_cost": net2x > 0, "G_hold": hold > 0, "G_beta": excess > 0,
             "G_dd": maxdd >= -0.20}
    core = ["G_dir", "G_p", "G_split_pre2016", "G_split_2016plus", "G_cost", "G_hold", "G_beta", "G_dd"]
    npass = sum(gates[g] for g in core)
    if npass == len(core): verdict = "STRONG-LEAD" if gates["G_p_bonf"] else "LEAD"
    elif gates["G_p"] and npass >= 5: verdict = "LEAD"
    elif net > 0 and pval <= 0.10: verdict = "参考"
    else: verdict = "REJECT"
    return {"n_weeks": len(dates), "avg_gross_exposure": round(expo, 3),
            "gross_sum": round(gross, 4), "net_sum": round(net, 4),
            "net_2xcost": round(net2x, 4), "net_hold5": round(hold, 4),
            "perm_p": round(pval, 4), "beta_take": round(beta, 4),
            "excess_vs_beta": round(excess, 4), "net_pre2016": round(net_pre, 4),
            "net_2016plus": round(net_post, 4), "maxdd_lev1": round(maxdd, 4),
            "gates": {k: bool(v) for k, v in gates.items()}, "verdict": verdict}

def main():
    os.makedirs(LOCAL, exist_ok=True); os.makedirs("./research/results", exist_ok=True)
    rows = weekly_frames()
    rng = np.random.default_rng(SEED)
    out = {"doc": "docs/104", "markets": list(CODES.values()), "cost_oneway": COST1,
           "hold_stress": HOLD_STRESS, "results": {}}
    for hid in ("H20a", "H20b"):
        W, R = portfolio(rows, hid)
        res = evaluate(W, R, rng)
        # 市場別内訳(参考)
        res["per_market_net"] = {s: round(float((W[s] * R[s]).sum()
                                 - W[s].diff().abs().sum() * COST1), 4) for s in W}
        out["results"][hid] = res
        print(hid, {k: res[k] for k in ("verdict", "net_sum", "perm_p", "net_pre2016", "net_2016plus")})
    h = hashlib.sha256()
    for f in sorted(os.listdir(LOCAL)):
        if f.startswith(("deacot", "duka_")): h.update(open(f"{LOCAL}/{f}", "rb").read())
    out["input_sha256"] = h.hexdigest()
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    print("saved:", OUT)

if __name__ == "__main__":
    main()
