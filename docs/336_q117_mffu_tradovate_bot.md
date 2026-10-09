# 336.【Q117】MFFU(Tradovate)向け先物ボットの実装 — 設計 v0.1・判明した制約(プロップ口座には Tradovate API キーが出ない → 送信経路は Webhook 橋渡しか NinjaTrader)・紙上パリティの手順
> 2026-10-09(ユーザー「MFFU の Tradovate ボット実装を登録して進めてください」)。docs/322 §5e。コード `ops/futures/`(`mffu_bot.py` v0.1・`config.example.json`・`test_mffu_bot.py`・`install_task_futures.ps1`)。セル 0(累積 9,640 不変)。口座の購入・課金はユーザー判断で、本稿は購入前にできる部分(設計・コード・オフライン検証)まで。

## 1. 載せるもの(docs/332〜335 の帰結)
| レグ | 先物(ミクロ) | 建て → 決済 | 根拠 |
|---|---|---|---|
| Mon 指数 日中版 | MES(US500)/ MNQ(NAS100)/ MYM(US30) | 月曜 13:00 UTC 成行買い → 同日 20:00 UTC 成行決済 | docs/333(US30 改良成立・US500/NAS100 は OOS で改善)、docs/334(先物 = CFD 相関 0.99)。20 UTC は 16:00 EDT / 15:00 EST で、MFFU の 16:10 ET 強制清算より常に前 |
| 日経(NIY) | 載せない | — | docs/335: ミクロが無く 1 枚 ≈ 2,000 万円で 50k 口座にはサイズ過大。CFD 側に残す |
| 6J(USDJPY)・Roll5 | 今回は載せない | — | docs/332 §3 の候補だが、まず 1 族で運用とパリティを確立してから |

## 2. 設計(`ops/futures/mffu_bot.py`)
- **判断と発注を分離**: 判断(月曜か・CME 休場か・HALT か・どの限月を何枚か・当日既建てか)はボットで完結し、発注は transport に委ねる。transport は `dry`(印字のみ)/ `webhook`(TradersPost 形式 JSON を POST)/ `tradovate`(REST・未検証)。
- **限月**: 四半期限月(H/M/U/Z)の第 3 金曜が取引日 + 8 日より後なら当該限月、そうでなければ次(出来高は満期 8 日前 = 前週木曜に移るため、満期週の月曜は次限月)。例: 2026-12-07 → MESZ2026、2026-12-14 → MESH2027。
- **3 つの実行**(VPS は JST・夏時間なしなので UTC 固定時刻をそのまま登録): `entry` 月 22:00 JST(13 UTC)、`exit` 火 05:00 JST(20 UTC)、`check` 火 05:30 JST(未決済が残っていれば決済を再送。16:10 ET の強制清算前の最後の保険)。
- **冪等**: `out/state.json` に日付ごとの {entered, open[], exited} を持ち、二重建て・二重決済・建てていない日の決済をしない。`HALT` という空ファイルを置くと建てなくなる(決済は続く)。
- **記録**: `mffu_log.csv`(UTC・action・限月・枚数・transport・応答)。config で Drive 同期フォルダ `chien_ops/futures/` に向ければ朝のダイジェストが読める(取り込みは稼働開始時に ops_ingest へ追加)。
- **秘密**: Webhook URL・API キーは `config.json`(git 管理外・`.gitignore` 済)にだけ置く。公開リポジトリには `config.example.json` のみ。
- **オフライン検証**: `test_mffu_bot.py` 5 本(第 3 金曜・限月ロール・スキップ条件・建て/決済の冪等・check の再送)を通過。`--dry` で全動作を印字確認済み。

## 3. 判明した制約(送信経路)— 購入前に決めること
| 経路 | 可否 | 費用 | 備考 |
|---|---|---|---|
| Tradovate REST を直接 | **現状不可** | API Access $25/月 | Tradovate の API キーは「本人名義の Live 口座・残高 $1,000 以上」でしか発行されず、プロップ・評価口座は対象外(Tradovate コミュニティ・PickMyTrade の 2026 年ガイド)。コードは残すが未検証 |
| **Webhook 橋渡し(TradersPost)** | **可**(MFFU 公式ガイドが TradersPost 経由の Tradovate 接続を案内) | Starter $41.65/月(年払い・資産クラス 1)〜 | ボットは JSON を POST するだけ。`{"ticker":"MESZ2026","action":"buy","quantity":2}` / 決済は `"sentiment":"flat"`。7 日無料・紙口座あり。相場データ不要(価格は受け取らないので CME ライセンス不要) |
| NinjaTrader(C# 戦略・VPS で常駐) | 可 | 自動売買はリース $225/四半期〜 | MT5 と同様に端末常駐。実装は別言語で、2 系統目の端末運用になる |
| PickMyTrade / CrossTrade | 可 | 各社月額 | TradersPost と同型の橋渡し |

**推奨**: TradersPost Starter(資産クラス = 先物)。ボット側は `transport: "webhook"` に切り替えるだけ。

**規約上の注意(購入前に MFFU に書面で確認)**: docs/332 では「自前の自動化 可」としたが、TradersPost の MFFU ガイドは「人の監視なしの完全自律ボットは禁止・半自動(監視しながら)なら可」と書く。当方は週 1 回・2 発注で、毎朝のダイジェストと VPS の記録で監視する運用になる。これが「監視あり」に当たるかを、**口座購入前に MFFU サポートへ文面で確認し、回答を保存**しておく。回答が「不可」なら Q117 は中止(費用ゼロ)。

## 4. 枚数(50k・×3・docs/332 §4 の写像)
名目 $150k を 3 銘柄に $50k ずつ: MES(≈$5 × 6,000 = $30k)2 枚、MNQ(≈$2 × 21,000 = $42k)1 枚、MYM(≈$0.5 × 42,000 = $21k)2 枚 = 合計 5 枚($153k)。`max_contracts_total: 5`。価格が 20% 以上動いたら config の qty を見直す(四半期ごと)。EOD トレーリング $2,000 に対し、1 日の最悪(docs/333 の最悪月 −2〜−3% ≒ 名目 $150k の −0.7%/日相当 ≈ −$1,000)で 2 日分の余裕。

## 5. 手順(購入後)
1. MFFU に自動化の文面確認(§3)。可なら Rapid 50k 購入(ユーザー)。
2. TradersPost 登録 → Tradovate 接続(MFFU 口座)→ 戦略を作り Webhook URL を取得(ユーザー・URL はチャットに貼らず VPS の config.json に直接)。
3. VPS: `C:\chien\ops\futures\config.json` を作成(transport は **まず `dry`**)→ `install_task_futures.ps1` で 3 タスク登録 → 月曜に印字だけで動くことを確認。
4. **紙上パリティ 4 週**: TradersPost の紙口座に transport=webhook で流し、約定価格と `research` 側 `shot(sym,13,20)`(Yahoo H1 先物)の始値を照合。差が往復 2 ティック以内なら本口座へ。
5. 本口座へ切替(ユーザー「切替」)。ダイジェストに `futures/mffu_log.csv` の取り込みを追加。

## 6. 判定・次
- Q117 は in_progress(コード・設計・オフライン検証まで完了)。購入・課金・規約確認はユーザー側。進捗は docs/322 §5e と本稿に追記。
- 11/1 改正案: 新ジャンル節に「先物 = 実装済み(送信は Webhook 橋渡し)・購入判断待ち」と記す。
