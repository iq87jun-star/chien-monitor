# -*- coding: utf-8 -*-
"""docs/244 Q262(新規・60 セル・2026-11-17 登録): 日足の逆張りの形を格子で比べる(指標 5 × 向き 3 × 保有 2 × 対象 2)。
ユーザー 2026-11-17「逆張りはどのような成績ですか」「テクニカルの種類は最適ですか」→ 最適とは言えないと回答 →「最適手法を調べてください」(= 登録して実行として扱う)。
現行 = USDJPY の逆張り v4(RSI14 < 35 かつ 20 日の z < −1.5 かつ 3 日連続の下げ かつ 当日 −0.5% 以下がすべてそろう時に買い・逆は売り。損切り 1.5 ATR・利確 1.2 倍・最長 8 日)。
格子(事前固定): 
  指標(単独): R2 = RSI(2) < 10 で買い / > 90 で売り。R14 = RSI(14) < 30 / > 70。BB = 20 日の z < −2 / > +2。ST = 3 日連続の下げ / 上げ。D5 = 5 日の変化率が自分の過去 252 日の下位 10% / 上位 10%。
  向き: 両方 / 買いだけ / 売りだけ。 保有: 3 営業日 / 5 営業日(シグナルの翌日の始値で建て、N 営業日後の始値で決済。保有中は新しいシグナルを取らない)。
  対象: USDJPY / 円クロス 4 本の束(GBPJPY・EURJPY・AUDJPY・USDJPY 各 0.25)。費用は往復 3 pip。
判定(事前固定): (a) 新規の標準 = 探索窓のプラス月の二項 p < 0.05 /(累積 + 60)・探索の月数 ≥ 24・OOS の平均 > 0・前窓のプラス月 ≥ 50%。
  (b) 現行 v4 に対する改良 = 3 窓すべてで月次 Sharpe が上回り、最悪月が悪化しない。 (c) 並べ方(参照)= 3 窓の Sharpe の最小値が大きい順(どの期間でも崩れない形を上に)。
使い方: cd research && PYTHONPATH=forward:queue:. python3 -W ignore queue/q262_daily_contrarian_grid.py <累積セル数>   出力: results/q262_daily_contrarian_grid.csv・_rank.csv"""
import sys, os
_ARGV = list(sys.argv)
from q_common import *
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END)); MON4 = ["GBPJPY", "EURJPY", "AUDJPY", "USDJPY"]
def rsi_n(c, n):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False).mean(); return 100 - 100 / (1 + up / dn.replace(0, np.nan))
_C = {}
def signals(sym):
    if sym not in _C:
        df = base.load_daily(sym); c = df["close"].astype(float); o = df["open"].astype(float); d = c.diff(); s20 = c.rolling(20).mean(); z = (c - s20) / c.rolling(20).std(); r5 = c / c.shift(5) - 1; rk = r5.rolling(253).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)
        dn3 = (d < 0) & (d.shift(1) < 0) & (d.shift(2) < 0); up3 = (d > 0) & (d.shift(1) > 0) & (d.shift(2) > 0); r2 = rsi_n(c, 2); r14 = rsi_n(c, 14)
        S = {"R2": (r2 < 10, r2 > 90), "R14": (r14 < 30, r14 > 70), "BB": (z < -2, z > 2), "ST": (dn3, up3), "D5": (rk <= 0.1, rk >= 0.9)}; _C[sym] = (o, S)
    return _C[sym]
def trade_series(sym, ind, side, hold):
    """戻り値 = 取引の損益(費用後・1 倍・index = 建てた日)。"""
    o, S = signals(sym); buy, sell = S[ind]; ov = o.values; idx = o.index; n = len(ov); b = buy.fillna(False).values; s = sell.fillna(False).values; out = {}; i = 0
    while i < n - 1 - hold:
        sig = 1 if (b[i] and side in ("both", "long")) else (-1 if (s[i] and side in ("both", "short")) else 0)
        if sig == 0 or np.isnan(ov[i + 1]) or np.isnan(ov[i + 1 + hold]): i += 1; continue
        e = ov[i + 1]; out[idx[i + 1]] = sig * (ov[i + 1 + hold] / e - 1) - float(cost(sym, [e])[0]); i += hold + 1
    r = pd.Series(out).sort_index(); return r[r.index >= PRE0]
