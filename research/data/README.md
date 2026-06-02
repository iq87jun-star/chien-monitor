# research/data — データ要件（ユーザーが Drive に配置）

> 拘束力ある10年検定はユーザーの Google Drive / Colab 実行が前提。本環境にはデータが無いため、
> ハーネスは Drive・ローカル両対応で書く（パスを環境変数 `EDGE_DATA_DIR` で切替）。

## 期間
全データ **2016-01-01 〜 2025-12-31**（10年）。短期サブ期間は参考併記のみ（規律2）。

## 既存（前セッション資産・要再配置）
| ファイル | 内容 |
|---|---|
| `EURJPY_h1.csv` / `GBPJPY_h1.csv` / `USDJPY_h1.csv` | FX H1, Dukascopy, bid/ask 付き（v7用・相関基準） |
| `v7_weekly_returns.csv` | v7 の週次リターン系列（`date,ret`）。ゲート⑥の相関基準。無ければ EA ロジックから再生成。 |

## 追加で必要（事前登録 docs/26 の候補別）
| 候補 | ファイル | 内容 |
|---|---|---|
| E3A | `US500_h1.csv`, `NAS100_h1.csv`, `JP225_h1.csv` | 指数 OHLC（日足境界が判る H1）。ギャップ・RSI 計算用。 |
| E3B | `AUDJPY_h1.csv`, `CADJPY_h1.csv`, `US500_h1.csv` | 商品系JPYクロス＋先行変数の米株。 |
| E3C | `<G10>_h1.csv`（対USD10ペア） ＋ `policy_rates_monthly.csv` | G10 横断＋各国政策金利（`date,ccy,rate`）。スポット超過収益検定。 |
| E3D | `EURUSD_h1.csv`, `GBPUSD_h1.csv` | 既存FX想定。東京レンジ→ロンドン・ブレイク。 |
| 全候補 | `costs.csv` | 各商品の往復スプレッド(pips)・1泊スワップ(符号付き)。ゲート⑤。 |

## CSV スキーマ（H1）
```
time(UTC, ISO8601), open, high, low, close, bid_close, ask_close, volume
```
- `bid_close`/`ask_close` が無い場合は `costs.csv` のスプレッドで往復コストを代用。
- 時刻は **UTC**。ブローカー時刻のものは UTC に変換してから配置すること。

## 配置例
```
EDGE_DATA_DIR=/content/drive/MyDrive/edge_research/data   # Colab
EDGE_DATA_DIR=./research/data                              # ローカル（短期/一部のみ）
```
