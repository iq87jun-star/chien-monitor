# -*- coding: utf-8 -*-
"""
selection_value_walkforward.py — 【実験①】直近窓Top-4選抜は価値を生んでいるか。

docs/186の事前登録ルールの実装(実行前に凍結済み・本スクリプトでルール変更はしない)。

問い(docs/186 §1): 直近窓スコアによるTop-4選抜は、同一セル母集団のブロード配分に対して
真のアウトオブサンプルで優位を生むか。docs/184でD案の12ヶ月バウンドが62.2%→9.5%に
劣化したことが動機。

既存の3バウンド(楽観/中間/悲観)はいずれも「選抜という行為」を評価できていない
(docs/186 §0)。本スクリプトは選抜規則を毎月適用し続けるウォークフォワードを回し、
選抜時点で未知だった期間の実現成績だけでアームを比較する。

アーム: SEL12/SEL6/SEL3(=B/C/D案規則) vs BROAD_FILT/BROAD_IV/BROAD_EW(選抜なし)
出力: results/selection_value_walkforward.json → docs/187
⚠ Yahoo日足近似。実口座成績ではない。
"""
import os, sys, json, math
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base

# ---- 凍結窓(docs/184と同一・キャッシュ共用) ----
base.DATA = os.path.join(HERE, "data_202609")
os.makedirs(base.DATA, exist_ok=True)
base.P2_EPOCH = 1788220799                      # 2026-08-31 23:59:59 UTC
base.W_ALL1 = pd.Timestamp("2026-08-31")
W_END = pd.Timestamp("2026-08-31")
WF_START = pd.Timestamp("2019-01-31")           # ウォークフォワード開始(2016-18はウォームアップ)
WF_LAST = pd.Timestamp("2026-07-31")            # 最終リバランス(以後1ヶ月をOOSで観測)

SEED = 7
MULT_HARD_CAP = 6.0
W_CAP = 0.40
DAY_CAP, DD_CAP = 0.04, 0.08                    # m*校正(docs/180 §1)

# ---- アーム定義(docs/186 §3・実行前固定) ----
SEL_RULES = {
    "SEL12": dict(sel_m=12, conf_kind="months", conf_n=6, min_active=15, hold_m=3),
    "SEL6":  dict(sel_m=6,  conf_kind="months", conf_n=3, min_active=8,  hold_m=2),
    "SEL3":  dict(sel_m=3,  conf_kind="weeks",  conf_n=6, min_active=5,  hold_m=1),
}
BROAD_ARMS = ["BROAD_FILT", "BROAD_IV", "BROAD_EW"]
BROAD_HOLD_M = 3


def wnd(s, a, b):
    return s[(s.index >= a) & (s.index <= b)]


def conf_start(t, kind, n):
    return (t - pd.DateOffset(months=n) + pd.Timedelta(days=1)) if kind == "months" \
        else (t - pd.Timedelta(weeks=n) + pd.Timedelta(days=1))


def cell_window_stats(s, t, sel_m, conf_kind, conf_n):
    """t時点までのデータのみで算出(look-ahead無し)"""
    sel0 = t - pd.DateOffset(months=sel_m) + pd.Timedelta(days=1)
    w12_0 = t - pd.DateOffset(months=12) + pd.Timedelta(days=1)
    ssel = wnd(s, sel0, t); sconf = wnd(s, conf_start(t, conf_kind, conf_n), t)
    s12 = wnd(s, w12_0, t)
    act = ssel[ssel != 0.0]; n = int(len(act))
    std = float(act.std()) if n > 2 else float("nan")
    score = float(act.mean() / std * np.sqrt(n)) if (n > 2 and std > 0) else None
    a12 = s12[s12 != 0.0]
    std12 = float(a12.std()) if len(a12) > 2 else float("nan")
    return dict(n_active=n, cum_sel=float((1 + ssel).prod() - 1),
                cum_conf=float((1 + sconf).prod() - 1),
                cum_12m=float((1 + s12).prod() - 1),
                score=score, std_active=std,
                n_active_12m=int(len(a12)), std_12m=std12)


