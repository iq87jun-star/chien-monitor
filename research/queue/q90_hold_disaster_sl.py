# -*- coding: utf-8 -*-
"""docs/322 Q90(改良系): Hold(連続 LONG)の災害 SL 水準。EA の現行 `InpHoldCatSLPct=15`(建値 −15% の固定 SL・ヒット後はフラットになり次の機会に再建て)を
基準とし、{10%, 20%, なし} を Hold 6 銘柄(US500 / NAS100 / GER40 / JP225 / XAUUSD / BTCUSD)で比較する。6 セル(銘柄 = セル、水準 3 本は同一セル内の比較)。
日足(Hold 6 と同じ Yahoo・凍結窓)で: SL は安値で判定、約定は SL 価格(始値が SL を割る日は始値 = ギャップ)、再建ては翌日始値(EA はガード当日は建てないため)、建値は前窓・IS・OOS の各初日に置き直す(= 窓開始に配備した EA。SL は建値固定で追随しない)、
再建て 1 回に往復 5 bps を課す。それ以外は hold_cell と同じ(終値→終値・月初 5 bps)。判定は docs/244 §1 改良系(IS・OOS 両方で Sharpe 改善 かつ 最悪月が悪化しない)。
使い方: cd research && python3 queue/q90_hold_disaster_sl.py <累積セル数>"""
import sys, os
from q_common import *
def stats(s, a, b):   # q_cal.stats と同一(q_cal は data_ext を要求するため写し)
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return (round(float(x.mean() / x.std() * np.sqrt(252)), 2) if x.std() > 0 else 0.0), round(float(m.min()) * 100, 2)
def improved(basis, var):   # q_cal.improved と同一
    bi, bo, gi, go = stats(basis, IS0, IS1), stats(basis, OOS0, END), stats(var, IS0, IS1), stats(var, OOS0, END)
    return dict(base_IS=bi, var_IS=gi, base_OOS=bo, var_OOS=go, ok=bool(gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]))
base.DATA = os.path.join(ROOT, "data_202609")
SYMS = base.HOLD_SYMS; LEVELS = {"15%(現行)": 15.0, "10%": 10.0, "20%": 20.0, "なし": None}; REENTRY_COST = 5e-4
def hold_sl(nm, pct):
    """日次リターン列(hold_cell と同じ窓・月初費)。pct=None は SL なし = hold_cell と同一。戻り値: (series, SL ヒット回数, 保有日数)"""
    d = base.load_daily(nm); o, h, l, c = d["open"].values, d["high"].values, d["low"].values, d["close"].values; idx = d.index
    r = np.full(len(d), np.nan); hits = 0; entry = c[0]; flat = False; sl = None if pct is None else entry * (1 - pct / 100)
    restarts = {idx[idx >= pd.Timestamp(x)][0] for x in (PRE0, IS0, OOS0) if (idx >= pd.Timestamp(x)).any()}   # 各窓の最初の営業日に建て直す(= 窓開始に配備した EA の建値。費用なし)
    for i in range(1, len(d)):
        if idx[i] in restarts and not flat:
            entry = c[i]; sl = None if pct is None else entry * (1 - pct / 100)
        if flat:   # 翌日始値で再建て
            entry = o[i]; sl = None if pct is None else entry * (1 - pct / 100); flat = False
            r[i] = c[i] / o[i] - 1 - REENTRY_COST; continue
        if sl is not None and l[i] <= sl:
            fill = min(o[i], sl); r[i] = fill / c[i - 1] - 1; hits += 1; flat = True; continue
        r[i] = c[i] / c[i - 1] - 1
    s = pd.Series(r, index=idx).dropna(); s = base.clip(s)
    firsts = pd.Series(s.index, index=s.index).groupby(pd.PeriodIndex(s.index, freq="M")).min(); s.loc[s.index.isin(firsts.values)] -= 5e-4
    return s, hits, int(len(s))
if __name__ == "__main__":   # paper_forward から hold_sl を import できるよう本体はここ
    cum = int(sys.argv[1]); R = Runner("Q90", cum, len(SYMS), "results/q90_hold_disaster_sl.csv"); rows = []
    for nm in SYMS:
        ser = {k: hold_sl(nm, v) for k, v in LEVELS.items()}
        b, bh, bn = ser["15%(現行)"]; R.add("Hold 災害 SL(改良系)", nm, "基準 = 現行 15%(セル内で 10% / 20% / なし を比較)", b)
        # 自己検証: SL なし = hold_cell と一致(docs/249 流の同一性チェック)
        z = (ser["なし"][0] - base.hold_cell(nm)).abs().max(); assert z < 1e-12, f"[PARITY] {nm} {z}"
        for k, (v, hh, _) in ser.items():
            if k == "15%(現行)": continue
            im = improved(b, v); x5 = lambda s: round(float(((1 + s[(s.index >= IS0) & (s.index <= END)]).prod() - 1) * 100), 1)
            rows.append(dict(symbol=nm, level=k, hits_base15=bh, hits_var=hh, cum5y_base15=x5(b), cum5y_var=x5(v), base_IS=im["base_IS"], var_IS=im["var_IS"], base_OOS=im["base_OOS"], var_OOS=im["var_OOS"], improved=im["ok"]))
    R.finish(); pd.set_option("display.width", 320); D = pd.DataFrame(rows); D.to_csv("results/q90_hold_disaster_sl_levels.csv", index=False)
    print("\n== Q90 水準比較(stats = Sharpe, 最悪月 %, 累積 %)==\n" + D.to_string(index=False))
    print("\n改良成立:", int(D.improved.sum()), "/", len(D), " 銘柄別:", {s: int(D[D.symbol == s].improved.sum()) for s in SYMS})
