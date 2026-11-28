# -*- coding: utf-8 -*-
"""Q53/Q54 共通: 日本の祝日(data_ext/jp_holidays_2016_2026.csv・jpholiday から生成、12/31〜1/3 の休場を追加)と JP 営業日。"""
import os, pandas as pd
from q_common import ROOT
H = pd.to_datetime(pd.read_csv(os.path.join(ROOT, "data_ext", "jp_holidays_2016_2026.csv"))["date"])
HOL = set(H.dt.normalize())
def is_jp_holiday(ts): return pd.Timestamp(ts).normalize() in HOL
def is_jp_bday(ts): ts = pd.Timestamp(ts).normalize(); return ts.dayofweek < 5 and ts not in HOL
def prev_jp_bday(ts):
    ts = pd.Timestamp(ts).normalize()
    while not is_jp_bday(ts): ts -= pd.Timedelta(days=1)
    return ts
def next_jp_bday(ts):
    ts = pd.Timestamp(ts).normalize() + pd.Timedelta(days=1)
    while not is_jp_bday(ts): ts += pd.Timedelta(days=1)
    return ts
