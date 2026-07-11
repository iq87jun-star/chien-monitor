# -*- coding: utf-8 -*-
"""
edge24_mof_flows.py — docs/129 の実行(W4: MOF週次証券フロー・ユーザー指示による白地消化)。
  M1: v7週次PnLを「最新公表の対外合計ネット vs 直近52レポート中央値」で分割(フィルタ採否)
  M2: 対外投資4週合計 vs 52週中央値 → USDJPY LONG/SHORT(週次・全週アクティブ)
  M3: 対内株式4週合計 vs 52週中央値 → JP225 LONG/SHORT(週次)
公表ラグ: 対象週(日〜土S)→翌週木曜公表→S+9日の月曜から有効。ルール・α=0.0033はdocs/129固定。
出力: results/edge24_mof_flows.json(入力SHA-256付き) → docs/130 へ転記。
"""
import os, sys, re, json, csv, glob, hashlib, urllib.request, datetime as dt
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
MOF = os.path.join(DATA, "mof", "week.csv")
sys.path.insert(0, HERE)

ALPHA = 0.01 / 3
MAIN = ("2016-01-01", "2026-06-30")
PRE = ("2006-01-01", "2015-12-31")
IS_END, OOS_START = "2020-12-31", "2021-01-01"
MED_WIN = 52
SUM_WIN = 4

from edge23_cot_positioning import (load_daily, weekly_open_returns, pip_size,
                                    weekly_cost, clip, metrics, perm_p, jackknife,
                                    v7_weekly, fetch)


def ensure_n225():
    p = os.path.join(DATA, "JP225_d.csv")
    if not os.path.exists(p):
        n = fetch("JP225", "%5EN225")
        print(f"  fetch JP225: {n} rows")


def parse_mof():
    """week.csv → DataFrame(week_end(土曜), out_total, out_lt, out_eq, in_eq)。億円。"""
    raw = open(MOF, "rb").read().decode("cp932", errors="replace")
    rows = []
    pat = re.compile(r"^(\d{4})．\s*(\d+)．\s*(\d+)[～〜]")
    for line in csv.reader(raw.splitlines()):
        if not line or not line[0]:
            continue
        m = pat.match(line[0].replace(" ", "").replace("　", ""))
        if not m:
            continue
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            start = dt.date(y, mo, d)
        except ValueError:
            continue
        week_end = start + dt.timedelta(days=6)

        def num(i):
            s = line[i].replace(",", "").replace('"', "").replace(" ", "").replace("　", "")
            if s in ("", "-", "…", "―"):
                return np.nan
            try:
                return float(s)
            except ValueError:
                return np.nan
        # 列: 1株取 2株処 3株净 4中取 5中処 6中净 7小計 8短取 9短処 10短净 11合計 |
        #     12株取 13株処 14株净 ... 22合計
        rows.append(dict(week_end=pd.Timestamp(week_end),
                         out_eq=num(3), out_lt=num(6), out_total=num(11),
                         in_eq=num(14)))
    df = pd.DataFrame(rows).dropna(subset=["out_total"]).drop_duplicates("week_end")
    return df.sort_values("week_end").set_index("week_end")


def effective_monday(week_end):
    """土曜S → S+9(公表木曜の翌月曜)。週端が土曜でない行も『次の月曜+7日』に正規化。"""
    d = week_end + pd.Timedelta(days=9)
    while d.dayofweek != 0:
        d += pd.Timedelta(days=1)
    return d


def signal_series(col, mode):
    """mode='level': 最新値>直近52レポート中央値(自身除く)
       mode='sum4' : 4週合計>直近52週の4週合計中央値(自身除く)。indexは有効月曜。"""
    s = FLOW[col]
    base = s.rolling(SUM_WIN).sum() if mode == "sum4" else s
    med = base.shift(1).rolling(MED_WIN, min_periods=MED_WIN).median()
    sig = (base > med).astype(float) * 2 - 1          # 超=+1 / 以下=−1
    sig[base.isna() | med.isna()] = np.nan
    sig.index = [effective_monday(t) for t in sig.index]
    sig = sig[~sig.index.duplicated(keep="last")]
    return sig.dropna()


