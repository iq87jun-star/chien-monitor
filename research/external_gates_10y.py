# -*- coding: utf-8 -*-
"""
external_gates_10y.py — 【実験】価格以外の外部状態による見送りゲート(docs/203の実装)。

N=4候補(VIX_TERM / VIX_HI / COT_JPY_SHORT / FOMC)を、MON_JPY / V4_FX / BOOK に非対称(見送りのみ)で適用し、
素版・プラセボ100本と比較する。Bonferroni α=0.0125。IS=2016-2021 / OOS=2022-2026。
倍率は素版で校正した値を固定(ゲートで静かになった分の倍率上乗せを混入させない)。
出力: results/external_gates_10y.json → docs/203 §9
"""
import os, sys, json
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recentfit_screen as base
base.DATA = os.path.join(HERE, "data_202609")
import deployed_book as db
import ext_data as ext

SEED = 7
N_MC_MAIN, N_MC_PLACEBO, N_PLACEBO, N_PERM = 10000, 2000, 100, 1000
ALPHA = 0.05 / 4
IS = (pd.Timestamp("2016-01-01"), pd.Timestamp("2021-12-31"))
OOS = (pd.Timestamp("2022-01-01"), pd.Timestamp("2026-08-31"))
FULL = (IS[0], OOS[1])
MON_JPY_SYMS = ["GBPJPY", "AUDJPY", "USDJPY", "EURJPY", "NZDJPY", "CADJPY", "CHFJPY"]
ENTRY_FAMILIES = {"Mon", "v4", "v4nfx", "MonThuS", "RSI2a", "RSI2b"}      # 新規建て型(Holdは除外)
GATES = ["VIX_TERM", "VIX_HI", "COT_JPY_SHORT", "FOMC"]


# ---------------- 外部状態 → 日付マスク(前日までに既知) ----------------
def build_states():
    vix, vix3m = ext.vix_series()
    cal = pd.date_range(FULL[0] - pd.Timedelta(days=10), FULL[1], freq="D")
    v = vix.reindex(cal).ffill(); v3 = vix3m.reindex(cal).ffill()
    # G1: 前日終値で VIX>VIX3M。VIX3M欠損(2026-07-17以降)は fail-open
    v3_known = vix3m.reindex(cal)                       # 欠損はNaNのまま
    last_v3 = vix3m.index[-1]
    g1 = ((v > v3) & (cal <= last_v3)).shift(1).fillna(False)
    # G2: 前日終値VIX > 直近252日80分位(前日まで)
    q80 = vix.rolling(252).quantile(0.80).reindex(cal).ffill()
    g2 = (v > q80).shift(1).fillna(False)
    # G3: 直近公表済みCOT JPY net%OI ≤ 直近52週20分位
    cot = ext.cot_lev_net()["JPY"].copy()
    cot["q20"] = cot["net_pct_oi"].rolling(52).quantile(0.20)
    cot["crowded"] = cot["net_pct_oi"] <= cot["q20"]
    rel = cot.set_index("release")["crowded"]
    rel = rel[~rel.index.duplicated(keep="last")].sort_index()
    g3 = rel.reindex(cal, method="ffill").shift(1).fillna(False).astype(bool)   # 公表日の翌日から既知
    # G4: FOMC決定日と翌営業日
    f = pd.DatetimeIndex([pd.Timestamp(d) for d in ext.fomc_dates()])
    f_next = f + pd.offsets.BDay(1)
    g4 = pd.Series(cal.isin(f) | cal.isin(f_next), index=cal)
    return {"VIX_TERM": g1.astype(bool), "VIX_HI": g2.astype(bool), "COT_JPY_SHORT": g3, "FOMC": g4}


def apply_gate(s, mask, symbol, gate):
    """新規建て型セルの、見送り日のリターンをゼロ化。COTはJPY銘柄のみ。"""
    if gate == "COT_JPY_SHORT" and not symbol.endswith("JPY"):
        return s
    m = mask.reindex(s.index).fillna(False).astype(bool)
    out = s.copy(); out[m.values] = 0.0
    return out


