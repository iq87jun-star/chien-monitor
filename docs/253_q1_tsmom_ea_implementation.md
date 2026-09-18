# 253.【Q1・2〜3 朝目】TSMOM レグの実装(ForwardRecorder v1.40)とパリティ用ツール

> docs/244 Q1 の 2 朝目(実装)と 3 朝目(パリティ用ツール)を 2026-09-18 に前倒しで実施(ユーザー「出来るものはこのまま進めてください」)。設計は docs/247。

## 1. 実装(`mql5/Chien_ForwardRecorder_RecentFit.mq5` v1.40)

| 項目 | 実装 |
|---|---|
| 入力 | `InpTsmomLegs`(SYM:重み CSV・`ParseLegs` 流用)/ `InpTsmomMult`(0 = `InpMult`)/ `InpTsmomEntryHourUTC` = 1 / `InpTsmomMaxSpreadBps` = 5 / `InpTsmomCatSLPct` = 0(SL なし) |
| Magic | `InpMagicBase + 6`。コメント `RFTsmom_<sym>`。`IsMine` に追加 |
| シグナル | `TsmomSign()`: 季節RG3 `SleeveE5` と同一(`CopyClose(PERIOD_MN1,0,16)`・`[14]` = 直近確定月・lb 1/3/6/12 の符号和) |
| 月替わり | `ManageTsmom(utc)`: 月キーが変わり UTC 時 ≥ 入力時刻で 1 回、全レグの符号を更新。建玉方向 ≠ 新符号なら決済(`FLIP_CLOSE` / `EXIT_FLAT`)。同符号は保持。月足 16 本未取得の銘柄があれば月キーを進めず次タイマーで再試行 |
| 建て | `EntriesTsmom()`: フラットかつ符号 ≠ 0 なら建てる(月初・反転後・手決済後の再建て)。スプレッド上限 bps・再試行 1 時間毎。`blockNew`(期限・日次停止・ロック・残高ガード)の後段なので新規停止中は建てない。決済側(`ManageTsmom`)は `blockNew` の前段 |
| 記録 | `Rec("ENTRY"/"SKIP_SPREAD"/"FLIP_CLOSE"/"EXIT_FLAT","TSMOM",...)`(`spread` 列は bps・`note=unit=bps`) |
| 再起動 | 符号は月足から決定的に再計算するため永続化不要。月初 00:00〜入力時刻の間は何もしない |
| 休場フィルタ | 12/20〜1/3 は `HolidayBlocked` で新規停止 → 1 月の建ては 1/4 以降(研究は 1 月初日から。差は年 1 回・小) |

`research/forward/leg_forward.py` の `LEG_RE` に `Tsmom` を追加。`mql5/presets/forward_recorder_chart1_recentfit.set` に `InpTsmomLegs=XAUUSD:0.10,SPX500:0.10,NDX100:0.10,GER40:0.10,BTCUSD:0.05,ETHUSD:0.05`(FNmarkets 実名)を追加。**コンパイルは未実施**(この環境に MetaEditor なし)。ユーザー側でコンパイルし、エラーがあれば貼ってもらう。

## 2. パリティ用ツール(docs/247 §4)

| 段 | ツール | 出力 |
|---|---|---|
| A. 符号一致 | 研究側 `research/queue/q01_tsmom_signal_dump.py` → `results/tsmom_signals_python.csv`(実行済み・2016-01〜)。MT5 側 `mql5/Chien_TsmomSignalDump.mq5`(スクリプト・任意チャートで実行 → `MQL5/Files/tsmom_signals_mt5.csv`)。突合 `research/queue/q01_tsmom_parity.py <mt5csv> "SPX500=US500,NDX100=NAS100"` | 銘柄別一致率(合格 ≥ 95%)と不一致月 |
| B. 損益一致 | ストラテジーテスター(v1.40・`InpTsmomLegs` のみ・2024-01〜2026-08・initBal 100,000)の月次損益 vs Python セル × 名目 | 取引数 ≥ 95%・累計損益差 ≤ 5%(未実施) |

## 3. 残作業(ユーザー側)

1. v1.40 のコンパイル(エラーがあれば貼る)。
2. `Chien_TsmomSignalDump.mq5` を FN または FTMO の MT5 で実行し、CSV を送る → 一致率を出す。
3. B 段はテスターの実行結果(レポート xlsx か取引一覧)を送る。

Q1 はこれで 3 朝分を消化。パリティの数値が出るまで `in_progress`(ユーザー側の作業待ち)。
