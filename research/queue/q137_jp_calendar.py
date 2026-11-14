# -*- coding: utf-8 -*-
"""docs/357 Q137(新規 18 セル): 日本固有の暦 — SQ(第 2 金曜)・配当の権利取り/権利落ち後(3・9 月)・期末/期初の資金フロー(JP225・USDJPY)。
定義は docs/357 §1(結果前に固定)。価格は H1 バー始値(欠けたら 3 時間以内の次のバー)。00 UTC = 東京の寄り、06 UTC ≈ 東京の引け。
使い方: cd research && python3 queue/q137_jp_calendar.py <累積セル数>"""
import sys
from q_common import *
from q_jp import is_jp_bday
BD = pd.DatetimeIndex([d for d in pd.date_range("2016-01-01", "2026-08-31") if is_jp_bday(d)])
def bd_shift(d, k):
    i = BD.get_loc(pd.Timestamp(d).normalize()); j = i + k
    return BD[j] if 0 <= j < len(BD) else None
def at(o, d, h):
    """日付 d の h UTC のバー始値(欠けたら 3 時間以内の次のバー)。"""
    if d is None: return np.nan
    t = pd.Timestamp(d).normalize() + pd.Timedelta(hours=h); i = o.index.searchsorted(t)
    return float(o.iloc[i]) if i < len(o) and o.index[i] - t <= pd.Timedelta(hours=3) else np.nan
def sq_days():
    out = []
    for m in pd.period_range("2016-01", "2026-08", freq="M"):
        d = pd.Timestamp(m.start_time); fri = [x for x in pd.date_range(d, d + pd.offsets.MonthEnd(0)) if x.dayofweek == 4][1]
        while not is_jp_bday(fri): fri -= pd.Timedelta(days=1)
        out.append(fri)
    return out
def month_bdays(y, mo): return BD[(BD.year == y) & (BD.month == mo)]
def div_days():
    """(権利付最終日, 権利落ち日) の 3・9 月。T+2 移行(2019-07-16)前は確定日の 3 営業日前が付最終日。"""
    out = []
    for y in range(2016, 2027):
        for mo in (3, 9):
            b = month_bdays(y, mo)
            if len(b) == 0: continue
            rec = b[-1]; lag = 3 if rec < pd.Timestamp("2019-07-16") else 2; cum = bd_shift(rec, -lag); out.append((cum, bd_shift(cum, 1)))
    return out
def windows():
    """セル名 → [(建て日, 建て時刻, 決済日, 決済時刻)]。"""
    W = {k: [] for k in ("A1", "A2", "A3", "A4", "B1", "B2", "C1", "C2")}
    for sq in sq_days():
        wk = BD[(BD >= sq - pd.Timedelta(days=sq.dayofweek)) & (BD <= sq)]; eve = bd_shift(sq, -1)
        if len(wk) >= 2 and eve is not None and eve >= wk[0]: W["A1"].append((wk[0], 0, eve, 6))
        if eve is not None: W["A2"].append((eve, 6, sq, 0))
        W["A3"].append((sq, 0, sq, 6))
        if bd_shift(sq, 5) is not None: W["A4"].append((bd_shift(sq, 1), 0, bd_shift(sq, 5), 6))
    for cum, ex in div_days():
        if bd_shift(cum, -10) is not None: W["B1"].append((bd_shift(cum, -10), 6, cum, 6))
        if ex is not None and bd_shift(ex, 5) is not None: W["B2"].append((ex, 0, bd_shift(ex, 5), 6))
    for y in range(2016, 2027):
        for mo in (3, 9):
            b = month_bdays(y, mo)
            if len(b) >= 6: W["C1"].append((b[-6], 6, b[-1], 6))
        for mo in (4, 10):
            b = month_bdays(y, mo)
            if len(b) >= 5: W["C2"].append((b[0], 0, b[4], 6))
    return W
def series(sym, wins, d):
    o = load(sym)["open"]; t, p0, p1 = [], [], []
    for d0, h0, d1, h1 in wins:
        t.append(pd.Timestamp(d0) + pd.Timedelta(hours=h0)); p0.append(at(o, d0, h0)); p1.append(at(o, d1, h1))
    return trades(sym, t, p0, np.full(len(t), d), p1)
def event_stats(r, a):
    x = r[r.index >= a]
    if len(x) < 2: return dict(n=len(x), mean_bps=np.nan, t=np.nan, win=np.nan)
    return dict(n=len(x), mean_bps=round(x.mean() * 1e4, 1), t=round(x.mean() / x.std(ddof=1) * np.sqrt(len(x)), 2), win=round((x > 0).mean(), 2))
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q137", cum, 18, "results/q137_jp_calendar.csv"); W = windows(); ev = []
    for s in ("JP225", "USDJPY"): selfcheck(s, load(s))
    CELLS = [("A. SQ", "A1", "SQ 週の前半(週初 00 → SQ 前日 06 UTC)", "JP225"), ("A. SQ", "A2", "SQ 前夜(前日 06 → SQ 日 00 UTC)", "JP225"),
             ("A. SQ", "A3", "SQ 日の場中(00 → 06 UTC)", "JP225"), ("A. SQ", "A4", "SQ 後(翌営業日 00 → 5 営業日目 06 UTC)", "JP225"),
             ("B. 配当", "B1", "権利取り(付最終日の 10 営業日前 06 → 付最終日 06 UTC)", "JP225"), ("B. 配当", "B2", "権利落ち後(落ち日 00 → +5 営業日 06 UTC)", "JP225"),
             ("C. 期末期初", "C1", "3・9 月の最終 6 営業日(06 → 06 UTC)", "USDJPY"), ("C. 期末期初", "C2", "4・10 月の最初の 5 営業日(00 → 06 UTC)", "USDJPY"),
             ("C. 期末期初", "C2", "4・10 月の最初の 5 営業日(00 → 06 UTC)", "JP225")]
    for fam, k, spec, sym in CELLS:
        for d, nm in ((1, "L"), (-1, "S")):
            r = series(sym, W[k], d); R.add(fam, sym, f"{k} {spec} {nm}", r)
            pre_start = PRE0 if sym == "USDJPY" else pd.Timestamp("2018-01-01")
            ev.append(dict(cell=f"{k} {nm}", symbol=sym, **{f"all_{a}": b for a, b in event_stats(r, pre_start).items()},
                           pre_mean=round(r[r.index < IS0].mean() * 1e4, 1), is_mean=round(r[(r.index >= IS0) & (r.index <= IS1)].mean() * 1e4, 1), oos_mean=round(r[r.index >= OOS0].mean() * 1e4, 1)))
    R.finish(); E = pd.DataFrame(ev); E.to_csv("results/q137_jp_calendar_events.csv", index=False)
    print("\n== イベント単位(全期間 n・平均 bps・t・勝率 / 前窓・IS・OOS の平均 bps)==\n" + E.to_string(index=False))
