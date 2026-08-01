# -*- coding: utf-8 -*-
"""
recentfit_short_screen.py — 【直近6ヶ月/3ヶ月トラック】docs/180の事前登録ルール実装。

ユーザー指示(2026-07-31): FTMO 50k×2口座を追加。直近6ヶ月強い手法(トラックC)と
直近3ヶ月強い手法(トラックD)を1口座ずつ。セル母集団・構築式・コストは
recentfit_screen.py(B案・docs/174)と同一。窓・フィルタ・倍率規則・MC土俵(FTMO 10/5)のみ
docs/180で事前固定した値に差し替え。実行後のルール変更は禁止。

出力: results/recentfit_short_screen.json → docs/181
⚠ 窓が短いほど選抜ノイズ増大。選抜窓の数字=定義上ほぼ最良であり実力と読まない。
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base   # セル構築・fetch・worst_stats等を同一実装で再利用

SEED = 7
N_MC = 10000
P1_TARGET, P2_TARGET = 0.10, 0.05     # FTMO 2-Step(実口座で+10%を実査確認, docs/178)
MAX_DD, DAY_GUARD = 0.10, 0.04
MULT_HARD_CAP = 6.0
W12_0 = pd.Timestamp("2025-08-01")

TRACKS = {
    "C_6m": dict(sel0=pd.Timestamp("2026-02-01"), conf0=pd.Timestamp("2026-05-01"),
                 min_active=8, expiry="2026-09-30"),
    "D_3m": dict(sel0=pd.Timestamp("2026-05-01"), conf0=pd.Timestamp("2026-06-18"),
                 min_active=5, expiry="2026-08-31"),
}
TOP_K, MAX_PER_FAMILY, W_CAP = 4, 2, 0.40


def win(s, a):
    return s[(s.index >= a) & (s.index <= base.W_ALL1)]


def stats_for(s, sel0, conf0):
    ssel = win(s, sel0); sconf = win(s, conf0); s12 = win(s, W12_0)
    act = ssel[ssel != 0.0]
    n = int(len(act))
    std = float(act.std()) if n > 2 else float("nan")
    score = float(act.mean() / std * np.sqrt(n)) if (n > 2 and std > 0) else float("-inf")
    return dict(n_active=n,
                cum_sel=round(float((1 + ssel).prod() - 1) * 100, 2),
                cum_conf=round(float((1 + sconf).prod() - 1) * 100, 2),
                cum_12m=round(float((1 + s12).prod() - 1) * 100, 2),
                score=round(score, 2) if np.isfinite(score) else None,
                std_active=round(std * 100, 3) if np.isfinite(std) else None,
                cum_full=round(float((1 + s[s != 0.0]).prod() - 1) * 100, 1))


def select_cells(table, min_active):
    ok = [(k, v) for k, v in table.items()
          if v["stats"]["n_active"] >= min_active
          and v["stats"]["cum_sel"] > 0 and v["stats"]["cum_conf"] > 0
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
        return {}
    iv = {k: 1.0 / (table[k]["stats"]["std_active"] / 100) for k in picked}
    tot = sum(iv.values())
    w = {k: iv[k] / tot for k in picked}
    over = {k: min(v, W_CAP) for k, v in w.items()}
    tot2 = sum(over.values())
    return {k: round(v / tot2, 3) for k, v in over.items()}


def max_mult(daily, day_cap=DAY_GUARD, floor_cap=0.08):
    best = 0.05
    for m in np.arange(0.05, 8.01, 0.05):
        wd, wdd = base.worst_stats(daily * m)
        if wd >= -day_cap and wdd >= -floor_cap:
            best = m
        else:
            break
    return best


def calibrate(comp, sel0):
    """docs/180: 選抜窓と直近12ヶ月の小さい方×0.8・上限6.0"""
    m_sel = max_mult(win(comp, sel0))
    m_12m = max_mult(win(comp, W12_0))
    return round(min(0.8 * min(m_sel, m_12m), MULT_HARD_CAP), 2), round(m_sel, 2), round(m_12m, 2)


def mc_challenge(daily, mult, rng, n=N_MC, block=5, max_days=250):
    """FTMO 2-Step: P1+10%→P2+5% / 静的−10% / 日次はEAガードで−4%クリップ。5日ブロックBS。"""
    r = np.clip(np.asarray(daily.values, float) * mult, -DAY_GUARD, None)
    if len(r) < block + 1:
        return dict(error="series too short")
    nb = len(r) - block + 1
    starts = rng.integers(0, nb, size=(n, max_days // block + 2))
    paths = r[(starts[:, :, None] + np.arange(block)[None, None, :])].reshape(n, -1)[:, :max_days * 2]
    eq = np.cumprod(1 + paths, axis=1)
    p1_days = np.full(n, -1); p2_days = np.full(n, -1); failed = np.zeros(n, bool)
    for i in range(n):
        e = eq[i]
        hit = np.where(e - 1 >= P1_TARGET)[0]
        dq = np.where(e - 1 <= -MAX_DD)[0]
        if len(dq) and (not len(hit) or dq[0] < hit[0]):
            failed[i] = True; continue
        if not len(hit) or hit[0] >= max_days:
            continue
        p1_days[i] = hit[0] + 1
        b2 = e[hit[0]]
        e2 = e[hit[0] + 1:] / b2
        hit2 = np.where(e2 - 1 >= P2_TARGET)[0]
        dq2 = np.where(e2 - 1 <= -MAX_DD)[0]
        if len(dq2) and (not len(hit2) or dq2[0] < hit2[0]):
            failed[i] = True; continue
        if len(hit2) and hit2[0] + hit[0] + 1 < max_days * 2:
            p2_days[i] = p1_days[i] + hit2[0] + 1
    okP1 = p1_days > 0; okP2 = p2_days > 0
    def q(a, p): return int(np.percentile(a, p)) if len(a) else None
    return dict(p1_pass=round(float(okP1.mean()) * 100, 1),
                funded=round(float(okP2.mean()) * 100, 1),
                fail=round(float(failed.mean()) * 100, 1),
                p1_days_med=q(p1_days[okP1], 50),
                funded_days_med=q(p2_days[okP2], 50), funded_days_p90=q(p2_days[okP2], 90))


def series_pack(s):
    mk = pd.PeriodIndex(s.index, freq="M")
    m = pd.Series({str(k): round(float((1 + s[mk == k]).prod() - 1) * 100, 2) for k in mk.unique()})
    return dict(list(m.sort_index().items())[-7:])


def main():
    print("[1/4] データ取得(recentfit_screen.pyの凍結窓を共用)")
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:60]}")

    print("[2/4] セル構築(34セル・B案と同一式)")
    cells = {}
    for nm in base.MON_FX + base.MON_IDX:
        cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    for nm in base.HOLD_SYMS:
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    for nm in base.TSMOM_SYMS:
        cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
    for p in base.V4_PAIRS:
        cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))

    out = dict(meta=dict(
        purpose="直近6ヶ月/3ヶ月トラック(docs/180)の事前固定スクリーニング",
        seed=SEED, n_mc=N_MC, mc_rule="FTMO P1+10%→P2+5%・静的−10%・−4%クリップ・5日ブロックBS",
        mult_rule="0.8×min(m*[選抜窓], m*[12ヶ月])・上限6.0",
        caveat="選抜窓で選び選抜窓で測る=構造的に楽観。窓が短いほどノイズ大。"
               "full_historyが正直な悲観バウンド。", inputs=base.sha256s()), tracks={})

    for tag, cfg in TRACKS.items():
        print(f"[3/4] {tag}: 統計・選抜 (SEL {cfg['sel0'].date()}.. / CONF {cfg['conf0'].date()}..)")
        table = {}
        for k, v in cells.items():
            table[k] = dict(family=v["family"], symbol=v["symbol"],
                            stats=stats_for(v["s"], cfg["sel0"], cfg["conf0"]))
        ranked = sorted([k for k in table if table[k]["stats"]["score"] is not None],
                        key=lambda k: table[k]["stats"]["score"], reverse=True)
        for k in ranked[:10]:
            print(f"  {k:16s} {table[k]['stats']}")
        weights = select_cells(table, cfg["min_active"])
        print("  選抜:", weights)
        if not weights:
            out["tracks"][tag] = dict(selected={}, note="フィルタ通過セルなし")
            continue

        idx = sorted(set().union(*[set(cells[k]["s"].index) for k in weights]))
        comp = pd.Series(0.0, index=pd.DatetimeIndex(idx))
        for k, w in weights.items():
            comp = comp.add(cells[k]["s"].reindex(comp.index).fillna(0.0) * w, fill_value=0.0)
        mult, m_sel, m_12m = calibrate(comp, cfg["sel0"])
        print(f"[4/4] {tag}: mult={mult} (m*_sel={m_sel} m*_12m={m_12m}) → MC")
        sM = comp * mult
        wd_sel, wdd_sel = base.worst_stats(win(sM, cfg["sel0"]))
        wd_12, wdd_12 = base.worst_stats(win(sM, W12_0))
        res = dict(
            selected=weights, mult=mult, m_star_sel=m_sel, m_star_12m=m_12m,
            expiry=cfg["expiry"],
            worst_day_sel=round(wd_sel * 100, 2), intramonth_dd_sel=round(wdd_sel * 100, 2),
            worst_day_12m=round(wd_12 * 100, 2), intramonth_dd_12m=round(wdd_12 * 100, 2),
            mc_sel_window=mc_challenge(win(comp, cfg["sel0"]), mult, np.random.default_rng(SEED)),
            mc_12m=mc_challenge(win(comp, W12_0), mult, np.random.default_rng(SEED)),
            mc_full=mc_challenge(comp, mult, np.random.default_rng(SEED)),
            monthly_12m=series_pack(win(sM, W12_0)),
            ranking_top10={k: table[k] for k in ranked[:10]})
        print(f"  MC sel={res['mc_sel_window']}")
        print(f"  MC 12m={res['mc_12m']}")
        print(f"  MC full={res['mc_full']}")
        out["tracks"][tag] = res

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", "recentfit_short_screen.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
