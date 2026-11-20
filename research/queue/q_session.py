# -*- coding: utf-8 -*-
"""先物プロップ向け「セッション版」の共通関数(docs/344〜)。CME の取引日 = 前日 22 UTC(18:00 ET、冬は 23 UTC)の再開から当日 20 UTC(16:00 ET)まで。
session(sym, dow, h_in, h_out=20, direction=+1): dow = 決済日の曜日(0=月)。h_in は "open"(前日 22 UTC 以降の最初のバー)または当日の時刻(0, 7, 13 ...)。"""
from q_common import *
def session(sym, dow, h_in, h_out=20, direction=1.0):
    o = load(sym)["open"]; days = pd.DatetimeIndex(sorted(set(o.index[(o.index.dayofweek == dow) & (o.index.hour == h_out)].normalize())))
    t_in, p_in, p_out = [], [], []
    for d in days:
        if h_in == "open":
            w = o[(o.index >= d - pd.Timedelta(hours=2)) & (o.index < d + pd.Timedelta(hours=2))]
            if len(w) == 0: continue
            ti = w.index[0]
        else:
            ti = d + pd.Timedelta(hours=int(h_in))
            if ti not in o.index: continue
        po = o.get(d + pd.Timedelta(hours=h_out))
        if po is None or np.isnan(po): continue
        t_in.append(ti); p_in.append(o[ti]); p_out.append(po)
    r = trades(sym, pd.DatetimeIndex(t_in), np.array(p_in), np.full(len(t_in), direction), np.array(p_out)); r.index = r.index.normalize(); return r
