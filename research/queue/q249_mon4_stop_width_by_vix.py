# -*- coding: utf-8 -*-
"""docs/244 Q249(改良系・6 セル・2026-11-16 登録): 損切り幅を前金曜の VIX で変える。対象 = Mon4(200 日線の下 1.0・上 0.5)+ 決済の切り替え E1 + 損切り(建値から ATR24 × k・H1 安値で判定・損切り価格で約定)。
基準 = 一律 k = 3.0。S1 = VIX > 25 の週 4.0、S2 = 同 6.0、S3 = 同 2.0、S4 = VIX ≤ 25 の週 2.0、S5 = 同 5.0、S6 = VIX > 25 の週 損切りなし。他の週は 3.0。
判定 = 基準に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。経路は Q186 / Q233 と同じ(Q233 の前半を読み込む)。静かな週は 20 UTC までに損切りに掛からなければ 20 UTC の始値で決済。
使い方: cd research && python3 -W ignore queue/q249_mon4_stop_width_by_vix.py <累積セル数>   出力: results/q249_mon4_stop_width_by_vix.csv・_ref.csv"""
import os, sys
_ARGV = list(sys.argv); HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py"), encoding="utf-8").read().split("\n# ---------------- (A) 本口座後")[0]; n3 = {"__name__": "q233_head", "__file__": os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py")}; exec(compile(_src, "q233_head", "exec"), n3)
np, pd, q = n3["np"], n3["pd"], n3["q"]; table0, flags_of, hot, X20 = n3["table0"], n3["flags_of"], n3["hot"], n3["X20"]
sys.path.insert(0, HERE)
from q147_roll_rate_diff_gate import stats
MON4 = ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"]; PRE0, IS0, IS1, OOS0, END = q.PRE0, q.IS0, q.IS1, q.OOS0, q.END; PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
_S = {}
def shots(sym):
    """ショットごと: 日付・VIX 25 超か・200 日線の倍率・k ごとの損益(E1 の決済つき)と損切りに掛かったか。"""
    if sym in _S: return _S[sym]
    M, res = table0(sym, False); weak = flags_of(sym); o = q.load(sym)["open"]; ks = list(res.keys()); rows = []
    for i, (d, t) in enumerate(zip(M.date.values, M.t.values)):
        d = pd.Timestamp(d); t = pd.Timestamp(t); h = hot(d); e = o.get(t, np.nan); o20 = o.get(d + pd.Timedelta(hours=20), np.nan); r20 = (float(o20) / float(e) - 1 - float(q.cost(sym, [float(e)])[0])) if (e == e and o20 == o20) else np.nan
        row = dict(date=d, hot=h, f=(1.0 if weak.get(d, False) else 0.5), n=int(M.nshots.values[i]))
        for k in ks:
            st = res[k]["stop"][i]; r24 = float(res[k]["r"][i]); early = (not h) and st >= X20 and r20 == r20; row[("r", k)] = r20 if early else r24; row[("hit", k)] = bool(st < (X20 if (not h and r20 == r20) else 10**5))
        rows.append(row)
    _S[sym] = (pd.DataFrame(rows), ks); return _S[sym]
def series(kh, kc):
    """kh = VIX 25 超の週の幅、kc = VIX 25 以下の週の幅(None = 損切りなし)。週次(index = 月曜)。"""
    out = None
    for s in MON4:
        D, ks = shots(s); r = np.where(D.hot, D[("r", kh)], D[("r", kc)]) * D.f.values * 0.25 / D.n.values; x = pd.Series(r, index=D.date).groupby(level=0).sum(); out = x if out is None else out.add(x, fill_value=0.0)
    return out[out.index >= PRE0].sort_index()
def hit_rate(kh, kc):
    a = []; 
    for s in MON4:
        D, ks = shots(s); a.append(pd.DataFrame({"hot": D.hot, "hit": np.where(D.hot, D[("hit", kh)], D[("hit", kc)])}))
    A = pd.concat(a); return round(float(A.hit[A.hot].mean()) * 100, 1), round(float(A.hit[~A.hot].mean()) * 100, 1)
def stop_by_vix(kind="S1"):
    """紙上候補用。"""
    kh, kc = {"S1": (4.0, 3.0), "S2": (6.0, 3.0), "S3": (2.0, 3.0), "S4": (3.0, 2.0), "S5": (3.0, 5.0), "S6": (None, 3.0), "base": (3.0, 3.0)}[kind]; return series(kh, kc)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 6; B = series(3.0, 3.0); bs = {w: stats(B, a, b) for w, a, b in WIN}; rows = []; ref = []
    C = [("S1 VIX > 25 の週は 4.0 倍", 4.0, 3.0), ("S2 VIX > 25 の週は 6.0 倍", 6.0, 3.0), ("S3 VIX > 25 の週は 2.0 倍", 2.0, 3.0), ("S4 VIX ≤ 25 の週は 2.0 倍", 3.0, 2.0), ("S5 VIX ≤ 25 の週は 5.0 倍", 3.0, 5.0), ("S6 VIX > 25 の週は損切りなし", None, 3.0)]
    for nm, kh, kc in C:
        v = series(kh, kc); vs = {w: stats(v, a, b) for w, a, b in WIN}; hh, hc = hit_rate(kh, kc)
        rows.append(dict(cell=nm, stop_hit_hot=hh, stop_hit_calm=hc, base_PRE=bs["前窓"], var_PRE=vs["前窓"], base_IS=bs["IS"], var_IS=vs["IS"], base_OOS=bs["OOS"], var_OOS=vs["OOS"], sharpe_up_3win=bool(all(vs[w][0] > bs[w][0] for w, _, _ in WIN)), verdict=("成立" if all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN) else "不成立")))
    D = pd.DataFrame(rows); D.to_csv("results/q249_mon4_stop_width_by_vix.csv", index=False)
    for k in shots("GBPJPY")[1]:
        v = series(k, k); hh, hc = hit_rate(k, k); ref.append(dict(uniform_k=("なし" if k is None else k), stop_hit_hot=hh, stop_hit_calm=hc, PRE=stats(v, *WIN[0][1:]), IS=stats(v, *WIN[1][1:]), OOS=stats(v, *WIN[2][1:])))
    RF = pd.DataFrame(ref); RF.to_csv("results/q249_mon4_stop_width_by_vix_ref.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 60)
    hb = hit_rate(3.0, 3.0); print(f"Q249: cells={N} cum_before={cum} cum_after={cum + N} passed={int((D.verdict == '成立').sum())}/{N}  基準(E1 + 一律 3.0 倍): {bs}  損切りに掛かる割合 VIX > 25 の週 {hb[0]}%・VIX ≤ 25 の週 {hb[1]}%  (値 = Sharpe, 最悪月 %, 累積 %, 建てた週)"); print(D.to_string(index=False)); print("\n== 参照: E1 のもとでの一律の幅(判定に使わない) =="); print(RF.to_string(index=False))
