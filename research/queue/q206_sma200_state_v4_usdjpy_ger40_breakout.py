# -*- coding: utf-8 -*-
"""docs/244 Q206(改良系・4 セル・2026-11-14 登録「登録して実行」): 200 日線の状態 × 稼働中の残り 2 レグ。
(1) USDJPY の逆張り v4(recentfit_screen.v4_cell と同じ規則・日足)  (2) GER40 のブレイクアウト(q52 donchian 120 本・2ATR トレイル・H1)。
状態 = その銘柄自身の日足で、建ての判断より前の最後の確定足の 終値 < SMA200 なら「下」。未計算は 1.0 倍。
各レグ × {(A) 下 1.0・上 0.5 倍、(B) 上 1.0・下 0.5 倍}。判定 = §1 改良系(IS・OOS の両方で Sharpe 改善 かつ 最悪月が悪化しない)。
使い方: cd research && python3 queue/q206_sma200_state_v4_usdjpy_ger40_breakout.py <累積セル数>   出力: results/q206_sma200_state_v4_usdjpy_ger40_breakout.csv・_ref.csv"""
import sys, os
from q_common import *
PRE1 = IS0 - pd.Timedelta(hours=1); WIN = (("前窓", PRE0, PRE1), ("IS", IS0, IS1), ("OOS", OOS0, END))
_src = open(os.path.join(ROOT, "queue", "q52_donchian_vs_hold.py"), encoding="utf-8").read().split("cum = int(sys.argv[1])")[0]; _ns = {"__name__": "q52_head"}; exec(compile(_src, "q52_head", "exec"), _ns); donchian = _ns["donchian"]
def v4_trades(p="USDJPY"):
    """recentfit_screen.v4_cell と同じ規則。戻り値: 取引のリスト dict(sig_date, entry_date, sig, below, ok, daily={日付: 損益}, ret)"""
    df = base.load_daily(p); o = df["open"].values; hh = df["high"].values; ll = df["low"].values; c = df["close"].values; idx = df.index; n = len(c); rsi = base.rsi_w(c); atr = base.atr_d(hh, ll, c); bb = 20
    sma = pd.Series(c).rolling(200).mean().values; cost = 2 * base.pip_size(p); T = []; i = bb + 2
    while i < n - 1:
        win = c[i - bb:i]; mean = win.mean(); sd = win.std(ddof=1); z = (c[i] - mean) / sd if sd > 0 else 0; down = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] < c[i - k - 1]: down += 1
            else: break
        up = 0
        for k in range(12):
            if i - k - 1 >= 0 and c[i - k] > c[i - k - 1]: up += 1
            else: break
        retd = (c[i] - c[i - 1]) / c[i - 1] if c[i - 1] else 0
        buy = int(rsi[i] < 35) + int(z < -1.5) + int(down >= 3) + int(retd < -.005); sell = int(rsi[i] > 65) + int(z > 1.5) + int(up >= 3) + int(retd > .005)
        sig = 1 if (buy >= 4 and buy > sell) else (-1 if (sell >= 4 and sell > buy) else 0)
        if sig == 0: i += 1; continue
        entry = o[i + 1]; sld = 1.5 * atr[i]; tpd = 1.2 * sld
        if sld <= 0 or entry <= 0: i += 1; continue
        sl = entry - sig * sld; tp = entry + sig * tpd; ex = None; j = i + 1; held = 0
        while j < n and held < 8:
            if sig > 0:
                if ll[j] <= sl: ex = sl; break
                if hh[j] >= tp: ex = tp; break
            else:
                if hh[j] >= sl: ex = sl; break
                if ll[j] <= tp: ex = tp; break
            j += 1; held += 1
        jx = min(j, n - 1)
        if ex is None: ex = c[jx]
        prev = entry; daily = {}
        for t in range(i + 1, jx + 1):
            px = ex if t == jx else c[t]; r = sig * (px - prev) / entry
            if t == i + 1: r -= cost / entry
            daily[idx[t]] = daily.get(idx[t], 0.0) + r; prev = px
        T.append(dict(sig_date=idx[i], entry_date=idx[i + 1], sig=sig, below=bool(c[i] < sma[i]) if sma[i] == sma[i] else False, ok=bool(sma[i] == sma[i]), daily=daily, ret=sum(daily.values()))); i = max(i + 1, j)
    return T
def v4_series(T, fac):
    acc = {}
    for t in T:
        f = fac(t["below"], t["ok"])
        for d, r in t["daily"].items(): acc[d] = acc.get(d, 0.0) + r * f
    return base.clip(pd.Series(acc).sort_index())
def ger_state(dates):
    c = load("GER40")["close"]; d = (c.index + pd.Timedelta(hours=2)).normalize(); x = c.groupby(d).last(); x = x[x.index.dayofweek < 5]
    s = (x / x.rolling(200).mean() - 1).shift(1).reindex(pd.DatetimeIndex(dates).normalize(), method="ffill"); return (s < 0).fillna(False).values, s.notna().values
