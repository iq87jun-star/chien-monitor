"""統計ゲートの実装。過去に「短期サンプルの過信」「自己相関の無視」で失敗した。
ここは再発防止の核なので、保守的・頑健側に倒す。

提供する検定:
  block_sign_perm_pvalue : 自己相関頑健な順列検定（月次ブロック符号シャッフル）。
  jackknife_year_pvalues : 1年抜きジャックナイフ。各 fold の最大 p を返す。
  placebo_standout       : 対象だけが突出しているか（プラセボ群と比較）。
  correlation            : v7 等との相関（分散先かどうか）。
  sharpe / max_drawdown  : 補助指標。
"""
import numpy as np
import pandas as pd


def sharpe(daily_returns, ann: int = 252) -> float:
    r = np.asarray(daily_returns, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) < 2:
        return 0.0
    sd = r.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(r.mean() / sd * np.sqrt(ann))


def max_drawdown(equity_curve) -> float:
    eq = np.asarray(equity_curve, dtype=float)
    if len(eq) == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    return float(dd.min())


def _stat(daily: np.ndarray, metric: str) -> float:
    if metric == "mean":
        return float(np.nanmean(daily))
    if metric == "sharpe":
        return sharpe(daily)
    if metric == "sum":
        return float(np.nansum(daily))
    raise ValueError(f"unknown metric {metric!r}")


def _block_keys(index, n: int, block: str):
    """各観測のブロック ID を返す。index があれば暦ブロック、無ければ連続21本ブロック。"""
    if index is not None:
        di = pd.DatetimeIndex(index)
        if di.tz is not None:
            di = di.tz_convert(None)
        return np.asarray(di.to_period(block).astype(str))
    return (np.arange(n) // 21).astype(str)


def block_sign_perm_pvalue(
    daily, index=None, block: str = "M", n_perm: int = 5000,
    metric: str = "sharpe", seed: int = 0,
):
    """月次ブロック単位で符号をランダム反転し、帰無分布（平均ゼロ）を作る両側順列検定。

    日次 PnL は系列相関を持つ（同一週・同一月で固まる）ため、観測単位でなく
    ブロック単位で符号を反転する。これにより自己相関を保ったまま帰無を構成する。
    返り値: (p_value, observed_stat)
    """
    vals = np.asarray(daily, dtype=float)
    vals = np.nan_to_num(vals, nan=0.0)
    if len(vals) == 0:
        return 1.0, 0.0
    obs = _stat(vals, metric)
    keys = _block_keys(index, len(vals), block)
    uniq = pd.unique(keys)
    idx_by_block = [np.where(keys == b)[0] for b in uniq]
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n_perm):
        signs = rng.choice((-1.0, 1.0), size=len(uniq))
        perm = vals.copy()
        for sgn, ii in zip(signs, idx_by_block):
            if sgn < 0:
                perm[ii] = -perm[ii]
        if abs(_stat(perm, metric)) >= abs(obs):
            count += 1
    p = (count + 1) / (n_perm + 1)  # +1 で偏りのない推定
    return float(p), float(obs)


def jackknife_year_pvalues(
    daily, index, block: str = "M", n_perm: int = 2000,
    metric: str = "sharpe", seed: int = 0,
):
    """1年ずつ抜いて p を再計算。最大 p を返す（どの1年に依存していないかを見る）。
    返り値: (p_max, {year: p})
    """
    s = pd.Series(np.asarray(daily, dtype=float), index=pd.DatetimeIndex(index))
    years = sorted(set(s.index.year))
    detail, pmax = {}, 0.0
    for y in years:
        sub = s[s.index.year != y]
        p, _ = block_sign_perm_pvalue(sub.values, sub.index, block, n_perm, metric, seed)
        detail[int(y)] = round(float(p), 4)
        pmax = max(pmax, p)
    return float(pmax), detail


def placebo_standout(target_daily, placebo_dailies: dict, metric: str = "sharpe"):
    """対象だけが突出しているか。placebo_dailies = {名前: daily系列}。
    返り値: {target, placebos:{...}, standout:bool, margin}
    """
    obs = _stat(np.asarray(target_daily, dtype=float), metric)
    pl = {k: _stat(np.asarray(v, dtype=float), metric) for k, v in placebo_dailies.items()}
    best_placebo = max(pl.values()) if pl else float("-inf")
    return {
        "target": round(obs, 4),
        "placebos": {k: round(v, 4) for k, v in pl.items()},
        "standout": bool(pl) and obs > best_placebo,
        "margin": round(obs - best_placebo, 4) if pl else None,
    }


def correlation(series_a, series_b) -> float:
    """同一頻度（例: 週次）に揃えた2系列の相関。重なりが少なければ NaN。"""
    a = pd.Series(np.asarray(series_a, dtype=float))
    b = pd.Series(np.asarray(series_b, dtype=float))
    j = pd.concat([a.reset_index(drop=True), b.reset_index(drop=True)], axis=1).dropna()
    if len(j) < 8:
        return float("nan")
    return float(j.iloc[:, 0].corr(j.iloc[:, 1]))
