# -*- coding: utf-8 -*-
"""
book_circuit_breaker_mc.py — 【実験】現ブック全体の同時失格MC(docs/199の実装)。

問い: C案の選抜に相関ペナルティ(docs/197 §8・λ=0.5)を掛けると、
docs/185 §2のサーキットブレーカー「30日以内に2口座以上が失格」の発火確率はどう変わるか。

docs/193はペア(2口座)で測ったが、口座A=4セル1口座という別構成だった。
docs/198は単体口座のコストだけを測った。本スクリプトは**同じ構成(全ブック基準・C案規則)で
ポートフォリオ側の利益を測り、両者を同じ物差しに載せる**。

核心: 全口座に**同一のブートストラップ・ブロック**を適用してクロス相関を保存する。
出力: results/book_circuit_breaker_mc.json → docs/199 §8
⚠ FN100k #14074882(季節RG3)は生成式が再構築できず含まれない(docs/199 §6.1)。
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import deployed_book as db
import recentfit_c6m_rescreen as c6

SEED = 7
N_MC = 10000
BLOCK = 5
HORIZON = 250
CB_WINDOW = 30
TARGET = c6.TARGET_ACCOUNT
DATES = ["2025-09-30", "2025-12-31", "2026-03-31", "2026-05-29", "2026-06-30", "2026-08-31"]

# docs/199 §3-4 の口座別規則(実行前固定)
RULES = {
    "FTMO100k_531343523":        dict(kind="2step", p1=0.10, p2=0.05, dd=0.10, guard=0.04),
    "FTMO50k_531407058":         dict(kind="2step", p1=0.10, p2=0.05, dd=0.10, guard=0.04),
    "FTMO50k_521100397":         dict(kind="2step", p1=0.10, p2=0.05, dd=0.10, guard=0.04),
    "FN100k_14166201":           dict(kind="2step", p1=0.08, p2=0.05, dd=0.10, guard=0.04),
    "Fintokei_Pearl500":         dict(kind="2step", p1=0.08, p2=0.06, dd=0.10, guard=0.04),
    "FN_Instant20k_11988011":    dict(kind="trail", trail=0.06, guard=0.04),
    "Fintokei_Sokkou2000_6078225": dict(kind="1step", p1=0.06, dd=0.03, guard=0.015, deadline=60),
}


def sim_2step(paths, mult, p1, p2, dd, guard):
    n, T = paths.shape
    eq = np.ones(n); ref = np.ones(n); phase = np.zeros(n, int)
    failed = np.zeros(n, bool); done = np.zeros(n, bool); fday = np.full(n, -1)
    for t in range(T):
        alive = ~(failed | done)
        if not alive.any():
            break
        r = np.clip(paths[:, t] * mult, -guard, None)
        eq = np.where(alive, eq * (1 + r), eq)
        rel = eq / ref - 1.0
        nf = alive & (rel <= -dd); failed |= nf; fday[nf] = t + 1
        alive = ~(failed | done)
        hit = alive & (rel >= np.where(phase == 0, p1, p2))
        h1 = hit & (phase == 0); ref[h1] = eq[h1]; phase[h1] = 1
        done |= (hit & (phase == 1))
    return failed, fday


def sim_trail(paths, mult, trail, guard, lock=True):
    """FN Instant: フロア=min(HWM−trail, 初期)=建値で止まるトレーリング(docs/177 §1)。目標なし。
    ⚠ 2026-09-02修正: 初版は lock なし(フロアが上がり続ける)で計算しており失格率が過大だった(docs/202 §10)。"""
    n, T = paths.shape
    eq = np.ones(n); hwm = np.ones(n)
    failed = np.zeros(n, bool); fday = np.full(n, -1)
    for t in range(T):
        alive = ~failed
        if not alive.any():
            break
        r = np.clip(paths[:, t] * mult, -guard, None)
        eq = np.where(alive, eq * (1 + r), eq)
        hwm = np.maximum(hwm, eq)
        floor = np.minimum(hwm - trail, 1.0) if lock else hwm - trail
        nf = alive & (eq <= floor); failed |= nf; fday[nf] = t + 1
    return failed, fday


def sim_1step(paths, mult, p1, dd, guard, deadline):
    """Fintokei速攻プロ: +6%単段・静的−3%・期限で時間切れ=失格(docs/183 §1)。"""
    n, T = paths.shape
    eq = np.ones(n)
    failed = np.zeros(n, bool); done = np.zeros(n, bool); fday = np.full(n, -1)
    for t in range(T):
        alive = ~(failed | done)
        if not alive.any():
            break
        r = np.clip(paths[:, t] * mult, -guard, None)
        eq = np.where(alive, eq * (1 + r), eq)
        rel = eq - 1.0
        nf = alive & (rel <= -dd); failed |= nf; fday[nf] = t + 1
        alive = ~(failed | done)
        done |= (alive & (rel >= p1))
        if t + 1 == deadline:                      # 時間切れ=失格扱い
            to = ~(failed | done); failed |= to; fday[to] = deadline
            break
    return failed, fday


def run_book(series_by_acct, rng):
    """全口座へ同一ブロックを適用(クロス相関保存)して同時失格を測る。"""
    keys = list(series_by_acct)
    df = pd.concat([series_by_acct[k].rename(k) for k in keys], axis=1).fillna(0.0)
    R = df.values
    nb = len(R) - BLOCK + 1
    st = rng.integers(0, nb, size=(N_MC, HORIZON // BLOCK + 1))
    idxs = (st[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N_MC, -1)[:, :HORIZON]

    fail = np.zeros((N_MC, len(keys)), bool)
    fday = np.full((N_MC, len(keys)), -1)
    for j, k in enumerate(keys):
        p = R[idxs, j]
        ru = RULES[k]; m = db.BOOK[k]["mult"]
        if ru["kind"] == "2step":
            f, d = sim_2step(p, m, ru["p1"], ru["p2"], ru["dd"], ru["guard"])
        elif ru["kind"] == "trail":
            f, d = sim_trail(p, m, ru["trail"], ru["guard"])
        else:
            f, d = sim_1step(p, m, ru["p1"], ru["dd"], ru["guard"], ru["deadline"])
        fail[:, j] = f; fday[:, j] = d

    nfail = fail.sum(axis=1)
    # CB: 失格日のうち「30日以内に2件以上」が存在するか
    cb = np.zeros(N_MC, bool)
    cand = np.where(nfail >= 2)[0]
    for i in cand:
        d = np.sort(fday[i][fail[i]])
        if np.any(d[1:] - d[:-1] <= CB_WINDOW):
            cb[i] = True
    return dict(P_circuit_breaker=round(float(cb.mean()) * 100, 2),
                P_any_fail=round(float((nfail >= 1).mean()) * 100, 1),
                P_two_or_more=round(float((nfail >= 2).mean()) * 100, 1),
                E_failed_accounts=round(float(nfail.mean()), 3),
                per_account={k: round(float(fail[:, j].mean()) * 100, 1) for j, k in enumerate(keys)})


def main():
    base.W_ALL1 = pd.Timestamp("2026-08-31")
    print("[1/3] セル構築(28セル・docs/197 §8.2でTSMOM族除外)")
    cells = {}
    for nm in base.MON_FX + base.MON_IDX:
        cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    for nm in base.HOLD_SYMS:
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    for p in base.V4_PAIRS:
        cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))

    others = {k: db.account_composite(k) for k in db.BOOK if k != TARGET}
    out = {"meta": dict(purpose="現ブック同時失格MC docs/199", seed=SEED, n_mc=N_MC,
                        horizon=HORIZON, cb_window=CB_WINDOW, dates=DATES,
                        excluded_account="FN100k_14074882(季節RG3・再構築不可・docs/199 §6.1)",
                        rules={k: v for k, v in RULES.items()},
                        approx=db.APPROX), "by_date": {}}

    print("[2/3] 基準日ごとにC案をλ=0/λ=0.5で選抜し、ブック全体のMCを回す")
    for d in DATES:
        END = pd.Timestamp(d)
        SEL0 = END - pd.DateOffset(months=6) + pd.Timedelta(days=1)
        CONF0 = END - pd.DateOffset(months=3) + pd.Timedelta(days=1)
        W12 = END - pd.DateOffset(months=12) + pd.Timedelta(days=1)
        book_ref = db.book_composite(exclude=TARGET, end=END)
        table = {k: dict(family=v["family"], symbol=v["symbol"],
                         stats=c6.stats_for(v["s"], SEL0, CONF0, W12, END),
                         rho_book=c6.rho_book(v["s"], book_ref, SEL0, END))
                 for k, v in cells.items()}
        rec = {}
        for tag, lam in (("lambda_0", 0.0), ("lambda_05", 0.5)):
            w, _ = c6.select(table, lam)
            if not w:
                rec[tag] = {"error": "通過セルなし"}; continue
            comp = c6.composite(cells, w, base.W_ALL0, END)
            mult = round(min(0.8 * min(c6.mstar(c6.wnd(comp, SEL0, END)),
                                       c6.mstar(c6.wnd(comp, W12, END))), 6.0), 2)
            # C案の倍率は選抜ごとに変わる → BOOKを一時的に差し替えて評価
            saved = db.BOOK[TARGET]["mult"]; db.BOOK[TARGET]["mult"] = mult
            series = dict(others); series[TARGET] = comp[comp.index <= END]
            series = {k: v[v.index <= END] for k, v in series.items()}
            res = run_book(series, np.random.default_rng(SEED))
            db.BOOK[TARGET]["mult"] = saved
            res.update(selected=w, mult=mult,
                       rho_C_vs_rest=c6.rho_book(comp, book_ref, SEL0, END))
            rec[tag] = res
            print(f"  {d} {tag:10s} mult={mult:<5} ρ={res['rho_C_vs_rest']:+.3f} "
                  f"CB={res['P_circuit_breaker']:5.2f}% 2件以上={res['P_two_or_more']:5.1f}% "
                  f"E[失格]={res['E_failed_accounts']:.3f}")
        out["by_date"][d] = rec

    print("[3/3] 集計と判定(docs/199 §5)")
    agg = {}
    for tag in ("lambda_0", "lambda_05"):
        g = [v[tag] for v in out["by_date"].values() if "P_circuit_breaker" in v.get(tag, {})]
        agg[tag] = dict(
            n_dates=len(g),
            P_circuit_breaker=round(float(np.mean([x["P_circuit_breaker"] for x in g])), 2),
            P_any_fail=round(float(np.mean([x["P_any_fail"] for x in g])), 1),
            P_two_or_more=round(float(np.mean([x["P_two_or_more"] for x in g])), 1),
            E_failed_accounts=round(float(np.mean([x["E_failed_accounts"] for x in g])), 3),
            rho_C_vs_rest=round(float(np.mean([x["rho_C_vs_rest"] for x in g])), 3),
            mult=round(float(np.mean([x["mult"] for x in g])), 2),
            per_account={k: round(float(np.mean([x["per_account"][k] for x in g])), 1)
                         for k in g[0]["per_account"]})
    z, a = agg["lambda_0"], agg["lambda_05"]
    rel = (a["P_circuit_breaker"] - z["P_circuit_breaker"]) / z["P_circuit_breaker"] * 100 \
        if z["P_circuit_breaker"] > 0 else 0.0
    out["aggregate"] = agg
    out["verdict"] = dict(rel_cb_change_pct=round(rel, 1),
                          supports_lambda_05=bool(rel <= -20.0),
                          d_E_failed=round(a["E_failed_accounts"] - z["E_failed_accounts"], 3))
    print(f"  λ=0   : CB={z['P_circuit_breaker']}% ρ={z['rho_C_vs_rest']} E[失格]={z['E_failed_accounts']}")
    print(f"  λ=0.5 : CB={a['P_circuit_breaker']}% ρ={a['rho_C_vs_rest']} E[失格]={a['E_failed_accounts']}")
    print(f"  相対変化={rel:+.1f}%  λ=0.5を支持={out['verdict']['supports_lambda_05']}")

    fp = os.path.join(HERE, "results", "book_circuit_breaker_mc_lockfix.json")
    with open(fp, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("saved:", fp)


if __name__ == "__main__":
    main()
