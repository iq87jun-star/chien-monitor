# docs/362 Q94: ストラテジーテスターの自動化(chien_tester.py・tester_parity.py)— 実装完了、実行はテスター専用端末の準備後(工学・セル 0)

2026-10-16(金)朝の定例。docs/322 Q94(order 11)。新規ファイル: `ops/vps/chien_tester.py`(1.0)、`ops/vps/tester.example.ini`、`research/forward/tester_parity.py`。配備(manifest・docs/241)と既存の agent / deploy は変更していない。

## 1. 目的
Q1 の B 段(docs/244: テスターの取引数 ≥ 95%・累計損益差 ≤ 5%)と、以後の EA 改訂(Q95 の include 化など)のパリティ確認を人手なしで回す。

## 2. 設計
- **テスター専用端末**: `terminals.json` に `"tester": {"path": "C:\\chien\\mt5\\_tester\\terminal64.exe", "login": …, "server": …, "currency": "USD", "leverage": 100}` を足す(ポータブル構成 = terminal64.exe と同じフォルダに MQL5。ログイン済みなら password 省略可)。**本番 10 端末では走らせない**(path が本番と同じ・端末が起動中なら中止)。自動売買は起動しない(`[Experts]` を書かない)。
- **手順**(`run_tester`): ① GitHub の `mql5/<EA>.mq5` を取得して MetaEditor でコンパイル(chien_deploy.compile_ea と同じ・`MQL5\Experts\chien\`)→ ② `chien_tester.ini`(`[Tester]` Expert / Symbol / Period / Model=1(1 分足 OHLC)/ FromDate / ToDate / Deposit / Report / ReplaceReport=1 / ShutdownTerminal=1 / Visual=0、任意で `ExpertParameters=<set>`)を書く → ③ `terminal64.exe /portable /config:chien_tester.ini` を起動し自動終了を待つ(既定 1 時間で打ち切り)→ ④ `report.htm`・`Tester\logs` の最新・パスワード行を除いた ini・`meta.json` を Drive `chien_ops/_tester/<UTC 日時>_<EA>_<銘柄>/` に置く。
- **比較**(`tester_parity.py`): レポートの約定表(英語 / 日本語の見出しに対応・lxml 不要)から決済約定を月次に集計し、Python 側の期待(`month,pnl,trades` の CSV・paper_forward / recentfit_screen の出力)と比較。出力: 取引数比・累計損益差(名目比 %)・月次符号一致率・判定(通過 / 不一致)。`--selftest` で合成レポートの自己検査(通過を確認済み)。
- 使い方:
  - VPS: `python chien_tester.py --config terminals.json --ea "<EA ファイル名>" --symbol GBPJPY --period H1 --from 2024-01-01 --to 2026-08-31 --deposit 100000`
  - 研究側: `cd research && python3 forward/tester_parity.py --report <report.htm> --expected <csv> --nominal 100000`

## 3. 制限・注意
- レポートは `Report=` の htm のみ(xlsx は MT5 の ini では指定できない)。多通貨 EA は `Symbol=` のチャート銘柄で起動し、他銘柄は EA が自分で参照する(履歴は端末側に必要・docs/291 の FN 履歴の範囲)。
- テスター端末のデータフォルダは本番と分離されるため、`InpLogUrl`(Q111)等の WebRequest は許可 URL 未登録で失敗するが、テスト結果には影響しない。
- 実行には VPS 側でテスター端末の準備(ポータブル展開・ログイン・履歴の取得)が要る。これは配備変更ではないが VPS 上の作業なので、10/17–18 の切替の後に別途行う(切替と混ぜない)。

## 4. 提案(11 月改訂・新規口座への含意)
- Q1 B 段: テスター端末が整い次第 `chien_tester.py` で v1.40(`InpTsmomLegs` のみ・2024-01〜2026-08)を走らせ、`tester_parity.py` で判定 → docs/291 の続き。
- Q95(include 化)の受け入れ基準を「include 版 = 現行版 のテスター一致(取引数 100%・損益差 0)」にし、本スクリプトで確認してから切替候補にする。
- 毎週土曜に manifest の EA 全部をテストする定期タスクは、端末準備後に `install_task.ps1` へ `chien_tester` タスクとして足す(別項目・11/1 改訂)。

累積セル数: 9,750(Q94 はセル 0)。次回: Q95(EA 共通部の include 化・設計)。