FA = lambda lo, ok: (0.5 if (ok and not lo) else 1.0); FB = lambda lo, ok: (0.5 if (ok and lo) else 1.0)
def v4_usdjpy_sma200(variant="A"): return v4_series(v4_trades("USDJPY"), FA if variant == "A" else FB)
def brk_ger40_sma200(variant="A"):
    r = donchian("GER40", 120, "trail2ATR"); lo, ok = ger_state(r.index); return r * np.array([(FA if variant == "A" else FB)(a, b) for a, b in zip(lo, ok)])
def stat(x, a, b):
    y = x[(x.index >= a) & (x.index <= b)]
    if len(y) < 3: return (0.0, 0.0, 0.0, 0)
    m = y.groupby(pd.PeriodIndex(y.index, freq="M")).sum(); return (round(float(y.mean() / y.std() * np.sqrt(252)), 2) if y.std() > 0 else 0.0, round(float(m.min()) * 100, 2), round(float(y.sum()) * 100, 2), int((y != 0).sum()))
def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return None if (len(a) < 5 or len(b) < 5) else round(float((a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))), 2)
if __name__ == "__main__":
    cum = int(sys.argv[1]); N = 4; rows = []; ref = []
    T = v4_trades("USDJPY"); b4 = v4_series(T, lambda lo, ok: 1.0); chk = base.v4_cell("USDJPY"); assert len(b4) == len(chk) and np.allclose(b4.values, chk.values), "v4 再実装が v4_cell と一致しない"
    g = donchian("GER40", 120, "trail2ATR"); glo, gok = ger_state(g.index)
    LEGS = (("USDJPY 逆張り v4", b4, v4_usdjpy_sma200("A"), v4_usdjpy_sma200("B")), ("GER40 ブレイクアウト", g, brk_ger40_sma200("A"), brk_ger40_sma200("B")))
    for nm, b_, A, B in LEGS:
        for vn, v in (("A 下 1.0・上 0.5", A), ("B 上 1.0・下 0.5", B)):
            s = {w: (stat(b_, a, z), stat(v, a, z)) for w, a, z in WIN}; ok = bool(s["IS"][1][0] > s["IS"][0][0] and s["OOS"][1][0] > s["OOS"][0][0] and s["IS"][1][1] >= s["IS"][0][1] and s["OOS"][1][1] >= s["OOS"][0][1])
            rows.append(dict(leg=nm, cell=vn, base_PRE=s["前窓"][0], var_PRE=s["前窓"][1], base_IS=s["IS"][0], var_IS=s["IS"][1], base_OOS=s["OOS"][0], var_OOS=s["OOS"][1], improved=ok))
    D = pd.DataFrame(rows); D.to_csv("results/q206_sma200_state_v4_usdjpy_ger40_breakout.csv", index=False); pd.set_option("display.width", 320); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
    print(f"Q206: cells={N} cum_before={cum} cum_after={cum + N} improved={int(D.improved.sum())}/{N}  (値 = Sharpe, 最悪月 %, 累積 %(単利), 損益のある日数 / 取引数)\nデータ末尾: v4 {b4.index.max().date()}・GER40 {g.index.max().date()}")
    print(D.to_string(index=False))
    # 参考: 取引ごとの状態別
    V = pd.DataFrame([dict(t=x["entry_date"], r=x["ret"], lo=x["below"], ok=x["ok"], sig=x["sig"]) for x in T]).set_index("t"); V = V[V.ok]
    Gd = pd.DataFrame({"r": g.values, "lo": glo, "ok": gok}, index=g.index); Gd = Gd[Gd.ok]
    def split(nm, X, sub=""):
        for wn, a, z in WIN + (("全期間", PRE0, END),):
            w = X[(X.index >= a) & (X.index <= z)]; l, h = w[w.lo].r, w[~w.lo].r
            ref.append(dict(leg=nm + sub, window=wn, n_below=len(l), mean_below_bps=round(float(l.mean()) * 1e4, 1) if len(l) else None, win_below=round(float((l > 0).mean()) * 100, 1) if len(l) else None, sd_below_bps=round(float(l.std()) * 1e4, 1) if len(l) > 1 else None,
                            n_above=len(h), mean_above_bps=round(float(h.mean()) * 1e4, 1) if len(h) else None, win_above=round(float((h > 0).mean()) * 100, 1) if len(h) else None, sd_above_bps=round(float(h.std()) * 1e4, 1) if len(h) > 1 else None, welch_t_below_minus_above=welch(l, h)))
    split("USDJPY 逆張り v4", V); split("USDJPY 逆張り v4", V[V.sig > 0], "(買いのみ)"); split("USDJPY 逆張り v4", V[V.sig < 0], "(売りのみ)"); split("GER40 ブレイクアウト", Gd)
    RF = pd.DataFrame(ref); RF.to_csv("results/q206_sma200_state_v4_usdjpy_ger40_breakout_ref.csv", index=False); print("\n== 参考: 取引ごと・状態別(コスト後) ==\n" + RF.to_string(index=False))