def weekly_strategy(pair, sig, cost_rt):
    """returns (r, wret, pos): pos=±1(有効シグナル・3週まで持越し許容)。"""
    wret = weekly_open_returns(pair)
    al = sig.reindex(wret.index, method="ffill")      # 直近有効シグナルを適用
    gap = pd.Series(sig.index, index=sig.index).reindex(wret.index, method="ffill")
    ok = (wret.index - gap) <= pd.Timedelta(days=21)
    pos = al.where(ok)
    r = (pos * wret - cost_rt).dropna()
    return r, wret, pos


def gate_battery(r, wret, pos, cost_rt):
    """ドリフト保存プラセボ = ポジション列(±1)を週間シャッフル(docs/129 §2)。"""
    m = metrics(r)
    p = perm_p(r)
    jk, jk_pos, jk_n = jackknife(r)
    r_is = clip(r, MAIN[0], IS_END); r_oos = clip(r, OOS_START, MAIN[1])
    w = clip(wret, *MAIN)
    pv = pos.reindex(w.index).values
    mask = ~np.isnan(pv)
    rng = np.random.default_rng(11)
    nets = []
    base = pv[mask].copy()
    wv = w.values[mask]
    for _ in range(500):
        rng.shuffle(base)
        nets.append(float((base * wv - cost_rt).sum()))
    plc_p95 = round(float(np.quantile(nets, 0.95)) * 100, 2)
    return m, p, jk, jk_pos, jk_n, r_is, r_oos, plc_p95


