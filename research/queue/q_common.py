# -*- coding: utf-8 -*-
"""docs/256 Q13〜Q17 共通: Dukascopy H1 の読込・コスト・トレード列の生成(方向を先に決めてからコスト・docs/249)・月次二項検定・判定。research/ で実行する前提。"""
import os, sys, numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from math import comb
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, ROOT)
import recentfit_screen as base
PRE0, IS0, IS1, OOS0, END = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-10-01"), pd.Timestamp("2024-12-31 23:00"), pd.Timestamp("2025-01-01"), pd.Timestamp("2026-12-31")
NONFX_COST = {"XAUUSD": 5e-4, "XAGUSD": 5e-4, "BRENT": 5e-4, "WTI": 5e-4, "UK100": 4e-4, "JP225": 4e-4, "EUSTX50": 4e-4, "US30": 3e-4, "AUS200": 4e-4, "HK50": 4e-4, "BUND": 2e-4, "USTBOND": 2e-4, "DXY": 3e-4}
def load(sym):
    df = pd.read_csv(f"data_dukascopy/{sym}_hour.csv.gz"); df["t"] = pd.to_datetime(df["timestamp"]); df = df.set_index("t").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df[((df.high > df.low) | (df.volume > 0)) & (df.index >= PRE0)]
def cost(sym, px):
    px = np.asarray(px, dtype=float); c = NONFX_COST.get(sym) or base.IDX_COST.get(sym)
    return np.full_like(px, c, dtype=float) if c is not None else 3 * base.pip_size(sym) / px
def trades(sym, t_in, px_in, dir_, px_out):
    """建て時刻・建値・方向(+1/-1)・出口価格 → コスト後リターン列(index=建て時刻)。NaN の出口は落とす。"""
    t_in = pd.DatetimeIndex(t_in); px_in = np.asarray(px_in, float); dir_ = np.asarray(dir_, float); px_out = np.asarray(px_out, float)
    ok = ~np.isnan(px_out) & ~np.isnan(px_in) & (dir_ != 0)
    r = dir_[ok] * (px_out[ok] / px_in[ok] - 1.0) - cost(sym, px_in[ok])
    return pd.Series(r, index=t_in[ok])
def pb(m): n = len(m); k = int((m > 0).sum()); return k, n, (sum(comb(n, j) for j in range(k, n + 1)) / 2 ** n if n else 1.0)
def st(r, a, b):
    x = r[(r.index >= a) & (r.index <= b)]
    if len(x) == 0: return dict(n=0, plus=0, rate=np.nan, mean=np.nan, p=1.0, trades=0)
    m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1); k, n, p = pb(m)
    return dict(n=n, plus=k, rate=round(k / n, 3), mean=round(float(x.mean()) * 1e4, 2), p=p, trades=len(x))
def atr24(df):
    """直前 24 本(当該バーを含まない)のレンジ平均。"""
    return (df["high"] - df["low"]).rolling(24).mean().shift(1)
def nonoverlap(idx_trig, exit_of):
    """トリガー時刻(昇順)を、前トレードの出口時刻より後のものだけ採用。exit_of(t) は出口時刻(Timestamp or NaT)。"""
    keep = []; busy_until = pd.Timestamp("1900-01-01")
    for t in idx_trig:
        if t <= busy_until: continue
        e = exit_of(t)
        if e is None or pd.isna(e): continue
        keep.append(t); busy_until = e
    return pd.DatetimeIndex(keep)
def selfcheck(sym, df):
    o = df["open"]; t0 = o.index[(o.index.hour == 8) & (o.index.dayofweek == 1)][:300]; p0 = o.reindex(t0).values; p1 = o.reindex(t0 + pd.Timedelta(hours=4)).values
    z = (trades(sym, t0, p0, np.ones(len(t0)), p1) + trades(sym, t0, p0, -np.ones(len(t0)), p1)).dropna()
    assert len(z) > 0 and float(z.max()) <= 1e-12 and float(z.min()) < 0, f"[COST SIGN] {sym}"
class Runner:
    def __init__(self, qid, cum, n_cells, out):
        self.qid, self.cum, self.N, self.out = qid, cum, n_cells, out; self.alpha = 0.05 / (cum + n_cells); self.rows = []
    def add(self, family, sym, spec, r):
        sp, si, so = st(r, PRE0, IS0), st(r, IS0, IS1), st(r, OOS0, END)
        pre_ok = (sp["n"] > 0 and sp["rate"] >= 0.5) or (sym == "XAUUSD" and sp["n"] == 0)   # docs/256 §4: XAUUSD は前窓なし
        passed = bool(si["p"] < self.alpha and si["n"] >= 24 and so["n"] > 0 and so["mean"] > 0 and pre_ok)
        self.rows.append(dict(family=family, symbol=sym, spec=spec, is_plus=si["plus"], is_n=si["n"], is_rate=si["rate"], is_mean_bps=si["mean"], is_trades=si["trades"], p=si["p"],
                              oos_plus=so["plus"], oos_n=so["n"], oos_mean_bps=so["mean"], pre_n=sp["n"], pre_rate=sp["rate"], passed=passed))
    def finish(self):
        R = pd.DataFrame(self.rows); assert len(R) == self.N, f"cells {len(R)} != planned {self.N}"
        R = R.sort_values("p"); R.to_csv(self.out, index=False); pd.set_option("display.width", 250)
        print(f"{self.qid}: cells={self.N} cum_before={self.cum} cum_after={self.cum+self.N} alpha={self.alpha:.2e} passed={int(R.passed.sum())} p<0.05={int((R.p<0.05).sum())}(期待 {self.N*0.05:.0f}) judged(IS n>=24)={int((R.is_n>=24).sum())}")
        print(R.head(12).to_string(index=False)); print("\n-- passed --"); print(R[R.passed].to_string(index=False) if R.passed.any() else "(none)")
        return R
