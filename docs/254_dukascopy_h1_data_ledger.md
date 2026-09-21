# 254.【データ台帳】Dukascopy H1(bid / ask)— 38 銘柄・57 ファイル・2026-09-19〜22 取得

> 2026-09-22 完了。ユーザー「Dukascopy のダウンロードはそちらで出来ますか」(9/19)→ 取得計画を 2 時間毎の Routine(このチャット内・105 分予算・部分保存と `manifest.json` による再開)で実行し、38/38 が揃った。
> 取得: `research/tools/dukascopy_fetch.py`(datafeed の `.bi5` を LZMA 展開・24 バイト固定長・20 秒間隔・503/接続リセットはバックオフ)・`research/tools/dukascopy_hourly.sh`(順序と予算)。生 `.bi5` は `research/data_dukascopy/raw/`(gitignore)、CSV は `research/data_dukascopy/<SYM>_hour[_ask].csv.gz`(`git add -f` でコミット済み)。
> 本書の表は `research/tools/dukascopy_ledger.py` の出力。

## 1. 計画と実績

| 区分 | 銘柄 | 側 | 期間 | 月数/銘柄 | 結果 |
|---|---|---|---|--:|---|
| ① 新銘柄 19 本 | EURCHF GBPCHF AUDNZD AUDCAD BRENT WTI UK100 JP225 EUSTX50 US30 AUS200 HK50 BUND USTBOND DXY XAGUSD NZDCAD CADCHF USDCAD | bid | 2018-01〜2026-08 | 104 | **19/19 完了**・404 なし |
| ② 旧銘柄 19 本 | EURGBP USDCHF NZDUSD AUDUSD CHFJPY GBPJPY EURJPY AUDJPY USDJPY CADJPY NZDJPY EURUSD GBPUSD EURAUD GBPAUD XAUUSD GER40 NAS100 US500 | ask | 2024-01〜2026-08 | 32 | **19/19 完了**・404 なし |
| ③ 新銘柄 ask | (①と同じ) | ask | — | — | **保留**(実測 ≈50 ファイル/時では日程内に収まらないため。必要になれば同じスクリプトで追加) |

実測: 2,608 ファイル(raw 22 MB)・CSV 合計 36 MB。ペースは 503 / 接続リセットの頻度で 25〜60 ファイル/時。取得失敗は 1 ヶ月単位で次回ジョブに持ち越し(EURUSD 2026-01・EURAUD 2025-02・XAUUSD 2026-01 が各 1 回)、すべて再試行で回収。

## 2. 台帳(全 57 ファイル)

「manifest外」= 本計画より前から存在した旧ファイル(別経路で取得。XAUUSD bid は 2021-01〜2025-12 のみ、CADJPY/CHFJPY/EURAUD/EURGBP/GBPAUD/NZDJPY bid は 2025-12 まで、NAS100 bid は 2026-04 まで)。

