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

## 手順(Windows)
1. theoption にログイン → メニュー「自動売買用API」→「お試し」タブ →「APIキーをリクエスト」。表示されたキーをコピー(一度しか出ない)。**キーはチャットやメールに貼らない。**
2. PowerShell で(自分の PC でだけ):
   ```
   [Environment]::SetEnvironmentVariable("THEOPTION_API_KEY", "<お試し用キー>", "User")
   ```
   PowerShell を開き直してから:
   ```
   cd C:\chien\ops\theoption
   pip install websockets
   python to_probe.py --check
   ```
   health・残高と、60 秒間に見えた契約の要約が出る(平日の昼に一度やって接続を確かめる)。
3. 月曜朝の記録をタスクに登録:
   ```
   powershell -ExecutionPolicy Bypass -File install_task_probe.ps1
   ```
   月曜 05:25 → 09:30 JST に記録する。PC は起動しておく(スリープ不可)。
4. 月曜 09:30 以降に:
   ```
   python to_summarize.py out\probe_demo_<日付>_0525.jsonl
   ```
   出力をそのままチャットに貼る(キーは含まれない)。

## 予定
- 10/26(月・夏時間 開場 06:00)と 11/2(月・冬時間 開場 07:00)の 2 回を記録 → 合格なら `ops/ig_binary/ig_gap_bot.py` を theoption API で自動発注する版にし、お試し環境で数週間。
- `contract_data` の購読書式はクイックスタートに要約しか無いため推測(`{"stream":"contract_data","key":<契約名>}`)。拒否されても応答を記録するので、要約の (4)(5) で書式を直す。

## ファイル
- `to_probe.py` — health / balance / WebSocket(contracts・contract_data)を記録。`/buy`・`/sell` は呼ばない(テストで確認)。
- `to_summarize.py` — 記録の要約。
- `install_task_probe.ps1` — 月曜朝のタスク登録。
- `test_to_probe.py` — `python -m pytest -q`(偽ゲートウェイで往復を確認・4 passed)。
