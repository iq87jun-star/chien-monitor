# -*- coding: utf-8 -*-
"""
compare_rg_vs_existing.py — 既存の確定スペック vs 新提案 P-RG をポートフォリオ単位で同条件比較。

目的: docs/64-66 の RG(レジーム・ゲート)＋金ヘッジを"組み込んだ"ポートフォリオ(P-RG)が、
既存(v4 55 : E-Mon 45, docs/61)と比べて本当に良いかを、同じYahoo日足10年・等ボラ標準化で採点する。

スリーブ(全て月次リターンに集約・等ボラ標準化して risk% で合成, docs/54/55 と同じ作法):
  v4      : FX9ペア k≥4 合議の逆張り(daily, SL1.5ATR/TP RR1.2/8日)。docs/42 のロジックを再構築。
  E-Mon   : 指数3つ 月曜LONG(raw)。  E-Mon_RG3: 同じだが非対称リスクオフ・ゲート(docs/66 の最良)。
  v7      : 円3クロス 月曜LONG(日足プロキシ・衛星)。
  gold_ro : リスクオフ週だけ XAU ロング(docs/66 の保険衛星)。

比較する構成:
  既存P-confirmed : v4 55 : E-Mon(raw) 45
  既存P-C(docs/54): v4 50 : v7 30 : E-Mon(raw) 20
  新 P-RG         : v4 50 : E-Mon(RG3) 38 : v7 6 : gold_ro 6
指標: 各構成を年率ボラ10%へ標準化し Sharpe / Calmar / maxDD / p95年DD(ブートストラップ) を比較。

⚠ Yahoo日足10年の一次近似(配当除く指数・FXは=X・往復bps)。拘束力ある確証は Drive(Dukascopy/実CFD)＋デモ。
"""
import os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
import edge_regime_gate_10y as RG    # 同ディレクトリのローダ/ゲート/Yahoo取得を再利用

HERE = os.path.dirname(os.path.abspath(__file__))
FX = ["EURJPY", "GBPJPY", "USDJPY", "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCHF", "USDCAD"]
RG.YAHOO.update({"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "AUDUSD": "AUDUSD=X",
                 "NZDUSD": "NZDUSD=X", "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X"})
RR = 1.2
ATR_MULT = 1.5
TIME_STOP = 8


# ---------- v4: FX k>=4 合議 逆張り(docs/42) ----------
def _ohlc_full(name):
    """high/low も保持する版(v4のSL/TP判定に必要)。RG._read_ohlc は open/close のみ。"""
    p = os.path.join(RG.LOCAL, f"{name}_d.csv")
    if not os.path.exists(p):
        if not (RG.ALLOW_YAHOO and RG._yahoo_fetch(name) is not None):
            return None
    df = pd.read_csv(p); df.columns = [c.strip().lower() for c in df.columns]
    tcol = next((c for c in ["time", "timestamp", "date", "datetime"] if c in df.columns), df.columns[0])
    df["t"] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
    df = df.dropna(subset=["t"]).sort_values("t")
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    df.index = df["t"].dt.floor("D")
    df = df[~df.index.duplicated(keep="first")]
    df = df[df.index.dayofweek <= 4]
    return df[["open", "high", "low", "close"]]

def _rsi(close, n=14):
    d = close.diff(); up = d.clip(lower=0).rolling(n).mean(); dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / (dn + 1e-12); return 100 - 100 / (1 + rs)

