# -*- coding: utf-8 -*-
"""
vix_term_confirm.py — 【確認研究】VIX_TERMゲート(docs/204の実装)。
docs/203でLEADになった1候補を、口座別配備倍率のブックMC(docs/199の土俵)で再検定する。
出力: results/vix_term_confirm.json → docs/204 §8
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import deployed_book as db, external_gates_10y as eg, joint_allocation_mc as ja

SEED = 7; N_MAIN = 10000; N_PLC = 3000; N_PLACEBO = 100; N_PERM = 1000; ALPHA = 0.05
WIN = {"IS": (pd.Timestamp("2016-01-01"), pd.Timestamp("2021-12-31")),
       "OOS": (pd.Timestamp("2022-01-01"), pd.Timestamp("2026-08-31")),
       "FULL": (pd.Timestamp("2016-01-01"), pd.Timestamp("2026-08-31"))}
GATE = "VIX_TERM"


def acct_series(k, gate=None, mask=None):
    legs = [(f, s, w, db.leg_series(f, s)) for f, s, w in db.BOOK[k]["legs"]]
    return eg.composite(legs, gate, mask)


def book_ret(series):
    tot = sum(db.BOOK[k]["capital_usd"] * db.BOOK[k]["mult"] for k in series)
    idx = sorted(set().union(*[set(s.index) for s in series.values()]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, s in series.items():
        out = out.add(s.reindex(out.index).fillna(0.0) * db.BOOK[k]["mult"] * db.BOOK[k]["capital_usd"] / tot, fill_value=0.0)
    return out


def ann(s):
    yrs = max((s.index[-1] - s.index[0]).days / 365.25, 1e-9)
    return round(float((1 + s).prod() ** (1 / yrs) - 1) * 100, 2)


def mc(series, n):
    ja.N_MC = n
    return ja.mc_book(series, {k: db.BOOK[k]["mult"] for k in series}, np.random.default_rng(SEED))


def main():
    base.W_ALL1 = pd.Timestamp("2026-08-31")
    masks = eg.build_states(); mask = masks[GATE]
    raw_all = {k: acct_series(k) for k in db.BOOK}
    gate_all = {k: acct_series(k, GATE, mask) for k in db.BOOK}
    base.verify_window(list(raw_all.values()))
    out = {"meta": dict(purpose="VIX_TERM確認研究 docs/204", seed=SEED, n_main=N_MAIN, n_plc=N_PLC,
                        n_placebo=N_PLACEBO, alpha=ALPHA, windows={k: [str(a.date()), str(b.date())] for k, (a, b) in WIN.items()}),
           "windows": {}}
    rng = np.random.default_rng(SEED)
    for wn, (a, b) in WIN.items():
        cut = lambda d: {k: v[(v.index >= a) & (v.index <= b)] for k, v in d.items()}
        R, G = cut(raw_all), cut(gate_all)
        cal = pd.date_range(a, b, freq="B")
        rate = float(mask.reindex(cal).fillna(False).mean())
        r_raw = mc(R, N_MAIN); r_gate = mc(G, N_MAIN)
        br, bg = book_ret(R), book_ret(G)
        # 順列検定(BOOK合成・見送った活動日)
        changed = br.index[(br != bg.reindex(br.index).fillna(0.0)) & (br != 0.0)]
        act = br[br != 0.0]; obs = float(br.loc[changed].mean()) if len(changed) else 0.0
        perm = np.array([rng.choice(act.values, len(changed), replace=False).mean() for _ in range(N_PERM)]) if len(changed) else np.zeros(1)
        perm_p = float((perm <= obs).mean()) if len(changed) else 1.0
        # プラセボ100本(同率ランダム見送り・建て型レッグのみ)
        plc = []
        for i in range(N_PLACEBO):
            m = pd.Series(rng.random(len(cal)) < rate, index=cal)
            P = cut({k: acct_series(k, GATE, m) for k in db.BOOK})   # GATE名はCOT以外なら全セル一律適用
            plc.append(mc(P, N_PLC)["E_failed"])
        plc = np.array(plc)
        rec = dict(skip_rate_bday=round(rate * 100, 2), n_skipped_active=int(len(changed)),
                   perm_p=round(perm_p, 4), skipped_mean_ret_pct=round(obs * 100, 4),
                   raw=dict(E_failed=r_raw["E_failed"], P_CB_new=r_raw["P_CB_new"], P_CB_old=r_raw["P_CB_old"], E_funded=r_raw["E_funded"], ann=ann(br), failed=r_raw["failed"]),
                   gate=dict(E_failed=r_gate["E_failed"], P_CB_new=r_gate["P_CB_new"], P_CB_old=r_gate["P_CB_old"], E_funded=r_gate["E_funded"], ann=ann(bg), failed=r_gate["failed"]),
                   placebo=dict(p05=round(float(np.percentile(plc, 5)), 3), med=round(float(np.median(plc)), 3),
                                p95=round(float(np.percentile(plc, 95)), 3),
                                gate_pct=round(float((plc <= r_gate["E_failed"]).mean()) * 100, 1)))
        out["windows"][wn] = rec
        print(f"[{wn}] 見送り{rate*100:.1f}% perm_p={perm_p:.4f} | E_failed 素{r_raw['E_failed']}→ゲート{r_gate['E_failed']} "
              f"(plc p05={rec['placebo']['p05']} med={rec['placebo']['med']} 位置{rec['placebo']['gate_pct']}%) | "
              f"CB_new {r_raw['P_CB_new']}→{r_gate['P_CB_new']} | E_funded {r_raw['E_funded']}→{r_gate['E_funded']} | 年率 {ann(br)}→{ann(bg)}")
    W = out["windows"]
    c1 = W["IS"]["perm_p"] < ALPHA and W["OOS"]["perm_p"] < ALPHA
    c2 = W["OOS"]["placebo"]["gate_pct"] <= 5.0
    c3 = all(W[w]["gate"]["E_failed"] < W[w]["raw"]["E_failed"] and W[w]["gate"]["P_CB_new"] <= W[w]["raw"]["P_CB_new"]
             and W[w]["gate"]["E_funded"] >= 0.98 * W[w]["raw"]["E_funded"] for w in ("IS", "OOS"))
    n = sum([c1, c2, c3])
    out["verdict"] = dict(perm_both=c1, placebo_oos=c2, is_oos_both=c3, result="ADOPT" if n == 3 else ("LEAD" if n else "REJECT"))
    print("判定:", out["verdict"])
    with open(os.path.join(HERE, "results", "vix_term_confirm.json"), "w") as f: json.dump(out, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
