# 247.【Q1・1 朝目】TSMOM 族の EA レグ設計 — 季節RG3 の E5 スリーブを RecentFit 系の単銘柄レグに移植する

> docs/244 キュー Q1(3 朝: 設計 / 実装 / パリティ)の 1 朝目。2026-09-18(手動テスト実行・このチャット)。セル数 0(実装項目・累積 3,400 のまま)。
> 目的: docs/194 §5 #1「TSMOM 族の EA レグ実装 + MT5 パリティ確認」。docs/184 §1 で「EA 未実装のため除外」した族を、ブロード版(BROAD_IV・34 セル)に載せられる状態にする。

## 1. 研究側の定義(`research/recentfit_screen.py` `tsmom_cell`)

| 項目 | 定義 |
|---|---|
| 対象 | `TSMOM_SYMS = XAUUSD, US500, NAS100, GER40, BTCUSD, ETHUSD`(6 セル・単銘柄) |
| シグナル | 月末終値 `px`。`sig = Σ_{lb∈{1,3,6,12}} sign(px/px.shift(lb) − 1)`。`pos = sign(sig)`(和が 0 なら建てない)。**前月末で確定した pos を当月に適用**(`shift(1)`) |
| 日次リターン | 当月の全営業日の close-to-close × pos。月初日に −5e-4(往復コスト定数) |
| 重み | セル単位では等ウェイト(合成側 `e5_composite` は 12 ヶ月逆ボラだが、**レグは選抜側の重みをそのまま使う**) |
| SL | なし(研究にもなし) |

## 2. 既に動いている実装 — 季節RG3 EA の `SleeveE5`(`mql5/【FN100k_口座14074882】季節RG3_1.0倍.mq5` L832〜)

同じシグナル(`CopyClose(sym,PERIOD_MN1,0,16)` → `[14]` = 直近確定月、lb 1/3/6/12 の符号和)を**既に MT5 で実装済み**。差分は次の 2 点だけ:

| 項目 | E5(季節RG3) | TSMOM レグ(本設計) |
|---|---|---|
| 銘柄配分 | 4 資産・12 ヶ月逆ボラで正規化 | 銘柄ごとに固定重み `w`(選抜出力) |
| 名目 | `equity × W × mult × invv/ΣinvV` | `initBal × w × mult`(Mon/Sess と同じ基準残高ベース) |
| 建て時刻 | 月初の最初のタイマー(`g_e5MonthKey` で月 1 回) | 同じ。月替わり後の最初の**該当銘柄の取引可能時刻** |
| 手動決済後の再建て | `InpReenterManualClose` | 同じ挙動を引き継ぐ |

→ **新規設計はほぼ不要。移植作業である。**

## 3. RecentFit 系への追加仕様(ForwardRecorder v1.40 → 各配備 EA)

| 項目 | 仕様 |
|---|---|
| 入力 | `InpTsmomLegs = "XAUUSD:0.10,US500:0.10,NAS100:0.10,GER40:0.10,BTCUSD:0.05,ETHUSD:0.05"`(SYM:重み・`ParseLegs` 流用)・`InpTsmomMult`(既定 = `InpMult`)・`InpTsmomEntryHourUTC = 1`(月替わり後、この UTC 時以降の最初のタイマーで建てる。00:00 直後のギャップ・広スプレッドを避ける)・`InpTsmomMaxSpreadBps = 5.0` |
| Magic | `InpMagicBase + 6`(Mon 1 / v4 2 / Hold 3 / Dow 4 / Sess 5 の次) |
| コメント | `RFTsmom_<sym>`。`forward/leg_forward.py` の `LEG_RE` に `Tsmom` を追加 |
| シグナル | `SleeveE5` と同一コード(`CopyClose(PERIOD_MN1,0,16)`・`[14]` 基準・lb 1/3/6/12 の符号和)。和 0 → 建てない(既存建玉があれば決済) |
| 月替わり処理 | 各銘柄について: 新符号 = 旧符号 → **保持(再建てしない)**。符号反転 → 決済して逆建て。0 → 決済。研究は毎月初 −5e-4 を引くので、保持はモデルより有利側 = 保守的 |
| SL | なし。ガード側で「SL なし建玉の想定損失 = 建玉額 × 10%」(季節RG3 `InpNoSLRiskAssumePct` と同じ)を `OpenSlRisk` 系に加える |
| 記録 CSV | `Rec("ENTRY","TSMOM",sym,0,side,lots,notional,spread,...)`・`Rec("FLIP"/"EXIT",...)`。family = `TSMOM` |
| 通知 | `IN TSMOM <sym> L/S <lots>` |
| 配備先 | **FN / FTMO のみ**(docs/194 §5 #4: Fintokei はトレードグループ 3% に常時保有が接触)。FTMO は指数のスワップ有り(docs/224 の FNmarkets 実測は SPX500 LONG −20%/年級だが、FTMO の値は別途実測) |

## 4. パリティ確認の方法(3 朝目)

docs/09 方式(Python 側の取引列と MT5 側の取引列を突き合わせる)を 2 段で行う。

| 段 | 内容 | 合格 |
|---|---|---|
| A. シグナル一致 | Python: `tsmom_cell` 内部の `pos`(月 × 銘柄・2016-01〜2026-08)を CSV に出す(`research/queue/q01_tsmom_signal_dump.py`)。MT5: スクリプト `Chien_TsmomSignalDump.mq5`(`Chien_SpecDump` と同型)で `CopyClose(PERIOD_MN1)` から同じ表を書き出す。**符号一致率 ≥ 95%**(不一致は月末終値の時刻差 = Yahoo の日付境界 vs ブローカーのサーバー時間。指数 CFD は特に) | ≥ 95% |
| B. 損益一致 | ストラテジーテスターで ForwardRecorder v1.40 を `InpTsmomLegs` のみ・2024-01〜2026-08・initBal 100,000 で走らせ、月次損益を Python セル × 名目と比較 | 取引数一致 ≥ 95%・累計損益差 ≤ 5% |

A で落ちる銘柄は「ブローカー月足で再計算した pos を正」とし、研究側の月足をブローカー月足に差し替える(FN/FTMO の MN1 履歴を `data_ext/` に保存)。

## 5. 2 朝目(実装)の作業手順

1. `Chien_ForwardRecorder_RecentFit.mq5` v1.40: `InpTsmomLegs` / `InpTsmomMult` / `InpTsmomEntryHourUTC` / `InpTsmomMaxSpreadBps`、`g_tsSym[]/g_tsW[]/g_tsSign[]/g_tsMonthKey`、`ManageTsmom()`(月替わり検知 → 保持/反転/決済)、`EntriesTsmom()`(`SleeveE5` のシグナル部を関数化 `TsmomSign(sym)`)、`IsMine` に `g_mTs` 追加、INIT ログ。
2. `research/forward/leg_forward.py` `LEG_RE` に `Tsmom` を追加。
3. `presets/forward_recorder_chart1_recentfit.set` に `InpTsmomLegs`(6 銘柄・0.10/0.10/0.10/0.10/0.05/0.05)を追加(FNmarkets 実弾記録。まだ入金待ち)。
4. 配備 EA(FN/FTMO 系)への同居は**パリティ通過後**。docs/241 は触らない。

## 6. 今朝の判定

設計完了・実装へ。新規セル 0・累積 3,400(閾値 p < 1.47e-5 のまま)。次回(2 朝目)= §5 の実装。