def cap_normalize(raw):
    """base.select_cells と同一手順: 正規化→cap一回→再正規化"""
    tot = sum(raw.values())
    if tot <= 0:
        return {}
    w = {k: v / tot for k, v in raw.items()}
    w = {k: min(v, W_CAP) for k, v in w.items()}
    t2 = sum(w.values())
    return {k: v / t2 for k, v in w.items()}


def weights_sel(table, min_active):
    ok = [(k, v) for k, v in table.items()
          if v["st"]["score"] is not None and v["st"]["n_active"] >= min_active
          and v["st"]["cum_sel"] > 0 and v["st"]["cum_conf"] > 0
          and np.isfinite(v["st"]["std_active"]) and v["st"]["std_active"] > 0]
    ok.sort(key=lambda kv: kv[1]["st"]["score"], reverse=True)
    picked, fam_ct, sym_used = [], {}, set()
    for k, v in ok:
        if v["family"] in ("",) or v["symbol"] in sym_used or fam_ct.get(v["family"], 0) >= 2:
            continue
        picked.append(k); sym_used.add(v["symbol"])
        fam_ct[v["family"]] = fam_ct.get(v["family"], 0) + 1
        if len(picked) == 4:
            break
    return cap_normalize({k: 1.0 / table[k]["st"]["std_active"] for k in picked})


def weights_broad(table, mode, min_active):
    """mode: FILT=SEL12と同一フィルタのみ / IV=全セル逆ボラ / EW=全セル等加重"""
    if mode == "FILT":
        keys = [k for k, v in table.items()
                if v["st"]["n_active"] >= min_active and v["st"]["cum_sel"] > 0
                and v["st"]["cum_conf"] > 0 and np.isfinite(v["st"]["std_12m"])
                and v["st"]["std_12m"] > 0]
    else:
        keys = [k for k, v in table.items()
                if v["st"]["n_active_12m"] >= 3 and np.isfinite(v["st"]["std_12m"])
                and v["st"]["std_12m"] > 0]
    if not keys:
        return {}
    if mode == "EW":
        return {k: 1.0 / len(keys) for k in keys}
    return cap_normalize({k: 1.0 / table[k]["st"]["std_12m"] for k in keys})


def composite(cells, weights, a, b):
    if not weights:
        return pd.Series(dtype=float)
    idx = sorted(set().union(*[set(wnd(cells[k]["s"], a, b).index) for k in weights]))
    if not idx:
        return pd.Series(dtype=float)
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, w in weights.items():
        out = out.add(wnd(cells[k]["s"], a, b).reindex(out.index).fillna(0.0) * w, fill_value=0.0)
    return out


def mstar(s):
    if len(s) == 0 or float(s.min()) >= 0:
        return 12.0
    best = 0.05
    for m in np.arange(0.05, 12.01, 0.05):
        wd, wdd = base.worst_stats(s * m)
        if wd >= -DAY_CAP and wdd >= -DD_CAP:
            best = m
        else:
            break
    return best


def mult_at(cells, weights, t, sel_m):
    """docs/186 §2の共通倍率規則。t以前のデータのみ使用"""
    if not weights:
        return 0.0
    sel0 = t - pd.DateOffset(months=sel_m) + pd.Timedelta(days=1)
    w12_0 = t - pd.DateOffset(months=12) + pd.Timedelta(days=1)
    m_sel = mstar(composite(cells, weights, sel0, t))
    m_12 = mstar(composite(cells, weights, w12_0, t))
    return round(min(0.8 * min(m_sel, m_12), MULT_HARD_CAP), 2)


def turnover(prev, cur):
    ks = set(prev) | set(cur)
    return 0.5 * sum(abs(cur.get(k, 0.0) - prev.get(k, 0.0)) for k in ks)


