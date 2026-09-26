# -*- coding: utf-8 -*-
"""docs/303 Q55(F12・改良系): 配備 7 構成のボラターゲット(直近 60 営業日の実現ボラの逆数で日次サイズ調整、平均レバ 1 に正規化、0.25〜4 でクリップ)。
基準: IS・OOS の両方でベース比 Sharpe 改善 かつ 最悪月が悪化しない。7 セル。使い方: python3 queue/q55_vol_target.py <累積>"""
import sys, os
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609")
import deployed_book as db
BD = pd.bdate_range("2016-01-01", "2026-08-31")
def on_bd(x): return x.groupby(x.index.normalize()).sum().reindex(BD).fillna(0.0)
def comp(legs):
    out = pd.Series(0.0, index=BD)
    for f, s, w in legs: out = out + on_bd(db.leg_series(f, s)) * w
    return out
MON4 = [("Mon","GBPJPY",.260),("Mon","EURJPY",.266),("Mon","AUDJPY",.215),("Mon","USDJPY",.258)]
C = {"Mon4": comp(MON4), "Mon2": comp([("Mon","GBPJPY",.537),("Mon","AUDJPY",.463)]),
     "A案 XAU+GBPJPY+NAS100": comp([("Hold","XAUUSD",.12),("Mon","GBPJPY",.632),("Mon","NAS100",.248)]),
     "Instant G": comp([("Mon","GBPJPY",.537*.8),("Mon","AUDJPY",.463*.8),("Mon","NAS100",.1),("Mon","US500",.1)]),
     "C6m": comp(db.BOOK["FTMO50k_531407058"]["legs"]), "RF5 A案": comp(db.BOOK["FTMO100k_531343523"]["legs"]),
     "非FX": comp(db.BOOK["FN100k_14166201"]["legs"])}
def stats(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]; m = x.groupby(pd.PeriodIndex(x.index, freq="M")).apply(lambda q: (1 + q).prod() - 1)
    return (round(float(x.mean() / x.std() * np.sqrt(252)), 2) if x.std() > 0 else 0.0), round(float(m.min()) * 100, 2)
cum = int(sys.argv[1]); R = Runner("Q55", cum, len(C), "results/q55_vol_target.csv"); rows = []
for nm, s in C.items():
    vol = s.rolling(60).std().shift(1); w = (1.0 / vol).replace([np.inf, -np.inf], np.nan)
    w = w / w[(w.index >= IS0) & (w.index <= IS1)].mean(); w = w.clip(0.25, 4.0).fillna(1.0)   # IS 平均レバ = 1 で正規化(OOS へ持ち越し)
    v = s * w; R.add("ボラターゲット(改良系)", nm, "60日実現ボラ逆数・IS平均1・0.25〜4", v[v != 0])
    bi, bo, gi, go = stats(s, IS0, IS1), stats(s, OOS0, END), stats(v, IS0, IS1), stats(v, OOS0, END)
    rows.append(dict(comp=nm, base_IS_sharpe=bi[0], vt_IS_sharpe=gi[0], base_OOS_sharpe=bo[0], vt_OOS_sharpe=go[0], base_IS_worst=bi[1], vt_IS_worst=gi[1], base_OOS_worst=bo[1], vt_OOS_worst=go[1],
                     improved=bool(gi[0] > bi[0] and go[0] > bo[0] and gi[1] >= bi[1] and go[1] >= bo[1]), mean_w_OOS=round(float(w[w.index >= OOS0].mean()), 2)))
R.finish(); pd.set_option("display.width", 300); print("\n== Q55 改良判定 ==\n" + pd.DataFrame(rows).to_string(index=False))