def main():
    global FLOW
    R = {"meta": dict(started=dt.datetime.now(dt.timezone.utc).isoformat(),
                      alpha=ALPHA, spec="docs/129")}
    print("[1/5] データ準備")
    ensure_n225()
    FLOW = parse_mof()
    print(f"  MOF: {len(FLOW)}週 {FLOW.index.min().date()}..{FLOW.index.max().date()}")
    R["meta"]["mof_weeks"] = int(len(FLOW))
    R["meta"]["mof_range"] = [str(FLOW.index.min().date()), str(FLOW.index.max().date())]

    # ---------- M1: v7 × 対外投資分割 ----------
    print("[2/5] M1 v7×フロー分割")
    v7w = v7_weekly()
    sig = signal_series("out_total", "level")          # +1=中央値超
    v7m = clip(v7w, *MAIN)
    al = sig.reindex(v7m.index, method="ffill")
    gap = pd.Series(sig.index, index=sig.index).reindex(v7m.index, method="ffill")
    ok = (v7m.index - gap) <= pd.Timedelta(days=21)
    al = al.where(ok)
    hi_w = v7m[al > 0]; lo_w = v7m[al < 0]
    unf, flt = float(v7m.sum()), float(hi_w.sum())
    obs = hi_w.mean() - lo_w.mean()
    lab = al.dropna(); vv = v7m.reindex(lab.index).values; hs = (lab > 0).values.copy()
    rng = np.random.default_rng(24); cnt = 0
    for _ in range(4000):
        rng.shuffle(hs)
        if vv[hs].mean() - vv[~hs].mean() >= obs:
            cnt += 1
    m1_p = round((cnt + 1) / 4001, 5)
    m1 = dict(n_hi=int(len(hi_w)), n_lo=int(len(lo_w)),
              v7_unfiltered_net=round(unf * 100, 2), v7_filtered_net=round(flt * 100, 2),
              mean_bps_hi=round(float(hi_w.mean()) * 1e4, 1),
              mean_bps_lo=round(float(lo_w.mean()) * 1e4, 1),
              split_perm_p=m1_p,
              gates=dict(filter_improves=flt > unf, split_p=m1_p < ALPHA))
    m1["verdict"] = "フィルタ採用候補" if all(m1["gates"].values()) else "REJECT(v7素通し維持)"
    R["M1"] = m1
    print(f"  M1: 素通し={m1['v7_unfiltered_net']}% フィルタ={m1['v7_filtered_net']}% "
          f"hi={m1['mean_bps_hi']}bps lo={m1['mean_bps_lo']}bps p={m1_p} → {m1['verdict']}")

    # ---------- M2 / M3 ----------
    for mid, col, pair, cost in (("M2", "out_total", "USDJPY", None),
                                 ("M3", "in_eq", "JP225", 3e-4)):
        print(f"[3/5] {mid}")
        sig = signal_series(col, "sum4")
        cost_rt = weekly_cost(pair) if cost is None else cost
        r_all, wret, pos = weekly_strategy(pair, sig, cost_rt)
        r = clip(r_all, *MAIN)
        m, p, jk, jk_pos, jk_n, r_is, r_oos, plc_p95 = gate_battery(r, wret, pos, cost_rt)
        r2 = clip(weekly_strategy(pair, sig, cost_rt * 2)[0], *MAIN)
        m2 = metrics(r2)
        pre = clip(r_all, *PRE)
        mpre = metrics(pre); ppre = perm_p(pre)
        gates = dict(G1_econ=m["net"] > 0, G2_perm=p < ALPHA,
                     G3_jk=(jk_pos / jk_n) >= 0.9 if jk_n else False,
                     G4_placebo=m["net"] > plc_p95,
                     G5_cost2x=m2["net"] > 0,
                     G6_isoos=(float(r_is.sum()) > 0 and float(r_oos.sum()) > 0))
        R[mid] = dict(main=m, perm_p=p, jk_pass=f"{jk_pos}/{jk_n}", jackknife=jk,
                      cost2x_net=m2["net"], is_net=round(float(r_is.sum()) * 100, 2),
                      oos_net=round(float(r_oos.sum()) * 100, 2), placebo_p95=plc_p95,
                      pre2016=dict(net=mpre["net"], perm_p=ppre, n=mpre["n_weeks"]),
                      gates=gates, gates_passed=sum(gates.values()),
                      verdict="ADOPT候補(G8確認へ)" if all(gates.values()) else "REJECT")
        print(f"  {mid}: net={m['net']}% p={p} JK={jk_pos}/{jk_n} pre16={mpre['net']}% "
              f"ゲート{sum(gates.values())}/6 → {R[mid]['verdict']}")

    # ---------- G8(記録) ----------
    print("[4/5] G8 相関")
    try:
        from parallel_vs_existing_compare import v7_monthly, v4_monthly, e5_monthly, emon_monthly
        sleeves = dict(v4=v4_monthly(), v7=v7_monthly(), EMon=emon_monthly(), E5=e5_monthly())
        for mid, col, pair, cost in (("M2", "out_total", "USDJPY", None),
                                     ("M3", "in_eq", "JP225", 3e-4)):
            sig = signal_series(col, "sum4")
            cost_rt = weekly_cost(pair) if cost is None else cost
            r = clip(weekly_strategy(pair, sig, cost_rt)[0], *MAIN)
            cm = r.copy(); cm.index = cm.index.to_period("M"); cm = cm.groupby(level=0).sum()
            cc = {}
            for k, s in sleeves.items():
                j = pd.concat([cm.rename("c"), s.rename("s")], axis=1).dropna()
                cc[k] = round(float(j["c"].corr(j["s"])), 3) if len(j) > 12 else None
            R[mid]["G8_corr"] = cc
            R[mid]["gates"]["G8"] = all(v is None or abs(v) < 0.4 for v in cc.values())
        print("  corr:", {c: R[c].get("G8_corr") for c in ("M2", "M3")})
    except Exception as e:
        print("  G8 skip:", e)

    # ---------- ハッシュ・保存 ----------
    print("[5/5] 保存")
    hashes = {"week.csv": hashlib.sha256(open(MOF, "rb").read()).hexdigest()[:16]}
    for n in ("USDJPY", "EURJPY", "GBPJPY", "JP225"):
        p = os.path.join(DATA, f"{n}_d.csv")
        if os.path.exists(p):
            hashes[f"{n}_d.csv"] = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    R["input_sha256"] = hashes
    out = os.path.join(HERE, "results", "edge24_mof_flows.json")
    json.dump(R, open(out, "w"), indent=1, ensure_ascii=False, default=str)
    print("saved:", out)


if __name__ == "__main__":
    main()