def run_arm(cells, arm, rebal_dates, hold_m):
    """ウォークフォワード実行。返り値: OOS日次系列・履歴"""
    is_sel = arm in SEL_RULES
    r = SEL_RULES[arm] if is_sel else SEL_RULES["SEL12"]
    pieces, hist, prev_w = [], [], {}
    for t in rebal_dates:
        table = {}
        for k, v in cells.items():
            table[k] = dict(family=v["family"], symbol=v["symbol"],
                            st=cell_window_stats(v["s"], t, r["sel_m"], r["conf_kind"], r["conf_n"]))
        if is_sel:
            w = weights_sel(table, r["min_active"])
        else:
            w = weights_broad(table, arm.split("_")[1], r["min_active"])
        mult = mult_at(cells, w, t, r["sel_m"] if is_sel else 12)
        end = min(t + pd.DateOffset(months=hold_m), W_END)
        seg_start = t + pd.Timedelta(days=1)
        seg = composite(cells, w, seg_start, end) * mult if w else pd.Series(dtype=float)
        # ノーポジション月も暦を埋める(0%として記録)
        if len(seg) == 0:
            cal = pd.date_range(seg_start, end, freq="B")
            seg = pd.Series(0.0, index=cal)
        pieces.append(seg)
        hist.append(dict(t=str(t.date()), n=len(w), mult=mult,
                         turnover=round(turnover(prev_w, w), 3),
                         w={k: round(v, 3) for k, v in sorted(w.items(), key=lambda x: -x[1])[:6]}))
        prev_w = w
    s = pd.concat(pieces).sort_index()
    s = s[~s.index.duplicated(keep="first")]
    return s, hist


def perf(s):
    if len(s) == 0:
        return {}
    act = s[s != 0.0]
    years = max((s.index[-1] - s.index[0]).days / 365.25, 1e-9)
    eq = (1 + s).cumprod()
    dd = float(((eq - eq.cummax()) / eq.cummax()).min())
    mk = pd.PeriodIndex(s.index, freq="M")
    wdd = 0.0
    for m in mk.unique():
        e = (1 + s[mk == m]).cumprod()
        wdd = min(wdd, float(((e - e.cummax()) / e.cummax()).min()))
    vol = float(s.std() * np.sqrt(252))
    cum = float(eq.iloc[-1] - 1)
    cagr = float(eq.iloc[-1] ** (1 / years) - 1)
    return dict(oos_cum=round(cum * 100, 2), oos_cagr=round(cagr * 100, 2),
                vol_ann=round(vol * 100, 2),
                sharpe=round(float(s.mean() / s.std() * np.sqrt(252)), 2) if s.std() > 0 else None,
                worst_day=round(float(s.min()) * 100, 2),
                worst_intramonth_dd=round(wdd * 100, 2), max_dd=round(dd * 100, 2),
                n_days=int(len(s)), n_active_days=int(len(act)),
                pct_flat_days=round(100.0 * (1 - len(act) / len(s)), 1))


