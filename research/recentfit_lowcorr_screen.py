# -*- coding: utf-8 -*-
"""
recentfit_lowcorr_screen.py — 【トラックE「LC1y」】docs/182の事前登録ルール実装。

ユーザー指示(2026-08-04): 1年特化で、現状採用されている銘柄(docs/178/181の13銘柄)と
相関が低い銘柄で最良の手法を構築する。
- 相関フィルタ: max(|ρ|全期間, |ρ|12m) < 0.55(採用13銘柄それぞれと)
- ユニバース: 既存22銘柄+暗号資産メジャー5(SOL/XRP/LTC/ADA/DOGE)
- セル: 生存銘柄 × {Hold, TSMOM}(構築式はrecentfit_screen.pyと同一・
  月初摩擦のみ銘柄別コストで保守化)
- 選抜: docs/174の1年特化ルール(SEL=直近12ヶ月・確認=6ヶ月・Top-4・銘柄1・ファミリー2)
- 倍率: 0.8×m*[12m]・上限6.0 / MC: FN Stellar(8/5)とFTMO(10/5)の両土俵
出力: results/recentfit_lowcorr_screen.json → docs/183
⚠ 直近窓で選び直近窓で測る=構造的に楽観。full_historyが正直な悲観バウンド。
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base   # fetch・セル構築式・worst_stats等を同一実装で再利用

SEED = 7
N_MC = 10000
MAX_DD, DAY_GUARD = 0.10, 0.04
MULT_HARD_CAP = 6.0
CORR_TH = 0.55
W12_0, W6_0, W_ALL1 = base.W12_0, base.W6_0, base.W_ALL1
TOP_K, MAX_PER_FAMILY, W_CAP, MIN_ACTIVE = 4, 2, 0.40, 15
EXPIRY = "2026-10-31"

ADOPTED = ["EURJPY", "GBPJPY", "USDJPY", "AUDJPY", "NZDUSD", "AUDUSD", "GBPUSD", "USDCHF",
           "NAS100", "US500", "GER40", "XAUUSD", "JP225"]

# ユニバース拡張(docs/182 §3) — 既存22銘柄+暗号資産メジャー5
EXTRA_CRYPTO = {"SOLUSD": "SOL-USD", "XRPUSD": "XRP-USD", "LTCUSD": "LTC-USD",
                "ADAUSD": "ADA-USD", "DOGEUSD": "DOGE-USD"}
base.YAHOO.update(EXTRA_CRYPTO)
base.CRYPTO.update(EXTRA_CRYPTO.keys())
base.IDX_COST.update({"SOLUSD": 25e-4, "XRPUSD": 25e-4, "LTCUSD": 20e-4,
                      "ADAUSD": 25e-4, "DOGEUSD": 30e-4})

# 相関フィルタの候補 = 未採用の全銘柄
CANDIDATES = [nm for nm in base.YAHOO if nm not in ADOPTED]
# 暗号資産クラス(Hold/TSMOMの適用域, docs/182 §4)
CRYPTO_CLASS = ["BTCUSD", "ETHUSD"] + list(EXTRA_CRYPTO.keys())


def daily_ret(nm):
    return base.load_daily(nm)["close"].pct_change().dropna()


def corr_pair(a, b, t0):
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    j = j[(j.index >= t0) & (j.index <= W_ALL1)]
    if len(j) < 100:
        return None
    return float(j.corr().iloc[0, 1])


def crypto_cell(kind, nm):
    """基準式そのまま+月初摩擦を銘柄別コストへ上乗せ(docs/182 §4・唯一の差分)"""
    s = base.hold_cell(nm) if kind == "Hold" else base.tsmom_cell(nm)
    fee = max(5e-4, base.IDX_COST.get(nm, 5e-4))
    extra = fee - 5e-4
    if extra > 0:
        act = s[s != 0.0] if kind == "TSMOM" else s
        if len(act):
            firsts = pd.Series(act.index, index=act.index).groupby(
                pd.PeriodIndex(act.index, freq="M")).min()
            s.loc[s.index.isin(firsts.values)] -= extra
    return s


def win(s, a):
    return s[(s.index >= a) & (s.index <= W_ALL1)]


def stats_for(s):
    s12 = win(s, W12_0); s6 = win(s, W6_0)
    act = s12[s12 != 0.0]
    n = int(len(act))
    std = float(act.std()) if n > 2 else float("nan")
    score = float(act.mean() / std * np.sqrt(n)) if (n > 2 and std > 0) else float("-inf")
    sall = s[s != 0.0]
    return dict(n_active=n,
                cum_12m=round(float((1 + s12).prod() - 1) * 100, 2),
                cum_6m=round(float((1 + s6).prod() - 1) * 100, 2),
                score=round(score, 2) if np.isfinite(score) else None,
                std_active=round(std * 100, 3) if np.isfinite(std) else None,
                worst_day_12m=round(float(s12.min()) * 100, 2) if len(s12) else None,
                cum_full=round(float((1 + sall).prod() - 1) * 100, 1))


def select_cells(table):
    ok = [(k, v) for k, v in table.items()
          if v["stats"]["n_active"] >= MIN_ACTIVE
          and v["stats"]["cum_12m"] > 0 and v["stats"]["cum_6m"] > 0
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


def mc_challenge(daily, mult, p1, p2, rng, n=N_MC, block=5, max_days=250):
    """2段階チャレンジ: P1→P2 / 静的−10% / 日次はEAガードで−4%クリップ。5日ブロックBS。"""
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
        hit = np.where(e - 1 >= p1)[0]
        dq = np.where(e - 1 <= -MAX_DD)[0]
        if len(dq) and (not len(hit) or dq[0] < hit[0]):
            failed[i] = True; continue
        if not len(hit) or hit[0] >= max_days:
            continue
        p1_days[i] = hit[0] + 1
        b2 = e[hit[0]]
        e2 = e[hit[0] + 1:] / b2
        hit2 = np.where(e2 - 1 >= p2)[0]
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
    return dict(list(m.sort_index().items())[-13:])


def deployed_composites():
    """配備中構成の日次近似系列(相関検証用, docs/182 §5)"""
    out = {}
    out["v7_FNInstant"] = sum(base.mon_cell(n) for n in ["EURJPY", "GBPJPY", "USDJPY"]) / 3
    out["EMon_FNInstant"] = sum(base.mon_cell(n) for n in ["NAS100", "US500", "GER40"]) / 3
    out["E5_FNInstant"] = base.e5_composite()
    def mix(parts):
        idx = sorted(set().union(*[set(s.index) for s, _ in parts]))
        c = pd.Series(0.0, index=pd.DatetimeIndex(idx))
        for s, w in parts:
            c = c.add(s.reindex(c.index).fillna(0.0) * w, fill_value=0.0)
        return c
    out["B_Fintokei"] = mix([(base.mon_cell("GBPJPY"), .374), (base.mon_cell("AUDJPY"), .322),
                             (base.v4_cell("USDJPY"), .304)])
    out["C_FTMO50k"] = mix([(base.mon_cell("GBPJPY"), .323), (base.mon_cell("AUDJPY"), .269),
                            (base.v4_cell("NZDUSD"), .207), (base.v4_cell("AUDUSD"), .201)])
    out["D_FTMO50k"] = mix([(base.mon_cell("USDJPY"), .374), (base.v4_cell("NZDUSD"), .287),
                            (base.mon_cell("GBPJPY"), .139), (base.v4_cell("AUDUSD"), .200)])
    return out


def main():
    print("[1/6] データ取得(凍結窓 2016-01-01..2026-07-29・拡張27銘柄)")
    for nm in base.YAHOO:
        try:
            base.fetch(nm)
        except Exception as e:
            print(f"  {nm} ERR {type(e).__name__} {str(e)[:60]}")

    print("[2/6] 相関フィルタ(採用13銘柄と max(|ρ|full,|ρ|12m) <", CORR_TH, ")")
    rets = {nm: daily_ret(nm) for nm in set(ADOPTED + CANDIDATES)}
    corr_report, survivors = {}, []
    for c in CANDIDATES:
        worst, wname = 0.0, ""
        detail = {}
        for a in ADOPTED:
            rf = corr_pair(rets[c], rets[a], base.W_ALL0)
            r12 = corr_pair(rets[c], rets[a], W12_0)
            m = max(abs(rf) if rf is not None else 0.0, abs(r12) if r12 is not None else 0.0)
            detail[a] = dict(full=round(rf, 2) if rf is not None else None,
                             m12=round(r12, 2) if r12 is not None else None)
            if m > worst:
                worst, wname = m, a
        passed = worst < CORR_TH
        corr_report[c] = dict(max_abs=round(worst, 3), vs=wname, passed=passed, detail=detail)
        print(f"  {c:8s} max|ρ|={worst:.2f} vs {wname:7s} {'✅' if passed else '❌'}")
        if passed:
            survivors.append(c)
    cell_syms = [s for s in survivors if s in CRYPTO_CLASS]
    print("  生存(セル適用域=暗号資産クラス):", cell_syms)

    print("[3/6] セル構築(Hold/TSMOM×生存銘柄・銘柄別月初摩擦)")
    cells = {}
    for nm in cell_syms:
        cells[f"Hold_{nm}"] = dict(family="Hold", symbol=nm, s=crypto_cell("Hold", nm))
        cells[f"TSMOM_{nm}"] = dict(family="TSMOM", symbol=nm, s=crypto_cell("TSMOM", nm))

    print("[4/6] 12ヶ月統計・選抜")
    table = {k: dict(family=v["family"], symbol=v["symbol"], stats=stats_for(v["s"]))
             for k, v in cells.items()}
    ranked = sorted([k for k in table if table[k]["stats"]["score"] is not None],
                    key=lambda k: table[k]["stats"]["score"], reverse=True)
    for k in ranked:
        print(f"  {k:16s} {table[k]['stats']}")
    weights = select_cells(table)
    print("  選抜:", weights)

    out = dict(meta=dict(
        purpose="1年特化・低相関トラックE(docs/182)の事前固定スクリーニング",
        seed=SEED, n_mc=N_MC, corr_threshold=CORR_TH, adopted=ADOPTED,
        sel_window=str(W12_0.date()) + "..2026-07-29", confirm="6m>0", expiry=EXPIRY,
        mult_rule="0.8×m*[12m]・上限6.0",
        mc_rule="FN Stellar 8/5 と FTMO 10/5 の両土俵・静的−10%・−4%クリップ・5日ブロックBS",
        cost_note="Hold/TSMOM月初摩擦=max(5bp,銘柄別コスト) — 基準式より保守的(docs/182 §4)",
        caveat="選抜窓で選び選抜窓で測る=構造的に楽観。full_historyが正直な悲観バウンド。",
        inputs=base.sha256s()),
        correlation_filter=corr_report, survivors=cell_syms,
        ranking={k: table[k] for k in ranked}, selected=weights)

    if not weights:
        out["note"] = "フィルタ通過セルなし"
    else:
        print("[5/6] 合成・校正・MC(FN 8/5・FTMO 10/5)")
        idx = sorted(set().union(*[set(cells[k]["s"].index) for k in weights]))
        comp = pd.Series(0.0, index=pd.DatetimeIndex(idx))
        for k, w in weights.items():
            comp = comp.add(cells[k]["s"].reindex(comp.index).fillna(0.0) * w, fill_value=0.0)
        m12 = max_mult(win(comp, W12_0))
        mult = round(min(0.8 * m12, MULT_HARD_CAP), 2)
        sM = comp * mult
        wd12, wdd12 = base.worst_stats(win(sM, W12_0))
        wdF, wddF = base.worst_stats(sM)
        res = dict(mult=mult, m_star_12m=round(m12, 2),
                   worst_day_12m=round(wd12 * 100, 2), intramonth_dd_12m=round(wdd12 * 100, 2),
                   worst_day_full=round(wdF * 100, 2), intramonth_dd_full=round(wddF * 100, 2),
                   monthly_12m=series_pack(win(sM, W12_0)))
        for tag, (p1, p2) in dict(FN_stellar=(0.08, 0.05), FTMO=(0.10, 0.05)).items():
            res[f"mc_{tag}_12m"] = mc_challenge(win(comp, W12_0), mult, p1, p2,
                                                np.random.default_rng(SEED))
            res[f"mc_{tag}_full"] = mc_challenge(comp, mult, p1, p2, np.random.default_rng(SEED))
            print(f"  {tag}: 12m={res[f'mc_{tag}_12m']}")
            print(f"  {tag}: full={res[f'mc_{tag}_full']}")
        out["composite"] = res

        print("[6/6] 配備中構成との相関検証")
        dep = deployed_composites()
        vs = {}
        for name, s in dep.items():
            rho_f = corr_pair(comp, s, base.W_ALL0)
            rho_12 = corr_pair(comp, s, W12_0)
            vs[name] = dict(full=round(rho_f, 3) if rho_f is not None else None,
                            m12=round(rho_12, 3) if rho_12 is not None else None)
            print(f"  vs {name:14s} full={vs[name]['full']} 12m={vs[name]['m12']}")
        out["corr_vs_deployed"] = vs

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    path = os.path.join(HERE, "results", "recentfit_lowcorr_screen.json")
    with open(path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("保存:", path)


if __name__ == "__main__":
    main()
