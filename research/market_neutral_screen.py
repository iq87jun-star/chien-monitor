# -*- coding: utf-8 -*-
"""
market_neutral_screen.py — 【市場中立(相対価値)トラック】docs/188の事前登録ルールの実装。

動機(docs/188 §1): 稼働8口座の収益源は「単一銘柄の絶対方向」1種類しかない。
非FXトラック(docs/182)でさえ64.4%がロングベータであり、型は増えていない。
本スクリプトは「2銘柄の相対」という現ブックに存在しない型を、
経済的に対になるペアだけを先験的に列挙して評価する(相関を見てからペアを選ばない)。

方法(docs/188 §3-5・全て実行前に固定):
  1) データ: Yahoo日足 2016-01-01..2026-08-31(docs/184/186と同一凍結)。XAGUSDを追加。
  2) スプレッド: 両脚をボラ目標(σは t-1 で確定=look-ahead無し)で名目化した差。
     u_t = rx_t*(vt/σx_{t-1}) − ry_t*(vt/σy_{t-1})
     vt=1%/日は単なる正規化定数で倍率multに完全に吸収される(戦略は不変)。
     名目レバレッジ gross = vt/σx + vt/σy は docs/188 §5 の m_notional 条件で評価する。
  3) セル: RVMR(zスコア±1.5逆張り・z=0跨ぎ or 10営業日で決済)と
     RVMOM(過去60日スプレッド符号・月次)の2型 × 11ペア = 22セル。
     コストは両脚に独立計上(中立戦略はコスト感応度が高いため保守側)。
  4) 配分: MN_BROAD(選抜なし・逆ボラcap40%)を主案、MN_SEL(docs/174規則)を対照。
  5) 倍率: min(0.8*min(m*_12m, m*_sel), 8.0, m_stress, m_notional)
  6) 採否: docs/188 §6の4条件を全て満たさない限り配備提案を出さない。
出力: results/market_neutral_screen.json → docs/189
⚠ Yahoo日足近似。実口座成績ではない。スプレッドは配備前にデモ実測が必須。
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base

SEED = 7
base.DATA = os.path.join(HERE, "data_202609")
os.makedirs(base.DATA, exist_ok=True)
base.P2_EPOCH = 1788220799                       # 2026-08-31 23:59:59 UTC
base.W_ALL1 = pd.Timestamp("2026-08-31")
W_END = pd.Timestamp("2026-08-31")
W12_0 = pd.Timestamp("2025-09-01")

# --- ユニバース拡張(docs/188 §3) ---
base.YAHOO.update({"WTI": "CL=F", "NATGAS": "NG=F", "XAGUSD": "SI=F"})
base.IDX_COST.update({"WTI": 5e-4, "NATGAS": 20e-4, "XAGUSD": 6e-4})

PAIRS = [
    ("US500", "NAS100", "Index"), ("GER40", "FR40", "Index"), ("GER40", "UK100", "Index"),
    ("US500", "GER40", "Index"), ("JP225", "US500", "Index"),
    ("XAUUSD", "XAGUSD", "Metal"), ("WTI", "NATGAS", "Energy"),
    ("BTCUSD", "ETHUSD", "Crypto"),
    ("AUDUSD", "NZDUSD", "FX"), ("EURUSD", "GBPUSD", "FX"), ("USDCAD", "EURUSD", "FX"),
]

VOL_TARGET = 0.01          # 1%/日・正規化定数(multに吸収される)
VOL_LB = 60                # σ推定窓
Z_LB = 60                  # zスコア窓
Z_ENTRY = 1.5
MR_MAX_HOLD = 10           # 営業日
MOM_LB = 60
MULT_HARD_CAP = 8.0
NOTIONAL_CAP = 10.0        # 両脚合計名目 ≤ 口座の10倍(docs/188 §5)
STRESS_MULT = 3.0          # 全期間最悪日の3倍(docs/188 §5)
W_CAP = 0.40
DAY_CAP, DD_CAP = 0.04, 0.08

# 現ブック近似(recentfit_nonfx_screen.py と同一定義)
BOOK_CELLS = [("Mon", "GBPJPY"), ("Mon", "AUDJPY"), ("Mon", "USDJPY"), ("Mon", "GBPUSD"),
              ("v4", "USDJPY"), ("v4", "NZDUSD"), ("v4", "AUDUSD")]


def wnd(s, a, b=W_END):
    return s[(s.index >= a) & (s.index <= b)]


def rel_cost(nm, price):
    """往復コストの対名目比率"""
    if nm in base.IDX_COST:
        return pd.Series(base.IDX_COST[nm], index=price.index)
    return 2 * base.pip_size(nm) / price


def spread_legs(X, Y):
    """両脚のボラ目標名目化。σは t-1 確定 → look-ahead 無し。"""
    dx = base.load_daily(X); dy = base.load_daily(Y)
    d = pd.concat([dx["close"].rename("px"), dy["close"].rename("py")], axis=1).dropna()
    rx = d["px"].pct_change(); ry = d["py"].pct_change()
    sx = rx.rolling(VOL_LB).std().shift(1)
    sy = ry.rolling(VOL_LB).std().shift(1)
    lx = (VOL_TARGET / sx).replace([np.inf, -np.inf], np.nan)
    ly = (VOL_TARGET / sy).replace([np.inf, -np.inf], np.nan)
    u = (rx * lx - ry * ly)
    gross = (lx + ly)
    cost = rel_cost(X, d["px"]) * lx + rel_cost(Y, d["py"]) * ly
    df = pd.concat([u.rename("u"), gross.rename("g"), cost.rename("c")], axis=1).dropna()
    return df[(df.index >= base.W_ALL0) & (df.index <= W_END)]


def rvmr_cell(X, Y):
    """zスコア逆張り: |z|>1.5 で翌日建て・z=0跨ぎ or 10営業日で決済・単玉"""
    df = spread_legs(X, Y)
    u = df["u"].values; c = df["c"].values; idx = df.index
    S = np.cumsum(u)
    n = len(u); out = np.zeros(n); i = Z_LB + 1
    while i < n - 1:
        w = S[i - Z_LB:i]
        sd = w.std(ddof=1)
        if sd <= 0:
            i += 1; continue
        z = (S[i] - w.mean()) / sd
        sig = 1 if z < -Z_ENTRY else (-1 if z > Z_ENTRY else 0)
        if sig == 0:
            i += 1; continue
        j = i + 1; held = 0
        out[j] += sig * u[j] - c[j]           # 建玉日にコスト計上
        while j < n - 1 and held < MR_MAX_HOLD:
            w2 = S[j - Z_LB:j]; sd2 = w2.std(ddof=1)
            z2 = (S[j] - w2.mean()) / sd2 if sd2 > 0 else 0.0
            if (sig > 0 and z2 >= 0) or (sig < 0 and z2 <= 0):
                break
            j += 1; held += 1
            out[j] += sig * u[j]
        i = max(i + 1, j)
    return pd.Series(out, index=idx), df


def rvmom_cell(X, Y):
    """過去60日スプレッド符号・月次リバランス"""
    df = spread_legs(X, Y)
    u = df["u"]; c = df["c"]; S = u.cumsum()
    sig = np.sign(S - S.shift(MOM_LB))
    me = pd.Series(S.index, index=S.index).groupby(pd.PeriodIndex(S.index, freq="M")).max()
    hold = sig.reindex(S.index).where(S.index.isin(me.values)).ffill().shift(1).fillna(0.0)
    out = hold * u
    # 月初(=建て直し日)にコスト計上。符号が変わらない月もロールコストを保守側に課す
    firsts = pd.Series(S.index, index=S.index).groupby(pd.PeriodIndex(S.index, freq="M")).min()
    mask = S.index.isin(firsts.values) & (hold != 0)
    out = out - c.where(mask, 0.0)
    return out.fillna(0.0), df


def cell_stats(s, a):
    sw = wnd(s, a); act = sw[sw != 0.0]; n = int(len(act))
    std = float(act.std()) if n > 2 else float("nan")
    return dict(n_active=n, cum=round(float((1 + sw).prod() - 1) * 100, 2),
                score=round(float(act.mean() / std * np.sqrt(n)), 2) if (n > 2 and std > 0) else None,
                std_active=std)


def cap_normalize(raw):
    tot = sum(raw.values())
    if tot <= 0:
        return {}
    w = {k: min(v / tot, W_CAP) for k, v in raw.items()}
    t2 = sum(w.values())
    return {k: v / t2 for k, v in w.items()}


def mstar(s):
    if len(s) == 0 or float(s.min()) >= 0:
        return 30.0
    best = 0.05
    for m in np.arange(0.05, 30.01, 0.05):
        wd, wdd = base.worst_stats(s * m)
        if wd >= -DAY_CAP and wdd >= -DD_CAP:
            best = m
        else:
            break
    return best


def combine(cells, weights, key="s"):
    idx = sorted(set().union(*[set(cells[k][key].index) for k in weights]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for k, w in weights.items():
        out = out.add(cells[k][key].reindex(out.index).fillna(0.0) * w, fill_value=0.0)
    return out


def book_proxy():
    parts = []
    for fam, sym in BOOK_CELLS:
        parts.append(base.mon_cell(sym) if fam == "Mon" else base.v4_cell(sym))
    idx = sorted(set().union(*[set(p.index) for p in parts]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for p in parts:
        out = out.add(p.reindex(out.index).fillna(0.0) / len(parts), fill_value=0.0)
    return out


def corr_with(s, other, a):
    x = wnd(s, a); y = wnd(other, a)
    j = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    return round(float(j["x"].corr(j["y"])), 2) if len(j) > 30 else None


def sharpe_full(s):
    act = s[s != 0.0]
    return round(float(act.mean() / act.std() * np.sqrt(252)), 2) if len(act) > 30 and act.std() > 0 else None


def main():
    print("[1/6] データ取得(凍結窓 ..2026-08-31・XAGUSD追加)")
    need = set(sum([[a, b] for a, b, _ in PAIRS], [])) | {"US500"} | {s for _, s in BOOK_CELLS}
    for nm in sorted(need):
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:60]}")

    print("[2/6] スプレッドセル構築(11ペア×2型=22セル)")
    cells = {}
    for X, Y, cls in PAIRS:
        try:
            smr, dmr = rvmr_cell(X, Y)
            smo, dmo = rvmom_cell(X, Y)
        except Exception as e:
            print(f"  {X}/{Y} ERR {type(e).__name__} {str(e)[:70]}"); continue
        for tag, s, d in (("RVMR", smr, dmr), ("RVMOM", smo, dmo)):
            k = f"{tag}_{X}_{Y}"
            cells[k] = dict(family=tag, symbol=f"{X}/{Y}", cls=cls, s=s, gross=d["g"])
    print(f"  セル数 {len(cells)}")

    print("[3/6] セル統計・相関")
    bp = book_proxy(); spx = base.hold_cell("US500")
    table = {}
    for k, v in cells.items():
        st12 = cell_stats(v["s"], W12_0); stf = cell_stats(v["s"], base.W_ALL0)
        table[k] = dict(family=v["family"], symbol=v["symbol"], cls=v["cls"],
                        stats_12m=dict(n_active=st12["n_active"], cum=st12["cum"], score=st12["score"]),
                        cum_full=stf["cum"], sharpe_full=sharpe_full(v["s"]),
                        corr_book_12m=corr_with(v["s"], bp, W12_0),
                        corr_spx_12m=corr_with(v["s"], spx, W12_0),
                        gross_med=round(float(wnd(v["gross"], W12_0).median()), 2),
                        gross_max_12m=round(float(wnd(v["gross"], W12_0).max()), 2))
    for k in sorted(table, key=lambda k: -(table[k]["sharpe_full"] or -9))[:12]:
        t = table[k]
        print(f"  {k:22s} SR_full={t['sharpe_full']} cum_full={t['cum_full']}% "
              f"12m={t['stats_12m']['cum']}% rho_book={t['corr_book_12m']} rho_spx={t['corr_spx_12m']}")

    print("[4/6] 配分(MN_BROAD 主案 / MN_SEL 対照)")
    avail = {k: v for k, v in table.items()
             if v["stats_12m"]["score"] is not None and cell_stats(cells[k]["s"], W12_0)["std_active"] > 0}
    iv = {k: 1.0 / cell_stats(cells[k]["s"], W12_0)["std_active"] for k in avail}
    w_broad = cap_normalize(iv)
    ok = [(k, v) for k, v in avail.items() if v["stats_12m"]["cum"] > 0 and v["stats_12m"]["n_active"] >= 15]
    ok.sort(key=lambda kv: kv[1]["stats_12m"]["score"], reverse=True)
    picked, fam_ct, sym_used = [], {}, set()
    for k, v in ok:
        if v["symbol"] in sym_used or fam_ct.get(v["family"], 0) >= 2:
            continue
        picked.append(k); sym_used.add(v["symbol"]); fam_ct[v["family"]] = fam_ct.get(v["family"], 0) + 1
        if len(picked) == 4:
            break
    w_sel = cap_normalize({k: iv[k] for k in picked}) if picked else {}
    print("  MN_BROAD:", len(w_broad), "セル / MN_SEL:", w_sel)

    print("[5/6] 倍率校正・MC・採否判定")
    out = {"meta": {"purpose": "市場中立(相対価値)トラック docs/188",
                    "freeze": "2016-01-01..2026-08-31", "seed": SEED,
                    "vol_target_per_leg": VOL_TARGET, "vol_lb": VOL_LB,
                    "mult_rule": "min(0.8*min(m*_12m,m*_full), 8.0, m_stress, m_notional)",
                    "approx": ["Yahoo日足近似", "実口座成績ではない",
                               "コストは両脚独立計上(保守側)", "スプレッドは配備前デモ実測が必須"]},
           "cells": table, "portfolios": {}}
    rng_seed = SEED
    for name, w in (("MN_BROAD", w_broad), ("MN_SEL", w_sel)):
        if not w:
            out["portfolios"][name] = {"error": "no cells selected"}; continue
        comp = combine(cells, w)
        gross = combine(cells, w, key="gross")
        c12, cfull = wnd(comp, W12_0), wnd(comp, base.W_ALL0)
        m_risk = 0.8 * min(mstar(c12), mstar(cfull))
        worst_full = abs(float(cfull.min()))
        m_stress = 0.10 / (STRESS_MULT * worst_full) if worst_full > 0 else MULT_HARD_CAP
        gmax = float(wnd(gross, W12_0).max())
        m_notional = NOTIONAL_CAP / gmax if gmax > 0 else MULT_HARD_CAP
        mult = round(min(m_risk, MULT_HARD_CAP, m_stress, m_notional), 2)
        binding = min([(m_risk, "risk"), (MULT_HARD_CAP, "hard_cap"),
                       (m_stress, "stress"), (m_notional, "notional")])[1]
        rec = dict(n_cells=len(w),
                   weights={k: round(v, 3) for k, v in sorted(w.items(), key=lambda x: -x[1])[:8]},
                   mult=mult, mult_binding=binding,
                   mult_components=dict(risk=round(m_risk, 2), hard_cap=MULT_HARD_CAP,
                                        stress=round(m_stress, 2), notional=round(m_notional, 2)),
                   gross_notional_med=round(float(wnd(gross, W12_0).median()), 2),
                   gross_notional_max=round(gmax, 2),
                   sharpe_full=sharpe_full(comp), sharpe_12m=sharpe_full(c12),
                   cum_12m=round(float((1 + c12).prod() - 1) * 100, 2),
                   cum_full=round(float((1 + cfull).prod() - 1) * 100, 1),
                   worst_day_12m=round(float(c12.min()) * 100, 2),
                   worst_day_full=round(worst_full * -100, 2),
                   corr_book_12m=corr_with(comp, bp, W12_0),
                   corr_book_full=corr_with(comp, bp, base.W_ALL0),
                   corr_spx_12m=corr_with(comp, spx, W12_0),
                   corr_spx_full=corr_with(comp, spx, base.W_ALL0))
        for venue, p1 in (("FTMO_10_5", 0.10), ("FN_8_5", 0.08)):
            base.P1_TARGET = p1
            rec.setdefault("mc", {})[venue] = {
                "recent_12m": base.mc_challenge(c12, mult, np.random.default_rng(rng_seed)),
                "full_pessimistic": base.mc_challenge(cfull, mult, np.random.default_rng(rng_seed))}
        mcf = rec["mc"]["FTMO_10_5"]["full_pessimistic"]
        rec["verdict"] = dict(
            c1_corr_book=bool(rec["corr_book_12m"] is not None and abs(rec["corr_book_12m"]) <= 0.25),
            c2_corr_spx=bool(rec["corr_spx_12m"] is not None and abs(rec["corr_spx_12m"]) <= 0.25),
            c3_pessimistic_funded_gt_fail=bool(mcf["funded"] > mcf["fail"]),
            c4_sharpe_full_gt_0_5=bool((rec["sharpe_full"] or -9) > 0.5))
        rec["verdict"]["ALL_PASS"] = all(rec["verdict"].values())
        out["portfolios"][name] = rec
        print(f"  {name}: mult={mult}({binding}) SR_full={rec['sharpe_full']} "
              f"rho_book={rec['corr_book_12m']} rho_spx={rec['corr_spx_12m']}")
        print(f"    MC full(FTMO): {mcf}")
        print(f"    判定: {rec['verdict']}")

    print("[6/6] 保存")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    fp = os.path.join(HERE, "results", "market_neutral_screen.json")
    with open(fp, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved:", fp)


if __name__ == "__main__":
    main()
