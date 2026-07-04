"""
edge19b_deribit_replication.py — H19a の別ソース再現【事前登録 docs/102】。
Deribit BTC-PERPETUAL の時間別 funding(interest_8h)と index_price のみ使用(Binance不使用)。
凍結ルール: F3d=直近72hのinterest_8h平均 <0 → 翌日LONG。片道10bp・2×/保有15%年ストレス。
判定: 6ゲート(dir/プラセボp≤0.05/split両半/2×コスト/保有/対ベータ)全通過=再現成立。G-ddは記録のみ。
"""
import os, json, time, hashlib, urllib.request
import numpy as np, pandas as pd

LOCAL = "./research/data"
OUT = "./research/results/edge19b_deribit_replication.json"
COST1, HOLD_STRESS, PERM_N, SEED = 0.0010, 0.15, 2000, 19

def fetch_deribit():
    path = f"{LOCAL}/deribit_funding_BTC.csv"
    if not os.path.exists(path):
        rows = []
        t = pd.Timestamp("2019-10-01")
        while t < pd.Timestamp("2026-07-01"):
            t2 = min(t + pd.DateOffset(months=1), pd.Timestamp("2026-07-01"))
            u = ("https://www.deribit.com/api/v2/public/get_funding_rate_history"
                 f"?instrument_name=BTC-PERPETUAL&start_timestamp={int(t.timestamp()*1000)}"
                 f"&end_timestamp={int(t2.timestamp()*1000)}")
            for k in range(5):
                try:
                    js = json.loads(urllib.request.urlopen(u, timeout=60).read()); break
                except Exception:
                    if k == 4: raise
                    time.sleep(2 ** k)
            time.sleep(0.35)
            rows += js["result"]
            t = t2
        df = pd.DataFrame(rows).drop_duplicates("timestamp")
        df[["timestamp", "interest_8h", "index_price"]].to_csv(path, index=False)
    return pd.read_csv(path)

def main():
    os.makedirs(LOCAL, exist_ok=True); os.makedirs("./research/results", exist_ok=True)
    df = fetch_deribit()
    ts = pd.to_datetime(df["timestamp"], unit="ms")
    f8 = pd.Series(df["interest_8h"].values, index=ts).sort_index()
    px = pd.Series(df["index_price"].values, index=ts).sort_index()
    f3d = f8.rolling(72).mean()
    day = pd.DataFrame({
        "close": px[px.index.hour == 0].groupby(px[px.index.hour == 0].index.normalize()).last(),
        "f3d": f3d[f3d.index.hour == 0].groupby(f3d[f3d.index.hour == 0].index.normalize()).last()})
    day["ret_next"] = day["close"].pct_change().shift(-1)
    m = day["f3d"].notna() & day["ret_next"].notna()
    p = (day.loc[m, "f3d"] < 0).astype(float).values
    r = day.loc[m, "ret_next"].values
    n, on = len(r), int(p.sum())
    gross = float((p * r).sum())
    turn = float(np.abs(np.diff(np.concatenate([[0.0], p]))).sum())
    net, net2x = gross - turn * COST1, gross - turn * COST1 * 2
    hold = gross - turn * COST1 - on * HOLD_STRESS / 365
    rng = np.random.default_rng(SEED)
    sims = np.array([r[rng.choice(n, size=on, replace=False)].sum() for _ in range(PERM_N)])
    pval = float((sims >= gross).mean())
    beta_take = float(p.mean() * r.sum()); excess = gross - beta_take
    half = n // 2
    def _net(pp, rr):
        return float((pp * rr).sum()) - float(np.abs(np.diff(np.concatenate([[0.0], pp]))).sum()) * COST1
    net_a, net_b = _net(p[:half], r[:half]), _net(p[half:], r[half:])
    eq = np.cumprod(1 + p * r - np.abs(np.diff(np.concatenate([[0.0], p]))) * COST1)
    maxdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    gates = {"G_dir": net > 0, "G_p": pval <= 0.05, "G_split": (net_a > 0) and (net_b > 0),
             "G_cost": net2x > 0, "G_hold": hold > 0, "G_beta": excess > 0}
    verdict = "再現成立" if all(gates.values()) else "再現不成立"
    out = {"doc": "docs/102", "source": "Deribit BTC-PERPETUAL (funding+index, Binance不使用)",
           "range": [str(day.index[0].date()), str(day.index[-1].date())],
           "n_days": n, "on_days": on, "on_ratio": round(on / n, 3),
           "gross_sum": round(gross, 4), "net_sum": round(net, 4), "net_2xcost": round(net2x, 4),
           "net_hold15": round(hold, 4), "perm_p": round(pval, 4),
           "beta_take": round(beta_take, 4), "excess_vs_beta": round(excess, 4),
           "net_half1": round(net_a, 4), "net_half2": round(net_b, 4),
           "maxdd_lev1_record_only": round(maxdd, 4),
           "gates": {k: bool(v) for k, v in gates.items()}, "verdict": verdict,
           "input_sha256": hashlib.sha256(open(f"{LOCAL}/deribit_funding_BTC.csv", "rb").read()).hexdigest()}
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False))

if __name__ == "__main__":
    main()
