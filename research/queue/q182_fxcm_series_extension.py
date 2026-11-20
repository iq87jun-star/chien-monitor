# -*- coding: utf-8 -*-
"""docs/244 Q182(工学・セル 0・2026-11-12 登録「登録して実行してください」): FXCM 公開ローソク足による主要通貨ペアの系列継ぎ足しの検証。
 (c) 重複期間(FXCM の 2026 年は 20〜31 週が欠けているため 2026-08-09〜08-31)の H1 リターン相関・中値の差・スプレッド差、2026-09〜の本数と欠損。
 (d) 継ぎ足し系列で月曜帳簿(Mon4 / Mon3 / Mon2)の 2026-09・10 月の月次損益(deployed_book.mon_cell_h1 と同じ式: 月曜 4/6/8/10 UTC 建て → 24h・往復 3pip)。
     実口座(ops_inbox の positions.csv・RFIMon_* / RFMon_* の円クロス)の同月損益と符号を突き合わせる(記述のみ)。
使い方: cd research && python3 fetch_fxcm.py 2026 20 47 && python3 -W ignore queue/q182_fxcm_series_extension.py"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT); sys.path.insert(0, HERE); os.chdir(ROOT)
import numpy as np, pandas as pd
import q_common as q
from fetch_fxcm import PAIRS, CUT, load_fxcm, load_duka, load_spliced
rows = []
for s in PAIRS:
    try: fb, fa = load_fxcm(s), load_fxcm(s, True)
    except FileNotFoundError: continue
    db_ = load_duka(s); db_ = db_[db_.volume > 0]; pip = 0.01 if s.endswith("JPY") else 0.0001
    try: da = load_duka(s, True); da = da[da.volume > 0]
    except FileNotFoundError: da = None
    ov = fb.index[(fb.index <= CUT)]; j = pd.DataFrame({"f": fb.close, "d": db_.close}).dropna(); j = j[j.index <= CUT]
    aft = fb[fb.index > CUT]; days = pd.bdate_range("2026-09-01", aft.index.max().normalize())
    per_day = aft.groupby(aft.index.normalize()).size().reindex(days).fillna(0)
    rows.append(dict(pair=s, overlap_bars=len(j), corr_h1_ret=round(float(np.log(j.f).diff().corr(np.log(j.d).diff())), 4), med_abs_diff_pips=round(float((j.f - j.d).abs().median() / pip), 2),
                     spread_fxcm_pips=round(float(((fa.close - fb.close)[fb.index <= CUT]).median() / pip), 2), spread_duka_pips=(round(float((da.close - db_.close).reindex(j.index).median() / pip), 2) if da is not None else None),
                     after_from=str(aft.index.min())[:13], after_to=str(aft.index.max())[:13], after_bars=len(aft), weekdays=len(days), weekdays_lt20bars=int((per_day < 20).sum())))
V = pd.DataFrame(rows); V.to_csv("results/q182_fxcm_overlap.csv", index=False); pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30); print(V.to_string(index=False))
# (d) 月曜帳簿の 2026-09・10 月
def mon_h1(sym, hours=(4, 6, 8, 10)):
    o = load_spliced(sym); o = o[(o.volume > 0)]["open"]; out = None
    for h in hours:
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]; t2 = t + pd.Timedelta(hours=24); ok = t2.isin(o.index); t, t2 = t[ok], t2[ok]
        r = q.trades(sym, t, o.reindex(t).values, np.ones(len(t)), o.reindex(t2).values); r.index = r.index.normalize(); out = r if out is None else out.add(r, fill_value=0.0)
    return (out / len(hours)).sort_index()
BOOKS = {"Mon4(4 通貨等分)": {"AUDJPY": .25, "EURJPY": .25, "GBPJPY": .25, "USDJPY": .25}, "Mon3(14074882 形)": {"EURJPY": .333, "USDJPY": .333, "NZDJPY": .334}, "Mon2 instG(11988011 形)": {"GBPJPY": .537, "AUDJPY": .463}}
LEG = {s: mon_h1(s) for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY", "NZDJPY")}; mrows = []
for nm, w in BOOKS.items():
    b = pd.concat([LEG[s] * wt for s, wt in w.items()], axis=1).dropna().sum(axis=1); b = b[b.index >= "2026-06-01"]
    m = b.groupby(b.index.to_period("M")).agg(["sum", "count"])
    for per, r in m.iterrows(): mrows.append(dict(book=nm, month=str(per), mondays=int(r["count"]), book_ret_pct=round(float(r["sum"]) * 100, 3), source="Dukascopy" if per <= pd.Period("2026-08") else "FXCM"))
M = pd.DataFrame(mrows)
# 実口座の円クロス月曜レグ(ドル建て損益 ÷ 初期残高)
def actual(acc, init, pat):
    p = f"ops_inbox/{acc}/positions.csv"
    if not os.path.exists(p): return {}
    cols = ["ot", "ticket", "sym", "side", "lots", "op", "sl", "tp", "ct", "cp", "swap", "comm", "profit", "comment", "magic", "slhit", "x"]
    d = pd.read_csv(p, header=None, names=cols, encoding="utf-8-sig"); d = d[pd.to_numeric(d.lots, errors="coerce").notna()]
    d = d[d.comment.astype(str).str.contains(pat) & d.sym.astype(str).str.endswith("JPY")]; d["ot"] = pd.to_datetime(d.ot, format="%Y.%m.%d %H:%M:%S")
    g = (pd.to_numeric(d.profit) + pd.to_numeric(d.swap).fillna(0)).groupby(d.ot.dt.to_period("M")).sum() / init * 100; n = d.groupby(d.ot.dt.to_period("M")).size()
    return {str(k): (round(float(v), 3), int(n[k])) for k, v in g.items()}
A = {"Mon2 instG(11988011 形)": actual("11988011", 20000, "RFIMon_"), "Mon3(14074882 形)": actual("14074882", 100000, "RFMon_")}
M["actual_acct_pct"] = [A.get(b, {}).get(mo, (None, None))[0] for b, mo in zip(M.book, M.month)]; M["actual_trades"] = [A.get(b, {}).get(mo, (None, None))[1] for b, mo in zip(M.book, M.month)]
M["book_x4_pct"] = (M.book_ret_pct * 4).round(2)        # 配備倍率 ×4(Mon2・Mon3)での口座 % の目安
M.to_csv("results/q182_mon_books_2026h2.csv", index=False); print(); print(M.to_string(index=False))
