# -*- coding: utf-8 -*-
"""docs/322 §5m Q136(診断・セル 0): Mon4 集中の同時ドローダウン実測。全口座の帳簿(docs/349 §8e・§8f の案を採った設定)を円換算で合算し、
10.6 年(2016-01〜2026-07)の日次合算損益の分布・最悪 5 日・全口座が同じ日に負けた回数、および同じ経路(同じ日付の再標本化)で 1 年内に同時失格する口座数の分布を出す。
使い方: cd research && python3 queue/q136_mon4_concentration_dd.py"""
import sys, os, datetime as dt
sys.path.insert(0, "queue"); import pandas as pd, q129_cfd_prop_expansion as q129
q129.CAL = pd.date_range(pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29"), freq="D")
from q_common import *
base.DATA = os.path.join(ROOT, "data_202609"); import deployed_book as db
from q129_cfd_prop_expansion import on_cal, roll5
L = lambda f, s: on_cal(db.leg_series(f, s))
mon4 = sum(L("Mon", s) * 0.25 for s in ("AUDJPY", "EURJPY", "GBPJPY", "USDJPY")); bplan = L("Mon", "GBPJPY") * 0.374 + L("Mon", "AUDJPY") * 0.322 + L("v4", "USDJPY") * 0.304
roll = on_cal(roll5()); holdxau = on_cal(base.hold_cell("XAUUSD")); nas = on_cal(base.mon_cell("NAS100")); spx = on_cal(base.mon_cell("US500"))
hold_uw = L("Hold", "UK100") * 0.491 + L("Hold", "WTI") * 0.153; mon3 = L("Mon", "EURJPY") * 0.333 + L("Mon", "USDJPY") * 0.333 + L("Mon", "NZDJPY") * 0.334
A = (holdxau + L("Mon", "GBPJPY") + nas) / 3; instG = L("Mon", "GBPJPY") * 0.537 * 4 + L("Mon", "AUDJPY") * 0.463 * 4 + (nas + spx) * 0.125 * 4
FX = 158.0
# 口座: (名前, 日次リターン系列(口座比), 残高 円, 床 %, 日次ガード)
ACC = [("FTMO 50k 521100397 Mon4 ×5", mon4 * 5, 50000 * FX, 0.10, 0.04), ("FTMO 50k 531407058 Mon4 ×5", mon4 * 5, 50000 * FX, 0.10, 0.04), ("パール B案 ×6", bplan * 6, 5_000_000, 0.10, 0.028),
       ("14074882 Mon3 ×4 + HoldXAU", mon3 * 4 + holdxau * 0.4, 100000 * FX, 0.10, 0.04), ("Instant G ×4", instG, 20000 * FX, 0.06, 0.04),
       ("1-Step EA9 ×3 + Mon4 ×2", A * 3 + mon4 * 2, 100000 * FX, 0.10, 0.024), ("宝くじ Mon4 ×10 + HoldXAU 0.9", mon4 * 10 + holdxau * 0.9, 100000 * FX, 0.095, 0.04),
       ("FN 14166201 Hold UK100/WTI ×2.22 + Roll ×4.5", hold_uw * 2.22 + roll * 4.5, 100000 * FX, 0.10, 0.04), ("ルビー B案 ×10", bplan * 10, 10_000_000, 0.10, 0.028), ("トパーズ Mon4 ×8", mon4 * 8, 35_000_000, 0.10, 0.028)]
P0, P1 = pd.Timestamp("2016-01-04"), pd.Timestamp("2026-07-29")
M = pd.concat({nm: (c.clip(lower=-dll) * bal)[(c.index >= P0) & (c.index <= P1)] for nm, c, bal, mdd, dll in ACC}, axis=1).fillna(0.0)
tot = M.sum(axis=1); balsum = sum(a[2] for a in ACC)
print(f"合計額面 {balsum/1e8:.2f} 億円・日次合算損益(ガード後)の σ {tot.std()/1e4:,.0f} 万円({tot.std()/balsum*100:.2f}%)・最悪日 {tot.min()/1e4:,.0f} 万円({tot.min()/balsum*100:.2f}%)")
w = tot.nsmallest(5); print("最悪 5 日:"); 
for d, v in w.items(): print(f"  {d.date()} {v/1e4:,.0f} 万円 ({v/balsum*100:.2f}%)  負けた口座 {(M.loc[d] < 0).sum()}/10  曜日 {d.day_name()}")
mon = M[M.index.dayofweek == 1]   # Mon ショットは火曜の決済で記録される(o2o の index は建て日 = 月曜。念のため両方)
mon0 = M[M.index.dayofweek == 0]
neg_all = (M.lt(0).sum(axis=1) >= 8).sum(); print(f"10 口座中 8 口座以上が同じ日に負けた日: {neg_all} 日 / {len(M)} 日(月曜 {(mon0.lt(0).sum(axis=1) >= 8).sum()} 日)")
print(f"合算の月次損益: 最悪月 {tot.groupby(pd.PeriodIndex(tot.index, freq='M')).sum().min()/1e4:,.0f} 万円・年率平均 {tot.groupby(tot.index.year).sum().mean()/1e4:,.0f} 万円")
# 同時失格(同じ日付の再標本化・1 年・静的床)
rng = np.random.default_rng(36); N, BLOCK, days = 20000, 5, 250
R = np.stack([np.asarray(c.clip(lower=-dll)[(c.index >= P0) & (c.index <= P1)].reindex(M.index).fillna(0.0).values, float) for nm, c, bal, mdd, dll in ACC], axis=1)   # (T, 10)
nb = len(R) - BLOCK + 1; stt = rng.integers(0, nb, size=(N, days // BLOCK + 1)); idx = (stt[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(N, -1)[:, :days]
E0 = np.array([1.04, 1.03, 1.03, 0.95, 0.99, 1.0, 0.93, 1.04, 1.0, 0.99]); FL = 1 - np.array([a[3] for a in ACC])
e = E0[None, :] * np.cumprod(1 + R[idx], axis=1); br = (e <= FL[None, None, :]).any(axis=1); k = br.sum(axis=1)
print("1 年内の同時失格(同じ相場経路): 口座数の分布 " + " ".join(f"{i}本:{(k==i).mean()*100:.1f}%" for i in range(0, 11)))
print(f"期待失格数 {k.mean():.2f} 本・3 本以上 {(k>=3).mean()*100:.1f}%・5 本以上 {(k>=5).mean()*100:.1f}%・独立なら 3 本以上 {1 - 0:.0f}(参考: 各口座の失格率 " + " ".join(f"{br[:, i].mean()*100:.0f}%" for i in range(10)) + ")")
pd.DataFrame(dict(account=[a[0] for a in ACC], fail_1y=br.mean(axis=0))).to_csv("results/q136_mon4_concentration_dd.csv", index=False)
