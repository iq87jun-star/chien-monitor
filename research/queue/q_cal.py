# -*- coding: utf-8 -*-
"""Q56〜Q59 共通: 各国祝日(data_ext/holidays_us_uk_au_nz_2016_2027.csv・holidays パッケージから生成)・BoJ 会合日・JP 祝日・合成ヘルパー。"""
import os, numpy as np, pandas as pd
from q_common import ROOT, base, IS0, IS1, OOS0, END
from q_jp import HOL as JPHOL, is_jp_holiday, is_jp_bday, prev_jp_bday, next_jp_bday
_h = pd.read_csv(os.path.join(ROOT, "data_ext", "holidays_us_uk_au_nz_2016_2027.csv")); _h["date"] = pd.to_datetime(_h["date"])
CAL = {k: set(g["date"].dt.normalize()) for k, g in _h.groupby("cal")}
BOJ = set(pd.to_datetime(pd.read_csv(os.path.join(ROOT, "data_ext", "events_boj.csv"))["date"]).dt.normalize())
def week_of(ts): ts = pd.Timestamp(ts).normalize(); return ts - pd.Timedelta(days=ts.dayofweek)   # 月曜
def in_week(ts, S): m = week_of(ts); return any((m + pd.Timedelta(days=k)) in S for k in range(5))
def obon(ts): ts = pd.Timestamp(ts); return ts.month == 8 and 11 <= ts.day <= 16
def jp_month_end(ts): ts = pd.Timestamp(ts).normalize(); return ts == prev_jp_bday(ts + pd.offsets.MonthEnd(0))
def gotobi(ts):
    ts = pd.Timestamp(ts).normalize()
    for d in [ts + pd.Timedelta(days=k) for k in range(0, 4)]:
        if (d.day in (5, 10, 15, 20, 25) or d == d + pd.offsets.MonthEnd(0)) and prev_jp_bday(d) == ts: return True
    return False
def first3(ts):
    ts = pd.Timestamp(ts).normalize(); d = ts.replace(day=1); k = 0
    while k < 3:
        if is_jp_bday(d):
            if d == ts: return True
            k += 1
        d += pd.Timedelta(days=1)
    return False
def mon7():
    parts = [base.mon_cell(p) for p in base.MON_FX]; idx = sorted(set().union(*[set(s.index) for s in parts]))
    out = pd.Series(0.0, index=pd.DatetimeIndex(idx))
    for s in parts: out = out.add(s.reindex(out.index).fillna(0.0) / 7.0, fill_value=0.0)
    return out
def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return (round(float(x.mean() / x.std() * np.sqrt(252)), 2) if x.std() > 0 else 0.0), round(float(m.min()) * 100, 2)
def improved(basis, var):
    bi, bo, gi, go = stats(basis, IS0, IS1), stats(basis, OOS0, END), stats(var, IS0, IS1), stats(var, OOS0, END)
    return dict(base_IS=bi, var_IS=gi, base_OOS=bo, var_OOS=go, ok=bool(gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]))
