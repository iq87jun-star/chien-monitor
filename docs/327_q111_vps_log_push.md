# 327.【Q111】記録版 EA — VPS 上の EA が自分でログ・スナップショット・約定を Drive に送る(WebRequest + Apps Script)
> docs/322 §5a Q111(工学・セル 0)。2026-10-07 ユーザー「EA を変更したいので、記録版を作成してください」。生成: `research/queue/q111_make_log_versions.py`(配備中 10 本に同じ加工を機械的に適用・再実行可)。受け口: `ops/gas/chien_log_receiver.gs`。取り込み: `research/forward/ops_ingest.py`(`vps_log_*.csv` を読む)。
> **配備は変えていない**(`ops/config/deploy_manifest.json`・docs/241 は不変)。切替はユーザーの「切替」後に manifest の `ensure` を新版名へ変えて bat → ログイン → プロファイル → VPS→移行。

## 1. 何が変わるか(取引ロジックは不変)
| 項目 | 内容 |
|---|---|
| 置換 | EA 内の `Print(...)` / `PrintFormat(...)` を `ChienLog(...)` / `ChienLog(StringFormat(...))` に機械置換。端末のエキスパートログには今までどおり出る + 送信キューに積む |
| 追加入力 | `InpLogUrl`(Apps Script の `/exec` URL・**空なら従来と完全に同じ動作**)、`InpLogSnapshotMin`(既定 60 分)、`InpLogTimeoutMs`(既定 2000) |
| 送信 | 30 秒ごとの `OnTimer` 先頭で: 新しい約定(DEAL)を拾う → 毎時スナップショット(SNAP)→ キューを 60 秒ごと(または 20 行たまったら)HTTPS POST。1 回 100 行まで・キュー上限 200 行(超えたら古い行から捨てる)。3 回連続失敗後は 10 分おきに再試行。失敗は `[LOG SEND]` を 1 時間に 1 回だけ端末ログに出し、取引には影響しない |
| DEAL の理由 | `DEAL_REASON` から SL / TP / STOPOUT / EXPERT(EA の時間決済・HALT など)/ CLIENT(手動)を付ける。SL 発動と「建てなかった」(`[Mon SKIP]` 等)が履歴だけでなく行として残る |
| フック | `OnInit` 末尾 `ChienLogInit()`(INIT 行 + 初回 SNAP + 即送信)、`OnDeinit` 先頭 `ChienLogDeinit()`、`OnTimer` 先頭 `ChienLogTimer()` |

生成した記録版(版 +0.01・別ファイル):

| 口座 | 元(配備中) | 記録版 |
|---|---|---|
| Topaz 6104739 | EA11 v1.11(Q93 ロット修正版・未配備) | `…EA11_Mon4x2.0+Roll5x1.0+NonFX0.5_v1.12.mq5` |
| ルビー 6104736 | B案 v1.01(同上) | `…RecentFit_B案_4.0倍_v1.02.mq5` |
| パール 6071612 | RecentFit_4.0倍 v1.07(同上) | `…RecentFit_4.0倍_v1.08.mq5` |
| FTMO 521100397 | EA8 v1.34 | `…EA8_Mon4_3.3倍+GER40ブレイク_2.0倍_v1.35.mq5` |
| FTMO 531407058 | EA3 v1.16 | `…EA3_Mon4_3.3倍_v1.17.mq5` |
| FN 11988011 | G v1.15 | `…RecentFit_G_Mon2x4+MonNAS100_US500x1_v1.16.mq5` |
| FN 14074882 | Mon3x4+HoldXAU0.4 v1.09 | `…RecentFit_Mon3x4+HoldXAU0.4_ギャンブル_v1.10.mq5` |
| FN 14166201 | NonFX 1.48 + Roll5 v1.31 | `…RecentFit_NonFX_1.48倍+Roll5_3.0倍_v1.32.mq5` |
| FTMO 531343523 | EA10L v1.01 | `…EA10L_Mon4_3.3倍+GER40ブレイク_2.0倍+HoldXAU0.3_v1.02.mq5` |
| FTMO 531466484(未稼働) | EA9 v1.00 | `…EA9_A案_HoldXAU+MonGBPJPY+MonNAS100_1.5倍_v1.01.mq5` |

検証(本セッション): 各記録版から Q111 ブロック・フック・置換を機械的に戻すと元ファイルと一致(差分は `PrintFormat(...)` の閉じ括弧 1 個のみ)。文字列外の括弧数は元 + ブロック分と一致。MetaEditor でのコンパイルは手元 PC の bat(manifest 更新後)で行う。

