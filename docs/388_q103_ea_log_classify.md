# 388.【Q103・工学・セル 0】EA ログの警告を agent 側で分類し 30 日保持 — agent 1.8: 抽出マーカーに見送り・再試行・停止理由(`[Roll SKIP gate]` `[Brk SKIP spread]` `[Mon RETRY]` `[STOP]` `MONTH STOP` `[PAYOUT]` `[DYN` 等)を追加し、各行に `category`(停止 / 見送り / 建て / 情報 / 既知 / その他)を付けて `ea_log_extract.csv` を直近 30 日分保持。status.json に当日の分類別件数。ダイジェスト(ops_ingest)は「停止」だけを警告に数え、「見送り」と「既知」を別に表示
> docs/322 Q103(order 21)。2026-10-30(平日夕の定例)。変更: `ops/vps/chien_ops_agent.py`(1.7c → **1.8**・取引に触れない読み取り側のみ)、`research/forward/ops_ingest.py`(category 列の利用・無ければ従来の正規表現)。セル 0(工学)。累積セル 10,060 のまま。配備・manifest・EA は変更していない。

## 1. 変更点
| 項目 | 1.7c | 1.8 |
|---|---|---|
| 抽出マーカー | HALT / BAL GUARD / DAILY STOP / EXPIRY / PROFIT LOCK / TRAIL / INIT / ENTRY / Mon SKIP / TIME EXIT / CLOSE ALL / NOTIFY / SIZE SANITY / 銘柄解決 / LOG | + `[STOP]` `MONTH STOP` `[Mon RETRY]` `[Roll SKIP …]` `[Roll RETRY]` `[Roll TIME EXIT]` `[Sess SKIP …]` `[Brk ENTRY/RETRY/SKIP …]` `[Hold SKIP/EXIT …]` `[v4 GIVEUP]` `[PAYOUT]` `[DYN …]` `[WEEKEND …]` |
| 分類 | なし | `category` 列: **既知**(補助 EA Util の診断・NAS100 未解決)→ **停止**(HALT・BAL GUARD・DAILY STOP・EXPIRY・PROFIT LOCK・TRAIL・STOP・MONTH STOP・CLOSE ALL・SIZE SANITY)→ **見送り**(SKIP・RETRY・GIVEUP・解決できず・WEEKEND)→ **建て**(ENTRY・TIME EXIT)→ **情報**(INIT・PAYOUT・DYN・NOTIFY・LOG・銘柄解決)→ その他。先に当たった分類が勝つ(既知を最優先) |
| 保持 | 毎時 `--log-days`(既定 3 日)分を上書き | 前回ファイルと結合し **直近 30 日**を保持(file + line で重複除去) |
| status.json | `halts`(抽出全体) | `halts` は当日分、`alert_counts_today` = 当日の分類別件数を追加 |
| ダイジェスト | 警告 = 正規表現 | 警告 = 停止、見送り・既知は別に件数表示(`警告 n 見送り m 既知 k`)。agent 1.7c の記録には従来どおり |

## 2. 検証(単体)
- 分類: `[HALT]`→停止、`[Roll SKIP gate] CADJPY`→見送り、`[Mon ENTRY]`→建て、`[INIT Q131]`→情報、`[銘柄解決] Util …`→既知、`'NAS100'を解決できず`→既知、`[CLOSE ALL Util]`→既知、`MONTH STOP`→停止、`[Brk SKIP spread]`→見送り。
- 保持: 40 日前の行は落ち、同じ行の重複は 1 本、当日行は category 付きで残る。
- `py_compile` 通過。実機(MetaTrader5 パッケージ)は自宅 PC でのみ動くため、反映後の初回 status.json で `agent_version: 1.8` と `alert_counts_today` を確認する。

## 3. Q83(執行差)への含意
見送り行(`[Roll SKIP gate]` `[Roll SKIP spread]` `[Brk SKIP spread]` `[Mon RETRY]`)が 30 日残るので、建て損ねの原因(門・スプレッド・再試行の失敗)を記録から確定できる。10/29 の Roll で EURJPY / CADJPY が建たなかった理由(金利差門)も、1.8 以降は `[Roll SKIP gate] … carry=1.25pp 門=2.00` の行で残る。

## 4. 反映(ユーザー操作・取引ロジックに無関係)
agent は自己更新しない(docs/328)。自宅 PC で `C:\chien\chien_setup.bat` を再実行すると GitHub から `chien_ops_agent.py` 1.8 を取り直して毎時タスクを再登録する(端末・EA には触れない)。急がない。次の月曜(11/9・11/2 は祝日)までに入っていれば Q83 の原因記録に間に合う。
