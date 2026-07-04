"""
edge22_onchain.py — BTCオンチェーン批次【事前登録 docs/108】。
CoinMetricsコミュニティ btc.csv(CapMVRVCur/HashRate/PriceUSD)。サンプル2011-01-01〜。
H22a MVRV-VALUE : MVRV<1.0 → 条件成立中 翌日LONG
H22b HASH-CAPIT : HashRate30日平均が60日前比−15%以下 → 翌日から90日LONG(再トリガー延長)
ゲート: dir/ドリフト保存プラセボp≤0.05(Bonf 0.025)/split両半/2×コスト(片道10bp)/保有15%年/対ベータ/DD≥−20%
"""
import os, json, time, hashlib, urllib.request
import numpy as np, pandas as pd

LOCAL, OUT = "./research/data", "./research/results/edge22_onchain.json"
COST1, HOLD_STRESS, PERM_N, SEED = 0.0010, 0.15, 2000, 22
URL = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv"

def data():
    path = f"{LOCAL}/coinmetrics_btc.csv"
    if not os.path.exists(path):
        for k in range(5):
            try:
                req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
                open(path, "wb").write(urllib.request.urlopen(req, timeout=180).read()); break
            except Exception:
                if k == 4: raise
                time.sleep(2 ** k)
    df = pd.read_csv(path, usecols=["time", "CapMVRVCur", "HashRate", "PriceUSD"])
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time").sort_index()
    df = df[df.index >= "2010-10-01"]  # 2011-01-01検定開始のためのウォームアップ含む
    df["ret_next"] = df["PriceUSD"].pct_change().shift(-1)
    h30 = df["HashRate"].rolling(30).mean()
    df["hashchg"] = h30 / h30.shift(60) - 1
    return df

def evaluate(df, hid, rng):
    if hid == "H22a":
        on = (df["CapMVRVCur"] < 1.0); sigcol = "CapMVRVCur"
    else:
        trig = (df["hashchg"] <= -0.15)
        on = trig.rolling(90, min_periods=1).max().astype(bool); sigcol = "hashchg"
    m = (df.index >= "2011-01-01") & df["ret_next"].notna() & df[sigcol].notna()
    p = on[m].astype(float).values
    r = df.loc[m, "ret_next"].values
    n, on_n = len(r), int(p.sum())
    if on_n < 30:
        return {"id": hid, "n_days": n, "on_days": on_n, "verdict": "REJECT", "note": "ON日数不足"}
    gross = float((p * r).sum())
    turn = float(np.abs(np.diff(np.concatenate([[0.0], p]))).sum())
    net = gross - turn * COST1
    net2x = gross - turn * COST1 * 2
    hold = net - on_n * HOLD_STRESS / 365
    sims = np.array([r[rng.choice(n, size=on_n, replace=False)].sum() for _ in range(PERM_N)])
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
            "net_2xcost": round(net2x, 4), "net_hold15": round(hold, 4),
            "perm_p": round(pval, 4), "beta_take": round(beta, 4),
            "excess_vs_beta": round(excess, 4), "net_half1": round(net_a, 4),
            "net_half2": round(net_b, 4), "maxdd_lev1": round(maxdd, 4),
            "gates": {k: bool(v) for k, v in gates.items()}, "verdict": verdict}

def main():
    os.makedirs(LOCAL, exist_ok=True); os.makedirs("./research/results", exist_ok=True)
    df = data()
    rng = np.random.default_rng(SEED)
    out = {"doc": "docs/108", "range": [str(df.index[0].date()), str(df.index[-1].date())],
           "cost_oneway": COST1, "hold_stress": HOLD_STRESS,
           "results": [evaluate(df, h, rng) for h in ("H22a", "H22b")],
           "input_sha256": hashlib.sha256(open(f"{LOCAL}/coinmetrics_btc.csv", "rb").read()).hexdigest()}
    for r in out["results"]:
        print(r["id"], {k: r[k] for k in ("verdict", "net_sum", "perm_p", "on_ratio") if k in r})
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    print("saved:", OUT)

if __name__ == "__main__":
    main()
