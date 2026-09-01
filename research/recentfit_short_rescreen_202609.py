# -*- coding: utf-8 -*-
"""
recentfit_short_rescreen_202609.py — D案(直近3ヶ月トラック)の2026-09月次再スクリーニング。

docs/180 §2の事前登録ルールを窓だけロールして再実行する(ルール変更は不可):
- セル母集団・構築式・コスト: recentfit_screen.pyと同一
- 選抜窓(D): 直近3ヶ月 = 2026-06-01..2026-08-31 / 確認窓: 直近6週(2026-07-21..)>0
- フィルタ: 活動日≥5・選抜窓累積>0・確認窓累積>0
- 加重: 選抜窓の逆ボラ・cap40%・銘柄1/ファミリー2・Top-4
- 倍率: m*=max{m: 最悪単日×m≥−4% ∧ 月中DD×m≥−8%} を選抜窓と直近12ヶ月の両方で計算し
  小さい方×0.8。上限6.0
- MC: FTMO P1+10%→P2+5%・3バウンド(選抜窓/12ヶ月/全期間)・シード7
データ: Yahoo日足 2016-01-01..2026-08-31(本再スクリーニング用に新規凍結・別キャッシュ)
出力: results/recentfit_short_rescreen_202609.json
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base

# --- 窓のロール(2026-09版・データ新規凍結) ---
base.DATA = os.path.join(HERE, "data_202609")   # 別キャッシュ(research/.gitignoreのdata*で除外)
os.makedirs(base.DATA, exist_ok=True)
base.P2_EPOCH = 1788220799                       # 2026-08-31 23:59:59 UTC
base.W_ALL1 = pd.Timestamp("2026-08-31")
base.W12_0 = pd.Timestamp("2025-09-01")          # 倍率校正用の直近12ヶ月
SEL0  = pd.Timestamp("2026-06-01")               # D: 直近3ヶ月
CONF0 = pd.Timestamp("2026-07-21")               # 直近6週
MIN_ACTIVE = 5
MULT_HARD_CAP = 6.0
base.P1_TARGET = 0.10                            # FTMO 2-Step


def win(s, a):
    return s[(s.index >= a) & (s.index <= base.W_ALL1)]


def stats_for(s):
    ssel = win(s, SEL0); sconf = win(s, CONF0); s12 = win(s, base.W12_0)
    act = ssel[ssel != 0.0]; n = int(len(act))
    std = float(act.std()) if n > 2 else float("nan")
    score = float(act.mean() / std * np.sqrt(n)) if (n > 2 and std > 0) else float("-inf")
    return dict(n_active=n,
                cum_sel=round(float((1 + ssel).prod() - 1) * 100, 2),
                cum_conf=round(float((1 + sconf).prod() - 1) * 100, 2),
                cum_12m=round(float((1 + s12).prod() - 1) * 100, 2),
                score=round(score, 2) if np.isfinite(score) else None,
                std_active=round(std * 100, 3) if np.isfinite(std) else None,
                cum_full=round(float((1 + s[s != 0.0]).prod() - 1) * 100, 1))


def select_cells(table):
    ok = [(k, v) for k, v in table.items()
          if v["stats"]["n_active"] >= MIN_ACTIVE
          and v["stats"]["cum_sel"] > 0 and v["stats"]["cum_conf"] > 0
          and v["stats"]["score"] is not None]
    ok.sort(key=lambda kv: kv[1]["stats"]["score"], reverse=True)
    picked, fam_ct, sym_used = [], {}, set()
    for k, v in ok:
        fam, sym = v["family"], v["symbol"]
        if sym in sym_used or fam_ct.get(fam, 0) >= 2:
            continue
        picked.append(k); sym_used.add(sym); fam_ct[fam] = fam_ct.get(fam, 0) + 1
        if len(picked) == 4:
            break
    if not picked:
        return {}
    iv = {k: 1.0 / (table[k]["stats"]["std_active"] / 100) for k in picked}
    tot = sum(iv.values())
    w = {k: min(iv[k] / tot, 0.40) for k in picked}
    tot2 = sum(w.values())
    return {k: round(v / tot2, 3) for k, v in w.items()}


def mult_for(comp):
    def mstar(s):
        best = 0.05
        for m in np.arange(0.05, 8.01, 0.05):
            wd, wdd = base.worst_stats(s * m)
            if wd >= -0.04 and wdd >= -0.08:
                best = m
            else:
                break
        return best
    m_sel = mstar(win(comp, SEL0)); m_12 = mstar(win(comp, base.W12_0))
    return round(min(0.8 * min(m_sel, m_12), MULT_HARD_CAP), 2), m_sel, m_12


def main():
    print("[1/4] データ取得(新凍結窓 ..2026-08-31)")
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:60]}")

    print("[2/4] セル構築(docs/174と同一母集団)")
    cells = {}
    for nm in base.MON_FX + base.MON_IDX:
        cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
    for nm in base.HOLD_SYMS:
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
    for nm in base.TSMOM_SYMS:
        cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
    for p in base.V4_PAIRS:
        cells[f"v4_{p}"] = dict(family="v4", symbol=p, s=base.v4_cell(p))

    print("[3/4] D窓統計と選抜")
    table = {}
    for k, v in cells.items():
        table[k] = dict(family=v["family"], symbol=v["symbol"], stats=stats_for(v["s"]))
    ranked = sorted([k for k in table if table[k]["stats"]["score"] is not None],
                    key=lambda k: table[k]["stats"]["score"], reverse=True)
    for k in ranked[:10]:
        print(f"  {k:16s} {table[k]['stats']}")
    weights = select_cells(table)
    print("  選抜:", weights)
    if not weights:
        print("  ⚠ フィルタ通過セルなし → D案は今月は休止(docs/180)")
        return

    print("[4/4] 合成・倍率・MC(FTMO 10/5・3バウンド)")
    idx = sorted(set().union(*[set(cells[k]["s"].index) for k in weights]))
    comp = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, w in weights.items():
        comp = comp.add(cells[k]["s"].reindex(comp.index).fillna(0.0) * w, fill_value=0.0)
    mult, m_sel, m_12 = mult_for(comp)
    print(f"  倍率: {mult} (m*_sel={m_sel:.2f}, m*_12m={m_12:.2f}, cap{MULT_HARD_CAP})")
    mc = {}
    for tag, s in (("sel_3m", win(comp, SEL0)), ("recent12m", win(comp, base.W12_0)), ("full", comp)):
        mc[tag] = base.mc_challenge(s, mult, np.random.default_rng(7))
        print(f"  {tag}: {mc[tag]}")

    res = dict(
        meta=dict(purpose="D案(直近3ヶ月)2026-09月次再スクリーニング(docs/180 §2の窓ロール)",
                  window_all="2016-01-01..2026-08-31", sel=str(SEL0.date()), conf=str(CONF0.date()),
                  w12=str(base.W12_0.date()), rule="docs/180 §2(変更なし)", seed=7,
                  mult=dict(mult=mult, m_sel=m_sel, m_12m=m_12, cap=MULT_HARD_CAP),
                  inputs=base.sha256s()),
        ranking={k: table[k] for k in ranked},
        selected=weights, mc=mc)
    path = os.path.join(HERE, "results", "recentfit_short_rescreen_202609.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
