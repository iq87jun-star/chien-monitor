# -*- coding: utf-8 -*-
"""診断(セル 0・2026-11-08 ユーザー「各通貨の急騰急落を調べられますか」): 各通貨・金の急変の統計(H1・q_common のデータ・2016-01〜2026-07)。
(1) 24h 変化(各時間足の始値 → 24 時間後の始値・重なりあり): σ・最悪/最良・|r|>2%, >3% の回数・尖度。(2) 1 時間足の変化: 最悪/最良・|r|>1% の回数。
(3) 週末の窓(金曜最終足終値 → 月曜最初の足始値)。(4) 最悪 1% の 24h 下落の曜日分布と、最悪 10 件の日付(円クロスは下落 = 円急騰)。
(5) Mon4(4 通貨等ウェイト・月曜 4〜10 UTC 建て 24h)のバスケット変化が、現行倍率 ×6 / ×8 / ×10 / ×12 で日次限度・最大 DD に当たる値幅を超えた月曜の回数(SL・日次ガード無しの素の値)。
使い方: cd research && python3 queue/q168_currency_tail_diag.py   出力: results/q168_tail_*.csv"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); ROOT = os.path.dirname(HERE)
from q_common import *
SYMS = ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY", "EURUSD", "GBPUSD", "AUDUSD", "USDCHF", "XAUUSD"]
WD = {0: "月", 1: "火", 2: "水", 3: "木", 4: "金", 5: "土", 6: "日"}
def kurt(x): z = (x - x.mean()) / x.std(); return float((z ** 4).mean() - 3)
rows, worst_rows, wd_rows = [], [], []
for s in SYMS:
    try: df = load(s)
    except Exception as e: print(s, "skip", e); continue
    o = df["open"]; o = o[o.index >= pd.Timestamp("2016-01-01")]
    r24 = (o.shift(-24) / o - 1).dropna(); r1 = (o.shift(-1) / o - 1).dropna()
    # 週末の窓: 金曜 (dow 4) の最終足終値 → 翌月曜最初の足始値
    c = df["close"][df.index >= pd.Timestamp("2016-01-01")]; d = c.index.normalize()
    fri_last = c.groupby(d).last(); fri_last = fri_last[fri_last.index.dayofweek == 4]
    mon_first = o.groupby(o.index.normalize()).first(); mon_first = mon_first[mon_first.index.dayofweek == 0]
    gap = pd.Series({m: mon_first[m] / fri_last[fri_last.index < m].iloc[-1] - 1 for m in mon_first.index if (fri_last.index < m).any()})
    rows.append(dict(sym=s, start=str(o.index.min().date()), sd24=round(r24.std() * 100, 2), worst24=round(r24.min() * 100, 2), best24=round(r24.max() * 100, 2), kurt24=round(kurt(r24), 1),
                     n24_gt2=int((r24.abs() > 0.02).sum()), n24_gt3=int((r24.abs() > 0.03).sum()), q24_005=round(r24.quantile(0.005) * 100, 2),
                     worst1h=round(r1.min() * 100, 2), best1h=round(r1.max() * 100, 2), n1h_gt1=int((r1.abs() > 0.01).sum()),
                     gap_sd=round(gap.std() * 100, 2), gap_worst=round(gap.min() * 100, 2), gap_best=round(gap.max() * 100, 2), gap_gt05=int((gap.abs() > 0.005).sum())))
    # 最悪 1% の 24h 変化(重なりを除くため日ごとに最悪値 1 つ)
    daily_worst = r24.groupby(r24.index.normalize()).min(); thr = daily_worst.quantile(0.01); bad = daily_worst[daily_worst <= thr]
    wd = bad.index.dayofweek.value_counts().reindex(range(5), fill_value=0)
    wd_rows.append(dict(sym=s, n=len(bad), **{WD[k]: int(v) for k, v in wd.items()}))
    for t, v in daily_worst.nsmallest(10).items():
        hour = r24[r24.index.normalize() == t].idxmin().hour
        worst_rows.append(dict(sym=s, date=str(t.date()), dow=WD[t.dayofweek], start_hour_utc=int(hour), ret24_pct=round(v * 100, 2)))
T = pd.DataFrame(rows); W = pd.DataFrame(wd_rows); X = pd.DataFrame(worst_rows)
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
print("=== 24h / 1h / 週末窓の尾(%) ==="); print(T.to_string(index=False))
print("\n=== 最悪 1% の 24h 下落の曜日分布(日数) ==="); print(W.to_string(index=False))
print("\n=== 最悪 10 件(24h・下落)==="); print(X.sort_values(["sym", "ret24_pct"]).to_string(index=False))
# (5) Mon4 バスケットの月曜 24h 変化と倍率別の限度超え
def mon24(sym):
    o = load(sym)["open"]; out = None
    for h in (4, 6, 8, 10):
        t = o.index[(o.index.dayofweek == 0) & (o.index.hour == h)]; t2 = t + pd.Timedelta(hours=24); ok = t2.isin(o.index); t, t2 = t[ok], t2[ok]
        r = pd.Series(o.reindex(t2).values / o.reindex(t).values - 1, index=t.normalize()); out = r if out is None else out + r
    return (out / 4).dropna()
B = sum(mon24(s) for s in ("GBPJPY", "EURJPY", "AUDJPY", "USDJPY")) / 4; B = B[B.index >= pd.Timestamp("2016-01-01")]
print(f"\n=== Mon4 バスケット(月曜 4〜10 UTC 建て 24h・コスト前)n={len(B)} 週・σ {B.std()*100:.2f}%・最悪 {B.min()*100:.2f}%({B.idxmin().date()})・最良 {B.max()*100:.2f}% ===")
lim = []
for mult, dll, mdd, acc in ((6.0, 0.04, 0.10, "FTMO 50k ×6"), (8.0, 0.028, 0.10, "パール ×8(Fintokei 日次 2.8%)"), (8.0, 0.028, 0.10, "トパーズ ×8"), (10.0, 0.04, 0.095, "宝くじ ×10"), (12.0, 0.028, 0.10, "ルビー ×12")):
    eq = B * mult; lim.append(dict(account=acc, mult=mult, 日次限度=dll, 最大DD=mdd, 日次限度超え_週=int((eq <= -dll).sum()), 最大DD超え_週=int((eq <= -mdd).sum()), 必要値幅_日次=round(-dll / mult * 100, 2), 必要値幅_MDD=round(-mdd / mult * 100, 2), 最悪週の損失=round(eq.min() * 100, 1)))
L = pd.DataFrame(lim); print(L.to_string(index=False))
print("\nMon4 バスケット 最悪 10 週:", [(str(t.date()), round(v * 100, 2)) for t, v in B.nsmallest(10).items()])
os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
T.to_csv(os.path.join(ROOT, "results", "q168_tail_summary.csv"), index=False); W.to_csv(os.path.join(ROOT, "results", "q168_tail_weekday.csv"), index=False); X.to_csv(os.path.join(ROOT, "results", "q168_tail_worst10.csv"), index=False); L.to_csv(os.path.join(ROOT, "results", "q168_tail_mon4_limits.csv"), index=False)
