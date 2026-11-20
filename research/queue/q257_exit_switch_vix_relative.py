# -*- coding: utf-8 -*-
"""docs/244 Q257(改良系・4 セル・2026-11-17 登録): 月曜の円クロスの決済の切り替えを、VIX の「水準(25 超)」ではなく「自分の平均との比較」で行う。
ユーザー 2026-11-17「フィルター機能ですが、移動平均線や VIX も別の時間軸のものを掛け合わせる事はできませんか」→ 未検証の 4 案を提示 →「1 で」(= 案 1 の登録して実行)。
配備形(200 日線の下 1.0・上 0.5)はそのまま。決済だけを替える: 条件に当たる週は全通貨 24 時間、当たらない週は全通貨 同日 20 UTC(E1 と同じ作り)。
前金曜(月曜 − 3 日・無ければ直前)の VIX 終値 v と、その日までの VIX で条件を作る:
  R1: v > 直近 20 営業日の平均。 R2: v > 直近 252 営業日の平均。
  R3: v が直近 252 営業日(その日を除く)の 80% の位置より上(SKEW の門と同じ作り方の分位)。 R4: 5 日平均 > 60 日平均(短い平均と長い平均の比較)。
判定(事前固定)= 配備形(常に 24h)に対して 3 窓すべてで Sharpe 改善 かつ 最悪月が悪化しない → 成立。
差し替えの提案は、採用済みの E1(VIX > 25)に対しても 3 窓すべてで Sharpe 改善 かつ 最悪月が悪化しない場合だけ。成立しても E1 を上回らなければ紙上候補にもしない(E1 の言い換えのため)。
参照(セル外): 各条件の週の割合・E1 との重なり・条件ごとの夜(20 UTC → 24h)の平均。
使い方: cd research && python3 -W ignore queue/q257_exit_switch_vix_relative.py <累積セル数>   出力: results/q257_exit_switch_vix_relative.csv・_ref.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
from q147_roll_rate_diff_gate import stats
from q238_late_entry_after_high_vix_and_short_nights import fx_frame
from q237_night_leg_after_high_vix import VIX
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); D1 = pd.Timedelta(days=1)
V = VIX.dropna().sort_index()
SIG = pd.DataFrame({"R1": V > V.rolling(20).mean(), "R2": V > V.rolling(252).mean(), "R3": V.rolling(253).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True) > 0.8, "R4": V.rolling(5).mean() > V.rolling(60).mean()})
LAB = {"R1": "R1 VIX > 自分の 20 日平均 の週だけ 24h", "R2": "R2 VIX > 自分の 252 日平均 の週だけ 24h", "R3": "R3 VIX が自分の 252 日の 80% の位置より上の週だけ 24h", "R4": "R4 VIX の 5 日平均 > 60 日平均 の週だけ 24h"}
def frame():
    P = fx_frame().copy(); d = pd.DatetimeIndex(P.index) - 3 * D1
    for k in SIG: P[k] = SIG[k].reindex(d, method="ffill").fillna(False).values.astype(bool)
    return P
def series(P, kind):
    m = {"base": np.ones(len(P), bool), "E1": P.hot.values}.get(kind); m = P[kind].values if m is None else m
    return pd.Series(np.where(m, P.r24, P.r20) * P.f.values * 0.25, index=P.index).groupby(level=0).sum()
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 4; P = frame(); B = series(P, "base"); E1 = series(P, "E1"); bs = {w: stats(B, a, b) for w, a, b in WIN}; es = {w: stats(E1, a, b) for w, a, b in WIN}; rows = []; ref = []
    print("基準(0.46 / 1.51 / 1.20 のはず):", {w: bs[w][:3] for w in bs}, " E1(0.67 / 2.31 / 1.65 のはず):", {w: es[w][:3] for w in es})
    wk = P.groupby(level=0).first()
    for k in SIG:
        v = series(P, k); vs = {w: stats(v, a, b) for w, a, b in WIN}; ok = all(vs[w][0] > bs[w][0] and vs[w][1] >= bs[w][1] for w, _, _ in WIN); be = all(vs[w][0] > es[w][0] and vs[w][1] >= es[w][1] for w, _, _ in WIN)
        rows.append(dict(cell=LAB[k], share_24h=round(float(wk[k].mean()), 3), base_PRE=bs["前窓"][:3], var_PRE=vs["前窓"][:3], E1_PRE=es["前窓"][:3], base_IS=bs["IS"][:3], var_IS=vs["IS"][:3], E1_IS=es["IS"][:3], base_OOS=bs["OOS"][:3], var_OOS=vs["OOS"][:3], E1_OOS=es["OOS"][:3], verdict=("成立" if ok else "不成立"), beats_E1_3win=bool(be)))
        night = (P.r24 - P.r20) * P.f.values
        for w, a, b in WIN + (("全期間", PRE0, END),):
            z = P[(P.index >= a) & (P.index <= b)]; nz = night[(P.index >= a) & (P.index <= b)]; on, off = nz[z[k].values], nz[~z[k].values]; won = on.groupby(level=0).mean(); woff = off.groupby(level=0).mean()
            ref.append(dict(cell=k, window=w, weeks_on=len(won), weeks_off=len(woff), night_on_bps=round(float(on.mean()) * 1e4, 1) if len(on) else None, night_off_bps=round(float(off.mean()) * 1e4, 1) if len(off) else None, t_on=round(float(won.mean() / won.std() * np.sqrt(len(won))), 2) if len(won) > 2 else None, t_off=round(float(woff.mean() / woff.std() * np.sqrt(len(woff))), 2) if len(woff) > 2 else None,
                            overlap_with_E1=round(float((wk[k] & wk.hot)[(wk.index >= a) & (wk.index <= b)].sum() / max(int(wk.hot[(wk.index >= a) & (wk.index <= b)].sum()), 1)), 2), E1_weeks=int(wk.hot[(wk.index >= a) & (wk.index <= b)].sum())))
    D = pd.DataFrame(rows); R = pd.DataFrame(ref); D.to_csv("results/q257_exit_switch_vix_relative.csv", index=False); R.to_csv("results/q257_exit_switch_vix_relative_ref.csv", index=False)
    pd.set_option("display.width", 340); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 70)
    print(f"\n== 判定(値 = Sharpe / 最悪月 % / 累積 %。累積セル {cum} + {N} = {cum + N}) =="); print(D.to_string(index=False)); print("\n== 参照: 夜(20 UTC → 24h・数量の縮小込み)の平均 bps。on = 条件に当たる週 =="); print(R.to_string(index=False))
