# -*- coding: utf-8 -*-
"""
recentfit_c6m_rescreen.py — C案(直近6ヶ月トラック)の再スクリーニング。
docs/180 §2の規則 + docs/197の相関ペナルティ λ=1.0 を実装する。

対象口座: FTMO50k #531407058(C案・期限2026-09-30)。
規則(docs/180 §2・不変):
  選抜窓=直近6ヶ月 / 確認窓=直近3ヶ月>0 / フィルタ 活動日≥8・SEL累積>0・CONF累積>0
  スコア mean/std×√n / 逆ボラcap40%・銘柄1・族2・Top-4
  倍率 0.8×min(m*_sel, m*_12m)・cap6.0 / MC=FTMO 10-5・3バウンド・シード7
追加(docs/197・2026-09-30の再スクリーニングから適用):
  score_adj = score × (1 − λ·max(0, ρ_book)) , λ=1.0
  ρ_book = 当該セルの選抜窓日次リターンと「対象口座を除く稼働中全口座の合成」の相関
  → **λ=0版とλ=1.0版の両方を必ず出力する**(docs/197 §4の可視化義務)

使い方:
  python3 recentfit_c6m_rescreen.py --as-of 2026-09-30      # 本番(9/30に実行)
  python3 recentfit_c6m_rescreen.py --as-of 2026-06-30 --dry # 実装検証用の過去日ドライラン
出力: results/recentfit_c6m_rescreen_<YYYYMM>.json
"""
import os, sys, json, argparse
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base

SEED = 7
LAMBDA = 1.0                 # docs/197 §2(変更は本docへの追記が必要)
MIN_ACTIVE = 8               # docs/180 §2 トラックC
MULT_HARD_CAP = 6.0
W_CAP = 0.40
TARGET_ACCOUNT = "FTMO50k_531407058"


def wnd(s, a, b):
    return s[(s.index >= a) & (s.index <= b)]


def stats_for(s, sel0, conf0, w12_0, end):
    ssel = wnd(s, sel0, end); sconf = wnd(s, conf0, end); s12 = wnd(s, w12_0, end)
    act = ssel[ssel != 0.0]; n = int(len(act))
    std = float(act.std()) if n > 2 else float("nan")
    score = float(act.mean() / std * np.sqrt(n)) if (n > 2 and std > 0) else None
    return dict(n_active=n,
                cum_sel=round(float((1 + ssel).prod() - 1) * 100, 2),
                cum_conf=round(float((1 + sconf).prod() - 1) * 100, 2),
                cum_12m=round(float((1 + s12).prod() - 1) * 100, 2),
                score=round(score, 3) if score is not None else None,
                std_active=std,
                cum_full=round(float((1 + s[s != 0.0]).prod() - 1) * 100, 1))


def rho_book(cell_s, book_s, sel0, end):
    x = wnd(cell_s, sel0, end); y = wnd(book_s, sel0, end)
    j = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    if len(j) < 20 or j["x"].std() == 0 or j["y"].std() == 0:
        return 0.0
    c = float(j["x"].corr(j["y"]))
    return 0.0 if not np.isfinite(c) else round(c, 3)


def cap_normalize(raw):
    tot = sum(raw.values())
    if tot <= 0:
        return {}
    w = {k: min(v / tot, W_CAP) for k, v in raw.items()}
    t2 = sum(w.values())
    r = {k: round(v / t2, 3) for k, v in w.items()}
    # 3桁丸めの誤差を最大重みへ寄せてΣw=1.000にする(docs/196 §1と同一手順)
    d = round(1.0 - sum(r.values()), 3)
    if d and r:
        big = max(r, key=r.get); r[big] = round(r[big] + d, 3)
    return r


def select(table, lam):
    """docs/180 §2の選抜。lam>0のときスコアにdocs/197のペナルティを掛ける。"""
    ok = [(k, v) for k, v in table.items()
          if v["stats"]["score"] is not None and v["stats"]["n_active"] >= MIN_ACTIVE
          and v["stats"]["cum_sel"] > 0 and v["stats"]["cum_conf"] > 0
          and np.isfinite(v["stats"]["std_active"]) and v["stats"]["std_active"] > 0]
    scored = []
    for k, v in ok:
        s = v["stats"]["score"]
        adj = s * (1.0 - lam * max(0.0, v["rho_book"])) if lam > 0 else s
        scored.append((k, v, round(adj, 3)))
    scored.sort(key=lambda x: -x[2])
    picked, fam_ct, sym_used = [], {}, set()
    for k, v, _ in scored:
        if v["symbol"] in sym_used or fam_ct.get(v["family"], 0) >= 2:
            continue
        picked.append(k); sym_used.add(v["symbol"])
        fam_ct[v["family"]] = fam_ct.get(v["family"], 0) + 1
        if len(picked) == 4:
            break
    w = cap_normalize({k: 1.0 / table[k]["stats"]["std_active"] for k in picked})
    return w, [(k, adj) for k, _, adj in scored]


