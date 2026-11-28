# -*- coding: utf-8 -*-
"""docs/244 Q194(改良系・6 セル・2026-11-13 登録「登録して実行」): 月曜の円クロス × その通貨自身のテクニカル状態による見送り。
基準 = 配備形 Mon4(GBPJPY / EURJPY / AUDJPY / USDJPY 各 0.25・deployed_book.mon_cell_h1 = 月曜 4/6/8/10 UTC 建て 24h・往復 3 pip)。
指標 = 同じ H1 から作る日足(日付 = 時刻 + 2 時間の暦日・終値 = その日の最後の H1 終値)の、月曜より前の最後の値。該当した通貨のその月曜の寄与を 0 にする。
セル: RSI(14) > 70 / RSI(14) < 30 / 終値 < SMA200 / 終値 < SMA20 / z20 > +2 / 前週下落。判定 = q114.improved + 累積 1/2 規則。
使い方: cd research && python3 queue/q194_mon_own_technical_state_gate.py <累積>   出力: results/q194_mon_own_technical_state_gate.csv・_levels.csv・_bypair.csv"""
import sys
from q_common import *
from q114_mon_index_intraday import stats, improved
import deployed_book as db
PAIRS = ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY")
def daily_close(sym):
    c = load(sym)["close"]; d = (c.index + pd.Timedelta(hours=2)).normalize(); x = c.groupby(d).last(); return x[x.index.dayofweek < 5]
def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean(); return 100 - 100 / (1 + up / dn)
def states(sym):
    c = daily_close(sym); s20 = c.rolling(20).mean(); return pd.DataFrame({"rsi": rsi(c), "sma200": c / c.rolling(200).mean() - 1, "sma20": c / s20 - 1, "z20": (c - s20) / c.rolling(20).std(), "wk": c / c.shift(5) - 1})
RULES = [("RSI(14) > 70", lambda S: S.rsi > 70), ("RSI(14) < 30", lambda S: S.rsi < 30), ("終値 < SMA200", lambda S: S.sma200 < 0), ("終値 < SMA20", lambda S: S.sma20 < 0), ("z20 > +2", lambda S: S.z20 > 2), ("前週下落", lambda S: S.wk < 0)]
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q194", cum, 6, "results/q194_mon_own_technical_state_gate.csv")
    M = {}; ST = {}; h1_end = None
    for s in PAIRS:
        h = load(s); m = db.mon_cell_h1(s); m = m[(m.index >= PRE0) & (m.index <= h.index.max())]; S = states(s)
        M[s] = m; ST[s] = S.shift(1).reindex(m.index, method="ffill")          # 月曜より前の最後の日足(shift(1) = 当日の足を使わない)
    idx = sorted(set().union(*[set(M[s].index) for s in PAIRS])); idx = pd.DatetimeIndex(idx)
    def comp(mask_fn=None, factor=0.0):
        out = pd.Series(0.0, index=idx)
        for s in PAIRS:
            x = M[s].copy()
            if mask_fn is not None:
                hit = mask_fn(ST[s]).fillna(False).values; x = x * np.where(hit, factor, 1.0)
            out = out.add(x * 0.25, fill_value=0.0)
        return out
    B = comp(); rows = []; bp = []
    for nm, fn in RULES:
        v = comp(fn, 0.0); R.add("Mon4 × 通貨自身の指標(改良系)", "Mon4", f"{nm} の通貨は見送り", v); im = improved(B, v); half = improved(B, comp(fn, 0.5))
        cum_ok = bool(im["var_IS"][2] >= 0.5 * im["base_IS"][2] and im["var_OOS"][2] >= 0.5 * im["base_OOS"][2])
        tot = sk = 0; ms = []; mk = []
        for s in PAIRS:
            x = M[s][M[s].index >= IS0]; hit = fn(ST[s]).reindex(x.index).fillna(False).values; tot += len(x); sk += int(hit.sum()); ms += list(x[hit].values); mk += list(x[~hit].values)
            for win, a, b in (("IS", IS0, IS1), ("OOS", OOS0, END)):
                y = M[s][(M[s].index >= a) & (M[s].index <= b)]; hh = fn(ST[s]).reindex(y.index).fillna(False).values
                bp.append(dict(rule=nm, pair=s, window=win, n=len(y), skipped=int(hh.sum()), mean_skipped_bps=round(float(y[hh].mean()) * 1e4, 1) if hh.any() else np.nan, mean_kept_bps=round(float(y[~hh].mean()) * 1e4, 1)))
        rows.append(dict(rule=nm, skipped=sk, total=tot, skip_share=round(sk / tot, 3), mean_skipped_bps=round(float(np.mean(ms)) * 1e4, 1) if ms else np.nan, mean_kept_bps=round(float(np.mean(mk)) * 1e4, 1), **im, cum_rule_ok=cum_ok,
                         verdict=("成立" if im["ok"] and cum_ok else ("成立だが累積 1/2 未満" if im["ok"] else "不成立")), half_IS=half["var_IS"], half_OOS=half["var_OOS"], half_ok=half["ok"]))
    R.finish(); D = pd.DataFrame(rows); D.to_csv("results/q194_mon_own_technical_state_gate_levels.csv", index=False); BP = pd.DataFrame(bp); BP.to_csv("results/q194_mon_own_technical_state_gate_bypair.csv", index=False)
    pd.set_option("display.width", 320); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
    print("\n基準 Mon4: IS", stats(B, IS0, IS1), "OOS", stats(B, OOS0, END), "| 月曜数 IS+OOS", int((B.index >= IS0).sum()), "| 末尾", B.index.max().date())
    print("\n== Q194 改良判定((Sharpe, 最悪月%, 累積%)) ==\n" + D.to_string(index=False)); print("\n改良成立:", int((D.verdict == "成立").sum()), "/ 6")
    print("\n== 通貨別(見送った建て / 残した建ての平均 bps) ==\n" + BP.to_string(index=False))
