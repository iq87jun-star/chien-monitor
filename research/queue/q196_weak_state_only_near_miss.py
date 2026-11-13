# -*- coding: utf-8 -*-
"""docs/244 Q196(改良系・9 セル・2026-11-13 登録「登録して実行」): 惜しくも外した銘柄 × 弱い状態(終値 < SMA200)のときだけ建てる。
対象: 月曜の円クロス NZDJPY / CADJPY / CHFJPY(mon_cell_h1)、月曜の指数 JP225 / UK100 / US30(q114.shot 13 UTC 24h)、木曜の金(mon_cell_dow)、月曜の ETHUSD / BTCUSD(base.mon_cell)。
判定: 前窓・IS・OOS の 3 窓すべてで、常に建てる基準比 Sharpe 改善 かつ 最悪月が悪化しない。累積 1/2 規則。前窓 < 24 か月は 2 窓・参考。
参照: 配備中の指数 NAS100 / US500 / GER40、SMA20・前週下落の only 型、弱い / それ以外の平均。口座モデルの診断は成立した円クロス・指数のみ。
使い方: cd research && python3 -W ignore queue/q196_weak_state_only_near_miss.py <累積>   出力: results/q196_weak_state_only_near_miss.csv・_levels.csv・_means.csv・_accounts.csv"""
import sys, os
from q_common import *
from q114_mon_index_intraday import shot, stats
from q194_mon_own_technical_state_gate import states as states_h1, rsi
import deployed_book as db
import recentfit_portfolio_compare as rpc
PRE1 = IS0 - pd.Timedelta(hours=1)
def states_daily(sym):
    c = base.load_daily(sym)["close"].astype(float); s20 = c.rolling(20).mean(); return pd.DataFrame({"rsi": rsi(c), "sma200": c / c.rolling(200).mean() - 1, "sma20": c / s20 - 1, "z20": (c - s20) / c.rolling(20).std(), "wk": c / c.shift(5) - 1})
def series_h1(sym):
    h = load(sym); m = db.mon_cell_h1(sym); return m[(m.index >= PRE0) & (m.index <= h.index.max())]
CELLS = [("月曜の円クロス", s, lambda s=s: series_h1(s), states_h1, True) for s in ("NZDJPY", "CADJPY", "CHFJPY")] \
      + [("月曜の指数", s, lambda s=s: shot(s, 13, None), states_h1, True) for s in ("JP225", "UK100", "US30")] \
      + [("木曜の金", "XAUUSD", lambda: rpc.mon_cell_dow("XAUUSD", 3), states_daily, True)] \
      + [("月曜の暗号資産", s, lambda s=s: base.mon_cell(s), states_daily, True) for s in ("ETHUSD", "BTCUSD")] \
      + [("月曜の指数(配備中・参照)", s, lambda s=s: shot(s, 13, None), states_h1, False) for s in ("NAS100", "US500", "GER40")]
