"""
edge_b_10y.py — 第2弾（docs/28, LOCKED）ベータ非依存3候補の10年検定。

B1: コインテグレーション・スプレッド平均回帰（ペア・スタットアーブ）
B2: 横断バリュー（5年MA乖離・ドル中立ロングショート）
B3: 横断・短期リバーサル（共通ドル要因除去残差・ドル中立・1週）

全候補とも長短ドル中立 or スプレッド＝設計でベータ相殺。判定は docs/26 の6ゲートに加え、
(A) の強化ゲート（④ベータ中立化 t>2.5 / ⑦Deflated Sharpe / ⑧PBO）を必須化。
拘束力ある判定は10年実データ（research/data）。
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from data_io import load_h1, load_costs, load_v7_weekly, report_path
from edge_harness import Trades, evaluate_edge
from validation import beta_neutralize, deflated_sharpe, pbo_cscv

N_TRIALS = 40          # docs/28: 累積試行数（控えめ見積もり）で DSR を割引く
ALPHA = 0.0167

# 通貨 → (対USDシンボル, 符号)  符号+1: シンボル上昇=通貨高 / -1: 反転
CCY = {
    "EUR": ("EURUSD", +1), "GBP": ("GBPUSD", +1), "AUD": ("AUDUSD", +1),
    "NZD": ("NZDUSD", +1), "JPY": ("USDJPY", -1), "CHF": ("USDCHF", -1),
    "CAD": ("USDCAD", -1), "SEK": ("USDSEK", -1), "NOK": ("USDNOK", -1),
}


def ccy_close_vs_usd(ccy: str) -> pd.Series:
    sym, sgn = CCY[ccy]
    c = load_h1(sym)["close"]
    return c if sgn > 0 else 1.0 / c      # 通貨高=上昇に統一


def weekly_ret_vs_usd() -> pd.DataFrame:
    cols = {c: ccy_close_vs_usd(c).resample("W-MON").last().pct_change() for c in CCY}
    return pd.DataFrame(cols).dropna(how="all")


def usd_factor_weekly() -> pd.Series:
    """共通ドル要因 = 全通貨対USD週次の等加重（ベータ中立化の market）。"""
    return weekly_ret_vs_usd().mean(axis=1)


def as_weekly_trades(weekly: pd.Series, cost_per_period: float) -> Trades:
    """週次純益系列を Trades（1週1行）に包む。"""
    w = weekly.dropna()
    df = pd.DataFrame({
        "entry_time": w.index, "exit_time": w.index, "symbol": "PORT",
        "direction": 1, "ret_gross": w.values,
        "cost": np.full(len(w), cost_per_period),
    })
    return Trades(df)


# ----------------------------------------------------------------------------
# B1 — コインテグレーション・スプレッド
# ----------------------------------------------------------------------------
B1_PAIRS = [("AUDUSD", "NZDUSD"), ("USDSEK", "USDNOK"), ("EURUSD", "GBPUSD")]


def b1_weekly(z_entry=2.0, lookback=250, max_hold=10) -> pd.Series:
    costs = load_costs()
    weekly_pnl = {}
    for ya, xa in B1_PAIRS:
        y = np.log(load_h1(ya)["close"].resample("1D").last().dropna())
        x = np.log(load_h1(xa)["close"].resample("1D").last().dropna())
        df = pd.concat([y, x], axis=1, keys=["y", "x"]).dropna()
        # ローリングOLS（先読み回避: 当日までの窓→shift(1)）
        beta = (df["y"].rolling(lookback).cov(df["x"]) /
                df["x"].rolling(lookback).var()).shift(1)
        spread = df["y"] - beta * df["x"]
        mu = spread.rolling(lookback).mean().shift(1)
        sd = spread.rolling(lookback).std().shift(1)
        z = (spread - mu) / sd
        cost = (costs.loc[ya, "roundtrip_cost_frac"] + costs.loc[xa, "roundtrip_cost_frac"]) \
            if ya in costs.index and xa in costs.index else 0.0002
        idx = df.index
        i = 0
        pnl = []
        while i < len(idx) - 1:
            zi = z.iloc[i]
            if np.isfinite(zi) and abs(zi) >= z_entry:
                direction = -1 if zi > 0 else +1     # 高z=スプレッド売り
                entry_sp = spread.iloc[i]
                j = i + 1
                while j < len(idx) and (j - i) <= max_hold:
                    if not np.isfinite(z.iloc[j]) or np.sign(z.iloc[j]) != np.sign(zi):
                        break
                    j += 1
                j = min(j, len(idx) - 1)
                ret = direction * (spread.iloc[j] - entry_sp) - cost   # log-spread ≒ fractional
                pnl.append((idx[j], ret))
                i = j + 1
            else:
                i += 1
        if pnl:
            s = pd.Series([r for _, r in pnl], index=[t for t, _ in pnl])
            weekly_pnl[ya + "_" + xa] = s.groupby(pd.Grouper(freq="W-MON")).sum()
    if not weekly_pnl:
        return pd.Series(dtype=float)
    return pd.DataFrame(weekly_pnl).sum(axis=1).rename("B1")


# ----------------------------------------------------------------------------
# B2 — 横断バリュー（5年MA乖離）
# ----------------------------------------------------------------------------
def b2_weekly(ma_years=5, n_leg=3) -> pd.Series:
    daily = {c: ccy_close_vs_usd(c).resample("1D").last() for c in CCY}
    px = pd.DataFrame(daily).dropna(how="all")
    ma = px.rolling(int(ma_years * 252)).mean()
    dev = (px / ma - 1.0).shift(1)               # 割安(負)=ロング候補。先読み回避
    mret = px.resample("MS").last().pct_change()  # 月次対USDリターン
    rebal = pd.date_range(px.index.min(), px.index.max(), freq="MS")
    out = {}
    for m in rebal:
        d = dev.reindex(px.index[px.index <= m]).iloc[-1] if (px.index <= m).any() else None
        if d is None:
            continue
        d = d.dropna()
        if len(d) < 2 * n_leg:
            continue
        order = d.sort_values()                  # 昇順=割安先頭
        longs, shorts = order.index[:n_leg], order.index[-n_leg:]
        nxt = mret.index[mret.index > m]
        if len(nxt) == 0:
            continue
        r = mret.loc[nxt[0]]
        out[nxt[0]] = float(r[longs].mean() - r[shorts].mean())
    s = pd.Series(out).sort_index()
    return (s - 0.0001).rename("B2")             # 簡易コスト


# ----------------------------------------------------------------------------
# B3 — 横断・短期リバーサル（残差・ドル中立）
# ----------------------------------------------------------------------------
def b3_weekly(n_leg=3) -> pd.Series:
    w = weekly_ret_vs_usd()
    resid = w.sub(w.mean(axis=1), axis=0)        # 共通ドル要因を除去
    out = {}
    idx = w.index
    for i in range(1, len(idx) - 1):
        prev = resid.iloc[i - 1].dropna()
        if len(prev) < 2 * n_leg:
            continue
        order = prev.sort_values()
        longs, shorts = order.index[:n_leg], order.index[-n_leg:]   # 負け→ロング(反転)
        nxt = w.iloc[i][list(longs) + list(shorts)]
        if nxt.isna().any():
            continue
        out[idx[i]] = float(w.iloc[i][longs].mean() - w.iloc[i][shorts].mean())
    s = pd.Series(out).sort_index()
    return (s - 0.0001).rename("B3")


# ----------------------------------------------------------------------------
# 評価（6ゲート + 強化ゲート④⑦⑧）
# ----------------------------------------------------------------------------
def evaluate_b(edge_id, main_weekly, variants, market, v7, cost_per_period):
    tr = as_weekly_trades(main_weekly, cost_per_period)
    base = evaluate_edge(edge_id, tr, v7, risk_budget_pct=0.6,
                         placebo_fn=None, alpha=ALPHA)
    w = main_weekly.dropna()
    a, b = w.align(market, join="inner")
    bn = beta_neutralize(a.values, b.values)
    hedged = a.values - bn["beta"] * b.values
    dsr = deflated_sharpe(hedged, n_trials=N_TRIALS, sr_trials_std=0.05)
    # PBO: パラメータ変種の週次行列
    vdf = pd.DataFrame({f"v{i}": v for i, v in enumerate(variants)}).dropna()
    pbo = pbo_cscv(vdf.values, n_splits=10) if vdf.shape[1] >= 2 else {"pbo": float("nan")}

    g = base.gates()
    g4 = bool(bn["t_alpha"] > 2.5 and bn["alpha"] > 0)     # ベータ中立で実残差
    g7 = bool(dsr["dsr"] >= 0.95)
    g8 = bool(np.isfinite(pbo["pbo"]) and pbo["pbo"] <= 0.20)
    gates = {**g, "g4_beta_neutral": g4, "g7_dsr": g7, "g8_pbo": g8}
    # ADOPT: 元①②③⑤⑥ + 強化④⑦⑧（元のg4プラセボは強化版で置換）
    core = [gates["g1_profit"], gates["g2_perm_p"], gates["g3_jackknife"],
            gates["g5_cost"], gates["g6_independent"], g4, g7, g8]
    grade = "ADOPT" if all(core) else ("LEAD" if (base.net_profit_10y > 0 and base.perm_p_net < 0.10) else "REJECT")
    out = base.to_json()
    out.update(grade=grade, gates=gates,
               beta=bn["beta"], alpha_weekly=bn["alpha"], t_alpha=bn["t_alpha"],
               hedged_sharpe=dsr["sharpe"], dsr=dsr["dsr"], sr0=dsr["sr0"],
               pbo=pbo["pbo"], n_variants=int(vdf.shape[1]))
    return out


def main():
    market = usd_factor_weekly()
    v7 = load_v7_weekly()
    specs = {
        "B1_cointegration": dict(
            main=b1_weekly(), cost=0.0002,
            variants=[b1_weekly(z, lb, mh) for z in (1.75, 2.0, 2.25)
                      for lb in (200, 250) for mh in (8, 12)]),
        "B2_value": dict(
            main=b2_weekly(), cost=0.0001,
            variants=[b2_weekly(y, n) for y in (3, 5, 7) for n in (2, 3, 4)]),
        "B3_reversal": dict(
            main=b3_weekly(), cost=0.0001,
            variants=[b3_weekly(n) for n in (2, 3, 4)]),
    }
    rows = []
    for eid, sp in specs.items():
        res = evaluate_b(eid, sp["main"], sp["variants"], market, v7, sp["cost"])
        with open(report_path(f"{eid.lower()}_result.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        rows.append({"edge": eid, "grade": res["grade"], "n": res["n_trades"],
                     "net": round(res["net_profit_10y"], 4), "p": round(res["perm_p_net"], 4),
                     "t_alpha": round(res["t_alpha"], 2), "dsr": round(res["dsr"], 3),
                     "pbo": round(res["pbo"], 3) if np.isfinite(res["pbo"]) else None,
                     "corr_v7": round(res["corr_v7"], 3)})
    print("\n=== B (beta-neutral) 10-year verdict | alpha=0.0167, N_trials=40 ===")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
