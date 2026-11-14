# -*- coding: utf-8 -*-
"""docs/244 Q195(改良系・6 セル・2026-11-13 登録「登録して実行」): 月曜の円クロス — 弱い状態の通貨に数量を寄せる。
弱い状態 W ∈ {終値 < SMA20, 終値 < SMA200, 前週下落}(金曜終値の日足・Q194 と同じ定義)× 数量 T ∈ {A: 1.5 / 0.75, B: 1.5 / 0.5}。配備形 Mon4・通貨ごと。
判定(事後的な規則のため厳しく): 前窓 2016-01〜2021-09・IS・OOS の 3 窓すべてで Sharpe 改善 かつ 最悪月が悪化しない。
診断: (1) 前窓での『弱い − それ以外』の平均差(プール・Welch 片側 p・通貨別)、(2) Q188 の口座モデル(SL・全決済ガード・自動決済)で全口座の現行と比較。
使い方: cd research && python3 -W ignore queue/q195_mon_weak_state_tilt.py <累積>   出力: results/q195_mon_weak_state_tilt.csv・_levels.csv・_prewindow.csv・_accounts.csv"""
import sys, os
from q_common import *
from q114_mon_index_intraday import stats
from q194_mon_own_technical_state_gate import PAIRS, states
import deployed_book as db
from scipy import stats as sps
W = [("終値 < SMA20", lambda S: S.sma20 < 0), ("終値 < SMA200", lambda S: S.sma200 < 0), ("前週下落", lambda S: S.wk < 0)]
T = [("A: 1.5 / 0.75", 1.5, 0.75), ("B: 1.5 / 0.5", 1.5, 0.5)]
PRE1 = IS0 - pd.Timedelta(hours=1)
_ST = {}
def st_at(sym, dates):
    """dates(月曜)より前の最後の日足の指標。"""
    if sym not in _ST: _ST[sym] = states(sym).shift(1)
    return _ST[sym].reindex(pd.DatetimeIndex(dates), method="ffill")
def factor_map(sym, dates, wfn, hi, lo):
    S = st_at(sym, dates); w = wfn(S); ok = S.notna().all(axis=1) if False else ~wfn(S).isna()
    return {d: (hi if bool(x) else lo) for d, x in zip(dates, wfn(S).fillna(False).values)}