RULES = [("終値 < SMA200", lambda S: S.sma200 < 0), ("終値 < SMA20", lambda S: S.sma20 < 0), ("前週下落", lambda S: S.wk < 0)]
WIN = (("pre", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
_STC = {}
def weak_flags(sym, sfn, dates, wfn):
    """dates(建て日)より前の最後の日足で条件に当たるか。指標が未計算(NaN)の日は None。"""
    if sym not in _STC: _STC[sym] = sfn(sym).shift(1)
    S = _STC[sym].reindex(pd.DatetimeIndex(dates), method="ffill"); f = wfn(S); valid = S.sma200.notna().values
    return f.fillna(False).values, valid
def weak_only_series(sym):
    """紙上候補 MonWeakOnlySMA200(docs/435): 建て日より前の最後の日足で 終値 < SMA200 のときだけ建てる系列(指標が未計算の期間は除く)。sym は CELLS のセル銘柄。"""
    fam, _, fn, sfn, _ = [c for c in CELLS if c[1] == sym][0]; b0 = fn(); b0 = b0[b0.index >= PRE0]; hit, valid = weak_flags(sym, sfn, b0.index, RULES[0][1]); b = b0[valid]; return b * np.where(hit[valid], 1.0, 0.0)
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q196", cum, 9, "results/q196_weak_state_only_near_miss.csv"); rows = []; means = []; passed = []
    for fam, sym, fn, sfn, is_cell in CELLS:
        b0 = fn(); b0 = b0[b0.index >= PRE0]
        for rn, wfn in RULES:
            hit, valid = weak_flags(sym, sfn, b0.index, wfn); b = b0[valid]; h = hit[valid]; v = b * np.where(h, 1.0, 0.0)       # 指標が計算できる期間だけで基準と比べる
            bs = {k: stats(b, a, e) for k, a, e in WIN}; vs = {k: stats(v, a, e) for k, a, e in WIN}
            nm = {k: int(b[(b.index >= a) & (b.index <= e)].groupby(pd.PeriodIndex(b[(b.index >= a) & (b.index <= e)].index, freq="M")).ngroups) for k, a, e in WIN}
            use = [k for k in ("pre", "IS", "OOS") if not (k == "pre" and nm["pre"] < 24)]
            ok = {k: bool(vs[k][0] > bs[k][0] and vs[k][1] >= bs[k][1]) for k in use}
            cum_ok = bool(vs["IS"][2] >= 0.5 * bs["IS"][2] and vs["OOS"][2] >= 0.5 * bs["OOS"][2])
            main = (rn == "終値 < SMA200")
            if main and is_cell: R.add("惜しくも外した銘柄 × 弱い状態のみ(改良系)", sym, f"{fam}: 終値 < SMA200 のときだけ建てる", v)
            ver = ("成立" if all(ok.values()) and cum_ok else ("成立だが累積 1/2 未満" if all(ok.values()) else "不成立")) + ("" if "pre" in use else "(前窓なし・参考)")
            rows.append(dict(family=fam, symbol=sym, rule=rn, cell=("セル" if (main and is_cell) else "参照"), pre_months=nm["pre"], base_pre=bs["pre"], var_pre=vs["pre"], ok_pre=ok.get("pre"), base_IS=bs["IS"], var_IS=vs["IS"], ok_IS=ok["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], ok_OOS=ok["OOS"], cum_rule_ok=cum_ok, verdict=ver))
            if main and is_cell and ver == "成立": passed.append((fam, sym))
            for k, a, e in WIN:
                x = b[(b.index >= a) & (b.index <= e)]; hh = h[(b.index >= a) & (b.index <= e)]
                means.append(dict(family=fam, symbol=sym, rule=rn, window=k, n=len(x), weak=int(hh.sum()), mean_weak_bps=(round(float(x[hh].mean()) * 1e4, 1) if hh.any() else np.nan), mean_other_bps=(round(float(x[~hh].mean()) * 1e4, 1) if (~hh).any() else np.nan)))
    R.finish(); D = pd.DataFrame(rows); D.to_csv("results/q196_weak_state_only_near_miss_levels.csv", index=False); MN = pd.DataFrame(means); MN.to_csv("results/q196_weak_state_only_near_miss_means.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)
    print("\n== Q196 改良判定(セル: 終値 < SMA200 のみ建てる・(Sharpe, 最悪月%, 累積%)) =="); print(D[D.cell == "セル"].drop(columns=["rule", "cell"]).to_string(index=False)); print("\n成立:", len(passed), "/ 9", passed)
    print("\n== 参照(判定なし) =="); print(D[D.cell == "参照"][["family", "symbol", "rule", "base_pre", "var_pre", "base_IS", "var_IS", "base_OOS", "var_OOS", "verdict"]].to_string(index=False))
    print("\n== 弱い / それ以外の建ての平均 bps(終値 < SMA200) =="); print(MN[MN.rule == "終値 < SMA200"].drop(columns=["rule"]).to_string(index=False))
    # ---- 口座モデルの診断(成立した円クロス・指数のみ) ----
    todo = [(f, s) for f, s in passed if f in ("月曜の円クロス", "月曜の指数")]
    if not todo: print("\n口座モデル: 対象なし"); sys.exit(0)
    HERE = os.path.dirname(os.path.abspath(__file__)); src = open(os.path.join(HERE, "q188_skew_gate_guard_model.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
    ns = {"__name__": "q188_head", "__file__": os.path.join(HERE, "q188_skew_gate_guard_model.py")}; exec(compile(src, "q188_head", "exec"), ns)
    cfg, table, us_dst, G, K, P0, P1, run_guard, evaluate, account_items, verdict, skew_gate_dates = (ns[k] for k in ("cfg", "table", "us_dst", "G", "K", "P0", "P1", "run_guard", "evaluate", "account_items", "verdict", "skew_gate_dates"))
    PRK = skew_gate_dates(); SKEW_ON = {"531343523", "531466484", "14074882"}; TARGET = {"531407058", "6104739", "531466484"}
    def paths_fac(items, cap, fac):
        """Q188 の paths と同じ。fac = {(sym, idx): {date: 倍率}}(無ければ 1.0)。"""
        parts = []
        for s, idxf, w in items:
            Mt, res = table(s, idxf); Rk = res[K]; p = Mt.copy(); p["w"] = w / p.nshots
            if (s, idxf) in fac: p["w"] = p.w * p.date.map(lambda d: fac[(s, idxf)].get(d, 1.0)).values
            p["risk_w"] = p.w * Rk["risk"]; p["stop"] = Rk["stop"]; p["i"] = np.arange(len(p)); p["key"] = f"{s}|{idxf}"; parts.append(p)
        S = pd.concat(parts); S = S[(S.date >= P0) & (S.date <= P1)].sort_values(["date", "t"]).reset_index(drop=True); f = np.ones(len(S))
        if cap:
            C, V = cap
            for d, g in S.groupby("date"):
                used = []
                for i in g.index:
                    r = S.risk_w[i]
                    if r <= 0: f[i] = 0.0; continue
                    room = C - sum(x for stp, x in used if V == "B" or stp > S.off[i]); fi = 1.0 if r <= room else (room / r if room >= 0.1 * r else 0.0); f[i] = fi; used.append((S.stop[i], r * fi))
        S["wf"] = S.w * f; out = []
        for d, g in S.groupby("date"):
            gb = (21 if us_dst(d) else 22) - 4; tot = {"lo": np.zeros(G), "cl": np.zeros(G)}; met = {"lo": np.zeros(G), "cl": np.zeros(G)}
            for key, gg in g.groupby("key"):
                s, idxs = key.split("|"); Rk = table(s, idxs == "True")[1][K]
                for i, wf, off, stp in zip(gg.i.values, gg.wf.values, gg.off.values, gg.stop.values):
                    if wf == 0: continue
                    close = int(min(stp, off + 24))
                    for tag, arr in (("lo", Rk["worst"][i]), ("cl", Rk["mark"][i])):
                        a = arr * wf; tot[tag] += a; bb = a.copy()
                        if close < gb: bb[gb:] = 0.0
                        met[tag] += bb
            out.append(dict(d=d, gb=gb, tot=tot, met=met, fin=float(tot["cl"][-1])))
        return out
    arows = []
    for a in cfg["accounts"]:
        aid, items, cap, g = account_items(a)
        if aid not in TARGET: continue
        fac0 = {}
        if aid in SKEW_ON:
            for s, idxf, w in items:
                if idxf: continue
                dts = [pd.Timestamp(d) for d in table(s, False)[0].date.unique()]; pr = PRK.reindex(pd.DatetimeIndex(dts) - pd.Timedelta(days=3), method="ffill").values; fac0[(s, False)] = {d: 0.0 for d, p in zip(dts, pr) if p == p and p > 0.8}
        ex = dict(guard_pct=round(g * 100, 1))
        arows += evaluate(a, aid, run_guard(paths_fac(items, cap, fac0), g), "現行", ex)
        def add_leg(fam, sym):
            idxf = (fam == "月曜の指数"); w = 0.5 if idxf else 1.0; dts = [pd.Timestamp(d) for d in table(sym, idxf)[0].date.unique()]; hit, valid = weak_flags(sym, states_h1, dts, RULES[0][1])
            sk = fac0.get(("GBPJPY", False), {}) if (aid in SKEW_ON and not idxf) else {}
            return (sym, idxf, w), {d: (1.0 if (hh and vv) else 0.0) * sk.get(d, 1.0) for d, hh, vv in zip(dts, hit, valid)}
        for fam, sym in todo:
            it, fm = add_leg(fam, sym)
            if any(s == sym and i == it[1] for s, i, _ in items): continue
            fac = dict(fac0); fac[(sym, it[1])] = fm; arows += evaluate(a, aid, run_guard(paths_fac(items + [it], cap, fac), g), f"+ {sym} 弱い状態のみ ×{it[2]}", ex)
        if len(todo) > 1:
            fac = dict(fac0); its = list(items)
            for fam, sym in todo:
                it, fm = add_leg(fam, sym)
                if any(s == sym and i == it[1] for s, i, _ in items): continue
                fac[(sym, it[1])] = fm; its.append(it)
            arows += evaluate(a, aid, run_guard(paths_fac(its, cap, fac), g), "+ 成立した全銘柄", ex)
    A = pd.DataFrame(arows); A.to_csv("results/q196_weak_state_only_near_miss_accounts.csv", index=False)
    print("\n== 口座モデル =="); print(A[["acct", "scen", "variant", "mean_bps_lo", "hits_lo", "mean_bps_cl", "hits_cl", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo"]].to_string(index=False))
    for (acct, sc), g_ in A[A.scen != "—"].groupby(["acct", "scen"], sort=False):
        cur, best = verdict(g_, "現行"); print(acct, sc, "→", "変更候補: " + best.variant if best is not None else "現行維持")
