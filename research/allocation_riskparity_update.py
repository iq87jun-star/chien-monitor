# -*- coding: utf-8 -*-
"""
allocation_riskparity_update.py — B-5(docs/99): 検証済み4スリーブ(v4/v7/E-Mon[RG3]/E5)の
相関行列を最新データ(2016-01〜2026-06 固定窓)で再計算し、リスクパリティ(ERC)配分と
現行配分(docs/76: v4 30/v7 25/E-Mon 25/E5 20)の差分を提示する。

★これは【提案止まり】: 配分変更の実装はユーザー承認+審査MC再実行(失格率確認)+デモ後のみ。
  月次リターンは既存の再構築ロジック(parallel_vs_existing_compare / edge_regime_gate_10y)を
  そのまま流用(手法の恣意的変更なし)。リスク配分の意味論に合わせ、各スリーブを
  月次vol 1%に正規化(z)した系列上の重み=リスク予算として扱う。

規律: 数字は盛らない。Yahoo日足近似(配当除く・v4はSL/TP簡易再現)=絶対値はDrive確定が正。
  入力CSVのSHA-256をJSONに記録(docs/71)。出力: results/allocation_riskparity_2026_06.json
"""
import os, sys, json, csv, time, hashlib, urllib.request, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")   # データは本スクリプトが固定窓で取得(勝手な再取得を防ぐ)

# 固定解析窓(再現性): 2016-01-01 .. 2026-06-30 UTC
P1, P2 = 1451606400, 1782863999
SYMBOLS = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "AUDUSD": "AUDUSD=X",
    "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X", "NZDUSD": "NZDUSD=X",
    "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
    "XAUUSD": "GC=F", "US500": "^GSPC", "NAS100": "^IXIC", "GER40": "^GDAXI",
}
CURRENT = {"v4": 0.30, "v7": 0.25, "E-Mon[RG3]": 0.25, "E5": 0.20}   # docs/76


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
        print(f"  {name}: {len(rows)} bars")
        time.sleep(0.6)


def sha256s():
    out = {}
    for name in SYMBOLS:
        p = os.path.join(DATA, f"{name}_d.csv")
        if os.path.exists(p):
            out[name] = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    return out


def build_series():
    from parallel_vs_existing_compare import v7_monthly, v4_monthly, e5_monthly, to_monthly
    import edge_regime_gate_10y as RG
    def to_m(w):
        s = w.copy(); s.index = pd.to_datetime(s.index).to_period("M"); return s.groupby(level=0).sum()
    return {
        "v4": v4_monthly(),
        "v7": v7_monthly(),
        "E-Mon[RG3]": to_m(RG.emon_weekly_gated("riskoff")).rename("E-Mon[RG3]"),
        "E5": e5_monthly(),
    }


def zscale(s, target=0.01):
    v = s.std()
    return s * (target / v) if v > 0 else s


def erc_weights(cov, iters=500):
    n = cov.shape[0]; w = np.ones(n) / n
    for _ in range(iters):
        rc = w * (cov @ w)                       # リスク寄与
        w = w * (rc.mean() / np.where(rc > 0, rc, 1e-12)) ** 0.5
        w = np.clip(w, 1e-6, None); w /= w.sum()
    return w


def port_metrics(series_df, weights):
    p = (series_df * pd.Series(weights)).sum(axis=1)
    eq = (1 + p).cumprod(); dd = float(((eq - eq.cummax()) / eq.cummax()).min()) * 100
    mu = p.mean() * 12; vol = p.std() * np.sqrt(12)
    cagr = (eq.iloc[-1] ** (12 / len(p)) - 1) * 100 if eq.iloc[-1] > 0 else -100
    return dict(net=round(float((eq.iloc[-1] - 1) * 100), 1), maxDD=round(dd, 2),
                sharpe=round(float(mu / vol) if vol > 0 else 0, 2),
                calmar=round(float(cagr / abs(dd)), 2) if dd else 0.0, months=int(len(p)))


def main():
    print("[1/3] データ取得(固定窓 2016-01-01..2026-06-30)")
    fetch_all()
    hashes = sha256s()

    print("[2/3] 4スリーブ月次リターン再構築(既存ロジック流用)")
    raw = build_series()
    df = pd.concat(raw.values(), axis=1).dropna()
    names = list(raw.keys())
    print(f"  共通月数: {len(df)} ({df.index[0]}..{df.index[-1]})")

    # リスク配分の意味論: 月次vol1%へ正規化した系列上の重み=リスク予算
    zdf = df.apply(zscale)

    result = dict(window=f"{df.index[0]}..{df.index[-1]}", months=int(len(df)),
                  input_sha256=hashes, sleeves=names)
    for tag, sub in [("full", zdf), ("recent36", zdf.iloc[-36:])]:
        corr = sub.corr().round(3)
        cov = sub.cov().values
        w_erc = erc_weights(cov)
        w_cur = np.array([CURRENT[n] for n in names])
        met_cur = port_metrics(sub, dict(zip(names, w_cur)))
        met_erc = port_metrics(sub, dict(zip(names, w_erc)))
        met_eq = port_metrics(sub, dict(zip(names, np.ones(4) / 4)))
        result[tag] = dict(
            corr=corr.to_dict(),
            raw_monthly_vol_pct={n: round(float(df[n].loc[sub.index].std() * 100), 3) for n in names},
            weights_current={n: round(float(x), 3) for n, x in zip(names, w_cur)},
            weights_erc={n: round(float(x), 3) for n, x in zip(names, w_erc)},
            weights_invvol_equal={n: 0.25 for n in names},   # z正規化後はinverse-vol=等配分
            port_current=met_cur, port_erc=met_erc, port_equal=met_eq,
        )
        print(f"\n== {tag} ==")
        print(corr.to_string())
        print("  現行(30/25/25/20):", met_cur)
        print("  ERC提案          :", {n: round(float(x), 3) for n, x in zip(names, w_erc)}, met_erc)
        print("  等リスク(参考)   :", met_eq)

    print("[3/3] 保存")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", "allocation_riskparity_2026_06.json")
    with open(path, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)
    print("⚠ 提案止まり: 配分変更は ユーザー承認 → 審査MC再実行(失格率) → デモ の順でのみ実施(docs/101)")


if __name__ == "__main__":
    main()
