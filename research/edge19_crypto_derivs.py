"""
edge19_crypto_derivs.py — クリプト・デリバティブ新データ批次【事前登録 docs/100】。
新データ: Binance無期限先物 資金調達率(2019-09〜) / Deribit DVOL(BTC/ETHオプションIV, 2021-03〜)。
仮説N=4(閾値は docs/100 で凍結・スキャンなし):
  H19a FUND-CONTRA-L: F3d(直近9回平均funding)<0        → 翌日LONG
  H19b FUND-CROWD-S : F3d>+0.05%/8h                     → 翌日SHORT
  H19c VRP-L        : DVOL−RV30>+10pt                    → 翌日LONG
  H19d IVSPIKE-L    : DVOLが5日前比+15pt以上上昇          → 翌日から5日LONG
ゲート: dir / ドリフト保存プラセボp≤0.05(Bonferroni α=0.0125併記) / split両半+ / 2×コスト /
保有コスト15%年 / 対ベータ超過 / maxDD≥−20%。全通過=STRONG-LEAD(ADOPTにはしない, docs/100 §2)。
"""
import os, io, json, time, hashlib, zipfile, urllib.request
import numpy as np, pandas as pd

LOCAL = "./research/data"
OUT = "./research/results/edge19_crypto_derivs.json"
COST1 = 0.0010          # 片道10bp(基本)
HOLD_STRESS = 0.15      # 保有コストストレス 15%/年
PERM_N, SEED = 2000, 19