def w(s, a, b): return s[(s.index >= a) & (s.index <= b)]


def build_targets(cells_cache):
    """MON_JPY / V4_FX / BOOK を「レッグ→(family,symbol,weight,series)」の形で返す(ゲートを個別適用するため)"""
    T = {}
    T["MON_JPY"] = [("Mon", s, 1 / 7, cells_cache(("Mon", s))) for s in MON_JPY_SYMS]
    T["V4_FX"] = [("v4", p, 1 / 9, cells_cache(("v4", p))) for p in base.V4_PAIRS]
    legs = []
    tot = sum(v["capital_usd"] * v["mult"] for v in db.BOOK.values())
    for k, v in db.BOOK.items():
        cw = v["capital_usd"] * v["mult"] / tot
        for fam, sym, wt in v["legs"]:
            legs.append((fam, sym, cw * wt, cells_cache((fam, sym))))
    T["BOOK"] = legs
    return T


def composite(legs, gate=None, mask=None):
    parts = []
    for fam, sym, wt, s in legs:
        if gate and fam in ENTRY_FAMILIES:
            s = apply_gate(s, mask, sym, gate)
        parts.append((s, wt))
    idx = sorted(set().union(*[set(s.index) for s, _ in parts]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s, wt in parts:
        out = out.add(s.reindex(out.index).fillna(0.0) * wt, fill_value=0.0)
    return w(out, *FULL)


def stats(s):
    act = s[s != 0.0]; yrs = max((s.index[-1] - s.index[0]).days / 365.25, 1e-9)
    eq = (1 + s).cumprod()
    return dict(ann=round(float(eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2),
                maxdd=round(float(((eq - eq.cummax()) / eq.cummax()).min()) * 100, 2),
                worst=round(float(s.min()) * 100, 2), n_active=int(len(act)))


def mstar(s):
    best = 0.05
    for m in np.arange(0.05, 12.01, 0.05):
        wd, wdd = base.worst_stats(s * m)
        if wd >= -0.04 and wdd >= -0.08: best = m
        else: break
    return min(0.8 * best, 6.0)


def fail_rate(s, mult, n):
    base.P1_TARGET = 0.10
    return base.mc_challenge(s, mult, np.random.default_rng(SEED), n=n)["fail"]


def main():
    base.W_ALL1 = pd.Timestamp("2026-08-31")
    print("[1/4] セル・外部状態")
    _cache = {}
    def cells_cache(key):
        if key not in _cache:
            fam, sym = key
            _cache[key] = db.leg_series(fam, sym)
        return _cache[key]
    T = build_targets(cells_cache)
    base.verify_window([s for legs in T.values() for *_, s in legs])
    masks = build_states()
    cal_full = pd.date_range(*FULL, freq="B")
    print("  見送り率(営業日ベース):", {g: round(float(m.reindex(cal_full).fillna(False).mean()) * 100, 1) for g, m in masks.items()})

    out = {"meta": dict(purpose="外部状態ゲート docs/203", seed=SEED, gates=GATES, alpha=ALPHA,
                        IS=[str(IS[0].date()), str(IS[1].date())], OOS=[str(OOS[0].date()), str(OOS[1].date())],
                        n_mc_main=N_MC_MAIN, n_mc_placebo=N_MC_PLACEBO, n_placebo=N_PLACEBO, n_perm=N_PERM,
                        skip_rate_bday={g: round(float(m.reindex(cal_full).fillna(False).mean()) * 100, 2) for g, m in masks.items()}),
           "targets": {}}
    rng = np.random.default_rng(SEED)

    for tname, legs in T.items():
        print(f"[2/4] {tname}")
        raw = composite(legs)
        mult = round(mstar(raw), 2)
        rec = dict(mult=mult, raw={})
        for wn, win in (("IS", IS), ("OOS", OOS), ("FULL", FULL)):
            rs = w(raw, *win); rec["raw"][wn] = dict(**stats(rs), fail=fail_rate(rs, mult, N_MC_MAIN))
        print(f"  素版 mult={mult} " + " ".join(f"{k}:失格{v['fail']}%/DD{v['maxdd']}%" for k, v in rec["raw"].items()))
        rec["gates"] = {}
        active_days = raw.index[raw != 0.0]
        for g in GATES:
            gs = composite(legs, g, masks[g])
            gr = {}
            for wn, win in (("IS", IS), ("OOS", OOS), ("FULL", FULL)):
                x = w(gs, *win); gr[wn] = dict(**stats(x), fail=fail_rate(x, mult, N_MC_MAIN))
            # 見送られた活動日(ゲートで値が変わった日)
            changed = raw.index[(raw != gs.reindex(raw.index).fillna(0.0)) & (raw != 0.0)]
            n_skip = len(changed)
            skip_share = round(n_skip / max(len(active_days), 1) * 100, 2)
            # 順列検定: 見送った日の素版平均リターン vs 同数ランダム日
            obs = float(raw.loc[changed].mean()) if n_skip > 0 else 0.0
            act_vals = raw.loc[active_days].values
            perm = np.array([rng.choice(act_vals, n_skip, replace=False).mean() for _ in range(N_PERM)]) if n_skip > 0 else np.zeros(1)
            perm_p = float((perm <= obs).mean()) if n_skip > 0 else 1.0
            # プラセボ: 同数のランダム活動日を見送り
            plc = {"IS": [], "OOS": []}
            for i in range(N_PLACEBO):
                drop = rng.choice(len(active_days), n_skip, replace=False) if n_skip > 0 else []
                ps = raw.copy(); ps.iloc[[raw.index.get_loc(d) for d in active_days[drop]]] = 0.0
                for wn, win in (("IS", IS), ("OOS", OOS)):
                    plc[wn].append(fail_rate(w(ps, *win), mult, N_MC_PLACEBO))
            plc_pct = {wn: round(float((np.array(plc[wn]) <= gr[wn]["fail"]).mean()) * 100, 1) for wn in plc}
            plc_sum = {wn: dict(p05=round(float(np.percentile(plc[wn], 5)), 1), med=round(float(np.median(plc[wn])), 1),
                                p95=round(float(np.percentile(plc[wn], 95)), 1)) for wn in plc}
            rec["gates"][g] = dict(n_skipped_active=n_skip, skip_share_active_pct=skip_share,
                                   skipped_mean_ret_pct=round(obs * 100, 4), perm_p=round(perm_p, 4),
                                   windows=gr, placebo_pct=plc_pct, placebo_dist=plc_sum)
            print(f"  {g:14s} 見送り{skip_share:5.1f}% perm_p={perm_p:.4f} "
                  + " ".join(f"{k}:失格{v['fail']}%(plc{plc_pct.get(k,'-')}%)DD{v['maxdd']}%" for k, v in gr.items()))
        out["targets"][tname] = rec

    print("[3/4] 判定(docs/203 §6・BOOK)")
    B = out["targets"]["BOOK"]; verdict = {}
    for g in GATES:
        r = B["gates"][g]; raw = B["raw"]
        c1 = r["perm_p"] < ALPHA
        c2 = r["placebo_pct"]["OOS"] <= 5.0
        c3 = all(r["windows"][wn]["maxdd"] > raw[wn]["maxdd"] and r["windows"][wn]["fail"] < raw[wn]["fail"] for wn in ("IS", "OOS"))
        n = sum([c1, c2, c3])
        verdict[g] = dict(perm=c1, placebo_oos=c2, is_oos_both=c3,
                          result="ADOPT" if n == 3 else ("LEAD" if n >= 1 else "REJECT"),
                          d_ann_full=round(r["windows"]["FULL"]["ann"] - raw["FULL"]["ann"], 2),
                          d_fail_full=round(r["windows"]["FULL"]["fail"] - raw["FULL"]["fail"], 1))
        print(f"  {g:14s} {verdict[g]}")
    out["verdict"] = verdict
    print("[4/4] 保存")
    fp = os.path.join(HERE, "results", "external_gates_10y.json")
    with open(fp, "w") as f: json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("saved:", fp)


if __name__ == "__main__":
    main()
