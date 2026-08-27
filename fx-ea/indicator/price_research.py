#!/usr/bin/env python3
"""GogoJungle インジケーター価格分布(実測・2026-08-27 取得)."""
import statistics as st

# 新着(不特定の出品者が実際に付けている価格)
NEW = [
 ("継続力インジケーター PRO MT4", 5980, "signal"),
 ("Elliott Wave Auto Detector", 3980, "signal"),
 ("MA Trend Signal", 1980, "signal"),
 ("MultiChart Symbol Sync MT5", 1980, "util"),
 ("継続力インジケーター PRO MT5", 5980, "signal"),
 ("Sショット(スクリーンショット)", 29800, "util"),
 ("Research_TrendLine_Pro", 39800, "signal"),
 ("SevenTF Triple MA Gradient", 980, "signal"),
 ("Auto Exit Monitor", 2980, "util"),
 ("ICT Core", 7988, "signal"),
 ("CP_POW 変化率ヒートマップ", 1980, "util"),
 ("RSI-ONE", 20000, "signal"),
 ("BB移動平均線 乖離率", 3500, "signal"),
 ("ExodiaFlow v1.40", 23800, "signal"),
 ("Zone Scope MTF (MT4)", 9800, "signal"),
 ("Zone Scope MTF (MT5)", 9800, "signal"),
 ("Alice_BlindTrainer", 980, "util"),
 ("FX Strategy Lab", 14800, "util"),
 ("決済おまかせくん", 14800, "util"),
 ("M5 EMA CROSS TREND v2.2", 4980, "signal"),
 ("自動スクリーンショット撮影", 3000, "util"),
 ("MrEnvelopeTouchSign", 400, "signal"),
 ("トレンドアロー Pro", 39800, "signal"),
 ("ストラクチャースコープ", 39800, "signal"),
 ("ゴールドスナイパー", 39800, "signal"),
 ("X CODE VISION MT5 PRO DX", 39800, "signal"),
 ("ロット自動計算オールインワン", 5000, "util"),
 ("ARXELION", 59800, "signal"),
]

# 売れ筋ランキング上位
RANK = [58000, 78000, 78000, 98800, 77800, 125000, 38980, 49800, 69800, 69800]

# セール対象の「通常価格」
SALE_LIST = [29800, 39800, 29800, 70000, 6980, 23800, 12800, 49800, 69800, 12000]
SALE_NOW  = [19800, 15000, 7980, 49800, 2980, 19800, 9800, 39800, 39179, 6900]

def show(name, xs):
    xs = sorted(xs)
    print(f"{name:<26} n={len(xs):>3}  中央値 {st.median(xs):>7,.0f}円   "
          f"平均 {st.mean(xs):>7,.0f}円   {min(xs):,}〜{max(xs):,}円")

print("="*94)
print("GogoJungle インジケーター 価格分布(2026-08-27 実測)")
print("="*94)
show("新着 全体", [p for _, p, _ in NEW])
show("  うち シグナル系", [p for _, p, k in NEW if k == "signal"])
show("  うち ユーティリティ系", [p for _, p, k in NEW if k == "util"])
print()
show("売れ筋ランキング上位", RANK)
show("セール対象の通常価格", SALE_LIST)
show("セール中の実売価格", SALE_NOW)

print("\n" + "="*94)
print("シグナル系の価格帯(新着)")
print("="*94)
sig = sorted([(p, n) for n, p, k in NEW if k == "signal"])
for p, n in sig:
    print(f"  {p:>7,}円   {n}")

print("\n" + "="*94)
print("ユーティリティ系の価格帯(新着)")
print("="*94)
uti = sorted([(p, n) for n, p, k in NEW if k == "util"])
for p, n in uti:
    print(f"  {p:>7,}円   {n}")

print("\n" + "="*94)
print("価格帯ごとの件数(新着28件)")
print("="*94)
bands = [(0,1999,"〜1,999"),(2000,4999,"2,000〜4,999"),(5000,9999,"5,000〜9,999"),
         (10000,19999,"10,000〜19,999"),(20000,29999,"20,000〜29,999"),
         (30000,49999,"30,000〜49,999"),(50000,999999,"50,000〜")]
for lo, hi, lab in bands:
    c = [p for _, p, _ in NEW if lo <= p <= hi]
    print(f"  {lab:<16} {len(c):>2}件  {'#'*len(c)}")

print("\n" + "="*94)
print("最頻価格")
print("="*94)
from collections import Counter
for p, c in Counter([p for _, p, _ in NEW]).most_common(6):
    if c >= 2: print(f"  {p:>7,}円  ... {c}件")
