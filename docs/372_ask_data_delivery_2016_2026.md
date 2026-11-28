# 372.【納品】Dukascopy ASK 1時間足 2016-01-01〜2026-09-30(11ペア)— 別ブランチ(バイナリー)より

2026-10-21。docs/244(10/21 分担の取り決め)の「ask 2016〜 は別ブランチが取得し、この枝は受け取って `research/data_dukascopy/` に置く」の実行。

## 内容
- `research/data_dukascopy/{PAIR}_hour_ask.csv.gz` 11本を 2024-01-01〜 → **2016-01-01〜2026-09-30** に置換・拡張。
- ペア: EURGBP / CHFJPY / EURJPY / GBPJPY / GBPUSD / USDCHF / CADJPY / NZDJPY / AUDJPY / AUDUSD / EURAUD。
- 形式は既存と同一: `timestamp,open,high,low,close,volume`、UTC、連続1時間グリッド(週末フラットバー込み、各ペア94,224行)。
- 出典: Dukascopy datafeed ASK_candles_hour_1.bi5(LZMA検品済み・全1,419月ファイル)。既存ファイルとの重複期間(2024-01〜2026-08)でEURJPYの行を突合し完全一致を確認。

## 効いてくる点
- **§1b(docs/367)の探索窓制約が解消**: 現実価格(ask/mid)での判定が2016年まで遡れるため、2024〜26の3年窓に限られていた再判定・走査が10年フルで可能になる。
- 待ち扱いだった **Q148(Mon4全セルの現実価格再判定)** が実行可能。Q144(ロールオーバー帯の売り再走査)も全期間で走る。
- 参考: 当方(バイナリー側)の10年フルミッド再判定は完了。月曜円クロス家族は10年でもミッドで BE+4〜10pp を維持(bid−midのΔは−9〜−13pp)。毎日7時系はEURGBP/EURJPYがBE+0.4〜1.8ppまで縮み、CHFJPY・USDCHFはBE割れ。詳細は別ブランチ `theoption_validation/README.md` 追補18。