def cell(univ, ind, side, hold):
    if univ == "USDJPY": return trade_series("USDJPY", ind, side, hold)
    out = None
    for s in MON4: x = trade_series(s, ind, side, hold) * 0.25; out = x if out is None else out.add(x, fill_value=0.0)
    return out.sort_index()
def msh(x, a, b):
    y = x[(x.index >= a) & (x.index <= b)]; m = y.groupby(pd.PeriodIndex(y.index, freq="M")).sum(); full = pd.period_range(pd.Timestamp(a).to_period("M"), min(pd.Timestamp(b), x.index.max() if len(x) else pd.Timestamp(b)).to_period("M"), freq="M"); m = m.reindex(full).fillna(0.0)
    return (round(float(m.mean() / m.std() * np.sqrt(12)), 2) if m.std() > 0 else 0.0, round(float(m.min()) * 100, 2), round(float(y.sum()) * 100, 1), len(y))
if __name__ == "__main__":
    cum = int(_ARGV[1]); R = Runner("Q262", cum, 60, "results/q262_daily_contrarian_grid.csv"); V4 = base.v4_cell("USDJPY"); V4 = V4[V4.index >= PRE0]; v4s = {w: msh(V4, a, b) for w, a, b in WIN}; rows = []
    IL = {"R2": "RSI(2) 10 / 90", "R14": "RSI(14) 30 / 70", "BB": "20 日の z ±2", "ST": "3 日連続", "D5": "5 日変化率の上下 10%"}; SL = {"both": "両方", "long": "買いだけ", "short": "売りだけ"}
    for univ in ("USDJPY", "円クロス 4 本"):
        for ind in IL:
            for side in SL:
                for hold in (3, 5):
                    x = cell(univ, ind, side, hold); nm = f"{univ}・{IL[ind]}・{SL[side]}・{hold} 日"; R.add("DailyContrarian", "USDJPY" if univ == "USDJPY" else "JPY4", nm, x); st = {w: msh(x, a, b) for w, a, b in WIN}
                    rows.append(dict(cell=nm, univ=univ, ind=IL[ind], side=SL[side], hold=hold, trades=len(x), PRE=st["前窓"][0], IS=st["IS"][0], OOS=st["OOS"][0], min3=min(st[w][0] for w in st), worst_PRE=st["前窓"][1], worst_IS=st["IS"][1], worst_OOS=st["OOS"][1], cum_all=round(float(x.sum()) * 100, 1), mean_bps=round(float(x.mean()) * 1e4 / (0.25 if univ != "USDJPY" else 1.0), 1) if len(x) else None,
                                     beats_v4=bool(all(st[w][0] > v4s[w][0] and st[w][1] >= v4s[w][1] for w in st))))
    D = R.finish(); K = pd.DataFrame(rows).sort_values("min3", ascending=False); K.to_csv("results/q262_daily_contrarian_grid_rank.csv", index=False)
    pd.set_option("display.width", 320); pd.set_option("display.max_rows", 100); pd.set_option("display.max_colwidth", 60)
    print(f"\n現行 v4(USDJPY): 月次 Sharpe {v4s['前窓'][0]} / {v4s['IS'][0]} / {v4s['OOS'][0]}・最悪月 {v4s['前窓'][1]} / {v4s['IS'][1]} / {v4s['OOS'][1]}%・取引 {len(V4)}")
    print("\n== 3 窓の Sharpe の最小値が大きい順(上位 15) =="); print(K.head(15)[["cell", "trades", "PRE", "IS", "OOS", "min3", "worst_PRE", "worst_IS", "worst_OOS", "cum_all", "mean_bps", "beats_v4"]].to_string(index=False))
    print("\n3 窓とも Sharpe がプラスのセル:", int(((K.PRE > 0) & (K.IS > 0) & (K.OOS > 0)).sum()), "/ 60・現行 v4 を 3 窓で上回るセル:", int(K.beats_v4.sum()))
    print("\n== まとめ(平均の Sharpe・3 窓) =="); 
    for k in ("univ", "ind", "side", "hold"): print(K.groupby(k)[["PRE", "IS", "OOS", "min3"]].mean().round(2).to_string())