| 銘柄 | 側 | Dukascopy コード | 開始 | 終了 | 行数 | 月数 | 完了 | 404 月 |
|---|---|---|---|---|--:|--:|---|---|
| AUDCAD | bid | AUDCAD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| AUDJPY | bid | AUDJPY | 2016-01-01 | 2026-08-31 | 93504 |  | manifest外 | - |
| AUDJPY | ask | AUDJPY | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| AUDNZD | bid | AUDNZD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| AUDUSD | bid | AUDUSD | 2016-01-01 | 2026-08-31 | 93504 |  | manifest外 | - |
| AUDUSD | ask | AUDUSD | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| AUS200 | bid | AUSIDXAUD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| BRENT | bid | BRENTCMDUSD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| BUND | bid | BUNDTREUR | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| CADCHF | bid | CADCHF | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| CADJPY | bid | CADJPY | 2016-01-03 | 2025-12-31 | 62350 |  | manifest外 | - |
| CADJPY | ask | CADJPY | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| CHFJPY | bid | CHFJPY | 2016-01-03 | 2025-12-31 | 62315 |  | manifest外 | - |
| CHFJPY | ask | CHFJPY | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| DXY | bid | DOLLARIDXUSD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| EURAUD | bid | EURAUD | 2016-01-03 | 2025-12-31 | 62336 |  | manifest外 | - |
| EURAUD | ask | EURAUD | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| EURCHF | bid | EURCHF | 2016-01-01 | 2026-08-31 | 93504 | 128 | yes | - |
| EURGBP | bid | EURGBP | 2016-01-03 | 2025-12-31 | 62347 |  | manifest外 | - |
| EURGBP | ask | EURGBP | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| EURJPY | bid | EURJPY | 2016-01-01 | 2026-08-31 | 93504 |  | manifest外 | - |
| EURJPY | ask | EURJPY | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| EURUSD | bid | EURUSD | 2003-05-01 | 2026-08-31 | 204576 |  | manifest外 | - |
| EURUSD | ask | EURUSD | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| EUSTX50 | bid | EUSIDXEUR | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| GBPAUD | bid | GBPAUD | 2016-01-03 | 2025-12-31 | 62273 |  | manifest外 | - |
| GBPAUD | ask | GBPAUD | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| GBPCHF | bid | GBPCHF | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| GBPJPY | bid | GBPJPY | 2016-01-01 | 2026-08-31 | 93504 |  | manifest外 | - |
| GBPJPY | ask | GBPJPY | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| GBPUSD | bid | GBPUSD | 2016-01-01 | 2026-08-31 | 93504 |  | manifest外 | - |
| GBPUSD | ask | GBPUSD | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| GER40 | bid | DEUIDXEUR | 2013-09-01 | 2026-08-31 | 113952 |  | manifest外 | - |
| GER40 | ask | DEUIDXEUR | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| HK50 | bid | HKGIDXHKD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| JP225 | bid | JPNIDXJPY | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| NAS100 | bid | USATECHIDXUSD | 2016-01-01 | 2026-04-30 | 62952 |  | manifest外 | - |
| NAS100 | ask | USATECHIDXUSD | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| NZDCAD | bid | NZDCAD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| NZDJPY | bid | NZDJPY | 2016-01-03 | 2025-12-31 | 62302 |  | manifest外 | - |
| NZDJPY | ask | NZDJPY | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| NZDUSD | bid | NZDUSD | 2016-01-01 | 2026-08-31 | 93504 |  | manifest外 | - |
| NZDUSD | ask | NZDUSD | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| UK100 | bid | GBRIDXGBP | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| US30 | bid | USA30IDXUSD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| US500 | bid | USA500IDXUSD | 2011-09-01 | 2026-08-31 | 131496 |  | manifest外 | - |
| US500 | ask | USA500IDXUSD | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| USDCAD | bid | USDCAD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| USDCHF | bid | USDCHF | 2016-01-01 | 2026-08-31 | 93504 |  | manifest外 | - |
| USDCHF | ask | USDCHF | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| USDJPY | bid | USDJPY | 2016-01-01 | 2026-08-31 | 93504 |  | manifest外 | - |
| USDJPY | ask | USDJPY | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |
| USTBOND | bid | USTBONDTRUSD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| WTI | bid | LIGHTCMDUSD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| XAGUSD | bid | XAGUSD | 2018-01-01 | 2026-08-31 | 75960 | 104 | yes | - |
| XAUUSD | bid | XAUUSD | 2021-01-01 | 2025-12-30 | 43800 |  | manifest外 | - |
| XAUUSD | ask | XAUUSD | 2024-01-01 | 2026-08-31 | 23376 | 32 | yes | - |

ファイル数 57・manifest complete 38/38

## 3. 形式と注意

- 列: `timestamp,open,high,low,close,volume`。timestamp は **UTC naive**(Dukascopy の H1 は UTC 境界)。volume は tick volume。
- 価格スケール: FX 非 JPY 1e-5、JPY クロス・金属・CFD・債券 1e-3(`dukascopy_fetch.py` の `SCALE`)。
- bid と ask は別ファイル。**往復コストの実測**は `ask.open − bid.open` を建玉時刻で取る(docs/249 の SHORT 再検定で使う)。
- 旧ファイル(manifest外)は期間が短いものがある。IS/OOS 窓(2021-10〜2026-08)を要する検定では、末尾が 2025-12 の 6 銘柄は OOS が 12 ヶ月に縮む。同じ銘柄の bid を 2026-08 まで延ばすには ① と同じ手順で 2026-01〜08 を追加取得すればよい(各 8 ファイル)。
- XAUUSD bid が 2021-01 からのため前窓(2016-01〜2021-09)が無い。docs/256 §4 の通り XAUUSD は前窓判定「該当なし」。

## 4. 使い道(登録済み・予定)

| 用途 | 参照 |
|---|---|
| 新銘柄 19 本の時間帯格子(Q12・完了・通過 0) | docs/255 |
| 出品着想の 5 族 Q13〜Q17(proposed) | docs/256 |
| 旧 19 銘柄の bid/ask 実測コストで SHORT 側を再検定(Sess 族の欠陥 docs/249 の後始末) | 次キューで登録 |
| 紙上フォワード(paper_forward)の H1 参照 | research/forward/ |

## 5. Routine

「Dukascopy H1 取得(2 時間毎・このチャット)」は本書の push をもって削除。再取得や範囲延長は `research/tools/dukascopy_hourly.sh <分>` を手動で回せば `manifest.json` から再開する。
