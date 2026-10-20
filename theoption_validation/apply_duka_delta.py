#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dukascopy 1時間足CSVの差分更新 (2026-10-20作成)
Colabで1セル実行すると、Drive上の forex_ml/dukascopy_hourly/{PAIR}_hourly.csv 16本を
2026-09-30まで延長する。差分はGitHub(claude/zaption-check-m776m7ブランチ)から取得。

使い方 (Colabセル):
  from google.colab import drive; drive.mount('/content/drive')
  !curl -sO https://raw.githubusercontent.com/iq87jun-star/chien-monitor/claude/zaption-check-m776m7/theoption_validation/apply_duka_delta.py
  %run apply_duka_delta.py

安全設計: 置換前に {PAIR}_hourly.csv.bak を同フォルダに残す。再実行しても結果は同じ(冪等)。
検証: 2026-05-01より前の行はそのまま、以降を差分(Dukascopy再取得・検品済み)で全面置換。
既知の差異: 2026-05-12 12:00 EURGBP低値の0.2pip修正(Dukascopy側の履歴修正)と、
旧CSV取得時の配信ラグで欠けていた2026-05-24深夜〜25朝の最大7本の補完。
"""
import csv, gzip, io, os, shutil, urllib.request

DIR = '/content/drive/MyDrive/forex_ml/dukascopy_hourly'
RAW = ('https://raw.githubusercontent.com/iq87jun-star/chien-monitor/'
       'claude/zaption-check-m776m7/theoption_validation/duka_delta/')
PAIRS = ("EURGBP USDCHF GBPJPY AUDJPY GBPUSD NZDJPY CADJPY EURJPY AUDUSD CHFJPY "
         "USDJPY EURUSD NZDUSD USDCAD EURAUD GBPAUD").split()
CUT = '2026-05-01'

for p in PAIRS:
    path = os.path.join(DIR, f'{p}_hourly.csv')
    with urllib.request.urlopen(RAW + f'{p}_delta_20260501_20260930.csv.gz', timeout=60) as r:
        delta = list(csv.reader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(r.read())), encoding='utf-8')))
    rows = list(csv.reader(open(path, encoding='utf-8-sig')))
    header, body = rows[0], [r for r in rows[1:] if r[0] < CUT]
    merged = [header] + body + delta[1:]
    shutil.copy(path, path + '.bak')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(merged)
    print(f'{p}: {len(rows)-1}行 → {len(merged)-1}行 (最終 {merged[-1][0]})')
print('完了。各CSVの旧版は .bak として残しています。')