def composite(cells, weights, a, b):
    if not weights:
        return pd.Series(dtype=float)
    idx = sorted(set().union(*[set(wnd(cells[k]["s"], a, b).index) for k in weights]))
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
        if wd >= -0.04 and wdd >= -0.08:
            best = m
        else:
            break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", required=True, help="再スクリーニング基準日 YYYY-MM-DD")
    ap.add_argument("--dry", action="store_true", help="過去日での実装検証(結果は選抜として扱わない)")
    a = ap.parse_args()
    END = pd.Timestamp(a.as_of)

    base.DATA = os.path.join(HERE, "data_202609")
    os.makedirs(base.DATA, exist_ok=True)
    base.W_ALL1 = END
    base.P1_TARGET = 0.10                      # FTMO 2-Step
    SEL0 = END - pd.DateOffset(months=6) + pd.Timedelta(days=1)
    CONF0 = END - pd.DateOffset(months=3) + pd.Timedelta(days=1)
    W12_0 = END - pd.DateOffset(months=12) + pd.Timedelta(days=1)

    print(f"[1/5] データ取得 / 基準日 {END.date()}"
          f"{'  ※ドライラン(実装検証)' if a.dry else '  ★本番'}")
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:50]}")
    # 基準日までのデータが存在するかを検査(未来日での実行を防ぐ)
    probe = base.load_daily("USDJPY")
    if probe.index[-1] < END - pd.Timedelta(days=3):
        raise SystemExit(f"[ABORT] 基準日 {END.date()} に対しデータ最終日 {probe.index[-1].date()}。"
                         f"基準日当日以降に実行すること。")

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
    base.verify_window([v["s"] for v in cells.values()], expect_end=END)   # docs/192

    print(f"[3/5] 現ブック合成(docs/197 §3・{TARGET_ACCOUNT}を除く)")
    import deployed_book as db
    book = db.book_composite(exclude=TARGET_ACCOUNT, end=END)
    print(f"  合成 n={len(book)} 最終日={book.index[-1].date()} "
          f"(合成不可: {', '.join(db.NOT_RECONSTRUCTIBLE)})")

    table = {}
    for k, v in cells.items():
        table[k] = dict(family=v["family"], symbol=v["symbol"],
                        stats=stats_for(v["s"], SEL0, CONF0, W12_0, END),
                        rho_book=rho_book(v["s"], book, SEL0, END))

    print("[4/5] 選抜(λ=0 従来規則 / λ=1.0 docs/197)")
    out = {"meta": dict(
        purpose="C案 直近6ヶ月トラックの再スクリーニング(docs/180 §2 + docs/197のλ=1.0)",
        as_of=str(END.date()), dry_run=bool(a.dry), seed=SEED, lam=LAMBDA,
        sel_window=f"{SEL0.date()}..{END.date()}", conf_window=f"{CONF0.date()}..{END.date()}",
        target_account=TARGET_ACCOUNT,
        book_excluded_from_composite=list(db.NOT_RECONSTRUCTIBLE),
        approx=db.APPROX), "versions": {}}

    for tag, lam in (("lambda_0", 0.0), ("lambda_1", LAMBDA)):
        w, ranked = select(table, lam)
        if not w:
            out["versions"][tag] = {"error": "フィルタ通過セルなし=当月は配備しない(docs/180)"}
            print(f"  {tag}: 通過セルなし"); continue
        comp = composite(cells, w, base.W_ALL0, END)
        m_sel = mstar(wnd(comp, SEL0, END)); m_12 = mstar(wnd(comp, W12_0, END))
        mult = round(min(0.8 * min(m_sel, m_12), MULT_HARD_CAP), 2)
        rec = dict(selected=w, mult=mult, m_sel=round(m_sel, 2), m_12m=round(m_12, 2),
                   top8_adjscore=[[k, s] for k, s in ranked[:8]],
                   legs={k: dict(rho_book=table[k]["rho_book"], **table[k]["stats"]) for k in w},
                   rho_book_composite=rho_book(comp, book, SEL0, END),
                   rho_book_composite_12m=rho_book(comp, book, W12_0, END))
        for btag, s in (("sel_6m", wnd(comp, SEL0, END)),
                        ("recent12m", wnd(comp, W12_0, END)),
                        ("full", comp)):
            rec.setdefault("mc", {})[btag] = base.mc_challenge(s, mult, np.random.default_rng(SEED))
        out["versions"][tag] = rec
        print(f"  {tag}: mult={mult} ρ_book(合成)={rec['rho_book_composite']} "
              f"選抜={ {k: v for k, v in w.items()} }")
        for b in ("sel_6m", "recent12m", "full"):
            m = rec["mc"][b]
            print(f"     MC {b:10s} p1={m['p1_pass']:5.1f} funded={m['funded']:5.1f} fail={m['fail']:5.1f}")

    v0, v1 = out["versions"].get("lambda_0", {}), out["versions"].get("lambda_1", {})
    if "selected" in v0 and "selected" in v1:
        s0, s1 = set(v0["selected"]), set(v1["selected"])
        out["penalty_effect"] = dict(
            pushed_out=sorted(s0 - s1), pulled_in=sorted(s1 - s0), unchanged=sorted(s0 & s1),
            d_rho_book=round(v1["rho_book_composite"] - v0["rho_book_composite"], 3),
            d_mult=round(v1["mult"] - v0["mult"], 2))
        print(f"[5/5] ペナルティの効果: 押し出し={out['penalty_effect']['pushed_out']} "
              f"/ 新規={out['penalty_effect']['pulled_in']} "
              f"/ Δρ_book={out['penalty_effect']['d_rho_book']}")

    tagname = ("DRY_" if a.dry else "") + END.strftime("%Y%m")
    fp = os.path.join(HERE, "results", f"recentfit_c6m_rescreen_{tagname}.json")
    with open(fp, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("saved:", fp)


if __name__ == "__main__":
    main()
