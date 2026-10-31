# theoption 自動売買 API の確認用プローブ(取引しない)

> 目的: 月曜朝の窓埋め効果(`research/ig_binary/README.md`。下窓・開場時点で未埋め → 07:00→08:00 の上昇率 70.8% / 70.3% / 76.6%)を、theoption の **期間固定(FD)・1 時間・ハイロー** で取れるかを決める。
> 国内業者は月曜の初回が 7:10〜9:00 で取れなかった。theoption の FD は「買った時点から 1 時間」なので、**開場直後に買えれば**取れる可能性がある。

## 確かめること(このプローブで分かる)
| | 何を見るか | 合格の目安 |
|---|---|---|
| 1 | 月曜に `通貨|FD|1H|HIGHLOW|…` が Opened で出る時刻(JST) | 開場(夏 06:00 / 冬 07:00)から **20 分以内** |
| 2 | 払い戻し倍率(契約 JSON の欄。名前が分からないので全欄を記録) | 1.8 倍なら損益分岐 55.6%、1.7 倍なら 58.8% |
| 2' | 22H / 23H(② Mon4 の形)と木曜朝の 1H(③ 水曜夜の円買い)も同じく初出・倍率を記録 | ② ③ は倍率 1.85 倍以上が目安 |
| 3 | 開場直後の判定価格(`contract_data` の値・取れれば) | 中値から大きくずれていないこと |

API の仕様は 2026-10 のクイックスタート(ユーザー提供の PDF)による。契約名は `資産|FE or FD|期間|商品|HIGH/LOW`、期間は 15S〜1H・22H・23H、商品は HighLow / Spread / Touch。最低 1,000 円、買いは 1 秒に 1 回まで。**developers.theoption.com と api.theoption.com は日本以外から遮断されている**ため、プローブは日本の PC / VPS で動かす。

## 手順(VPS・ワンクリック)
1. theoption にログイン → メニュー「自動売買用API」→「お試し」タブ →「APIキーをリクエスト」。表示されたキーをコピー(一度しか出ない)。**キーはチャットやメールに貼らない。**
2. VPS に RDP で入り、ブラウザで次を開いて `to_setup.bat` をデスクトップに保存し、ダブルクリック:
   `https://raw.githubusercontent.com/iq87jun-star/chien-monitor/ccr-dbb29a98-7cflzp/ops/theoption/to_setup.bat`
   (右クリック →「名前を付けて保存」。拡張子が .txt にならないよう「すべてのファイル」で保存)