def _atr(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def v4_monthly(cost_bps=2.0):
    """k=4 合議の逆張りトレードを9ペアで実行し、月次リターン(リスクR単位)を返す。"""
    daily = {}
    for p in FX:
        df = _ohlc_full(p)
        if df is None or len(df) < 260: continue
        c = df["close"]; ret = c.pct_change()
        rsi = _rsi(c); ma = c.rolling(20).mean(); sd = c.rolling(20).std(); z = (c - ma) / (sd + 1e-12)
        atr = _atr(df)
        up3 = (ret > 0) & (ret.shift(1) > 0) & (ret.shift(2) > 0)
        dn3 = (ret < 0) & (ret.shift(1) < 0) & (ret.shift(2) < 0)
        long_sig  = (rsi < 35) & (z < -1.5) & dn3 & (ret < -0.005)    # 売られ過ぎ→逆張りLONG
        short_sig = (rsi > 65) & (z > 1.5) & up3 & (ret > 0.005)      # 買われ過ぎ→逆張りSHORT
        idx = df.index; o = df["open"].values; h = df["high"].values; l = df["low"].values; cl = df["close"].values
        av = atr.values; ls = long_sig.values; ss = short_sig.values
        i = 1; n = len(df)
        while i < n - 1:
            side = 1 if ls[i] else (-1 if ss[i] else 0)
            if side == 0 or not np.isfinite(av[i]) or av[i] <= 0:
                i += 1; continue
            entry = o[i + 1]; sl_d = ATR_MULT * av[i]; tp_d = RR * sl_d
            R = None
            for k in range(i + 1, min(i + 1 + TIME_STOP, n)):
                if side == 1:
                    if l[k] <= entry - sl_d: R = -1.0; xk = k; break
                    if h[k] >= entry + tp_d: R = +RR; xk = k; break
                else:
                    if h[k] >= entry + sl_d: R = -1.0; xk = k; break
                    if l[k] <= entry - tp_d: R = +RR; xk = k; break
            else:
                xk = min(i + TIME_STOP, n - 1)
                R = side * (cl[xk] - entry) / sl_d
            R -= cost_bps / 1e4 / (sl_d / entry)        # 往復コストをR換算で控除(近似)
            d = idx[xk]; daily[d] = daily.get(d, 0.0) + R
            i = xk + 1                                   # 1ペア1ポジ: 決済後に次を探す
    if not daily: return None
    s = pd.Series(daily).sort_index()
    return s.groupby([s.index.year, s.index.month]).sum()


# ---------- 月次集約ヘルパ ----------
def _wk_to_monthly(w):
    if w is None: return None
    w = w.copy(); w.index = pd.to_datetime(w.index)
    return w.groupby([w.index.year, w.index.month]).sum()

def _std_vol(m, target=0.10):
    """月次系列を年率ボラ target に標準化(スケール不変の質比較用)。"""
    v = m.std() * np.sqrt(12)
    return m * (target / (v + 1e-12))

def _metrics(m):
    m = m.dropna()
    if len(m) < 12: return dict(sharpe=0, calmar=0, maxdd=0, cagr=0, p95=0)
    eq = (1 + m).cumprod(); dd = (eq / eq.cummax() - 1)
    yrs = len(m) / 12
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    sharpe = m.mean() / (m.std() + 1e-12) * np.sqrt(12)
    mdd = float(dd.min())
    # p95年DD: 12ヶ月ブロック・ブートストラップ
    rng = np.random.default_rng(3); dds = []
    a = m.values
    for _ in range(3000):
        s = rng.choice(a, size=12, replace=True)
        e = (1 + s).cumprod(); dds.append(float((e / np.maximum.accumulate(e) - 1).min()))
    p95 = float(np.percentile(dds, 5))
    return dict(sharpe=round(sharpe, 3), calmar=round(cagr / abs(mdd) if mdd else 0, 3),
                maxdd=round(mdd, 4), cagr=round(cagr, 4), p95=round(p95, 4))


def blend(weights, sleeves, target=0.10):
    """weights: {name: risk%}. 各スリーブを等ボラ標準化→risk加重→合算→ブレンドを target ボラへ。"""
    cols = []
    for nm, w in weights.items():
        m = sleeves.get(nm)
        if m is None: continue
        cols.append((_std_vol(m) * w).rename(nm))
    if not cols: return None
    j = pd.concat(cols, axis=1).fillna(0.0)
    b = j.sum(axis=1)
    return _std_vol(b, target)


def main():
    print("スリーブ構築中(Yahoo日足10年, 初回は取得に時間)...")
    emon_raw = RG.emon_weekly_raw()
    emon_rg3 = RG.emon_weekly_gated("riskoff")
    v7_raw, _ = RG.v7_weekly_raw_and_gated()
    gold_ro, _, _ = RG.gold_riskoff_weekly()
    sleeves = dict(
        v4=v4_monthly(),
        EmonRaw=_wk_to_monthly(emon_raw),
        EmonRG3=_wk_to_monthly(emon_rg3),
        v7=_wk_to_monthly(v7_raw),
        gold=_wk_to_monthly(gold_ro),
    )
    for k, v in sleeves.items():
        print(f"  sleeve {k:9s}: {'OK n=%d' % len(v) if v is not None else 'MISSING'}")

    portfolios = {
        "既存 confirmed (v4 55 : EmonRaw 45)":          {"v4": 0.55, "EmonRaw": 0.45},
        "★最小変更 (v4 55 : EmonRG3 45)":               {"v4": 0.55, "EmonRG3": 0.45},
        "P-RG-lite (v4 50 : EmonRG3 44 : gold 6)":      {"v4": 0.50, "EmonRG3": 0.44, "gold": 0.06},
        "P-RG-full (v4 50 : EmonRG3 38 : v7 6 : gold 6)": {"v4": 0.50, "EmonRG3": 0.38, "v7": 0.06, "gold": 0.06},
    }
    rows = {}
    for name, w in portfolios.items():
        b = blend(w, sleeves)
        rows[name] = _metrics(b) if b is not None else None

    # 個別スリーブの質も併記(等ボラ10%標準化)
    print("\n=== 個別スリーブ(年率ボラ10%標準化) ===")
    print(f"{'sleeve':10s} {'Sharpe':>7s} {'Calmar':>7s} {'maxDD':>8s} {'p95年DD':>8s}")
    for k, v in sleeves.items():
        if v is None: continue
        mm = _metrics(_std_vol(v))
        print(f"{k:10s} {mm['sharpe']:7.2f} {mm['calmar']:7.2f} {mm['maxdd']*100:7.1f}% {mm['p95']*100:7.1f}%")

    print("\n=== ポートフォリオ比較(各構成を年率ボラ10%へ標準化) ===")
    print(f"{'構成':46s} {'Sharpe':>7s} {'Calmar':>7s} {'maxDD':>8s} {'p95年DD':>8s}")
    for name, m in rows.items():
        if m is None: print(f"{name:46s}  (データ不足)"); continue
        print(f"{name:46s} {m['sharpe']:7.2f} {m['calmar']:7.2f} {m['maxdd']*100:7.1f}% {m['p95']*100:7.1f}%")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "compare_rg_vs_existing.json"), "w") as fp:
        json.dump({"portfolios": rows,
                   "sleeves": {k: _metrics(_std_vol(v)) for k, v in sleeves.items() if v is not None}},
                  fp, indent=2, ensure_ascii=False)
    print("\n-> results/compare_rg_vs_existing.json")


if __name__ == "__main__":
    main()
