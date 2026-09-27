# 317 運用自動化 段階 1: VPS エージェント + Google Drive + 毎朝の取り込み(2026-09-27)

ユーザー「インジケータ変更自動化や、フォワード記録の取得等、セッティングから運用まで総じて自動化したい」→「VPS 1 台に集約」「Drive で Ok」。

## 0. 全体像(4 段階)
| 段階 | 内容 | 状態 |
|---|---|---|
| **1** | **運用エージェント**(VPS の Python が各 MT5 端末から約定・建玉・equity・EA ログを毎時 CSV に出す)→ Google Drive → 研究側の Routine が毎朝取り込み、ダイジェスト・逸脱監視・台帳更新 | **本書・実装済み(VPS 側の初回セットアップ待ち)** |
| 2 | 配備スクリプト: リポジトリ pull → MetaEditor CLI で一括コンパイル → 各端末へ配置 → .set / テンプレート(表示インジケータ込み)を自動適用 | 設計済み・未実装 |
| 3 | EA の設定ホットリロード(`MQL5/Files/chien_config.json`): 祝日リスト・倍率・スキップ日を再アタッチ無しで反映 | 未実装(EA 8 本の改修) |
| 4 | 日次ダイジェストの通知(プッシュ/メール) | 段階 1 の Routine 報告で代替、後で通知に拡張 |

## 1. 段階 1 の構成
```
VPS(Windows)                                   Google Drive              研究側(このセッション)
┌───────────────────────────┐   同期   ┌───────────────┐  MCP   ┌──────────────────────────┐
│ MT5 端末 ×9(各業者)         │ ───▶ │ マイドライブ/  │ ───▶ │ research/ops_inbox/<acct>/ │
│ chien_ops_agent.py(毎時)   │        │  chien_ops/    │        │ forward/ops_ingest.py       │
│  → chien_ops/<acct>/*.csv  │        │   <acct>/*.csv │        │ forward/deviation_monitor.py│
└───────────────────────────┘        └───────────────┘        │ 台帳ページ更新・報告          │
                                                                └──────────────────────────┘
```
出力(口座ごと): `positions.csv`(決済済みポジション。MT5 履歴 xlsx と同じ列 + `magic` `sl_hit` `tp_hit`)/ `open_positions.csv` / `equity_log.csv`(毎時追記)/ `ea_log_extract.csv`(MQL5/Logs から `[HALT]` `[BAL GUARD]` `[DAILY STOP]` `[EXPIRY]` `[INIT` `[Mon ENTRY]` 等)/ `deals_raw.csv`(監査用)。ルートに `status.json`(端末ごとの成否)。

研究側は `mt5_report.parse()` が `.csv` を xlsx と同じ形で返すようにしたので、`leg_forward.py`・`deviation_monitor.py`・月次スコアリングがそのまま使える(xlsx の手動送付は不要になる)。

