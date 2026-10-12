# -*- coding: utf-8 -*-
"""docs/358 Q138(新規 40 セル): Q137 の型を銘柄別に — 各市場の先物満期週(E1 前半・E3 満期後)8 指数 + 現地の季節(S1/S2 HK50 春節・S3/S4 AUS200 会計年度末)。
定義は docs/358 §1(結果前に固定)。価格は H1 バー始値(欠けたら 3 時間以内の次のバー)。
使い方: cd research && python3 queue/q138_local_calendar.py <累積セル数>"""
import sys
from q_common import *
from q137_jp_calendar import at, event_stats
HOL = pd.concat([pd.read_csv(os.path.join(ROOT, "data_ext", f)) for f in ("holidays_us_uk_au_nz_2016_2027.csv", "holidays_cn_hk_2016_2027.csv")])
HOL["date"] = pd.to_datetime(HOL["date"])
def bdays(cal):
    h = set(HOL[HOL["cal"] == cal]["date"].dt.normalize())
    return pd.DatetimeIndex([d for d in pd.date_range("2016-01-01", "2026-08-31") if d.dayofweek < 5 and d not in h])
# 銘柄 → (祝日表, 寄り UTC, 引け UTC, 満期規則)
MKT = {"US500": ("NYSE", 14, 20, "fri3"), "NAS100": ("NYSE", 14, 20, "fri3"), "US30": ("NYSE", 14, 20, "fri3"),
       "GER40": ("UK", 8, 16, "fri3"), "EUSTX50": ("UK", 8, 16, "fri3"), "UK100": ("UK", 8, 16, "fri3"),
       "HK50": ("HK", 2, 8, "hk"), "AUS200": ("AU", 0, 6, "thu3")}
def expiries(BD, rule):
    out = []
    for m in pd.period_range("2016-01", "2026-08", freq="M"):
        mb = BD[(BD.year == m.year) & (BD.month == m.month)]
        if len(mb) < 2: continue
        if rule == "hk": out.append(mb[-2]); continue
        wd = 4 if rule == "fri3" else 3; d = [x for x in pd.date_range(m.start_time, m.end_time.normalize()) if x.dayofweek == wd][2]
        while d not in BD: d -= pd.Timedelta(days=1)
        out.append(d)
    return out
def shift(BD, d, k):
    i = BD.get_loc(d); j = i + k
    return BD[j] if 0 <= j < len(BD) else None
def at_close(o, d, ho, hc):
    """引け: hc のバー始値。半日取引(春節前日・米国の短縮日)で hc のバーが無ければ、その日の ho〜hc にある最後のバーの始値。"""
    v = at(o, d, hc)
    if not np.isnan(v): return v
    x = o[(o.index >= d + pd.Timedelta(hours=ho)) & (o.index <= d + pd.Timedelta(hours=hc))]
    return float(x.iloc[-1]) if len(x) else np.nan
def run(sym, wins, dir_):
    o = load(sym)["open"]; t, p0, p1 = [], [], []
    for d0, h0, d1, h1 in wins:
        t.append(d0 + pd.Timedelta(hours=h0)); p0.append(at(o, d0, h0)); p1.append(at_close(o, d1, h0, h1))   # 窓はすべて現地の寄り h0 で建てる
    return trades(sym, t, p0, np.full(len(t), dir_), p1)
def expiry_windows(sym):
    cal, ho, hc, rule = MKT[sym]; BD = bdays(cal); E1, E3 = [], []
    for x in expiries(BD, rule):
        wk = BD[(BD >= x - pd.Timedelta(days=x.dayofweek)) & (BD < x)]
        if len(wk) >= 1: E1.append((wk[0], ho, wk[-1], hc))
        a, b = shift(BD, x, 1), shift(BD, x, 5)
        if a is not None and b is not None: E3.append((a, ho, b, hc))
    return E1, E3
def season_windows():
    HKB = bdays("HK"); AUB = bdays("AU"); S = {k: [] for k in ("S1", "S2", "S3", "S4")}
    for d in HOL[(HOL["cal"] == "HK") & (HOL["name"] == "農曆年初一")]["date"]:
        last = HKB[HKB < d]; nxt = HKB[HKB > d]
        if len(last) >= 10 and len(nxt) >= 5:
            S["S1"].append((last[-10], 2, last[-1], 8)); S["S2"].append((nxt[0], 2, nxt[4], 8))
    for y in range(2016, 2027):
        jun = AUB[(AUB.year == y) & (AUB.month == 6)]; jul = AUB[(AUB.year == y) & (AUB.month == 7)]
        if len(jun) >= 10: S["S3"].append((jun[-10], 0, jun[-1], 6))
        if len(jul) >= 10: S["S4"].append((jul[0], 0, jul[9], 6))
    return S
if __name__ == "__main__":
    cum = int(sys.argv[1]); R = Runner("Q138", cum, 40, "results/q138_local_calendar.csv"); ev = []
    def add(fam, sym, spec, wins, start):
        for d, nm in ((1, "L"), (-1, "S")):
            r = run(sym, wins, d); R.add(fam, sym, f"{spec} {nm}", r)
            ev.append(dict(cell=f"{spec} {nm}", symbol=sym, **{f"all_{a}": b for a, b in event_stats(r, start).items()},
                           pre_mean=round(r[r.index < IS0].mean() * 1e4, 1), is_mean=round(r[(r.index >= IS0) & (r.index <= IS1)].mean() * 1e4, 1), oos_mean=round(r[r.index >= OOS0].mean() * 1e4, 1)))
    for sym in MKT:
        selfcheck(sym, load(sym)); E1, E3 = expiry_windows(sym); st0 = load(sym).index.min()
        add("E. 満期週", sym, "E1 満期週の前半", E1, st0); add("E. 満期週", sym, "E3 満期後 5 営業日", E3, st0)
    S = season_windows()
    add("S. 季節", "HK50", "S1 春節前 10 営業日", S["S1"], PRE0); add("S. 季節", "HK50", "S2 春節明け 5 営業日", S["S2"], PRE0)
    add("S. 季節", "AUS200", "S3 6 月の最終 10 営業日", S["S3"], PRE0); add("S. 季節", "AUS200", "S4 7 月の最初の 10 営業日", S["S4"], PRE0)
    R.finish(); E = pd.DataFrame(ev); E.to_csv("results/q138_local_calendar_events.csv", index=False); pd.set_option("display.width", 250)
    print("\n== イベント単位(全期間 n・平均 bps・t・勝率 / 前窓・IS・OOS の平均 bps)==\n" + E.to_string(index=False))
