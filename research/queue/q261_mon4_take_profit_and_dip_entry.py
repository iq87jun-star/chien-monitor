# -*- coding: utf-8 -*-
"""docs/244 Q261(改良系・6 セル・2026-11-17 登録「登録して実行」): 月曜の円クロスで決済・建ての時間軸を短くする 2 つの形(途中の利確 / 月曜の中の押し目で建てる)。
ユーザー 2026-11-17「デイトレード 30 分足などでトレードする方法でもテクニカル分析等または強い月曜日に複数回決済など決済時間軸を短くしたトレードはありませんか」→ 検証済みの一覧と未検証の 2 案を提示 →「登録して実行」(2 案とも)。
基準 = 採用済みの形: Mon4(200 日線の下 1.0・上 0.5)・4 / 6 / 8 / 10 UTC 建て・損切り 3.0 × ATR24(1 時間足の安値で判定・損切り価格で約定)・決済 E1(前金曜 VIX ≤ 25 の週は同日 20 UTC・25 超は 24 時間)。Q249 の基準 0.92 / 2.00 / 1.55 を再現する。
(1) 途中の利確(指値・1 時間足の高値で判定・指値の価格で約定。同じ足で損切りと重なったら損切りを先に数える):
    P1 = 建値 + 3.0 × ATR24 で半分を利確・残りは基準どおり。P2 = + 2.0 × ATR24 で半分。P3 = + 3.0 × ATR24 で全部。P4 = + 2.0 × ATR24 で全部。
(2) 月曜の中の押し目で建てる: 各ショットは予定の時刻から 1 時間ごとに「直前の 1 時間足の終値 < 直近 24 本の終値の平均」を確かめ、最初に当たった時刻の始値で建てる(14 UTC まで)。
    D1 = 14 UTC まで当たらなければそのショットは見送る。D2 = 当たらなければ 14 UTC に建てる。決済は基準と同じ(静かな週 20 UTC・荒れた週は予定の時刻 + 24 時間)。損切りは建てた時点の ATR24 × 3.0。
判定(事前固定)= 基準に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。成立した形だけ口座モデル(第 2 段)へ。
使い方: cd research && PYTHONPATH=queue:. python3 -W ignore queue/q261_mon4_take_profit_and_dip_entry.py <累積セル数>   出力: results/q261_mon4_tp_dip.csv・_ref.csv"""
import os, sys
_ARGV = list(sys.argv); HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py"), encoding="utf-8").read().split("\n# ---------------- (A) 本口座後")[0]; n3 = {"__name__": "q233_head", "__file__": os.path.join(HERE, "q233_exit_switch_line_vs_vix_account_model.py")}; exec(compile(_src, "q233_head", "exec"), n3)
np, pd, q = n3["np"], n3["pd"], n3["q"]; flags_of, hot = n3["flags_of"], n3["hot"]
sys.path.insert(0, HERE)
from q147_roll_rate_diff_gate import stats
MON4 = ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"]; HOURS = (4, 6, 8, 10); H = pd.Timedelta(hours=1); PRE0, IS0, IS1, OOS0, END = q.PRE0, q.IS0, q.IS1, q.OOS0, q.END; PRE1 = IS0 - H; WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
_D = {}
def data(sym):
    if sym not in _D:
        df = q.load(sym); idx = pd.date_range(df.index[0], df.index[-1], freq="h"); o = df["open"].reindex(idx); c = df["close"].reindex(idx); cf = c.ffill(); hi = df["high"].reindex(idx).fillna(cf); lo = df["low"].reindex(idx).fillna(cf)
        dip = (df["close"] < df["close"].rolling(24).mean()).shift(1).reindex(idx)          # 直前の(実在する)1 時間足で判定
        _D[sym] = dict(o=o, hi=hi.values, lo=lo.values, atr=q.atr24(df), pos={t: i for i, t in enumerate(idx)}, idx=idx, dip=dip, pip=q.base.pip_size(sym), mondays=pd.DatetimeIndex(sorted(set(df.index[df.index.dayofweek == 0].normalize()))), weak=flags_of(sym))
    return _D[sym]
