# theoption 自動売買 API の確認用プローブ(取引しない)

> 目的: 月曜朝の窓埋め効果(`research/ig_binary/README.md`。下窓・開場時点で未埋め → 07:00→08:00 の上昇率 70.8% / 70.3% / 76.6%)を、theoption の **期間固定(FD)・1 時間・ハイロー** で取れるかを決める。
> 国内業者は月曜の初回が 7:10〜9:00 で取れなかった。theoption の FD は「買った時点から 1 時間」なので、**開場直後に買えれば**取れる可能性がある。

## 確かめること(このプローブで分かる)
| | 何を見るか | 合格の目安 |
|---|---|---|
| 1 | 月曜に `通貨|FD|1H|HIGHLOW|…` が Opened で出る時刻(JST) | 開場(夏 06:00 / 冬 07:00)から **20 分以内** |
| 2 | 払い戻し倍率(契約 JSON の欄。名前が分からないので全欄を記録) | 1.8 倍なら損益分岐 55.6%、1.7 倍なら 58.8% |
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
   - タスク登録: `chien_theoption_monday`(月曜 05:25〜09:30 記録)・`chien_theoption_check`(火〜金 12:00 に 60 秒の接続確認)
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