3. 黒い画面で「APIキー」と聞かれたら、コピーしたキーを貼り付けて Enter(画面には出ない)。あとは自動:
   - `C:\chien\ops\theoption\` にスクリプトを置き、Python と websockets を確認
   - キーは Windows のユーザー環境変数 `THEOPTION_API_KEY` にだけ保存(ファイルには書かない)
   - 記録先を Google Drive の `chien_ops\theoption\` に設定(既存のエージェントと同じ Drive)
   - その場で 60 秒の接続確認 → 結果を画面に表示
   - タスク登録: `chien_theoption_monday`(月曜 05:25〜09:30 記録)・`chien_theoption_thursday`(木曜 04:55〜09:30 = 水曜 20〜24 UTC の記録・v0.3。設定済みの VPS には次回の実行時に自動で追加)・`chien_theoption_check`(火〜金 12:00 に 60 秒の接続確認)
4. チャットに「theoption 設定完了」と一言。以後は Drive の `chien_ops/theoption/` の要約(`*.summary.txt`・`_diag/last_run.txt`)をチャット側から読む。**手作業は無し。**
- 実行のたびに GitHub から最新の `to_probe.py` / `to_summarize.py` を取り直す(`to_run.ps1`)。書式の修正などはこちらで push すれば次回から反映。
- キーを替えるとき: コマンドプロンプトで `to_setup.bat run -NewKey`。止めるとき: タスクスケジューラで `chien_theoption_*` を無効化。
- ログ: `C:\chien\ops\theoption\run.log`。

## 予定
- 10/26(月・夏時間 開場 06:00)と 11/2(月・冬時間 開場 07:00)の 2 回を記録 → 合格なら `ops/ig_binary/ig_gap_bot.py` を theoption API で自動発注する版にし、お試し環境で数週間。
- `contract_data` の購読書式はクイックスタートに要約しか無いため推測(`{"stream":"contract_data","key":<契約名>}`)。拒否されても応答を記録するので、要約の (4)(5) で書式を直す。

## ファイル
- `to_probe.py` — health / balance / WebSocket(contracts・contract_data)を記録。`/buy`・`/sell` は呼ばない(テストで確認)。
- `to_summarize.py` — 記録の要約。
- `to_setup.bat` / `to_setup.ps1` — VPS のワンクリック設定。`to_run.ps1` — タスクから呼ぶ実行ラッパー(自己更新)。
- `test_to_probe.py` — `python -m pytest -q`(偽ゲートウェイで往復を確認・5 passed)。

## v0.9 (2026-10-23): 転売実測プローブ `to_tenbai.py`(お試し口座で ¥1,000 × 3 本を置き、転売価格を実測)
- 目的: `theoption_validation/README.md` 追補21・21補足の「転売価格 vs 公正値(含み損の深さ別)」の実測。
- 動作(タスク `chien_theoption_tenbai`・月曜 07:05 JST・初回のプローブ実行時に自動登録 → `to_run.ps1 -Mode tenbai` = `--live-demo`):
  07:00:10 JST に EURJPY / AUDJPY / NZDJPY の `FE|23H|HIGHLOW|HIGH`(翌 06:00 JST 判定)を ¥1,000 ずつ成行で購入(`/trading/buy`、
  契約名と expiration_time は同時刻の記録プローブの JSONL から。07:05 起動なので実際の発注は起動直後)→ 30 分ごとに `trades`
  (can_sell / sell)と `contract_data`(判定価格)を 15 秒だけ記録 → 翌 03:00 JST に含み損の取引を 1 本だけ転売(`/trading/sell`、
  優先 NZDJPY→AUDJPY→EURJPY)→ 翌 06:10 JST に `/history/trades` で結果を取り `tenbai_demo_<日時>.summary.txt` を out(Drive)に書く。
- 安全: キーの JWT 発行者が `TheOptionDemo` でなければ発注・転売せず終了。接続先は apidemo / gatewaydemo 固定(本番ホストは持たない)。
  発注は 1 回の実行で最大 3 本・各 ¥1,000、`_diag/tenbai_state.json` で同日の二重発注を防ぐ、残高 < ¥3,000 なら発注しない、
  07:10 JST 以降の起動は発注を見送る。`--live-demo` 無し(既定)は記録のみ(`test_to_tenbai.py` で保証)。
- 前提: お試し(API)残高に ¥10,000 以上(仮想資金・API ページの「+チャージ」)。
- 動作確認: `powershell -NoProfile -ExecutionPolicy Bypass -File C:\chien\ops\theoption\to_run.ps1 -Mode tenbai_once`(発注せず 1 回収集)。

## v1.0 (2026-10-24) / v1.1 (2026-10-26): 本番メニューの自動発注 `to_live.py`(既定はお試し口座で本番同一条件・実口座は二重オプトイン)
- メニュー(v1.1・追補23): 10/26 の開場記録で **月曜 07:00 に 1H 契約は無く(1H は 08:00 から)、23H の判定時刻は翌 06:00 のみ** と判明したため、
  実行可能な 4 本に縮小: EURJPY 16,000 / AUDJPY 17,000 / NZDJPY 14,000(月曜 07:00 → 翌 06:00 HIGH)+ EURGBP 7,500(月火水金 23:00 → 翌 06:00 LOW・
  対象月のみ)。DD 予算 30 万円で月期待 +38,971 円。倍率規則(追補17): 22H/23H は 1.90 未満で見送り、2.0 以上で 1.5 倍。
- タスク(初回のプローブ実行時に自動登録): `chien_theoption_live_0700`(月 06:58)・`_2300`(毎日 22:58、曜日と月はスクリプトが判定)・
  `_settle`(毎日 06:45、`/history/trades` の結果を `live_trades_<口座>.csv` に追記 = 週次突合の入力)。`_1100` は商品が無く廃止(登録済みでも脚が無く何もしない)。
- 契約の選び方: 定刻 +10 秒に contracts を 20 秒集め、「銘柄 | FE | 任意の期間 | HIGHLOW | HIGH/LOW」で**判定時刻が一致する**契約を選ぶ。
  無ければ「契約なし」で見送り(判定時刻が未確認の GBPJPY→14 時・AUDJPY→翌 10 時はこれで安全に扱う)。
- 口座: 既定はお試し(キーの iss = TheOptionDemo を要求)。実口座は `to_config.json` に `"live_real": true` **かつ** ユーザー環境変数
  `THEOPTION_API_KEY_REAL` の両方が揃ったときだけ(本番ホスト・本番キー)。片方だけでは常にお試し。
- 安全: health 失敗で発注なし、残高 < 必要額で発注なし、日次ベット上限 120,000 円、1 脚 20 万円上限、`_diag/live_state.json` で同日同脚の二重発注防止、
  購入は 1 秒 1 回、拒否コードは記録して見送り。
- 記録: `live_<口座>_<日付>.jsonl`、`live_entries_<口座>.csv`(date,strategy_id,pair,direction,payout_actual,stake,trade_id,strike,contract,note)。
- 予定: 10/26(月)はお試し口座で本番同一条件を実行 → 10/27(火)の週次突合で判定 → 問題なければ 11/2(月)から実口座(設定の切替のみ)。
- 動作確認: `powershell -NoProfile -ExecutionPolicy Bypass -File C:\chien\ops\theoption\to_run.ps1 -Mode live_plan`(今日の対象脚を表示・発注しない)。

## v1.2 (2026-10-27): メニューを 14 本に拡張(追補29補足「現行4脚+勝率上位10セル」、DD予算30万円で月期待 +50,153円)
- `to_live.py` MENU: 07:00×3(5,100/5,300/4,400)+ 月曜の分割エントリー(AUDJPY 10:00、EURJPY 13:00/14:00/16:00/21:00、USDJPY 14:00/18:00)+ EURGBP 23:00(2,300)
  + 深夜建て→同日 06:00 判定の 3 本(火 01:00 EURJPY、水 00:00 GBPJPY、水 02:00 AUDJPY)。月曜合計 54,000 円(DAILY_STAKE_CAP 120,000 の内側)。
- `legs_for_slot` が日付をまたぐ定刻(火 23:58 起動→水 00:00 建て)を翌日の脚として拾い、`_day` を付けて返す。run_entries は state/CSV/契約照合をその日で扱う。
- `to_probe.py` EXTRA_TASKS に 9 タスク追加(月 09:58/12:58/13:58/15:58/17:58/20:58、火 00:58/23:58、水 01:58)。登録は次回の to_probe 実行時(`-Mode check` で即時)。
- ベット額は DD 予算 30 万円(資金 40 万円に緩衝 10 万円)。40 万円を DD 予算にするなら全脚 ×1.33。
- テスト: `python -m pytest -q test_to_live.py`(13 件)。

## v1.3 (2026-10-27): メニューを「勝率上位10セルのみ」に変更(追補29裁定・ユーザー決定、DD予算40万円で月期待 +69,646円・最悪月 −162,058円)
- 既存4脚(07:00×3・EURGBP 23:00)を外し、上位10セルだけにする。06:58 と 22:58 のタスクは脚が無く「実行する脚は無い」で終了(無害)。
- ベット(DD予算40万円=資金40万円全額。ヒストリカル最悪DDで口座が尽きる設定であることは追補29補足に記載): AUDJPY 10:00 9,800 / EURJPY 13:00 9,800 / EURJPY 14:00 9,600 / USDJPY 14:00 9,600 / EURJPY 16:00 10,400 / USDJPY 18:00 9,400 / EURJPY 21:00 9,000 / EURJPY 火 01:00 9,400 / GBPJPY 水 00:00 9,600 / AUDJPY 水 02:00 8,900。月曜 67,600 円、週 95,500 円。
- v1.2 からの差分はメニューのみ(日付またぎ処理・9タスクは v1.2 のまま)。

## 実口座キーの登録 `to_setkey_real.bat` (2026-10-28)
- theoption マイページ → 自動売買用API →「リアル」タブ →「APIキーをリクエスト」で出たキーを、PC で `to_setkey_real.bat` を実行して貼り付ける(画面に出ない・ユーザー環境変数 `THEOPTION_API_KEY_REAL` に保存)。
- 直後に実口座の health と残高を読むだけの接続確認を行う(発注しない)。キーの iss が実口座用でなければ中止。
- これだけでは実口座で発注しない。`to_config.json` に `"live_real": true` を入れた時点で切り替わる(11/3 の週次突合で判定)。

## v1.4 (2026-10-31): 実口座メニューを「事前登録4脚 + AUDJPY 02:00 プール脚」に(追補31裁定、DD予算40万円換算で月期待 +61,160円)
- ウォークフォワード(追補31)で v1.3 の勝率上位10は実力がインサンプルの約4割と判明 → 紙上追跡に降格。
- MENU: EURJPY 21,300 / AUDJPY 22,700 / NZDJPY 18,700(月 07:00→翌06:00)、EURGBP 10,000(月火水金 23:00・対象月)、AUDJPY 4,800(火〜金 02:00→同日06:00 = 月〜木セッション末尾)。月曜合計 72,700 円。
- `to_probe.py` EXTRA_TASKS に 火・木・金 01:58 の live タスクを追加(水は v1.2 の既存タスク、月 06:58・毎日 22:58 は v1.0 から)。登録は次回の `-Mode check`。
- v1.2/v1.3 で追加した月曜 10:00〜21:00・火 00:58・火 23:58 のタスクは脚が無いため空振り(無害。削除は任意: `schtasks /Delete /TN chien_theoption_live_1000 /F` など)。
- テスト: `python -m pytest -q test_to_live.py`。