def monthly(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    return pd.Series({k: float((1 + s[mk == k]).prod() - 1) for k in mk.unique()}).sort_index()


def block_boot_ci(d, rng, block=3, n=10000):
    """月次差の平均のブロックブートストラップ95%CI"""
    a = np.asarray(d, float)
    if len(a) < block + 1:
        return None, None
    nb = len(a) - block + 1
    st = rng.integers(0, nb, size=(n, len(a) // block + 1))
    samp = a[(st[:, :, None] + np.arange(block)[None, None, :])].reshape(n, -1)[:, :len(a)]
    m = samp.mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def ttest_paired(d):
    a = np.asarray(d, float)
    n = len(a)
    if n < 3 or a.std(ddof=1) == 0:
        return None, None
    tstat = float(a.mean() / (a.std(ddof=1) / np.sqrt(n)))
    # 正規近似の両側p(scipy非依存)
    p = float(2 * (1 - 0.5 * (1 + math.erf(abs(tstat) / np.sqrt(2)))))
    return round(tstat, 2), round(p, 4)


def main():
    rng = np.random.default_rng(SEED)
    print("[1/5] データ取得(凍結窓 2016-01-01..2026-08-31)")
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:60]}")

    print("[2/5] セル構築(34セル・docs/174と同一母集団)")
    cells = {}
    for nm in base.MON_FX + base.MON_IDX:
        cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    for nm in base.HOLD_SYMS:
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    for nm in base.TSMOM_SYMS:
        cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
    for p in base.V4_PAIRS:
        cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))
    print(f"  セル数 {len(cells)}")

    rebal_all = pd.date_range(WF_START, WF_LAST, freq="ME")
    arms = list(SEL_RULES) + BROAD_ARMS
    out = {"meta": {
        "purpose": "選抜(Top-4)の価値をウォークフォワードで検証(docs/186)",
        "freeze": "2016-01-01..2026-08-31", "seed": SEED,
        "wf_rebalance": f"{WF_START.date()}..{WF_LAST.date()} 月末",
        "n_cells": len(cells), "mult_rule": "0.8*min(m*_sel, m*_12m), cap 6.0",
        "approx": ["Yahoo日足近似", "実口座成績ではない",
                   "セル構築式は全てcausal(全期間一括構築=逐次構築)",
                   "月曜o2oは月曜始値→火曜始値の実現(月末跨ぎの計上ズレは最大1営業日)"]},
        "arms": {}, "monthly_series": {}, "history": {}}

    print("[3/5] ウォークフォワード実行")
    daily = {}
    for mode, tag in ((1, "monthly"), (None, "cadence")):
        for arm in arms:
            hold = 1 if mode == 1 else (SEL_RULES[arm]["hold_m"] if arm in SEL_RULES else BROAD_HOLD_M)
            dates = rebal_all if mode == 1 else rebal_all[::hold]
            s, hist = run_arm(cells, arm, dates, hold)
            daily[(tag, arm)] = s
            out["arms"].setdefault(arm, {})[tag] = perf(s)
            if tag == "monthly":
                out["history"][arm] = hist
                out["monthly_series"][arm] = {str(k): round(v * 100, 2)
                                              for k, v in monthly(s).items()}
                avg_to = np.mean([h["turnover"] for h in hist[1:]]) if len(hist) > 1 else 0
                avg_n = np.mean([h["n"] for h in hist])
                avg_m = np.mean([h["mult"] for h in hist])
                out["arms"][arm]["walkforward"] = dict(
                    avg_turnover=round(float(avg_to), 3), avg_n_cells=round(float(avg_n), 1),
                    avg_mult=round(float(avg_m), 2),
                    n_flat_rebalances=int(sum(1 for h in hist if h["n"] == 0)))
            print(f"  {tag:8s} {arm:11s} {out['arms'][arm][tag]}")

    print("[4/5] MC(OOS系列に対する正直なバウンド)")
    for arm in arms:
        s = daily[("monthly", arm)]
        for venue, p1 in (("FTMO_10_5", 0.10), ("FN_8_5", 0.08)):
            base.P1_TARGET = p1
            out["arms"][arm].setdefault("mc_oos", {})[venue] = base.mc_challenge(
                s, 1.0, np.random.default_rng(SEED))
        print(f"  {arm:11s} {out['arms'][arm]['mc_oos']}")

    print("[5/5] 検定・相関")
    mons = {a: monthly(daily[("monthly", a)]) for a in arms}
    idx = sorted(set().union(*[set(m.index) for m in mons.values()]))
    M = pd.DataFrame({a: mons[a].reindex(idx).fillna(0.0) for a in arms})
    out["corr_oos_monthly"] = {a: {b: round(float(M[a].corr(M[b])), 2) for b in arms} for a in arms}
    tests = {}
    for a, b in [("SEL12", "BROAD_IV"), ("SEL6", "BROAD_IV"), ("SEL3", "BROAD_IV"),
                 ("SEL12", "BROAD_FILT"), ("SEL12", "BROAD_EW"), ("BROAD_FILT", "BROAD_IV")]:
        d = (M[a] - M[b]).values
        t, p = ttest_paired(d)
        lo, hi = block_boot_ci(d, rng)
        tests[f"{a}-{b}"] = dict(
            mean_monthly_diff_pct=round(float(np.mean(d)) * 100, 3), t=t, p=p,
            ci95_monthly_pct=[round(lo * 100, 3), round(hi * 100, 3)] if lo is not None else None,
            significant=bool(lo is not None and (lo > 0 or hi < 0)), n_months=int(len(d)))
        print(f"  {a}-{b}: {tests[f'{a}-{b}']}")
    out["tests"] = tests

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    fp = os.path.join(HERE, "results", "selection_value_walkforward.json")
    with open(fp, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved:", fp)


if __name__ == "__main__":
    main()
