# -*- coding: utf-8 -*-
"""
recentfit_midcorr_explore.py — 【探索】トラックE'の閾値感度: 「中相関」まで許容したら何が変わるか。

ユーザー質問(2026-08-04)「中相関だとどうですか」への計測。docs/183 §1で0.55閾値の結果が
暗号資産のみ=EV不成立だったのを受け、閾値を 0.70 / 0.85 / 1.00(未採用銘柄全部) に緩めて
同じ1年特化ルール(docs/182 §5)で選抜〜MCを再実行する。
⚠ これは事前登録前の探索計測。採用する閾値が決まったら別docで事前登録してから配備判断する。

セル適用域(基準式のクラス域・docs/182 §4と同じ考え方):
  Mon   = 基準MON_FX/MON_IDX ∩ 候補 = NZDJPY/CADJPY/CHFJPY/UK100/FR40
  v4    = 基準V4_PAIRS ∩ 候補       = EURUSD/USDCAD
  Hold/TSMOM = 指数・暗号クラス      = UK100/FR40 + 暗号7(銘柄別月初摩擦)
出力: results/recentfit_midcorr_explore.json → docs/184
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_lowcorr_screen as lc     # 相関・セル・選抜・MC実装を再利用(拡張ユニバース込み)
import recentfit_screen as base

SEED = 7
THRESHOLDS = [0.70, 0.85, 1.00]

MON_DOMAIN = [s for s in base.MON_FX + base.MON_IDX if s in lc.CANDIDATES]
V4_DOMAIN = [s for s in base.V4_PAIRS if s in lc.CANDIDATES]
HT_DOMAIN = ["UK100", "FR40"] + lc.CRYPTO_CLASS


def idx_cell(kind, nm):
    """UK100/FR40のHold/TSMOM: 基準式そのまま(月初摩擦5bp>コスト4bpのため上乗せなし)"""
    return base.hold_cell(nm) if kind == "Hold" else base.tsmom_cell(nm)


def build_cells(univ):
    cells = {}
    for nm in univ:
        if nm in MON_DOMAIN:
            cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
        if nm in V4_DOMAIN:
            cells[f"v4_{nm}"] = dict(family="v4", symbol=nm, s=base.v4_cell(nm))
        if nm in HT_DOMAIN:
            mk = lc.crypto_cell if nm in lc.CRYPTO_CLASS else idx_cell
            cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=mk("Hold", nm))
            cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=mk("TSMOM", nm))
    return cells


def main():
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {e}")

    print("[1/3] 候補×採用13銘柄の max(|ρ|full,|ρ|12m)")
    rets = {nm: lc.daily_ret(nm) for nm in set(lc.ADOPTED + lc.CANDIDATES)}
    maxrho = {}
    for c in lc.CANDIDATES:
        worst, wname = 0.0, ""
        for a in lc.ADOPTED:
            rf = lc.corr_pair(rets[c], rets[a], base.W_ALL0)
            r12 = lc.corr_pair(rets[c], rets[a], lc.W12_0)
            m = max(abs(rf) if rf is not None else 0.0, abs(r12) if r12 is not None else 0.0)
            if m > worst:
                worst, wname = m, a
        maxrho[c] = dict(max_abs=round(worst, 3), vs=wname)
        print(f"  {c:8s} {worst:.2f} vs {wname}")

    dep = lc.deployed_composites()
    out = dict(meta=dict(purpose="中相関の閾値感度探索(docs/183 §6起点・事前登録前)",
                         seed=SEED, thresholds=THRESHOLDS,
                         rule="選抜〜MCはdocs/182 §5の1年特化ルールをそのまま適用",
                         inputs=base.sha256s()),
               max_rho=maxrho, runs={})

    for th in THRESHOLDS:
        univ = [c for c in lc.CANDIDATES if maxrho[c]["max_abs"] < th]
        print(f"\n[2/3] TH={th}: ユニバース={univ}")
        cells = build_cells(univ)
        table = {k: dict(family=v["family"], symbol=v["symbol"], stats=lc.stats_for(v["s"]))
                 for k, v in cells.items()}
        ranked = sorted([k for k in table if table[k]["stats"]["score"] is not None],
                        key=lambda k: table[k]["stats"]["score"], reverse=True)
        for k in ranked[:8]:
            print(f"  {k:16s} {table[k]['stats']}")
        weights = lc.select_cells(table)
        print("  選抜:", weights)
        run = dict(universe=univ, selected=weights,
                   ranking_top8={k: table[k] for k in ranked[:8]})
        if weights:
            idx = sorted(set().union(*[set(cells[k]["s"].index) for k in weights]))
            comp = pd.Series(0.0, index=pd.DatetimeIndex(idx))
            for k, w in weights.items():
                comp = comp.add(cells[k]["s"].reindex(comp.index).fillna(0.0) * w, fill_value=0.0)
            m12 = lc.max_mult(lc.win(comp, lc.W12_0))
            mult = round(min(0.8 * m12, lc.MULT_HARD_CAP), 2)
            sM = comp * mult
            wd12, wdd12 = base.worst_stats(lc.win(sM, lc.W12_0))
            run.update(mult=mult, m_star_12m=round(m12, 2),
                       worst_day_12m=round(wd12 * 100, 2),
                       intramonth_dd_12m=round(wdd12 * 100, 2),
                       cum_12m_scaled=round(float((1 + lc.win(sM, lc.W12_0)).prod() - 1) * 100, 1),
                       monthly_12m=lc.series_pack(lc.win(sM, lc.W12_0)))
            for tag, (p1, p2) in dict(FN_stellar=(0.08, 0.05), FTMO=(0.10, 0.05)).items():
                run[f"mc_{tag}_12m"] = lc.mc_challenge(lc.win(comp, lc.W12_0), mult, p1, p2,
                                                       np.random.default_rng(SEED))
                run[f"mc_{tag}_full"] = lc.mc_challenge(comp, mult, p1, p2,
                                                        np.random.default_rng(SEED))
                print(f"  {tag} 12m={run[f'mc_{tag}_12m']}")
                print(f"  {tag} full={run[f'mc_{tag}_full']}")
            print("[3/3] 配備中構成との相関")
            vs = {}
            for name, s in dep.items():
                vs[name] = dict(full=lc.corr_pair(comp, s, base.W_ALL0),
                                m12=lc.corr_pair(comp, s, lc.W12_0))
                vs[name] = {k: (round(v, 3) if v is not None else None)
                            for k, v in vs[name].items()}
                print(f"  vs {name:14s} {vs[name]}")
            run["corr_vs_deployed"] = vs
        out["runs"][f"TH_{th}"] = run

    path = os.path.join(HERE, "results", "recentfit_midcorr_explore.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
