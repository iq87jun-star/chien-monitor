# -*- coding: utf-8 -*-
"""docs/244 Q170(セル 0・配備判断の MC・2026-11-08 ユーザー「(a) を登録して今行って」):
配備形 Mon4(月曜 4/6/8/10 UTC 建て 24h)と Q165 セッション形(日曜 22 UTC 寄り建て → 月曜 20 UTC)を、各口座で規約(日次限度・最大 DD)内に収まる倍率へ縮尺し、
到達 / 失格 / 出金の MC(account_cards.mc・N=6000・種 44・30 か月)で比較する。Mon レグ(GBPJPY・EURJPY・AUDJPY・USDJPY の mon:SYM)だけを sess:SYM に置換し、他レグ・重みは EA 実レグのまま。
4 通り: 現状 / Q165 置換(同倍率) / 現状の規約揃え / Q165 置換の規約揃え。判定は無し(配備は「切替」)。
使い方: cd research && python3 -W ignore queue/q170_mon4_session_rule_mc.py   出力: results/q170_mon4_session_rule_mc.csv"""
import os, sys, copy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
src = open(os.path.join(ROOT, "forward", "account_cards.py"), encoding="utf-8").read().split("rows_a, rows_m = [], []")[0]
ns = {"__name__": "account_cards_head", "__file__": os.path.join(ROOT, "forward", "account_cards.py")}; exec(compile(src, "account_cards_head", "exec"), ns)
import numpy as np, pandas as pd
from q_session import session
cfg, EA_LEGS, S, ea_book, mc, daily_window, mdd_daily, solve_scale, acc_id, META, ps = (ns[k] for k in ("cfg", "EA_LEGS", "S", "ea_book", "mc", "daily_window", "mdd_daily", "solve_scale", "acc_id", "META", "ps"))
SESS = ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY")
_sess = {}
def sess(sym):
    """Q165 セッション形の暦日系列(損益は決済日 = 月曜に置く・往復 3pip・q_common)"""
    if sym not in _sess:
        r = session(sym, 0, "open"); r.index = pd.DatetimeIndex(r.index).normalize() + pd.Timedelta(days=1); _sess[sym] = ps.on_cal(r.groupby(r.index).sum())
    return _sess[sym]
_real = {}
def sess_real(sym):
    """実スプレッド版: 日曜 22 UTC 寄り足の ASK 始値で買い、月曜 20 UTC 足の BID 始値で売る(data_dukascopy の bid/ask H1・追加コスト無し)。
    研究系列(bid 同士 + 往復 3pip)は週明けのスプレッド拡大(2016〜26 平均 GBPJPY 8.2 / EURJPY 5.4 / AUDJPY 8.3 / USDJPY 4.0 bps・日中の 6〜8 倍)を含まないため、その下限補正。"""
    if sym not in _real:
        b = pd.read_csv(f"data_dukascopy/{sym}_hour.csv.gz"); a = pd.read_csv(f"data_dukascopy/{sym}_hour_ask.csv.gz"); tc = [c for c in b.columns if "time" in c.lower() or "date" in c.lower()][0]
        for d in (b, a): d[tc] = pd.to_datetime(d[tc], utc=True).dt.tz_localize(None)
        m = b.merge(a, on=tc, suffixes=("_b", "_a")).set_index(tc).sort_index(); ob, oa = m["open_b"], m["open_a"]
        mons = oa.index[(oa.index.dayofweek == 0) & (oa.index.hour == 20)]; out = {}
        for d in mons:
            w = oa[(oa.index >= d.normalize() - pd.Timedelta(hours=2)) & (oa.index < d.normalize() + pd.Timedelta(hours=2))]   # 日曜 22 UTC〜月曜 01 UTC の最初の足 = 週明け寄り
            if len(w) == 0: continue
            out[d.normalize()] = float(ob[d] / w.iloc[0] - 1)
        r = pd.Series(out); _real[sym] = ps.on_cal(r)
    return _real[sym]
S_orig = S
def S2(key):
    fam, _, sym = key.partition(":")
    return sess(sym) if fam == "sess" else sess_real(sym) if fam == "sreal" else S_orig(key)
ns["S"] = S2   # ea_book は ns 内の S を参照する
def swap(lg, fam="sess"): return {(fam + ":" + k.split(":")[1] if k.startswith("mon:") and k.split(":")[1] in SESS else k): w for k, w in lg.items()}
def rule_scale(lg, sw, a):
    rd = daily_window(ea_book(lg, sw)); s_mdd = solve_scale(rd, a["mdd"]); wd = float(rd.min()); s_dll = a["dll"] / abs(wd) if wd < 0 else 20.0
    sc = min(s_mdd, s_dll); return sc, ("日次限度" if s_dll < s_mdd else "最大 DD"), rd
