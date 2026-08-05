# -*- coding: utf-8 -*-
"""
yearly_optima_ladder.py — 【検証】年次最適解ラダーはリスクヘッジになるか。

ユーザー質問(2026-08-05)「2年以降1年ずつの最適解を作成することでリスクヘッジを
可能に出来ますか」への実装。

方法:
  1) 8月始まりの12ヶ月窓を2016-08から10本並べ、各窓でdocs/174と同一の選抜ルール
     (score=mean/std*sqrt(n)・活動日≥15・窓累積>0・後半6ヶ月>0・Top-4・銘柄1・族2・
     逆ボラ加重cap40%)を実行 → 「その年の最適解」を10個作る。
  2) 持続性マトリクス: 各年の最適解を後続の全窓でOOS評価(対角=イン・サンプル)。
  3) ヘッジ検定: 各テスト窓Tで「前年最適解のみ」vs「直前3年の最適解の等ブレンド」を
     OOS比較(累積・最悪単日・月中DD)。ブレンドがDD/テールを削るなら「ヘッジ可能」。
  4) 配備候補F(=直近3年ラダー 2023/2024/2025窓)の相関・倍率校正・MC(FN/FTMO)。
セル母集団: B/C/D系と同じ34セル+暗号アルト10セル(Hold/TSMOM×SOL/XRP/LTC/ADA/DOGE・
  銘柄別月初摩擦のlc実装。BTC/ETHは基準実装のまま=基準セルと重複させない)。
出力: results/yearly_optima_ladder.json → docs/187
⚠ 対角(イン・サンプル)の数字は定義上ほぼ最良。読み取りはOOS(非対角)のみで行う。
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_lowcorr_screen as lc
import recentfit_screen as base
import portfolio_pair_compare as ppc
import strategy_corr_matrix as scm

SEED = 7
TOP_K, MAX_PER_FAMILY, W_CAP, MIN_ACTIVE = 4, 2, 0.40, 15
MULT_HARD_CAP = 6.0
DATA_END = base.W_ALL1
WINDOWS = [(pd.Timestamp(f"{y}-08-01"),
            min(pd.Timestamp(f"{y + 1}-07-31"), DATA_END)) for y in range(2016, 2026)]


def build_cells():
    cells = {}
    for nm in base.MON_FX + base.MON_IDX:
        cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    for nm in base.HOLD_SYMS:
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    for nm in base.TSMOM_SYMS:
        cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
    for p in base.V4_PAIRS:
        cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))
    for nm in lc.EXTRA_CRYPTO:                       # アルトのみ追加(BTC/ETHは基準セル)
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=lc.crypto_cell("Hold", nm))
        cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=lc.crypto_cell("TSMOM", nm))
    return cells


def wstats(s, w0, w1):
    sw = s[(s.index >= w0) & (s.index <= w1)]
    conf = sw[sw.index >= w0 + pd.DateOffset(months=6)]
    act = sw[sw != 0.0]
    n = int(len(act))
    std = float(act.std()) if n > 2 else float("nan")
    score = float(act.mean() / std * np.sqrt(n)) if (n > 2 and std > 0) else float("-inf")
    return dict(n_active=n,
                cum=round(float((1 + sw).prod() - 1) * 100, 2),
                cum_conf=round(float((1 + conf).prod() - 1) * 100, 2),
                score=round(score, 2) if np.isfinite(score) else None,
                std_active=round(std * 100, 3) if np.isfinite(std) else None)


def select_window(cells, w0, w1):
    table = {k: dict(family=v["family"], symbol=v["symbol"], stats=wstats(v["s"], w0, w1))
             for k, v in cells.items()}
    ok = [(k, v) for k, v in table.items()
          if v["stats"]["n_active"] >= MIN_ACTIVE
          and v["stats"]["cum"] > 0 and v["stats"]["cum_conf"] > 0
          and v["stats"]["score"] is not None]
    ok.sort(key=lambda kv: kv[1]["stats"]["score"], reverse=True)
    picked, fam_ct, sym_used = [], {}, set()
    for k, v in ok:
        fam, sym = v["family"], v["symbol"]
        if sym in sym_used or fam_ct.get(fam, 0) >= MAX_PER_FAMILY:
            continue
        picked.append(k); sym_used.add(sym); fam_ct[fam] = fam_ct.get(fam, 0) + 1
        if len(picked) == TOP_K:
            break
    if not picked:
        return {}, table
    iv = {k: 1.0 / (table[k]["stats"]["std_active"] / 100) for k in picked}
    tot = sum(iv.values())
    w = {k: min(iv[k] / tot, W_CAP) for k in picked}
    t2 = sum(w.values())
    return {k: round(v / t2, 3) for k, v in w.items()}, table


def composite(cells, weights):
    idx = sorted(set().union(*[set(cells[k]["s"].index) for k in weights]))
    c = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, w in weights.items():
        c = c.add(cells[k]["s"].reindex(c.index).fillna(0.0) * w, fill_value=0.0)
    return c


def blend(port_list):
    out = {}
    for w in port_list:
        for k, v in w.items():
            out[k] = out.get(k, 0.0) + v / len(port_list)
    return {k: round(v, 4) for k, v in out.items()}


def eval_window(s, w0, w1):
    sw = s[(s.index >= w0) & (s.index <= w1)]
    if not len(sw):
        return None
    wd, wdd = base.worst_stats(sw)
    return dict(cum=round(float((1 + sw).prod() - 1) * 100, 2),
                worst_day=round(wd * 100, 2), mdd=round(wdd * 100, 2))


def main():
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception:
            pass
    print("[1/5] セル構築(44セル)")
    cells = build_cells()

    print("[2/5] 年次最適解(8月始まり12ヶ月窓×10)")
    optima, comps = {}, {}
    for w0, w1 in WINDOWS:
        tag = f"Y{w0.year}"
        weights, _ = select_window(cells, w0, w1)
        optima[tag] = weights
        if weights:
            comps[tag] = composite(cells, weights)
        print(f"  {tag} ({w0.date()}..{w1.date()}): {weights}")

    print("[3/5] 持続性マトリクス(行=学習年・列=評価年・OOSのみ読む)")
    persist = {}
    tags = [f"Y{w0.year}" for w0, _ in WINDOWS]
    for ti, (w0i, w1i) in zip(tags, WINDOWS):
        if ti not in comps:
            continue
        persist[ti] = {}
        for tj, (w0j, w1j) in zip(tags, WINDOWS):
            r = eval_window(comps[ti], w0j, w1j)
            persist[ti][tj] = r["cum"] if r else None
        nxt = {tj: persist[ti][tj] for tj in tags if tj > ti}
        print(f"  {ti}: 翌年以降OOS {nxt}")

    print("[4/5] ヘッジ検定: 前年単独 vs 直前3年ブレンド のOOS比較")
    hedge = []
    for i in range(3, len(WINDOWS)):
        tT = tags[i]; w0, w1 = WINDOWS[i]
        prev1 = optima.get(tags[i - 1], {})
        prev3 = [optima[t] for t in tags[i - 3:i] if optima.get(t)]
        if not prev1 or len(prev3) < 2:
            continue
        c1 = composite(cells, prev1)
        c3 = composite(cells, blend(prev3))
        r1, r3 = eval_window(c1, w0, w1), eval_window(c3, w0, w1)
        hedge.append(dict(test=tT, single_prev=r1, ladder3=r3))
        print(f"  {tT}: 前年単独={r1}  3年ラダー={r3}")
    avg = lambda rows, key, sub: round(float(np.mean([r[key][sub] for r in rows])), 2)
    summary = dict(
        single=dict(cum=avg(hedge, "single_prev", "cum"), worst_day=avg(hedge, "single_prev", "worst_day"),
                    mdd=avg(hedge, "single_prev", "mdd"),
                    neg_years=sum(1 for r in hedge if r["single_prev"]["cum"] < 0)),
        ladder3=dict(cum=avg(hedge, "ladder3", "cum"), worst_day=avg(hedge, "ladder3", "worst_day"),
                     mdd=avg(hedge, "ladder3", "mdd"),
                     neg_years=sum(1 for r in hedge if r["ladder3"]["cum"] < 0)))
    print("  平均:", summary)

    print("[5/5] 配備候補F=直近3年ラダー(Y2023+Y2024+Y2025)の校正・MC・相関")
    F = blend([optima[t] for t in ["Y2023", "Y2024", "Y2025"] if optima.get(t)])
    cF = composite(cells, F)
    cFb = ppc.to_bdays(cF)
    m12 = lc.max_mult(cFb[cFb.index >= base.W12_0])
    mult = round(min(0.8 * m12, MULT_HARD_CAP), 2)
    res = dict(weights=F, mult=mult, m_star_12m=round(m12, 2))
    for tag, (p1, p2) in dict(FN=(0.08, 0.05), FTMO=(0.10, 0.05)).items():
        res[f"mc_{tag}_12m"] = lc.mc_challenge(cFb[cFb.index >= base.W12_0], mult, p1, p2,
                                               np.random.default_rng(SEED))
        res[f"mc_{tag}_full"] = lc.mc_challenge(cFb, mult, p1, p2, np.random.default_rng(SEED))
        print(f"  {tag} 12m={res[f'mc_{tag}_12m']}")
        print(f"  {tag} full={res[f'mc_{tag}_full']}")
    acct, _ = scm.build_strategies()
    res["corr_vs_deployed"] = {}
    for name, s in acct.items():
        rho = lc.corr_pair(cF, s, base.W_ALL0)
        rho12 = lc.corr_pair(cF, s, base.W12_0)
        res["corr_vs_deployed"][name] = dict(full=round(rho, 3) if rho is not None else None,
                                             m12=round(rho12, 3) if rho12 is not None else None)
    print("  相関:", res["corr_vs_deployed"])

    out = dict(meta=dict(purpose="年次最適解ラダーのヘッジ検証(2016-08起点・12ヶ月窓×10)",
                         seed=SEED, rule="docs/174選抜ルールを各窓に適用・窓後半6ヶ月を確認窓",
                         cells=len(cells),
                         caveat="対角=イン・サンプル。判定はOOS(翌年以降)のみで行う。",
                         inputs=base.sha256s()),
               yearly_optima=optima, persistence_matrix=persist,
               hedge_test=hedge, hedge_summary=summary, F_candidate=res)
    path = os.path.join(HERE, "results", "yearly_optima_ladder.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