## 2. 送信形式と保存先
- 1 行 1 レコードの CSV: `account,utc,server_time,kind,ea,text`。`kind` = `LOG`(ログ行・400 文字まで)/ `SNAP`(`balance= equity= margin= free= positions=N sym|side|vol|open|pnl|magic|comment;…`)/ `DEAL`(`deal= pos= IN|OUT sym buy|sell vol= price= profit= comm= swap= magic= reason= time= comment=`)/ `INIT` / `DEINIT`。
- Apps Script が Drive `chien_ops/<口座>/vps_log_YYYY-MM.csv` に追記(口座フォルダが無ければ作る)。手元 PC のエージェントと同じフォルダなので、毎朝の取り込み(`ops_ingest.py`)がそのまま読む。
- ダイジェストに追加: `VPS ログ: 最終 <utc>(<h> 時間前) 24h {LOG: n, SNAP: n, DEAL: n} ENTRY 3d n`。**最後の受信から 2 時間以上**空くと `[VPS SILENT]` 警告(EA 停止・端末切断・WebRequest 不許可のいずれか)。`[HALT]` `[MONTH STOP]` `[LOG SEND]` 等は警告欄に出る。

## 3. ユーザー側の準備(一度だけ)
1. **Apps Script を公開**: https://script.google.com → 新しいプロジェクト → `ops/gas/chien_log_receiver.gs` の中身を Code.gs に貼る → デプロイ → 新しいデプロイ → ウェブアプリ → 実行ユーザー「自分」・アクセス「全員」→ デプロイ。表示された `https://script.google.com/macros/s/…/exec` を控える(= `InpLogUrl`)。ブラウザで開いて `{"ok":true,…}` が返れば受け口は動いている。初回は Drive へのアクセス許可を求められる。
2. **端末の許可 URL**: 各端末で ツール → オプション → エキスパート → 「WebRequest を許可する URL」に `https://script.google.com` と `https://script.googleusercontent.com` の 2 行を追加(POST 後のリダイレクト先も必要)。この設定は VPS 移行時に写る。
3. **切替時**(ユーザー「切替」後・11 月の改訂と同時でも可): manifest の `ensure` を記録版名に更新 → bat でコンパイル → 口座でログイン → プロファイル `chien_<口座>` → 記録版の入力 `InpLogUrl` に 1 の URL を貼る → VPS→移行。移行後の最初の 1 分以内に Drive に `vps_log_YYYY-MM.csv` ができ、`INIT` と `SNAP` の行が入る。
4. 戻し方: `InpLogUrl` を空にする(送信しない・他は同一)か、元の版に戻す。

## 4. 注意
- `InpLogUrl` と Apps Script の URL は**公開リポジトリに書かない**(.set ファイルか入力欄にだけ置く)。URL は書き込み専用の受け口で、漏れても被害は「ゴミ行が入る」程度。
- `WebRequest` は同期呼び出し(最大 `InpLogTimeoutMs`=2 秒)。送信は 60 秒に 1 回・OnTimer 内のみで、OnTick(残高ガード)はブロックしない。
- MetaQuotes VPS で `WebRequest` が使えることは MQL5 の仕様どおり(許可 URL は移行時に同期)。移行後に `[LOG SEND] WebRequest 不許可(err 4014)` が端末ログに出たら 2 の設定漏れ。
- Apps Script の無料枠(1 日あたりの実行時間・回数)に対し、EA 10 本 × 毎分 1 回でも十分余裕がある。1 回の追記は数十ミリ秒。
- 手元 PC のエージェント(3 口座)は EA が止まった時の保険としてそのまま残す。読み取り専用端末 6 本の追加は本項と独立(docs/322 §5a)。

## 5. 提案(11 月の改訂への含意)
| 項目 | 変更する / しない |
|---|---|
| 記録版への切替 | **ユーザー判断(「切替」)**。10 月中に切り替えれば 11/1 の月次改正案に VPS 側の SKIP/HALT/約定理由が揃う。切替自体は EA の取引ロジックを変えないので、docs/322「10 月は配備を変えない」の趣旨(戦略を変えない)には反しない |
| Q95 include 化 | 記録版のブロックをそのまま `chien_core.mqh` の一部にする(生成スクリプトの BLOCK が原型) |
| Q103 531343523 の月内停止ガード | 記録版で `[MONTH STOP]` 行が残るようになるので、11 月以降は原因が記録から確定できる |
| 決済コメントの理由コード | DEAL の `reason=` で足りるため、コメント改変は**しない**(CTrade の決済コメントは業者側で上書きされることがある) |
