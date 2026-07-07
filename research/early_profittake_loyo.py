# -*- coding: utf-8 -*-
"""
early_profittake_loyo.py — docs/114(事前登録)の実行: 月内途中利確(手決済の体系化)の
ルール族 T1(固定閾値)/T2(トレーリング)/T3(時間切り) を、LOYO OOSの
「校正後期待月利(mult×平均月利)」でT0(現行=途中利確なし)と比較する。

⚠ 事前登録(docs/114)の後に実行。結果はdocs/115へ転記。ルール・グリッド・決定規則は
  docs/114から変更しない。
再利用: seasonal_optimize_loyo(fetch/SHA/月次スリーブ/R4重み) +
        portfolio_daily_compare(日次スリーブ/合成/倍率校正) — 逐語流用。
出力: results/early_profittake_loyo.json
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("RG_ALLOW_YAHOO", "0")

from seasonal_optimize_loyo import fetch_all, sha256s, build_sleeves, month_stats, weights_for, LOYO_YEARS
from portfolio_daily_compare import (load_daily, clip, mon_daily, cc_daily, e5_daily, v4_daily,
                                     composite_daily, calibrate, worst_stats, M3,
                                     YEN, V7X, EMON, EMONX)

SEED = 7
PLACEBO_REPS = 200
GRIDS = {"T1": [1.0, 1.5, 2.0, 3.0], "T2": [0.5, 1.0, 1.5], "T3": [10, 15]}
T2_ARM = 1.0          # トレーリングのアーム水準(+1.0% MTD・docs/114 §2で固定)
COND_X = [1.0, 1.5, 2.0, 3.0]   # §3-7 条件付き分布の到達水準


# ---------- 日次スリーブ(cost_mult対応・portfolio_daily_compareの流用+コスト倍率) ----------
def build_daily_sleeves(cm=1.0):
    from portfolio_daily_compare import pip_size
    def mon_cm(names, idx_cost=None):
        parts = []
        for nm in names:
            df = load_daily(nm)
            cost = (idx_cost if idx_cost is not None else 2 * pip_size(nm) / df["open"]) * cm
            parts.append((df[df["weekday"] == 0]["o2o"] - cost).rename(nm))
        return clip(pd.concat(parts, axis=1).mean(axis=1, skipna=True).dropna())
    sl = dict(v7=mon_cm(YEN), v7x=mon_cm(V7X),
              EMon=mon_cm(EMON, 3e-4), EMonX=mon_cm(EMONX, 3e-4),
              E5=e5_daily(), SJul=cc_daily(["US500", "NAS100"]), v4=v4_daily())
    if cm > 1.0:
        # 近似(docs/104と同旨・保守側): v4 +0.04%/月, E5 +0.05%/月, SJul +0.05%/月 を月初日に追加控除
        for k, extra in (("v4", 4e-4), ("E5", 5e-4), ("SJul", 5e-4)):
            s = sl[k].copy()
            mk = pd.PeriodIndex(s.index, freq="M")
            firsts = pd.Series(s.index, index=s.index).groupby(mk).min()
            s.loc[s.index.isin(firsts.values)] -= extra * (cm - 1.0)
            sl[k] = s
    return sl


# ---------- ルール適用(当日終値で判定→翌日以降を当月ゼロ=全決済+新規停止) ----------
def apply_rule(daily, rule, param):
    if rule == "T0":
        return daily, dict(trig_months=0, months=0, mean_trig_day=None)
    out = daily.copy()
    mk = pd.PeriodIndex(daily.index, freq="M")
    trig_n, days = 0, []
    for m in mk.unique():
        s = daily[mk == m]
        cum = (1 + s).cumprod().values - 1.0
        trig = None
        if rule == "T1":
            hit = np.where(cum >= param / 100.0)[0]
            trig = int(hit[0]) if len(hit) else None
        elif rule == "T2":
            peak = np.maximum.accumulate(cum)
            hit = np.where((peak >= T2_ARM / 100.0) & (cum <= peak - param / 100.0))[0]
            trig = int(hit[0]) if len(hit) else None
        elif rule == "T3":
            trig = int(param) - 1 if len(s) > int(param) else None
        if trig is not None:
            trig_n += 1; days.append(trig + 1)
            if trig < len(s) - 1:
                out.loc[s.index[trig + 1:]] = 0.0
    return out, dict(trig_months=trig_n, months=int(len(mk.unique())),
                     mean_trig_day=round(float(np.mean(days)), 1) if days else None)


# ---------- 採点 ----------
def monthly_series(daily):
    mk = pd.PeriodIndex(daily.index, freq="M")
    return pd.Series({m: float((1 + daily[mk == m]).prod() - 1) for m in mk.unique()}).sort_index()


def score_series(daily):
    """主指標: 校正後期待月利 = mult(docs/87逆算×0.8) × 平均月利(1x)。副指標同梱。"""
    mret = monthly_series(daily)
    mult = calibrate(daily)                      # 最悪単日-4%/月中DD-8% 逆算×0.8(既存コード)
    eq = (1 + mret).cumprod()
    dd = float(((eq - eq.cummax()) / eq.cummax()).min()) * 100
    mu = mret.mean() * 12; vol = mret.std() * np.sqrt(12)
    cagr = (eq.iloc[-1] ** (12 / len(mret)) - 1) * 100 if eq.iloc[-1] > 0 else -100
    wd, wdd = worst_stats(daily)
    return dict(score_calib_mean=round(mult * float(mret.mean() * 100), 3),
                mult=mult, mean_month_pct=round(float(mret.mean() * 100), 3),
                sharpe=round(float(mu / vol) if vol > 0 else 0, 3),
                maxDD=round(dd, 2), calmar=round(float(cagr / abs(dd)), 2) if dd else 0.0,
                worst_month_pct=round(float(mret.min() * 100), 2),
                worst_day_pct=round(wd * 100, 2), worst_intramonth_DD=round(wdd * 100, 2),
                months=int(len(mret)))


# ---------- LOYO ----------
def loyo_run(sleeves, df_monthly, baseline):
    """baseline: 'R4'(主基準・フォールド毎に重み再学習) or 'M3'(固定テーブル)。
       返り値: {rule: dict(oos_daily, params_by_fold, trig)}"""
    res = {r: dict(parts=[], params={}, trig=[]) for r in ["T0", "T1", "T2", "T3"]}
    for y in LOYO_YEARS:
        train = [t for t in LOYO_YEARS if t != y]
        if baseline == "R4":
            mu, sd = month_stats(df_monthly, train)
            wmap = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}
        else:
            wmap = M3
        comp = composite_daily(sleeves, wmap)
        tr = comp[[t.year in train for t in comp.index]]
        te = comp[comp.index.year == y]
        res["T0"]["parts"].append(te)
        for rule, grid in GRIDS.items():
            best, bp = None, None
            for p in grid:
                d, _ = apply_rule(tr, rule, p)
                sc = score_series(d)
                key = (sc["score_calib_mean"], sc["calmar"])
                if best is None or key > best:
                    best, bp = key, p
            d, st = apply_rule(te, rule, bp)
            res[rule]["parts"].append(d)
            res[rule]["params"][y] = bp
            res[rule]["trig"].append(st)
    out = {}
    for rule, d in res.items():
        oos = pd.concat(d["parts"]).sort_index()
        sc = score_series(oos)
        if rule != "T0":
            tm = sum(t["trig_months"] for t in d["trig"]); mm = sum(t["months"] for t in d["trig"])
            days = [t["mean_trig_day"] for t in d["trig"] if t["mean_trig_day"]]
            sc["trigger_rate_pct"] = round(100.0 * tm / mm, 1) if mm else 0.0
            sc["mean_trigger_day"] = round(float(np.mean(days)), 1) if days else None
            sc["params_by_fold"] = d["params"]
        out[rule] = dict(stats=sc, oos=oos)
    return out


# ---------- プラセボ: 発動頻度を合わせたランダム日打ち切り ----------
def placebo(daily_T0, trigger_rate, real_score, rng):
    dist = []
    mk = pd.PeriodIndex(daily_T0.index, freq="M")
    mlist = list(mk.unique())
    for _ in range(PLACEBO_REPS):
        out = daily_T0.copy()
        for m in mlist:
            if rng.random() < trigger_rate:
                s = daily_T0[mk == m]
                if len(s) > 6:
                    t = int(rng.integers(4, len(s) - 1))
                    out.loc[s.index[t + 1:]] = 0.0
        dist.append(score_series(out)["score_calib_mean"])
    dist = np.array(dist)
    return dict(real=real_score, placebo_mean=round(float(dist.mean()), 3),
                placebo_p95=round(float(np.percentile(dist, 95)), 3),
                p_value=round(float((dist >= real_score).mean()), 4),
                verdict=("利益条件に固有価値あり" if (dist >= real_score).mean() < 0.05
                         else "ランダム打ち切りと区別できない"))


# ---------- 条件付き分布: 「+X%到達後、持ち続けると残月はどうなるか」 ----------
def conditional_afterX(daily):
    out = {}
    mk = pd.PeriodIndex(daily.index, freq="M")
    for X in COND_X:
        rem = []
        for m in mk.unique():
            s = daily[mk == m]
            cum = (1 + s).cumprod().values - 1.0
            hit = np.where(cum >= X / 100.0)[0]
            if len(hit):
                t = hit[0]
                rem.append(((1 + cum[-1]) / (1 + cum[t]) - 1.0) * 100)
        if rem:
            a = np.array(rem)
            out[f"+{X}%"] = dict(n_months=int(len(a)), mean=round(float(a.mean()), 2),
                                 median=round(float(np.median(a)), 2),
                                 p25=round(float(np.percentile(a, 25)), 2),
                                 p75=round(float(np.percentile(a, 75)), 2),
                                 pct_negative=round(float((a < 0).mean() * 100), 0))
    return out


def main():
    rng = np.random.default_rng(SEED)
    print("[1/6] データ取得(2015-01〜2026-06 固定窓・SHA-256記録)")
    fetch_all()
    hashes = sha256s()

    print("[2/6] スリーブ構築(月次=R4重み用 / 日次=ルール適用用)")
    dfm = build_sleeves(1.0)
    dfm = dfm[(dfm.index.year >= 2016) & (dfm.index.year <= 2025)]
    sleeves = build_daily_sleeves(1.0)
    print("  日次:", {k: len(v) for k, v in sleeves.items()})

    print("[3/6] LOYO OOS採点(主基準R4 / 参考M3)")
    results = {}
    oos_keep = {}
    for base in ("R4", "M3"):
        r = loyo_run(sleeves, dfm, base)
        results[base] = {k: v["stats"] for k, v in r.items()}
        oos_keep[base] = {k: v["oos"] for k, v in r.items()}
        for k in ("T0", "T1", "T2", "T3"):
            print(f"  [{base}] {k}: {results[base][k]}")

    print("[4/6] プラセボ(発動頻度マッチのランダム打ち切り×%d)" % PLACEBO_REPS)
    cands = {k: v["stats"]["score_calib_mean"] for k, v in
             {kk: dict(stats=results["R4"][kk]) for kk in ("T1", "T2", "T3")}.items()}
    winner = max(cands, key=cands.get)
    plc = placebo(oos_keep["R4"]["T0"], results["R4"][winner]["trigger_rate_pct"] / 100.0,
                  results["R4"][winner]["score_calib_mean"], rng)
    print(f"  winner候補 {winner}: {plc}")

    print("[5/6] コスト2倍感応(LOYO再実行・パラメータ再選択込み)")
    sleeves2 = build_daily_sleeves(2.0)
    dfm2 = build_sleeves(2.0)
    dfm2 = dfm2[(dfm2.index.year >= 2016) & (dfm2.index.year <= 2025)]
    r2 = loyo_run(sleeves2, dfm2, "R4")
    cost2 = {k: v["stats"] for k, v in r2.items()}
    for k in ("T0", "T1", "T2", "T3"):
        print(f"  cost2x [{k}] score {results['R4'][k]['score_calib_mean']} -> {cost2[k]['score_calib_mean']}")

    print("[6/6] 条件付き分布(+X%到達後の残月・T0/R4のOOS系列)")
    cond = conditional_afterX(oos_keep["R4"]["T0"])
    for k, v in cond.items():
        print(f"  {k}: {v}")

    # 参考: 2026H1(LOYO外)— 2016-2025訓練のR4重み+勝者パラメータを2026H1に適用
    mu, sd = month_stats(dfm, LOYO_YEARS)
    wmap26 = {m: weights_for("R4", mu.loc[m], sd.loc[m]) for m in range(1, 13)}
    comp26 = composite_daily(sleeves, wmap26)
    comp26 = comp26[comp26.index.year == 2026]
    best26, bp26 = None, None
    full = composite_daily(sleeves, wmap26)
    fullTr = full[full.index.year <= 2025]
    for p in GRIDS[winner]:
        d, _ = apply_rule(fullTr, winner, p)
        sc = score_series(d)
        key = (sc["score_calib_mean"], sc["calmar"])
        if best26 is None or key > best26:
            best26, bp26 = key, p
    d26, _ = apply_rule(comp26, winner, bp26)
    ref26 = dict(T0=round(float(((1 + comp26).prod() - 1) * 100), 2),
                 **{winner: round(float(((1 + d26).prod() - 1) * 100), 2)}, param=bp26)
    print("  2026H1参考(1x・LOYO外):", ref26)

    # 決定規則(docs/114 §4)の機械適用 — 主基準R4・勝者候補のみ採用対象
    t0 = results["R4"]["T0"]
    c = results["R4"][winner]
    checks = dict(
        score_110pct=bool(c["score_calib_mean"] >= 1.1 * t0["score_calib_mean"]),
        worst_month_not_worse=bool(c["worst_month_pct"] >= t0["worst_month_pct"]),
        placebo_pass=bool(plc["p_value"] < 0.05),
        cost2x_rank_kept=bool(cost2[winner]["score_calib_mean"] >= cost2["T0"]["score_calib_mean"]))
    if all(checks.values()):
        decision, why = winner, "決定規則(docs/114 §4)を全て満たす"
    else:
        failed = [k for k, v in checks.items() if not v]
        decision, why = "T0(現行=途中利確なし)", f"不合格条件: {failed}"

    out = dict(prereg="docs/114", loyo_years=LOYO_YEARS, input_sha256=hashes,
               grids=GRIDS, t2_arm=T2_ARM,
               loyo_oos=dict(R4=results["R4"], M3=results["M3"]),
               placebo=dict(rule=winner, **plc),
               cost2x_R4=cost2,
               conditional_after_reach=cond, ref_2026H1_net_pct=ref26,
               decision=dict(winner_candidate=winner, checks=checks, adopted=decision, reason=why))
    path = os.path.join(HERE, "results", "early_profittake_loyo.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)
    print("決定:", decision, "|", why)


if __name__ == "__main__":
    main()