def one(sym, d, h, tp_k=None, tp_frac=0.0, dip=None):
    """1 ショットの損益(コスト後・1 倍)。戻り値 (r, 利確に掛かったか, 損切りに掛かったか, 建てた時刻) または None(建てない / データなし)。"""
    X = data(sym); o = X["o"]; t0 = d + h * H; tx24 = t0 + 24 * H; t = t0
    if tx24 not in X["pos"] or np.isnan(o.get(t0, np.nan)) or np.isnan(o.get(tx24, np.nan)): return None
    if dip is not None:
        t = None
        for k in range(h, 15):
            tk = d + k * H
            if bool(X["dip"].get(tk, False)) and not np.isnan(o.get(tk, np.nan)): t = tk; break
        if t is None:
            if dip == "skip": return None
            t = d + 14 * H
            if np.isnan(o.get(t, np.nan)): return None
    a = X["atr"].get(t, np.nan)
    if np.isnan(a): return None
    e = float(o[t]); c = float(q.cost(sym, [e])[0]); sd = max(3.0 * float(a), 10 * X["pip"]); t20 = d + 20 * H; calm = (not hot(d)) and (t20 in X["pos"]) and not np.isnan(o.get(t20, np.nan)) and t20 > t
    tx = t20 if calm else tx24; i0, i1 = X["pos"][t], X["pos"][tx]; lo = X["lo"][i0:i1]; hi = X["hi"][i0:i1]; rem = 1.0; pnl = 0.0; tp = False; tpl = (e + tp_k * float(a)) if tp_k else None
    js = np.flatnonzero(lo <= e - sd); j_sl = int(js[0]) if len(js) else None; j_tp = None
    if tpl is not None:
        jt = np.flatnonzero(hi >= tpl); j_tp = int(jt[0]) if len(jt) else None
        if j_tp is not None and (j_sl is None or j_tp < j_sl): pnl += tp_frac * (tpl / e - 1); rem -= tp_frac; tp = True
    if rem > 0: pnl += rem * ((-sd / e) if j_sl is not None else (float(o[tx]) / e - 1))
    return pnl - c, tp, (j_sl is not None and rem > 0), t
def series(tp_k=None, tp_frac=0.0, dip=None, info=None):
    rows = []
    for s in MON4:
        X = data(s)
        for d in X["mondays"]:
            if d < PRE0: continue
            f = 1.0 if X["weak"].get(d, False) else 0.5
            for h in HOURS:
                r = one(s, d, h, tp_k, tp_frac, dip)
                if r is None: continue
                rows.append((d, r[0] * f * 0.25 / len(HOURS), r[1], r[2], (r[3] - d) / H))
    D = pd.DataFrame(rows, columns=["d", "r", "tp", "sl", "hour"])
    if info is not None: info.update(n=len(D), tp=round(float(D.tp.mean()) * 100, 1), sl=round(float(D.sl.mean()) * 100, 1), hour=round(float(D.hour.mean()), 1))
    return D.groupby("d").r.sum().sort_index()
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 6; ib = {}; B = series(info=ib); bs = {w: stats(B, a, b) for w, a, b in WIN}; rows = []
    print("基準(Q249 の 0.92 / 2.00 / 1.55 のはず):", {w: bs[w][:3] for w in bs}, ib)
    C = [("P1 +3.0 ATR で半分を利確", dict(tp_k=3.0, tp_frac=0.5)), ("P2 +2.0 ATR で半分を利確", dict(tp_k=2.0, tp_frac=0.5)), ("P3 +3.0 ATR で全部を利確", dict(tp_k=3.0, tp_frac=1.0)), ("P4 +2.0 ATR で全部を利確", dict(tp_k=2.0, tp_frac=1.0)), ("D1 月曜の押し目で建てる(14 UTC まで・無ければ見送り)", dict(dip="skip")), ("D2 月曜の押し目で建てる(無ければ 14 UTC に建てる)", dict(dip="late"))]
    for nm, kw in C:
        inf = {}; v = series(info=inf, **kw); vs = {w: stats(v, a, b) for w, a, b in WIN}; wk = v.reindex(B.index).fillna(0.0)
        rows.append(dict(cell=nm, shots=inf["n"], tp_hit_pct=inf["tp"], sl_hit_pct=inf["sl"], mean_entry_hour=inf["hour"], var_PRE=vs["前窓"][:3], var_IS=vs["IS"][:3], var_OOS=vs["OOS"][:3], week_win_pct=round(float((v > 0).mean()) * 100, 1), verdict=("成立" if all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN) else "不成立")))
    D = pd.DataFrame(rows); D.to_csv("results/q261_mon4_tp_dip.csv", index=False); ref = []
    for k in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
        for fr in (0.5, 1.0):
            inf = {}; v = series(tp_k=k, tp_frac=fr, info=inf); ref.append(dict(tp_atr=k, frac=fr, tp_hit_pct=inf["tp"], PRE=stats(v, *WIN[0][1:])[:3], IS=stats(v, *WIN[1][1:])[:3], OOS=stats(v, *WIN[2][1:])[:3], week_win_pct=round(float((v > 0).mean()) * 100, 1)))
    RF = pd.DataFrame(ref); RF.to_csv("results/q261_mon4_tp_dip_ref.csv", index=False)
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 60)
    print(f"\n== 判定(値 = Sharpe / 最悪月 % / 累積 %。基準 {bs['前窓'][:3]} / {bs['IS'][:3]} / {bs['OOS'][:3]}・基準の週の勝率 {100 * (B > 0).mean():.1f}%・損切り {ib['sl']}%。累積セル {cum} + {N} = {cum + N}) =="); print(D.to_string(index=False)); print("\n== 参照(セル外): 利確の幅の並び =="); print(RF.to_string(index=False))
