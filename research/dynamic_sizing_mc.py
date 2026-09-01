# -*- coding: utf-8 -*-
"""
dynamic_sizing_mc.py — 【実験③】バッファ依存・動的サイジングの評価(docs/190の実装)。

問い: 現行の「固定倍率+利益ロック」に対し、口座の状態(フロアまでの距離)と実現ボラで
倍率を動かすと、失格率・資金化率・所要日数はどう変わるか。

docs/185は「丁半博打(マーチンゲール型)の定量却下」を既に記録している。本研究が評価するのは
その逆(アンチマーチンゲール=バッファに比例して張る)であり、思想的に矛盾しない。

アーム(docs/190 §2・実行前固定): FIXED(現行) / BUFFER(γ=1) / BUFFER_G05(γ=0.5) /
VOLTGT(20日実現ボラ) / BOTH。scaleは全アーム [0.5, 1.5] にクリップ。
評価構成(docs/190 §3): 稼働中のC案6.0 / D案2026-09版5.0 / B案4.0 / 非FX1.48。
出力: results/dynamic_sizing_mc.json → docs/191
⚠ ブロックブートストラップは系列相関を5日ブロックまでしか保存しない(docs/190 §6)。
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
import recentfit_nonfx_screen as nfx        # v4_cell_nonfx とユニバース拡張を再利用

SEED = 7
N_MC = 10000
BLOCK = 5
MAX_DAYS = 250
MAX_DD = 0.10
GUARD = 0.04
SC_LO, SC_HI = 0.5, 1.5
VOL_LB = 20

base.DATA = os.path.join(HERE, "data_202609")
os.makedirs(base.DATA, exist_ok=True)
base.P2_EPOCH = 1788220799                   # 2026-08-31 23:59:59 UTC
base.W_ALL1 = pd.Timestamp("2026-08-31")
W12_0 = pd.Timestamp("2025-09-01")

# --- 稼働中の配備構成(docs/178/181/182/184の焼き込み値) ---
CONFIGS = {
    "C案_6m(FTMO50k)": dict(mult=6.00, legs=[("Mon", "GBPJPY", 0.323), ("Mon", "AUDJPY", 0.269),
                                             ("v4", "NZDUSD", 0.207), ("v4", "AUDUSD", 0.201)]),
    "D案_3m_202609(FTMO50k)": dict(mult=5.00, legs=[("Mon", "USDJPY", 0.459), ("v4", "GBPJPY", 0.458),
                                                    ("Hold", "GER40", 0.083)]),
    "B案_2026H2(Fintokei)": dict(mult=4.00, legs=[("Mon", "GBPJPY", 0.374), ("Mon", "AUDJPY", 0.322),
                                                  ("v4", "USDJPY", 0.304)]),
    "非FX分散(FN100k)": dict(mult=1.48, legs=[("Hold", "UK100", 0.491), ("Hold", "WTI", 0.153),
                                             ("v4nfx", "BTCUSD", 0.211), ("Mon", "ETHUSD", 0.145)]),
}
ARMS = ["FIXED", "BUFFER", "BUFFER_G05", "VOLTGT", "BOTH"]


def build(legs):
    parts = []
    for fam, sym, w in legs:
        s = {"Mon": base.mon_cell, "Hold": base.hold_cell,
             "v4": base.v4_cell, "v4nfx": nfx.v4_cell_nonfx}[fam](sym)
        parts.append((s, w))
    idx = sorted(set().union(*[set(s.index) for s, _ in parts]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s, w in parts:
        out = out.add(s.reindex(out.index).fillna(0.0) * w, fill_value=0.0)
    return out[(out.index >= base.W_ALL0) & (out.index <= base.W_ALL1)]


def rolling_std_prev(x, w):
    """t時点で t-w..t-1 の標準偏差(t自身を含めない=look-ahead無し)"""
    n, T = x.shape
    out = np.full((n, T), np.nan)
    c1 = np.concatenate([np.zeros((n, 1)), np.cumsum(x, axis=1)], axis=1)
    c2 = np.concatenate([np.zeros((n, 1)), np.cumsum(x ** 2, axis=1)], axis=1)
    for t in range(w, T):
        s1 = c1[:, t] - c1[:, t - w]
        s2 = c2[:, t] - c2[:, t - w]
        out[:, t] = np.sqrt(np.maximum(s2 / w - (s1 / w) ** 2, 0.0))
    return out


def mc_dynamic(daily, mult0, arm, rng, p1_target, p2_target=0.05):
    r = np.asarray(daily.values, float)
    nb = len(r) - BLOCK + 1
    T = MAX_DAYS * 2
    st = rng.integers(0, nb, size=(N_MC, T // BLOCK + 1))
    paths = r[(st[:, :, None] + np.arange(BLOCK)[None, None, :])].reshape(N_MC, -1)[:, :T]

    need_vol = arm in ("VOLTGT", "BOTH")
    if need_vol:
        sig_t = float(np.std(r))
        rv = rolling_std_prev(paths, VOL_LB)

    eq = np.ones(N_MC); ref = np.ones(N_MC)
    phase = np.zeros(N_MC, dtype=int)
    p1_day = np.full(N_MC, -1); p2_day = np.full(N_MC, -1)
    failed = np.zeros(N_MC, bool); done = np.zeros(N_MC, bool)
    sc_sum = np.zeros(N_MC); sc_n = np.zeros(N_MC)

    for t in range(T):
        alive = ~(failed | done)
        if not alive.any():
            break
        d = eq / ref - (1.0 - MAX_DD)                    # フロアまでの距離
        if arm == "FIXED":
            sc = np.ones(N_MC)
        elif arm in ("BUFFER", "BUFFER_G05", "BOTH"):
            g = 0.5 if arm == "BUFFER_G05" else 1.0
            sc = np.clip(np.maximum(d, 0) / MAX_DD, 0, None) ** g
            sc = np.clip(sc, SC_LO, SC_HI)
        else:
            sc = np.ones(N_MC)
        if need_vol:
            v = rv[:, t]
            scv = np.where(np.isfinite(v) & (v > 0), sig_t / np.where(v > 0, v, 1.0), 1.0)
            scv = np.clip(scv, SC_LO, SC_HI)
            sc = np.clip(sc * scv, SC_LO, SC_HI) if arm == "BOTH" else scv
        sc_sum += np.where(alive, sc, 0.0); sc_n += alive

        ret = np.clip(paths[:, t] * mult0 * sc, -GUARD, None)
        eq = np.where(alive, eq * (1 + ret), eq)
        rel = eq / ref - 1.0

        nf = alive & (rel <= -MAX_DD)
        failed |= nf
        alive = ~(failed | done)

        tgt = np.where(phase == 0, p1_target, p2_target)
        hit = alive & (rel >= tgt)
        h1 = hit & (phase == 0)
        if t < MAX_DAYS:
            p1_day[h1] = t + 1
            ref[h1] = eq[h1]              # P2は基準リセット(EAのBaselineResetと同じ扱い)
            phase[h1] = 1
        else:
            # P1の期限切れ: 以後P1の通過は記録しない(mc_challengeと同じ扱い)
            pass
        h2 = hit & (phase == 1)
        p2_day[h2] = t + 1
        done |= h2

    okP1 = p1_day > 0; okP2 = p2_day > 0
    def q(a, p): return int(np.percentile(a, p)) if len(a) else None
    return dict(p1_pass=round(float(okP1.mean()) * 100, 1),
                funded=round(float(okP2.mean()) * 100, 1),
                fail=round(float(failed.mean()) * 100, 1),
                p1_days_med=q(p1_day[okP1], 50),
                funded_days_med=q(p2_day[okP2], 50), funded_days_p90=q(p2_day[okP2], 90),
                avg_scale=round(float((sc_sum / np.maximum(sc_n, 1)).mean()), 3))


def main():
    print("[1/3] データ・構成の再構築")
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:50]}")
    comps = {k: build(v["legs"]) for k, v in CONFIGS.items()}
    for k, s in comps.items():
        s12 = s[s.index >= W12_0]
        print(f"  {k:24s} n={len(s)} 12m累積={float((1+s12).prod()-1)*100:.1f}% "
              f"最悪日(12m)={float(s12.min())*100*CONFIGS[k]['mult']:.2f}%(倍率込)")

    out = {"meta": {"purpose": "バッファ依存・動的サイジングの評価 docs/190",
                    "freeze": "2016-01-01..2026-08-31", "seed": SEED,
                    "arms": ARMS, "scale_clip": [SC_LO, SC_HI], "vol_lb": VOL_LB,
                    "approx": ["Yahoo日足近似", "5日ブロックBSは系列相関を5日までしか保存しない",
                               "EA日次ガード−4%クリップは全アームに適用"]},
           "results": {}}

    print("[2/3] MC(5アーム × 4構成 × 2土俵 × 2バウンド)")
    for cname, comp in comps.items():
        mult0 = CONFIGS[cname]["mult"]
        c12 = comp[comp.index >= W12_0]
        out["results"][cname] = {"mult0": mult0}
        for venue, p1t in (("FTMO_10_5", 0.10), ("FN_8_5", 0.08)):
            for bound, series in (("recent_12m", c12), ("full_pessimistic", comp)):
                for arm in ARMS:
                    res = mc_dynamic(series, mult0, arm, np.random.default_rng(SEED), p1t)
                    out["results"][cname].setdefault(venue, {}).setdefault(bound, {})[arm] = res
        for venue in ("FTMO_10_5", "FN_8_5"):
            for bound in ("recent_12m", "full_pessimistic"):
                r = out["results"][cname][venue][bound]
                print(f"  {cname:24s} {venue:10s} {bound:17s} " +
                      " | ".join(f"{a}: f{r[a]['funded']}/x{r[a]['fail']}" for a in ARMS))

    print("[3/3] 採否判定(docs/190 §5)")
    verdict = {}
    for arm in ARMS:
        if arm == "FIXED":
            continue
        cells = []
        for cname in comps:
            for venue in ("FTMO_10_5", "FN_8_5"):
                for bound in ("recent_12m", "full_pessimistic"):
                    a = out["results"][cname][venue][bound][arm]
                    f = out["results"][cname][venue][bound]["FIXED"]
                    cells.append(dict(cfg=cname, venue=venue, bound=bound,
                                      d_fail=round(a["fail"] - f["fail"], 1),
                                      d_funded=round(a["funded"] - f["funded"], 1)))
        ok = all(c["d_fail"] < 0 and c["d_funded"] >= 0 for c in cells)
        n_better = sum(1 for c in cells if c["d_fail"] < 0 and c["d_funded"] >= 0)
        verdict[arm] = dict(adopt_candidate=bool(ok), n_cells=len(cells), n_pass=n_better,
                            mean_d_fail=round(float(np.mean([c["d_fail"] for c in cells])), 2),
                            mean_d_funded=round(float(np.mean([c["d_funded"] for c in cells])), 2),
                            detail=cells)
        print(f"  {arm:11s} 採用候補={ok} ({n_better}/{len(cells)}セル合格) "
              f"平均Δ失格={verdict[arm]['mean_d_fail']} 平均Δ資金化={verdict[arm]['mean_d_funded']}")
    out["verdict"] = verdict

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    fp = os.path.join(HERE, "results", "dynamic_sizing_mc.json")
    with open(fp, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved:", fp)


if __name__ == "__main__":
    main()