def hist(rd):
    m = (1 + rd).resample("ME").prod() - 1; eq = (1 + m).cumprod()
    return dict(mean_m=float(m.mean()), worst_m=float(m.min()), mdd=float((eq / eq.cummax() - 1).min()), worst_d=float(rd.min()), sharpe=float(m.mean() / m.std() * np.sqrt(12)))
# 系列の比較(等ウェイト 4 通貨・IS/OOS)
from q_common import IS0, IS1, OOS0, END, PRE0
def wstats(x, lo, hi):
    y = x[(x.index >= lo) & (x.index <= hi)]; y = y[y != 0]; m = (1 + y).resample("ME").prod() - 1
    return dict(sharpe=round(float(y.mean() / y.std() * np.sqrt(52)), 2), bps=round(float(y.mean()) * 1e4, 1), worst_m=round(float(m.min()) * 100, 2))
cmp_rows = []
for nm, f in (("配備形 Mon4", lambda s_: S_orig("mon:" + s_)), ("Q165(bid 同士 + 3pip)", sess), ("Q165 実スプレッド(ask 建て・bid 決済)", sess_real)):
    x = sum(f(s_) * 0.25 for s_ in SESS)
    cmp_rows.append(dict(系列=nm, **{f"前窓_{k}": v for k, v in wstats(x, PRE0, IS0).items()}, **{f"IS_{k}": v for k, v in wstats(x, IS0, IS1).items()}, **{f"OOS_{k}": v for k, v in wstats(x, OOS0, END).items()}))
C = pd.DataFrame(cmp_rows); print(C.to_string(index=False)); C.to_csv("results/q170_series_compare.csv", index=False)
j = sess("GBPJPY").index; print("研究系列と実スプレッド系列の相関(GBPJPY・非ゼロ週):", round(float(pd.concat([sess("GBPJPY"), sess_real("GBPJPY")], axis=1).replace(0, np.nan).dropna().corr().iloc[0, 1]), 3), flush=True)
rows = []
for a in cfg["accounts"]:
    if not a.get("active", True): continue
    aid = acc_id(a["name"]); EL = EA_LEGS.get(aid)
    if not EL or not any(k.startswith("mon:") and k.split(":")[1] in SESS for k in EL["eval"]): print("skip", aid); continue
    fn = a.get("funded_now", False); sw = a.get("swap_xau_bps_m", 0.0); firm, label, ea = META[aid]
    for form, lgs in (("配備形 Mon4", EL), ("Q165 置換", {"eval": swap(EL["eval"]), "funded": swap(EL["funded"])}), ("Q165 実スプレッド", {"eval": swap(EL["eval"], "sreal"), "funded": swap(EL["funded"], "sreal")})):
        cur = lgs["funded"] if fn else lgs["eval"]
        sc, binding, rd = rule_scale(cur, sw, a)
        for mode, s_ in (("同倍率", 1.0), ("規約揃え", sc)):
            ar = copy.deepcopy(a); ar["eval"] = {k: w * s_ for k, w in lgs["eval"].items()}; ar["funded"] = {k: w * s_ for k, w in lgs["funded"].items()}
            r = mc(ar); h = hist(rd * s_)
            rows.append(dict(account=aid, name=a["name"], firm=firm, stage="資金化済" if fn else "評価中", rule=a.get("rule", "static"), dll=a["dll"], mdd=a["mdd"], form=form, mode=mode, scale=round(s_, 3), binding=binding if mode == "規約揃え" else "",
                             p_reach=r["p_reach"], p_fail=r["p_fail"], p_pay=r["p_pay"], t_med_m=r["t_med_m"], a_med=r["a_med"], c12_med=r["c12_med"], c30_mean=r["c30_mean"], c30_p0=r["c30_p0"],
                             mean_m=h["mean_m"], worst_m=h["worst_m"], mdd_d=h["mdd"], worst_d=h["worst_d"], sharpe_m=h["sharpe"], legs=" + ".join(f"{k} ×{w*s_:.3g}" for k, w in cur.items())))
            print(aid, form, mode, f"×{s_:.2f}", {k: round(v, 3) for k, v in r.items() if k in ("p_reach", "p_fail", "p_pay", "c30_mean", "c12_med")}, flush=True)
T = pd.DataFrame(rows); os.makedirs("results", exist_ok=True); T.to_csv("results/q170_mon4_session_rule_mc.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
print(T[["account", "stage", "form", "mode", "scale", "binding", "p_reach", "p_fail", "p_pay", "t_med_m", "a_med", "c12_med", "c30_mean", "mean_m", "worst_m", "mdd_d", "worst_d", "sharpe_m"]].round(3).to_string(index=False))