## 2. VPS 側セットアップ(ユーザー操作・初回のみ、30 分)
**ワンクリック**: `ops/vps/chien_setup.bat` を VPS に置いてダブルクリック(UAC「はい」)。Git 導入 → clone → `setup.ps1`(Python 導入 → `--discover` で各端末に接続して口座番号を自動判定し terminals.json を生成 → 1 回実行 → 毎時タスク)まで無入力で進む。未ログイン端末があった時だけメモ帳が開く。
**最短経路(Claude Code)**: VPS に Claude Code(Windows 版 CLI またはデスクトップ)を入れ、このリポジトリを clone して `ops/vps/setup.ps1` を管理者 PowerShell で実行させる。Python 導入・pip・端末の自動検出・terminals.json 雛形・手動 1 回実行・毎時タスク登録まで 1 コマンド(パスワードは VPS 上のメモ帳で記入し、外に出ない)。Cowork は Windows 上ではコードを隔離 Linux VM で実行するため、Windows 専用の MetaTrader5 パッケージ実行やタスクスケジューラ登録は行えない(ファイルの準備までは可)。以下は手動で行う場合の手順。
1. Python 3.11(64bit)を入れ、`pip install MetaTrader5 pandas`。
2. Google Drive for desktop を入れ、マイドライブに `chien_ops` フォルダを作る(同期先が `G:\マイドライブ\chien_ops` になる想定。ドライブ文字が違えば手順 4 で直す)。
3. リポジトリの `ops/vps/` フォルダを VPS にコピー(`chien_ops_agent.py` `terminals.example.json` `install_task.ps1`)。
4. `terminals.example.json` を `terminals.json` にコピーして編集: 端末ごとの `path`(terminal64.exe の実パス)、`account`、`login`、`server`、必要なら `password`。`out_root` を Drive の同期パスに。**terminals.json は VPS の外に出さない**(git 管理外・私にも送らない)。
5. 手動で 1 回実行して確認: `python chien_ops_agent.py --config terminals.json`。端末ごとに `[名前] ok balance=... equity=... 建玉=... 決済済=...` と出れば成功。失敗した端末はエラー(`Authorization failed` = ログイン情報、`initialize 失敗 (-10005...)` = path)を直す。
6. 管理者 PowerShell で `powershell -ExecutionPolicy Bypass -File install_task.ps1` → 毎時実行のタスク `chien_ops_agent` が登録される。ログは `agent.log`。
7. Drive の `chien_ops/<口座>/` に CSV が現れたら、このチャットに「エージェント稼働」と一言。私が Routine の初回取り込みを実行して結果を確認する。

注意:
- MetaTrader5 パッケージは一度に 1 端末しか接続できないため、9 端末を順に回す(1 端末 5〜20 秒)。
- 端末が起動していれば attach、起動していなければ `path` から起動する(初回はログイン情報が要る)。
- FTMO/FN/Fintokei とも「自分の口座の履歴を読む」だけで発注しないので規約上の問題はない。
- 「サーバー時刻」で記録される(MT5 履歴 xlsx と同じ)。研究側の既存パーサと整合。

## 3. 研究側(実装済み)
- `research/forward/ops_ingest.py <dir>`: ダイジェスト(口座ごとの equity・建玉・7 日/30 日損益・SL 決済率・レグ別損益・警告行・最後の INIT)→ `results/ops_digest_latest.json`。
- `research/forward/mt5_report.parse_csv()`: `positions.csv` を xlsx と同じ tuple で返す。`deviation_monitor.latest_reports()` は `<acct>/positions.csv` も拾う。
- Routine「運用ダイジェスト(毎朝)」(07:50 JST): Drive の `chien_ops` を `research/ops_inbox/` に落とし → `ops_ingest.py` → 異常(ガード発動・EXPIRY・エージェント失敗・24h 建て無し)があればその口座を報告、無ければ 1 行。月曜は `deviation_monitor.py` も実行。毎月 1 日は月次スコアリングに使う。

## 4. 段階 2〜3 の設計メモ(次に着手する内容)
- 配備: `ops/vps/deploy.ps1` — `git pull` → `metaeditor64.exe /compile:"<file>" /log` を EA ごとに → `.ex5` を各端末の `MQL5/Experts/chien/` へコピー → 端末の起動 ini(`[StartUp] Expert=chien\EA3 Symbol=GBPJPY Period=H1 ExpertParameters=EA3.set`)。表示インジケータ `Chien_View.mq5`(ショット時刻・SL 水準・スキップ日・指数寄り窓)を `.tpl` に同梱。
- ホットリロード: 各 EA に `InpConfigFile="chien_config.json"` を追加し、毎時 `FileOpen` で読んで `InpJpHolidayMondays` 等の実効値を上書き(input は変更できないため実効値を別変数に持つ)。リポジトリの `ops/config/chien_config.json` を Drive 経由で各端末の `MQL5/Files/` に同期。
- どちらもユーザーの「段階 2 に進む」で着手。
