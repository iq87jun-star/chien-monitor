# 71. 再現性ハードニング — Google Colab バージョン更新への耐性化

> **背景**: 「Googleコード(=Google Colab)が新しいバージョンに変わった」ことで、本リポジトリの
> 検証数値が再現できるのかという問い。調査の結果、**乱数(MC)は決定的だが、データ取得が実行日基準の
> ローリング窓＋依存無固定**で、Colab更新前から既に再現性が崩れる構造だった。本コミットでその構造的
> 弱点を是正する。数値計算ロジックには手を入れていない(=過去結論の意味は不変、再実行時の一致性のみ向上)。

## 0. 一行結論
**「再実行すると同じ数字が出る」状態に近づけた。** 具体的には (1) データ窓を固定日付に凍結、
(2) 依存ライブラリをピン留め、(3) 非推奨API `utcfromtimestamp` を将来安全な形へ、を実施。
ただし**合否を決める看板数値の最終確証は依然ユーザーのDukascopy私物データ依存**であり、それは
§4 の手順(生出力＋ハッシュのコミット)を踏まないとリポジトリ単体では独立再現できない。

## 1. 変更点

### (1) データ窓の凍結 — ローリング `range` を廃止
Yahoo Finance 取得を `range=10y` / `range=730d`(=**実行日基準**でズレる)から、固定の
`period1`/`period2`(UNIX秒)へ全面置換。
- **日足10年**: `period1=1451606400`(2016-01-01 00:00:00Z)〜`period2=1767225599`(2025-12-31 23:59:59Z)
  → docs/18 の Dukascopy 検証窓「2016-01〜2025-12」と一致させた。
- **H1 ~2年**: `period1=1704067200`(2024-01-01)〜`period2=1767225599`(2025-12-31)。

対象: `fetch_data.py` `fetch_calendar.py` `fetch_multiasset.py` `colab_*` 各取得関数、
`build_*_notebook.py`、`colab_firms_2v3_compare.py:_yf`、`edge_regime_gate_10y.py:_yahoo_fetch`。

> 効果: いつ実行しても**同一の価格データ**を取得する。これが従来、最大の非再現要因だった。

### (2) 依存ピン留め — `research/requirements.txt`
`numpy==1.26.4 / pandas==2.2.2 / matplotlib==3.9.2` を固定。Colab 先頭セルで:
```python
!pip install -q -r research/requirements.txt
```
numpy 2.x 昇格や pandas の既定挙動変更(`fillna` ダウンキャスト、`resample`/`groupby` 既定、NaN処理)
による端数のブレを封じる。**MC乱数は `np.random.default_rng`(PCG64)でシード固定済**のため、
本ピンと合わせれば結果は決定的になる。

### (3) 非推奨APIの除去 — `datetime.utcfromtimestamp`
Python 3.12+ で非推奨(将来削除)の `dt.datetime.utcfromtimestamp(t)` を
`dt.datetime.fromtimestamp(t, dt.timezone.utc).replace(tzinfo=None)` へ置換。
**naive-UTC の値は完全一致**するため数値・CSV文字列は不変、将来のColab Python更新での破綻のみ回避。

## 2. 変更していない(意図的)
- 戦略・バックテスト・MCの**計算ロジックは一切不変**。よって docs/01〜70 の結論の意味は変わらない。
- シード値(7,11,13…)も不変。

## 3. 再現手順(更新後)
```python
# Colab 先頭
!pip install -q -r research/requirements.txt
# 以降、各 colab_*.py を実行 → 固定窓・固定依存・固定シードで決定的に再現
```

## 4. 残課題 — Dukascopy 看板数値の独立再現(手作業が必要)
docs/13・18 等の**合否判定の根拠数値**は、ユーザーの Google Drive 上の Dukascopy H1(実bid/ask)を
回した**印字出力の手転記**であり、(a) 入力データがリポジトリ外、(b) 生出力が未コミット。
リポジトリ単体での独立再現には次が必要(本コミットでは未実施＝データが手元に無いため):
1. 検証ノートの各セルの**生出力を JSON/CSV で `research/results/` に保存・コミット**。
2. 入力 Dukascopy CSV の **SHA-256 ハッシュ**を併記(同一入力であることの証跡)。
3. 以後は数値を docs に**手転記せず**、保存JSONを参照する運用へ。

→ ユーザーが Dukascopy データで再実行する際に上記を出力する小ヘルパーを追加可能(要依頼)。
