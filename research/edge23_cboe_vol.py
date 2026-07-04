"""
edge23_cboe_vol.py — CBOEボラ派生指数批次【事前登録 docs/110】。
SKEW(1990〜)/VVIX(2006〜)公式CSV + Dukascopy USA500IDXUSD 日足BID。
H23a VVIX-SPIKE-L: VVIX≥120 → 翌日から5営業日LONG(再トリガー延長)
H23b SKEW-TAIL-S : SKEW≥150 → 翌日から10営業日SHORT(再トリガー延長)
ゲート: dir/ドリフト保存プラセボp≤0.05(Bonf 0.025)/split両半/2×コスト(片道1.5bp)/保有3%年/対ベータ/DD≥−20%
"""
import os, json, time, lzma, struct, hashlib, urllib.request
import numpy as np, pandas as pd

LOCAL, OUT = "./research/data", "./research/results/edge23_cboe_vol.json"
COST1, HOLD_STRESS, PERM_N, SEED = 0.00015, 0.03, 2000, 23

def _get(url, path):
    if not os.path.exists(path):
        for k in range(5):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                open(path, "wb").write(urllib.request.urlopen(req, timeout=60).read()); break
            except Exception:
                if k == 4: raise
                time.sleep(2 ** k)
    return path

def cboe(name):
    p = _get(f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv",
             f"{LOCAL}/cboe_{name}.csv")
    df = pd.read_csv(p)
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                  index=pd.to_datetime(df.iloc[:, 0])).dropna()
    return s

def us500_daily():
    vals = {}
    for y in range(2005, 2027):
        path = f"{LOCAL}/duka_USA500IDXUSD_{y}.bi5"
        if not os.path.exists(path):
            try:
                req = urllib.request.Request(
                    f"https://datafeed.dukascopy.com/datafeed/USA500IDXUSD/{y}/BID_candles_day_1.bi5",
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
            vals[pd.Timestamp(f"{y}-01-01") + pd.Timedelta(seconds=t)] = c / 1000.0
    s = pd.Series(vals).sort_index()
    return s[s != s.shift()]  # 週末/休日フラット行を除去

def evaluate(df, hid, rng):
    if hid == "H23a":
        trig = df["vvix"] >= 120; hold_days, d = 5, +1; sigcol = "vvix"
    else:
        trig = df["skew"] >= 150; hold_days, d = 10, -1; sigcol = "skew"
    on = trig.rolling(hold_days, min_periods=1).max().astype(bool).shift(1).fillna(False)
    m = df["ret"].notna() & df[sigcol].shift(1).notna()
    p = on[m].astype(float).values * d
    r = df.loc[m, "ret"].values
    n, on_n = len(r), int((p != 0).sum())
    if on_n < 30:
        return {"id": hid, "n_days": n, "on_days": on_n, "verdict": "REJECT", "note": "ON日数不足"}
    gross = float((p * r).sum())
    turn = float(np.abs(np.diff(np.concatenate([[0.0], p]))).sum())
    net = gross - turn * COST1
    net2x = gross - turn * COST1 * 2
    hold = net - on_n * HOLD_STRESS / 365
    sims = np.array([d * r[rng.choice(n, size=on_n, replace=False)].sum() for _ in range(PERM_N)])
    pval = float((sims >= gross).mean())
    beta = float(p.mean() * r.sum()); excess = gross - beta
    half = n // 2
    def _net(pp, rr):
        return float((pp * rr).sum()) - float(np.abs(np.diff(np.concatenate([[0.0], pp]))).sum()) * COST1
    net_a, net_b = _net(p[:half], r[:half]), _net(p[half:], r[half:])
    eq = np.cumprod(1 + p * r - np.abs(np.diff(np.concatenate([[0.0], p]))) * COST1)
    maxdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    gates = {"G_dir": net > 0, "G_p": pval <= 0.05, "G_p_bonf": pval <= 0.025,
             "G_split": (net_a > 0) and (net_b > 0), "G_cost": net2x > 0,
             "G_hold": hold > 0, "G_beta": excess > 0, "G_dd": maxdd >= -0.20}
    core = ["G_dir", "G_p", "G_split", "G_cost", "G_hold", "G_beta", "G_dd"]
    npass = sum(gates[g] for g in core)
    if npass == len(core): verdict = "STRONG-LEAD" if gates["G_p_bonf"] else "LEAD"
    elif gates["G_p"] and npass >= 4: verdict = "LEAD"
    elif net > 0 and pval <= 0.10: verdict = "参考"
    else: verdict = "REJECT"
    return {"id": hid, "n_days": n, "on_days": on_n, "on_ratio": round(on_n / n, 3),
            "gross_sum": round(gross, 4), "net_sum": round(net, 4),
            "net_2xcost": round(net2x, 4), "net_hold3": round(hold, 4),
            "perm_p": round(pval, 4), "beta_take": round(beta, 4),
            "excess_vs_beta": round(excess, 4), "net_half1": round(net_a, 4),
            "net_half2": round(net_b, 4), "maxdd_lev1": round(maxdd, 4),
            "gates": {k: bool(v) for k, v in gates.items()}, "verdict": verdict}

def main():
    os.makedirs(LOCAL, exist_ok=True); os.makedirs("./research/results", exist_ok=True)
    px = us500_daily()
    vvix, skew = cboe("VVIX"), cboe("SKEW")
    n_anom = int((vvix < 50).sum())
    vvix = vvix[vvix >= 50]  # docs/110 事前明記の異常値除外
    df = pd.DataFrame({"px": px})
    df["ret"] = df["px"].pct_change()
    df["vvix"] = vvix.reindex(df.index)
    df["skew"] = skew.reindex(df.index)
    rng = np.random.default_rng(SEED)
    out = {"doc": "docs/110", "px_range": [str(df.index[0].date()), str(df.index[-1].date())],
           "vvix_anomalies_dropped": n_anom, "cost_oneway": COST1, "hold_stress": HOLD_STRESS,
           "results": [evaluate(df, h, rng) for h in ("H23a", "H23b")]}
    h = hashlib.sha256()
    for f in sorted(os.listdir(LOCAL)):
        if f.startswith(("cboe_", "duka_USA500IDXUSD_")): h.update(open(f"{LOCAL}/{f}", "rb").read())
    out["input_sha256"] = h.hexdigest()
    for r in out["results"]:
        print(r["id"], {k: r[k] for k in ("verdict", "net_sum", "perm_p", "on_ratio") if k in r})
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    print("saved:", OUT)

if __name__ == "__main__":
    main()
