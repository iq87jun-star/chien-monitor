# IG 窓埋めボット(判定・通知・記録)— VPS 配置手順

> **注意(2026-10-13): IG 証券は月曜 07:00 の回号を提供していない(9:00 / 夏 8:00 から)。このボットの 07:00→09:00 は IG では買えない。** 他社も月曜 07:10 以降で、効果は残らない(`research/ig_binary/README.md`「業者別の実行可能性」)。記録用としてのみ使う。

根拠と未確認事項は `research/ig_binary/README.md`。IG 証券の国内バイナリーは API 発注の可否が未確認のため、**発注は手動**。ボットは月曜 07:02 に「買う通貨ペア」を通知し、09:05 に勝敗と仮想損益を記録する。

## 1. 置く・入れる
`C:\chien\ops\ig_binary\` に `ig_gap_bot.py`・`config.example.json`・`install_task_ig.ps1`・`test_ig_gap_bot.py` を置き、
```
pip install dukascopy-python pandas
```

## 2. config.json
```
cd C:\chien\ops\ig_binary
Copy-Item config.example.json config.json
notepad config.json
```
- 最初は `"transport": "dry"`・`"stake": 1000`(デモ口座の期間)
- 通知先: Slack の Incoming Webhook URL(`"notify_format": "slack"`)か Discord の Webhook URL(`"discord"`)を `webhook_url` に貼り、`"transport": "webhook"` にする。URL はチャットに貼らない
- `log_csv` は Google ドライブ同期フォルダに置くとスマホから見られる

## 3. 検証(ネットワークあり・発注なし)
```
python -m pytest -q                                                    # 6 passed
python ig_gap_bot.py --config config.json --action signal --date 2026-10-12 --dry
python ig_gap_bot.py --config config.json --action settle --date 2026-10-12 --dry
python ig_gap_bot.py --config config.json --action report
Remove-Item out\state.json, <log_csv> -ErrorAction SilentlyContinue  # 試し実行の記録を消す
```
期待(2026-10-12): 7 ペアすべて HIGH、結果は 3 勝 4 敗(EURUSD・GBPUSD・AUDUSD が勝ち)。

## 4. タスク登録
```
powershell -ExecutionPolicy Bypass -File install_task_ig.ps1
```
signal 月曜 07:02 / settle 月曜 09:05 / report 日曜 12:00(JST)。止めるときは同じフォルダに `HALT` という空ファイルを置く。

## 5. 毎週の手作業
1. 07:02 の通知を見て、IG の第 4 回号(07:00→09:00)で該当ペアの「HIGH」を買う。
2. 1 枚あたりの購入価格(円)を `log_csv` の `ig_premium` 列に記入する(IG の判定が中値と違ったときは `ig_result` 列に win / lose)。
3. `--action report` で `ig_breakeven`(実際の損益分岐)と `ig_pnl` を確認する。`ig_breakeven` が 0.60 を超えるなら、この手法は IG では成り立たない。

## 段階
| 段階 | 期間 | stake | 進む条件 |
|---|---|---|---|
| デモ | 4〜6 週 | デモ 1,000 円 | 月曜 07 時に買えること・`ig_breakeven` ≤ 0.57 |
| 本番 小 | 2 か月 | 1,000〜5,000 円 | 実勝率 ≥ 58%・`ig_pnl` > 0 |
| 本番 | — | 20,000 円 | 直近 8 週の勝率 < 50% なら 1 段階戻す |
