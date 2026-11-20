# -*- coding: utf-8 -*-
"""docs/244 Q255(改良系・2 セル・2026-11-17 登録「登録して実行」): 金の保有 × 金そのものの 200 日線(線の上のときだけ持つ)。
きっかけ: Q196(docs/435)で金は「200 日線の上のほうが良い」(円クロス・指数と逆)。金の保有の形では未検証。金は 2026-09-04 に線を下回り、9 月下旬に建てた 3 口座の金はすべて線の下。
基準 = 金の保有(base.hold_cell("XAUUSD")・終値 → 終値の連続保有・月初 5 bps・スワップなし = Q236 と同じ系列)。
G1 = 前営業日の終値が 200 日単純移動平均(その日を含む)より上の日だけ 1.0 倍・下は 0。G2 = 上 1.0 倍・下 0.5 倍。持ち高を変える日に 5 bps × 変化量の費用。
  2016-01 より前の移動平均の助走は Dukascopy の日足(平日・出来高あり)で補う。
判定(事前固定)= 基準に対して 前窓・IS・OOS の 3 つすべてで Sharpe 改善 かつ 最悪月が悪化しない。成立した形だけ第 2 段(Q253 の口座モデル)へ進む。
参照(セル外): 日数 100・250、スワップ込み(−52・−76 bps/月を持っている日に)、線の上 / 下の日次平均、長期(Dukascopy 日足 2003〜2015)。
使い方: cd research && python3 -W ignore queue/q255_gold_hold_own_sma200.py <累積セル数>   出力: results/q255_gold_hold_own_sma200.csv・_ref.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
import q206_sma200_state_v4_usdjpy_ger40_breakout as q206
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); ALLW = WIN + (("全期間", PRE0, END),); SW = 5e-4
R = base.hold_cell("XAUUSD"); R = R[R.index >= PRE0]; CL = base.load_daily("XAUUSD")["close"].astype(float)
DK = pd.read_csv("data_dukascopy/XAUUSD_day.csv"); DK["d"] = pd.to_datetime(DK["timestamp"]); DK = DK[(DK.d.dt.dayofweek <= 4) & (DK.volume > 5)].set_index("d")["close"].astype(float)
ALLC = pd.concat([DK[DK.index < CL.index[0]], CL]).sort_index()
def gate(n=200, low=0.0, close=ALLC):
    """持ち高(その日の収益に掛ける倍率): 前営業日の終値 > n 日移動平均 → 1.0、それ以外 → low。"""
    above = (close > close.rolling(n).mean()).astype(float); pos = (above * (1 - low) + low).shift(1); return pos
def series(n=200, low=0.0, swap=0.0):
    pos = gate(n, low).reindex(R.index).fillna(1.0); x = R * pos - SW * pos.diff().abs().fillna(0.0) + pos * swap / 1e4 / 21.0; return x, pos
def dd(x): e = x.cumsum(); return round(float((e - e.cummax()).min()) * 100, 1)
if __name__ == "__main__":
    cum = int(_ARGV[1]); N = 2; rows = []; ref = []; b = R; b_ = {w: q206.stat(b, a, e) for w, a, e in WIN}
    print("基準(Q236 と同じはず 0.61 / 0.89 / 1.16):", {w: b_[w][:3] for w in b_})
    for nm, low in (("G1 線の上 1.0 倍・下 0", 0.0), ("G2 線の上 1.0 倍・下 0.5 倍", 0.5)):
        x, pos = series(200, low); x_ = {w: q206.stat(x, a, e) for w, a, e in WIN}; ok = all(x_[w][0] > b_[w][0] and x_[w][1] >= b_[w][1] for w, _, _ in WIN)
        rows.append(dict(cell=nm, base_PRE=b_["前窓"][:3], var_PRE=x_["前窓"][:3], base_IS=b_["IS"][:3], var_IS=x_["IS"][:3], base_OOS=b_["OOS"][:3], var_OOS=x_["OOS"][:3], maxdd_base=dd(b), maxdd_var=dd(x), days_below_pct=round(float((pos < 1).mean()) * 100, 1), switches=int((pos.diff().abs() > 0).sum()), verdict=("成立" if ok else "不成立")))
    D = pd.DataFrame(rows); D.to_csv("results/q255_gold_hold_own_sma200.csv", index=False)
    for n in (100, 250):
        x, pos = series(n, 0.0); ref.append(dict(kind=f"日数 {n}(G1)", **{w: q206.stat(x, a, e)[:3] for w, a, e in ALLW}, maxdd=dd(x)))
    for sw, lab in ((-52.0, "スワップ −52 bps/月"), (-76.0, "スワップ −76 bps/月")):
        for nm, n, low in (("基準", 200, 1.0), ("G1", 200, 0.0), ("G2", 200, 0.5)):
            x, pos = series(n, low, sw); ref.append(dict(kind=f"{lab}: {nm}", **{w: q206.stat(x, a, e)[:3] for w, a, e in ALLW}, maxdd=dd(x)))
    pos1 = gate(200, 0.0).reindex(R.index).fillna(1.0)
    for w, a, e in ALLW:
        y = R[(R.index >= a) & (R.index <= e)]; p = pos1.reindex(y.index); up, dn = y[p == 1], y[p == 0]
        ref.append(dict(kind=f"線の上 / 下の日次平均 bps({w})", 上=f"{up.mean() * 1e4:+.1f}({len(up)} 日・t {up.mean() / up.std() * np.sqrt(len(up)):.1f})", 下=f"{dn.mean() * 1e4:+.1f}({len(dn)} 日・t {dn.mean() / dn.std() * np.sqrt(len(dn)):.1f})" if len(dn) > 5 else "—", 差の_t=q206.welch(up.values, dn.values)))
    # 長期(参照): Dukascopy 日足 2003〜2015(月初 5 bps・持ち高の変更 5 bps)
    rl = DK.pct_change().dropna(); rl = rl[rl.abs() < 0.2]; first = pd.Series(rl.index, index=rl.index).groupby(pd.PeriodIndex(rl.index, freq="M")).min(); rl.loc[rl.index.isin(first.values)] -= 5e-4
    for a, e, lab in (("2004-01-01", "2011-12-31", "長期 2004〜2011"), ("2012-01-01", "2015-12-31", "長期 2012〜2015"), ("2004-01-01", "2015-12-31", "長期 2004〜2015")):
        for nm, low in (("基準", 1.0), ("G1", 0.0), ("G2", 0.5)):
            pos = gate(200, low, DK).reindex(rl.index).fillna(1.0); x = rl * pos - SW * pos.diff().abs().fillna(0.0); s = q206.stat(x, pd.Timestamp(a), pd.Timestamp(e)); y = x[a:e]; ref.append(dict(kind=f"{lab}: {nm}", 全期間=s[:3], maxdd=dd(y)))
    RF = pd.DataFrame(ref); RF.to_csv("results/q255_gold_hold_own_sma200_ref.csv", index=False)
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 80)
    print(f"\n== 判定(値 = Sharpe / 最悪月 % / 累積 %。累積セル {cum} + {N} = {cum + N}) =="); print(D.to_string(index=False)); print("\n== 参照(セル外) =="); print(RF.fillna("").to_string(index=False))
    c = ALLC; s = c.rolling(200).mean(); print("\nデータ末尾", c.index[-1].date(), "終値", round(c.iloc[-1]), "200 日線", round(s.iloc[-1]), "線の上?" , bool(c.iloc[-1] > s.iloc[-1]))