def mon4_weak_tilt(state="終値 < SMA200", hi=1.5, lo=0.75):
    """紙上候補 MonWeakSMA200A / B(docs/434): 配備形 Mon4(各 0.25・EA 実時刻)で、金曜終値が弱い状態の通貨を hi 倍・それ以外を lo 倍にした系列。"""
    wfn = dict(W)[state]; out = None
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); x = m[(m.index >= PRE0) & (m.index <= h.index.max())]; hit = wfn(st_at(s, x.index)).fillna(False).values; x = x * np.where(hit, hi, lo) * 0.25
        out = x if out is None else out.add(x, fill_value=0.0)
    return out
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q195", cum, 6, "results/q195_mon_weak_state_tilt.csv")
    M = {}
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); M[s] = m[(m.index >= PRE0) & (m.index <= h.index.max())]
    idx = pd.DatetimeIndex(sorted(set().union(*[set(M[s].index) for s in PAIRS])))
    def comp(wfn=None, hi=1.0, lo=1.0):
        out = pd.Series(0.0, index=idx)
        for s in PAIRS:
            x = M[s].copy()
            if wfn is not None: hit = wfn(st_at(s, x.index)).fillna(False).values; x = x * np.where(hit, hi, lo)
            out = out.add(x * 0.25, fill_value=0.0)
        return out
    B = comp(); WIN = (("pre", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); bs = {k: stats(B, a, b) for k, a, b in WIN}; rows = []; pw = []
    for wn, wfn in W:
        # 確認の診断: 前窓で 弱い − それ以外
        a_all, b_all = [], []
        for s in PAIRS:
            for k, a, b in WIN:
                x = M[s][(M[s].index >= a) & (M[s].index <= b)]; hit = wfn(st_at(s, x.index)).fillna(False).values
                pw.append(dict(state=wn, pair=s, window=k, n=len(x), weak=int(hit.sum()), mean_weak_bps=round(float(x[hit].mean()) * 1e4, 1), mean_other_bps=round(float(x[~hit].mean()) * 1e4, 1)))
                if k == "pre": a_all += list(x[hit].values); b_all += list(x[~hit].values)
        tt = sps.ttest_ind(a_all, b_all, equal_var=False); p1 = float(tt.pvalue / 2 if tt.statistic > 0 else 1 - tt.pvalue / 2)
        pw.append(dict(state=wn, pair="プール(4 通貨)", window="pre", n=len(a_all) + len(b_all), weak=len(a_all), mean_weak_bps=round(float(np.mean(a_all)) * 1e4, 1), mean_other_bps=round(float(np.mean(b_all)) * 1e4, 1), welch_p_one_sided=round(p1, 4)))
        for tn, hi, lo in T:
            v = comp(wfn, hi, lo); R.add("Mon4 × 弱い状態に寄せる(改良系)", "Mon4", f"{wn} の通貨 {hi} 倍 / それ以外 {lo} 倍", v); vs = {k: stats(v, a, b) for k, a, b in WIN}
            ok = {k: bool(vs[k][0] > bs[k][0] and vs[k][1] >= bs[k][1]) for k in bs}
            rows.append(dict(state=wn, tilt=tn, base_pre=bs["pre"], var_pre=vs["pre"], ok_pre=ok["pre"], base_IS=bs["IS"], var_IS=vs["IS"], ok_IS=ok["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], ok_OOS=ok["OOS"], verdict=("成立" if all(ok.values()) else "不成立")))
    R.finish(); D = pd.DataFrame(rows); D.to_csv("results/q195_mon_weak_state_tilt_levels.csv", index=False); PW = pd.DataFrame(pw); PW.to_csv("results/q195_mon_weak_state_tilt_prewindow.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
    print("\n== Q195 改良判定((Sharpe, 最悪月%, 累積%)・3 窓) ==\n" + D.to_string(index=False)); print("\n成立:", int((D.verdict == "成立").sum()), "/ 6")
    print("\n== 弱い状態 / それ以外の建ての平均 bps ==\n" + PW.to_string(index=False))
    # ---- 口座モデルの診断(セル 0): Q188 の経路モデルに通貨別の倍率を掛ける ----
    HERE = os.path.dirname(os.path.abspath(__file__)); src = open(os.path.join(HERE, "q188_skew_gate_guard_model.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
    ns = {"__name__": "q188_head", "__file__": os.path.join(HERE, "q188_skew_gate_guard_model.py")}; exec(compile(src, "q188_head", "exec"), ns)
    cfg, table, us_dst, G, K, P0, P1, run_guard, evaluate, account_items, verdict, skew_gate_dates = (ns[k] for k in ("cfg", "table", "us_dst", "G", "K", "P0", "P1", "run_guard", "evaluate", "account_items", "verdict", "skew_gate_dates"))
    SKEW_ON = {"531343523", "531466484", "14074882"}; PRK = skew_gate_dates()
    def paths_pair(items, cap, fac):
        """Q188 の paths と同じ。fac = {sym: {date: 倍率}}(円クロスのみ・無ければ 1.0)。"""
        parts = []
        for s, idxf, w in items:
            Mt, res = table(s, idxf); Rk = res[K]; p = Mt.copy(); p["w"] = w / p.nshots
            if not idxf and s in fac: p["w"] = p.w * p.date.map(lambda d: fac[s].get(d, 1.0)).values
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
                        a = arr * wf; tot[tag] += a; b = a.copy()
                        if close < gb: b[gb:] = 0.0
                        met[tag] += b
            out.append(dict(d=d, gb=gb, tot=tot, met=met, fin=float(tot["cl"][-1])))
        return out
    arows = []
    for a in cfg["accounts"]:
        aid, items, cap, g = account_items(a); fx = [s for s, idxf, w in items if not idxf]
        if not fx or not (a.get("targets") or []): continue
        dates = sorted({d for s in fx for d in table(s, False)[0].date.unique()}); dates = [pd.Timestamp(d) for d in dates]
        sk = {}
        if aid in SKEW_ON:
            pr = PRK.reindex(pd.DatetimeIndex(dates) - pd.Timedelta(days=3), method="ffill").values; sk = {d: 0.0 for d, p in zip(dates, pr) if p == p and p > 0.8}
        def fac_for(wfn=None, hi=1.0, lo=1.0):
            F = {}
            for s in fx:
                hit = wfn(st_at(s, dates)).fillna(False).values if wfn is not None else np.zeros(len(dates), bool)
                F[s] = {d: sk.get(d, 1.0) * ((hi if h else lo) if wfn is not None else 1.0) for d, h in zip(dates, hit)}
            return F
        ex = dict(guard_pct=round(g * 100, 1), pairs="/".join(fx), skew_skip=(aid in SKEW_ON))
        arows += evaluate(a, aid, run_guard(paths_pair(items, cap, fac_for()), g), "現行", ex)
        for wn, wfn in W:
            for tn, hi, lo in T: arows += evaluate(a, aid, run_guard(paths_pair(items, cap, fac_for(wfn, hi, lo)), g), f"{wn}|{tn}", ex)
    A = pd.DataFrame(arows); A.to_csv("results/q195_mon_weak_state_tilt_accounts.csv", index=False); picks = []
    for (acct, sc), g_ in A[A.scen != "—"].groupby(["acct", "scen"], sort=False):
        cur, best = verdict(g_, "現行"); picks.append(dict(acct=acct, scen=sc, cur_reach_lo=cur.reach_lo, cur_reach_cl=cur.reach_cl, cur_fail_lo=cur.fail_lo, cur_weeks=cur.weeks_lo, verdict=("変更候補" if best is not None else "現行維持"), variant=(best.variant if best is not None else "—"),
                                                               reach_lo=(best.reach_lo if best is not None else None), reach_cl=(best.reach_cl if best is not None else None), fail_lo=(best.fail_lo if best is not None else None), weeks=(best.weeks_lo if best is not None else None)))
    print("\n== 口座モデル(判定) ==\n" + pd.DataFrame(picks).to_string(index=False))
    print("\n== 口座モデル(全行) ==\n" + A[["acct", "scen", "variant", "mean_bps_lo", "hits_lo", "mean_bps_cl", "reach_lo", "reach_cl", "fail_lo", "fail_cl", "weeks_lo"]].to_string(index=False))
    # ---- 実行後の追加(登録外・参考): 損切り込みのショット単位で、弱い状態 / それ以外の平均と損切り率(口座モデルの期間・Mon4 の 4 通貨) ----
    sl = []
    for wn, wfn in W:
        aw, ao, sw, so = [], [], [], []
        for s in PAIRS:
            Mt, res = table(s, False); Rk = res[K]; d = pd.DatetimeIndex(Mt.date); okd = (d >= P0) & (d <= P1); hit = wfn(st_at(s, d)).fillna(False).values; r = np.asarray(Rk["r"]); stopped = np.asarray(Rk["stop"]) < Mt.off.values + 24
            aw += list(r[okd & hit]); ao += list(r[okd & ~hit]); sw += list(stopped[okd & hit]); so += list(stopped[okd & ~hit])
        sl.append(dict(state=wn, n_weak=len(aw), n_other=len(ao), mean_weak_bps=round(float(np.mean(aw)) * 1e4, 1), mean_other_bps=round(float(np.mean(ao)) * 1e4, 1), sl_rate_weak=round(float(np.mean(sw)) * 100, 1), sl_rate_other=round(float(np.mean(so)) * 100, 1)))
    SLD = pd.DataFrame(sl); SLD.to_csv("results/q195_mon_weak_state_tilt_sl.csv", index=False); print("\n== 参考(登録外): 損切り込みのショット単位 ==\n" + SLD.to_string(index=False))
