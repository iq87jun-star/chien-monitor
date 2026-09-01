# -*- coding: utf-8 -*-
"""
correlation_penalty_wf.py — 【実験⑥】相関ペナルティ付き選抜(docs/193の実装)。

問い: 2口座目の選抜スコアに「1口座目との相関ペナルティ」を1項加えると、
docs/185 §2のサーキットブレーカー(30日以内に2口座失格)の発火確率は下がるか。

現状 Mon GBPJPY は最大5口座で並走している(docs/181 §3)。規約上は可でも、
ある月曜の朝に5口座が同時に傷つく構造は残る。本実験はそれを選抜段階で緩和できるか測る。

核心はペア同時MC: 2口座に**同一のブートストラップ・ブロック**を適用してクロス相関を保存する
(独立に2回引くと相関が消え、測りたいものが消える)。
出力: results/correlation_penalty_wf.json → docs/193 §8
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
import selection_value_walkforward as wf     # セル構築・窓・選抜の実装を再利用

SEED = 7
N_MC = 10000
BLOCK = 5
MAX_DAYS = 250
MAX_DD = 0.10
GUARD = 0.04
CB_WINDOW = 30                                # docs/185 §2: 30日以内に2口座失格
ARMS = {"LAM0": 0.0, "EXCL": 0.0, "LAM05": 0.5, "LAM10": 1.0}
R = wf.SEL_RULES["SEL12"]


def corr_to(cell_s, ref, a, t):
    x = wf.wnd(cell_s, a, t); y = wf.wnd(ref, a, t)
    j = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    if len(j) < 30 or j["x"].std() == 0 or j["y"].std() == 0:
        return 0.0
    c = float(j["x"].corr(j["y"]))
    return 0.0 if not np.isfinite(c) else c


def weights_B(cells, table, arm, w_A, ref_A, sel0, t):
    """口座B: 現行フィルタ+制約は不変。スコアにペナルティ1項だけを加える。"""
    lam = ARMS[arm]
    ok = [(k, v) for k, v in table.items()
          if v["st"]["score"] is not None and v["st"]["n_active"] >= R["min_active"]
          and v["st"]["cum_sel"] > 0 and v["st"]["cum_conf"] > 0
          and np.isfinite(v["st"]["std_active"]) and v["st"]["std_active"] > 0]
    if arm == "EXCL":
        ok = [(k, v) for k, v in ok if k not in w_A]
    scored = []
    for k, v in ok:
        s = v["st"]["score"]
        if lam > 0 and ref_A is not None:
            s = s * (1.0 - lam * max(0.0, corr_to(cells[k]["s"], ref_A, sel0, t)))
        scored.append((k, v, s))
    scored.sort(key=lambda x: -x[2])
    picked, fam_ct, sym_used = [], {}, set()
    for k, v, _ in scored:
        if v["symbol"] in sym_used or fam_ct.get(v["family"], 0) >= 2:
            continue
        picked.append(k); sym_used.add(v["symbol"])
        fam_ct[v["family"]] = fam_ct.get(v["family"], 0) + 1
        if len(picked) == 4:
            break
    return wf.cap_normalize({k: 1.0 / table[k]["st"]["std_active"] for k in picked})


def simulate(paths, mult, p1t, p2t):
    """固定倍率の2段階チャレンジ。失格日を返す(未失格は-1)。"""
    n, T = paths.shape
    eq = np.ones(n); ref = np.ones(n); phase = np.zeros(n, int)
    funded = np.zeros(n, bool); failed = np.zeros(n, bool); fail_day = np.full(n, -1)
    p1_ok = np.zeros(n, bool)
    for t in range(T):
        alive = ~(failed | funded)
        if not alive.any():
            break
        ret = np.clip(paths[:, t] * mult, -GUARD, None)
        eq = np.where(alive, eq * (1 + ret), eq)
        rel = eq / ref - 1.0
        nf = alive & (rel <= -MAX_DD)
        failed |= nf; fail_day[nf] = t + 1
        alive = ~(failed | funded)
        hit = alive & (rel >= np.where(phase == 0, p1t, p2t))
        h1 = hit & (phase == 0)
        if t < MAX_DAYS:
            p1_ok |= h1; ref[h1] = eq[h1]; phase[h1] = 1
        h2 = hit & (phase == 1)
        funded |= h2
    return funded, failed, fail_day, p1_ok


def mc_pair(sA, sB, multA, multB, p1t, p2t, rng):
    j = pd.concat([sA.rename("a"), sB.rename("b")], axis=1).fillna(0.0)
    r = j.values
    nb = len(r) - BLOCK + 1
    T = MAX_DAYS * 2
    st = rng.integers(0, nb, size=(N_MC, T // BLOCK + 1))
    idxs = (st[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N_MC, -1)[:, :T]
    pA = r[idxs, 0]; pB = r[idxs, 1]                     # 同一ブロック=クロス相関を保存
    fA, xA, dA, _ = simulate(pA, multA, p1t, p2t)
    fB, xB, dB, _ = simulate(pB, multB, p1t, p2t)
    both = xA & xB
    cb = both & (np.abs(dA - dB) <= CB_WINDOW)
    return dict(fundedA=round(float(fA.mean()) * 100, 1), fundedB=round(float(fB.mean()) * 100, 1),
                failA=round(float(xA.mean()) * 100, 1), failB=round(float(xB.mean()) * 100, 1),
                P_both_fail=round(float(both.mean()) * 100, 1),
                P_circuit_breaker=round(float(cb.mean()) * 100, 2),
                P_any_funded=round(float((fA | fB).mean()) * 100, 1),
                E_funded_accounts=round(float((fA.astype(int) + fB.astype(int)).mean()), 3))


def main():
    print("[1/4] データ・セル構築(docs/186と同一34セル)")
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:50]}")
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

    rebal = pd.date_range(wf.WF_START, wf.WF_LAST, freq="ME")
    piecesA = []; piecesB = {a: [] for a in ARMS}
    histB = {a: [] for a in ARMS}; overlap = {a: [] for a in ARMS}

    print("[2/4] ウォークフォワード(口座A=SEL12固定 / 口座B=4アーム)")
    for t in rebal:
        sel0 = t - pd.DateOffset(months=R["sel_m"]) + pd.Timedelta(days=1)
        table = {}
        for k, v in cells.items():
            table[k] = dict(family=v["family"], symbol=v["symbol"],
                            st=wf.cell_window_stats(v["s"], t, R["sel_m"], R["conf_kind"], R["conf_n"]))
        wA = wf.weights_sel(table, R["min_active"])
        multA = wf.mult_at(cells, wA, t, R["sel_m"])
        refA = wf.composite(cells, wA, sel0, t) if wA else None
        end = min(t + pd.DateOffset(months=1), wf.W_END); seg0 = t + pd.Timedelta(days=1)
        def seg(w, m):
            s = wf.composite(cells, w, seg0, end) * m if w else pd.Series(dtype=float)
            if len(s) == 0:
                s = pd.Series(0.0, index=pd.date_range(seg0, end, freq="B"))
            return s
        piecesA.append(seg(wA, multA))
        for arm in ARMS:
            wB = weights_B(cells, table, arm, wA, refA, sel0, t)
            multB = wf.mult_at(cells, wB, t, R["sel_m"])
            piecesB[arm].append(seg(wB, multB))
            ov = len(set(wA) & set(wB))
            overlap[arm].append(ov)
            histB[arm].append(dict(t=str(t.date()), mult=multB, overlap=ov,
                                   w=[k for k in sorted(wB, key=lambda x: -wB[x])]))

    def cat(ps):
        s = pd.concat(ps).sort_index()
        return s[~s.index.duplicated(keep="first")]
    sA = cat(piecesA)
    out = {"meta": {"purpose": "相関ペナルティ付き選抜 docs/193", "seed": SEED,
                    "arms": list(ARMS), "cb_window_days": CB_WINDOW,
                    "wf": f"{wf.WF_START.date()}..{wf.WF_LAST.date()} 月末・保有1ヶ月",
                    "approx": ["Yahoo日足近似", "2口座への単純化",
                               "ρは平常時の推定であり危機時の相関収斂は捉えない"]},
           "accountA": wf.perf(sA), "arms": {}}

    print("[3/4] ペア同時MC(同一ブロック=クロス相関保存)")
    for arm in ARMS:
        sB = cat(piecesB[arm])
        j = pd.concat([sA.rename("a"), sB.rename("b")], axis=1).fillna(0.0)
        rec = dict(perfB=wf.perf(sB),
                   corr_daily=round(float(j["a"].corr(j["b"])), 3),
                   corr_monthly=round(float(wf.monthly(sA).reindex(wf.monthly(sB).index)
                                             .fillna(0).corr(wf.monthly(sB))), 3),
                   avg_overlap_cells=round(float(np.mean(overlap[arm])), 2),
                   avg_multB=round(float(np.mean([h["mult"] for h in histB[arm]])), 2))
        # 倍率は各リバランスで変動するが、MCは配備相当の平均倍率で評価(全アーム同一手順)
        for venue, p1t in (("FTMO_10_5", 0.10), ("FN_8_5", 0.08)):
            rec.setdefault("mc_pair", {})[venue] = mc_pair(
                sA, sB, 1.0, 1.0, p1t, 0.05, np.random.default_rng(SEED))
        out["arms"][arm] = rec
        m = rec["mc_pair"]["FTMO_10_5"]
        print(f"  {arm:6s} ρ日次={rec['corr_daily']:.3f} 重複セル={rec['avg_overlap_cells']:.2f} "
              f"CB発火={m['P_circuit_breaker']}% 両方失格={m['P_both_fail']}% "
              f"いずれか資金化={m['P_any_funded']}%")

    print("[4/4] 判定(docs/193 §5)")
    verdict = {}
    b0 = out["arms"]["LAM0"]["mc_pair"]
    for arm in ARMS:
        if arm == "LAM0":
            continue
        rows = []
        for venue in ("FTMO_10_5", "FN_8_5"):
            a = out["arms"][arm]["mc_pair"][venue]; z = b0[venue]
            rel = (a["P_circuit_breaker"] - z["P_circuit_breaker"]) / z["P_circuit_breaker"] * 100 \
                if z["P_circuit_breaker"] > 0 else 0.0
            rows.append(dict(venue=venue, rel_cb_change_pct=round(rel, 1),
                             d_any_funded=round(a["P_any_funded"] - z["P_any_funded"], 1)))
        ok = all(r["rel_cb_change_pct"] <= -20.0 and r["d_any_funded"] >= 0 for r in rows)
        tradeoff = all(r["rel_cb_change_pct"] <= -20.0 for r in rows) and not ok
        verdict[arm] = dict(adopt_candidate=bool(ok), tradeoff_to_user=bool(tradeoff), detail=rows)
        print(f"  {arm:6s} 採用候補={ok} トレードオフ提示={tradeoff} {rows}")
    out["verdict"] = verdict

    fp = os.path.join(HERE, "results", "correlation_penalty_wf.json")
    with open(fp, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved:", fp)


if __name__ == "__main__":
    main()