def _fetch(url, path):
    if not os.path.exists(path):
        try:
            d = urllib.request.urlopen(url, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            raise
        with open(path, "wb") as f: f.write(d)
    return path

def _ms(t):
    return t // 1000 if t > 10**14 else t  # 2025+のBinanceはマイクロ秒

def months(a, b):
    p = pd.period_range(a, b, freq="M")
    return [str(m) for m in p]

def funding(sym):
    rows = []
    for m in months("2019-09", "2026-06"):
        url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip"
        p = _fetch(url, f"{LOCAL}/fund_{sym}_{m}.zip")
        if p is None: continue
        z = zipfile.ZipFile(p); txt = z.read(z.namelist()[0]).decode()
        for ln in txt.strip().splitlines():
            f0 = ln.split(",")
            if not f0[0].isdigit(): continue
            rows.append((_ms(int(f0[0])), float(f0[2])))
    s = pd.Series({pd.Timestamp(t, unit="ms"): v for t, v in rows}).sort_index()
    return s

def daily_close(sym):
    rows = []
    for m in months("2019-06", "2026-06"):
        url = f"https://data.binance.vision/data/spot/monthly/klines/{sym}/1d/{sym}-1d-{m}.zip"
        p = _fetch(url, f"{LOCAL}/kline_{sym}_{m}.zip")
        if p is None: continue
        z = zipfile.ZipFile(p); txt = z.read(z.namelist()[0]).decode()
        for ln in txt.strip().splitlines():
            f0 = ln.split(",")
            if not f0[0].isdigit(): continue
            rows.append((_ms(int(f0[0])), float(f0[4])))
    s = pd.Series({pd.Timestamp(t, unit="ms").normalize(): v for t, v in rows}).sort_index()
    return s[~s.index.duplicated()]

def dvol(ccy):
    path = f"{LOCAL}/dvol_{ccy}.csv"
    if not os.path.exists(path):
        # APIは範囲の末尾1000本を返す仕様 → 後方ページング
        rows, t0 = [], int(pd.Timestamp("2021-03-01").timestamp()*1000)
        end = int(pd.Timestamp("2026-07-01").timestamp()*1000)
        while True:
            u = ("https://www.deribit.com/api/v2/public/get_volatility_index_data"
                 f"?currency={ccy}&start_timestamp={t0}&end_timestamp={end}&resolution=3600")
            for k in range(5):
                try:
                    js = json.loads(urllib.request.urlopen(u, timeout=60).read()); break
                except Exception:
                    if k == 4: raise
                    time.sleep(2 ** k)
            time.sleep(0.35)
            data = js["result"]["data"]
            if not data: break
            rows = data + rows
            if int(data[0][0]) <= t0: break
            end = int(data[0][0]) - 3600_000
        df = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c"]).drop_duplicates("t")
        df.to_csv(path, index=False)
    df = pd.read_csv(path)
    ts = pd.to_datetime(df["t"], unit="ms")
    s = pd.Series(df["c"].values, index=ts)
    # 日次終値 = 各UTC日の 23:00 バーの終値(≈翌00:00の値)
    d = s[s.index.hour == 23]
    return pd.Series(d.values, index=d.index.normalize())

def build(sym, ccy):
    px = daily_close(sym)
    fu = funding(sym)
    dv = dvol(ccy)
    df = pd.DataFrame({"close": px})
    df["ret"] = df["close"].pct_change()
    logr = np.log(df["close"]).diff()
    df["rv30"] = logr.rolling(30).std() * np.sqrt(365) * 100
    # F3d: 日t終了時点までの直近9回(8h×9=3日)の平均funding
    f3 = fu.rolling(9).mean()
    df["f3d"] = f3.groupby(f3.index.normalize()).last().reindex(df.index).ffill(limit=2)
    df["dvol"] = dv.reindex(df.index)
    df["vrp"] = df["dvol"] - df["rv30"]
    df["ivchg5"] = df["dvol"] - df["dvol"].shift(5)
    df["ret_next"] = df["ret"].shift(-1)
    return df

def positions(df, hid):
    if hid == "H19a": on = (df["f3d"] < 0);           d = +1
    elif hid == "H19b": on = (df["f3d"] > 0.0005);    d = -1
    elif hid == "H19c": on = (df["vrp"] > 10);        d = +1
    elif hid == "H19d":
        trig = (df["ivchg5"] >= 15)
        on = trig.rolling(5, min_periods=1).max().astype(bool); d = +1
    pos = on.astype(float) * d
    pos[df[["ret_next"]].isna().any(axis=1)] = np.nan
    return pos

def evaluate(df, hid, rng):
    pos = positions(df, hid)
    m = pos.notna() & df["ret_next"].notna()
    # 仮説ごとの有効期間(シグナル系列が存在する範囲)に限定
    sig = {"H19a": "f3d", "H19b": "f3d", "H19c": "vrp", "H19d": "ivchg5"}[hid]
    m &= df[sig].notna()
    p, r = pos[m].values, df.loc[m, "ret_next"].values
    n = len(r); on = int((p != 0).sum())
    if on < 30:
        return {"id": hid, "n_days": n, "on_days": on, "verdict": "REJECT", "note": "ON日数不足"}
    gross = float((p * r).sum())
    turn = float(np.abs(np.diff(np.concatenate([[0.0], p]))).sum())
    net = gross - turn * COST1
    net2x = gross - turn * COST1 * 2
    hold = net - on * HOLD_STRESS / 365
    # ドリフト保存プラセボ: 同方向・ON日数保存のランダム配置
    d = np.sign(p[p != 0][0])
    sims = np.empty(PERM_N)
    for i in range(PERM_N):
        idx = rng.choice(n, size=on, replace=False)
        sims[i] = d * r[idx].sum()
    pval = float((sims >= gross).mean())
    beta_take = float(p.mean() * r.sum())
    excess = gross - beta_take
    # split(有効期間の中央)
    half = n // 2
    net_a = float((p[:half] * r[:half]).sum()) - float(np.abs(np.diff(np.concatenate([[0.0], p[:half]]))).sum()) * COST1
    net_b = float((p[half:] * r[half:]).sum()) - float(np.abs(np.diff(np.concatenate([[0.0], p[half:]]))).sum()) * COST1
    eq = np.cumprod(1 + p * r - np.abs(np.diff(np.concatenate([[0.0], p]))) * COST1)
    maxdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    gates = {"G_dir": net > 0, "G_p": pval <= 0.05, "G_p_bonf": pval <= 0.0125,
             "G_split": (net_a > 0) and (net_b > 0), "G_cost": net2x > 0,
             "G_hold": hold > 0, "G_beta": excess > 0, "G_dd": maxdd >= -0.20}
    core = ["G_dir", "G_p", "G_split", "G_cost", "G_hold", "G_beta", "G_dd"]
    npass = sum(gates[g] for g in core)
    if npass == len(core): verdict = "STRONG-LEAD" if gates["G_p_bonf"] else "LEAD"
    elif gates["G_p"] and npass >= 4: verdict = "LEAD"
    elif net > 0 and pval <= 0.10: verdict = "参考"
    else: verdict = "REJECT"
    return {"id": hid, "n_days": n, "on_days": on, "on_ratio": round(on / n, 3),
            "gross_sum": round(gross, 4), "net_sum": round(net, 4), "net_2xcost": round(net2x, 4),
            "net_hold15": round(hold, 4), "perm_p": round(pval, 4),
            "beta_take": round(beta_take, 4), "excess_vs_beta": round(excess, 4),
            "net_half1": round(net_a, 4), "net_half2": round(net_b, 4),
            "maxdd_lev1": round(maxdd, 4), "gates": {k: bool(v) for k, v in gates.items()},
            "verdict": verdict}

def sha_all():
    h = hashlib.sha256()
    for f in sorted(os.listdir(LOCAL)):
        if f.startswith(("fund_", "kline_", "dvol_")):
            h.update(open(f"{LOCAL}/{f}", "rb").read())
    return h.hexdigest()

def main():
    os.makedirs(LOCAL, exist_ok=True); os.makedirs("./research/results", exist_ok=True)
    rng = np.random.default_rng(SEED)
    out = {"doc": "docs/100", "cost_oneway": COST1, "hold_stress": HOLD_STRESS,
           "perm_n": PERM_N, "assets": {}}
    for sym, ccy, role in [("BTCUSDT", "BTC", "primary"), ("ETHUSDT", "ETH", "confirm")]:
        df = build(sym, ccy)
        res = [evaluate(df, h, rng) for h in ["H19a", "H19b", "H19c", "H19d"]]
        span = {h["id"]: h.get("n_days") for h in res}
        out["assets"][sym] = {"role": role, "rows": int(len(df)),
                              "px_range": [str(df.index[0].date()), str(df.index[-1].date())],
                              "results": res}
        print(f"== {sym} ({role})")
        for h in res:
            print("  ", {k: h[k] for k in ("id", "verdict", "net_sum", "perm_p", "on_ratio") if k in h})
    out["input_sha256"] = sha_all()
    json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
    print("saved:", OUT)

if __name__ == "__main__":
    main()
