# -*- coding: utf-8 -*-
"""
recentfit_nonfx_screen.py — 【非FX分散トラック・候補調査】現ブックと相関の低い非FX資産で
直近フィット・セルを同一固定規則で選抜する(2026-08-06 ユーザー依頼)。

背景: 現行配備(FTMO100k A案 / FTMO50k C・D案 / Fintokei B案)は円クロス・リスクオンFXに
集中しており(GBPJPY-AUDJPY日次相関≈0.74)、実質1ベットに近い。金・エネルギー・暗号・指数は
現ブックとの日次相関がほぼゼロ(実測|ρ|≤0.28)のため、同じ「直近フィット」枠組みでの
分散候補になり得るかを調査する。

方法: recentfit_screen.py(docs/174)と同一のセル構築式・コスト・選抜規則
(12ヶ月スコア降順・活動日≥15・12m/6m累積>0・Top4・銘柄1/ファミリー2制約・逆ボラ加重cap40%)。
ユニバースのみ非FXに限定: 金・WTI・天然ガス(新規追加)・指数6・BTC/ETH。
追加出力: 各セル/選抜合成の現ブック近似との日次相関。

⚠ 本スクリーンは docs/174 と同じく「直近レジーム継続への有償ベット」であり耐久エッジの
  主張はしない。選抜窓の数字=定義上ほぼ最良。full_history が正直な悲観バウンド。
⚠ JP225が選抜された場合、FN100k #14074882(季節RG3)とのJP225重複に注意 —
  配備は別業者(FTMO/Fintokei等)なら可(docs/173書面・docs/161 §5)。
出力: results/recentfit_nonfx_screen.json
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base   # セル構築・fetch・選抜・校正・MCを同一実装で再利用

SEED = 7

# --- ユニバース拡張(エネルギー2銘柄を追加・凍結窓はbaseと同一) ---
base.YAHOO.update({"WTI": "CL=F", "NATGAS": "NG=F"})
base.IDX_COST.update({"WTI": 5e-4, "NATGAS": 20e-4})   # CFD実勢スプレッド近似(往復・保守側)

NONFX = ["XAUUSD", "WTI", "NATGAS", "BTCUSD", "ETHUSD",
         "US500", "NAS100", "GER40", "JP225", "UK100", "FR40"]

# 現ブック近似(docs/178/181の配備セルを同じ生成式で再構築・等ウェイト):
#   Mon GBPJPY/AUDJPY(Fintokei・C6m), Mon USDJPY(D3m), Mon GBPUSD(A案S1),
#   v4 USDJPY(Fintokei), v4 NZDUSD/AUDUSD(C6m・D3m)
# A案S3(木曜USDCHF 6h)・S4/S5(RSI2逆張り)は生成式が無いため近似から除外。
BOOK_CELLS = [("Mon", "GBPJPY"), ("Mon", "AUDJPY"), ("Mon", "USDJPY"), ("Mon", "GBPUSD"),
              ("v4", "USDJPY"), ("v4", "NZDUSD"), ("v4", "AUDUSD")]


def v4_cell_nonfx(nm):
    """base.v4_cell と同一ロジック。コストのみFXのpip固定→IDX_COST相対コストに変更。"""
    df = base.load_daily(nm)
    o = df["open"].values; hh = df["high"].values; ll = df["low"].values; c = df["close"].values
    idx = df.index; n = len(c); rsi = base.rsi_w(c); atr = base.atr_d(hh, ll, c); bb = 20
    cost_rel = base.IDX_COST[nm]; acc = {}; i = bb + 2
    while i < n - 1:
        win_ = c[i - bb:i]; mean = win_.mean(); sd = win_.std(ddof=1)
        z = (c[i] - mean) / sd if sd > 0 else 0
        down = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
            else: break
        up = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
            else: break
        retd = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0
        buy = int(rsi[i] < 35) + int(z < -1.5) + int(down >= 3) + int(retd < -.005)
        sell = int(rsi[i] > 65) + int(z > 1.5) + int(up >= 3) + int(retd > .005)
        sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
        if sig == 0:
            i += 1; continue
        entry = o[i + 1]; sld = 1.5 * atr[i]; tpd = 1.2 * sld
        if sld <= 0 or entry <= 0:
            i += 1; continue
        sl = entry - sig * sld; tp = entry + sig * tpd; ex = None; j = i + 1; held = 0
        while j < n and held < 8:
            if sig > 0:
                if ll[j] <= sl: ex = sl; break
                if hh[j] >= tp: ex = tp; break
            else:
                if hh[j] >= sl: ex = sl; break
                if ll[j] <= tp: ex = tp; break
            j += 1; held += 1
        jx = min(j, n - 1)
        if ex is None: ex = c[jx]
        prev = entry
        for t in range(i + 1, jx + 1):
            px = ex if t == jx else c[t]
            r = sig * (px - prev) / entry
            if t == i + 1: r -= cost_rel
            acc[idx[t]] = acc.get(idx[t], 0.0) + r
            prev = px
        i = max(i + 1, j)
    return base.clip(pd.Series(acc).sort_index())


def daily_aligned(series_list):
    """カレンダー整列(非活動日=0)の日次リターン行列"""
    idx = sorted(set().union(*[set(s.index) for s in series_list]))
    return [s.reindex(pd.DatetimeIndex(idx)).fillna(0.0) for s in series_list]


def corr_vs_book(s, book):
    """候補セル vs 現ブック近似の日次相関(全期間/直近12ヶ月・非活動日=0で整列)"""
    a, b = daily_aligned([s, book])
    out = {}
    for tag, t0 in (("full", base.W_ALL0), ("12m", base.W12_0)):
        aa = a[(a.index >= t0)]; bb2 = b[(b.index >= t0)]
        if len(aa) > 30 and aa.std() > 0 and bb2.std() > 0:
            out[tag] = round(float(np.corrcoef(aa.values, bb2.values)[0, 1]), 3)
        else:
            out[tag] = None
    return out


def main():
    print("[1/5] データ取得(凍結窓 2016-01-01..2026-07-29・エネルギー2銘柄追加)")
    for nm in list(base.YAHOO):
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:60]}")

    print("[2/5] 現ブック近似の構築")
    book_parts = []
    for fam, nm in BOOK_CELLS:
        book_parts.append(base.mon_cell(nm) if fam == "Mon" else base.v4_cell(nm))
    book = sum(daily_aligned(book_parts)) / len(book_parts)

    print("[3/5] 非FXセル構築(Mon/Hold/TSMOM/v4 × 11銘柄)")
    cells = {}
    for nm in NONFX:
        cells[f"Mon_{nm}"] = dict(family="Mon", symbol=nm, s=base.mon_cell(nm))
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=base.hold_cell(nm))
        cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=base.tsmom_cell(nm))
        cells[f"v4_{nm}"] = dict(family="v4", symbol=nm, s=v4_cell_nonfx(nm))

    print("[4/5] 統計・選抜・相関")
    table = {}
    for k, v in cells.items():
        st = base.cell_stats(v["s"])
        table[k] = dict(family=v["family"], symbol=v["symbol"], stats=st,
                        corr_book=corr_vs_book(v["s"], book))
    ranked = sorted([k for k in table if table[k]["stats"]["score_12m"] is not None],
                    key=lambda k: table[k]["stats"]["score_12m"], reverse=True)
    for k in ranked[:15]:
        t = table[k]
        print(f"  {k:16s} score={t['stats']['score_12m']} 12m={t['stats']['cum_12m']}% "
              f"6m={t['stats']['cum_6m']}% 全期間={t['stats']['cum_full']}% ρ_book12m={t['corr_book']['12m']}")

    weights = base.select_cells(table)
    print("  選抜:", weights)

    print("[5/5] 合成・校正・MC(FTMO 10/5土俵)・合成相関")
    aligned = daily_aligned([cells[k]["s"] for k in weights])
    comp = sum(a * w for a, w in zip(aligned, weights.values()))
    comp12 = base.win(comp, base.W12_0)
    mult_std = base.calibrate(comp12)
    # FTMO 2-Step(P1+10%)土俵はshort版と同じ差し替え
    base.P1_TARGET = 0.10
    variants = {}
    for tag, mult in (("standard", mult_std), ("fast_1.5x", round(mult_std * 1.5, 2))):
        mc_recent = base.mc_challenge(comp12, mult, np.random.default_rng(SEED))
        mc_full = base.mc_challenge(comp, mult, np.random.default_rng(SEED))
        s = comp12 * mult
        wd, wdd = base.worst_stats(s)
        variants[tag] = dict(mult=mult, recent12m=mc_recent, full_history=mc_full,
                             recent_worst_day=round(wd * 100, 2),
                             recent_worst_intramonth_dd=round(wdd * 100, 2))
        print(f"  {tag}: mult={mult} 直近={mc_recent} 全期間={mc_full}")
    comp_corr = corr_vs_book(comp, book)
    print("  選抜合成 vs 現ブック近似 相関:", comp_corr)

    res = dict(
        meta=dict(
            purpose="非FX分散トラック候補調査(現ブックと低相関の直近フィット・セル)",
            universe=NONFX, window_all="2016-01-01..2026-07-29",
            window_12m=str(base.W12_0.date()), window_6m=str(base.W6_0.date()), seed=SEED,
            selection_rule="recentfit_screen.pyと同一(score降順/活動≥15/12m>0∧6m>0/Top4/"
                           "銘柄1・ファミリー2/逆ボラcap40%)",
            book_proxy=[f"{f}_{s}" for f, s in BOOK_CELLS],
            book_proxy_note="A案S3(木曜USDCHF)・S4/S5(RSI2逆張り)は生成式が無いため近似から除外",
            mc_rule="FTMO 2-Step P1+10%→P2+5%・静的DD−10%・日次−4%クリップ・5日ブロックBS",
            caveat="直近窓で選び直近窓で測る=構造的に楽観。full_historyが正直な悲観バウンド。"
                   "Yahoo日足近似・配当除く。JP225採用時はFN100k季節RG3と別業者配備が必要",
            inputs=base.sha256s()),
        ranking={k: table[k] for k in ranked},
        selected=weights,
        composite_corr_vs_book=comp_corr,
        variants=variants)
    path = os.path.join(HERE, "results", "recentfit_nonfx_screen.json")
    with open(path, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
