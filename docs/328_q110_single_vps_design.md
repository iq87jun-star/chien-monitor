# 328.【Q110】VPS 1 台への集約設計 — Windows VPS 1 台に端末 10 本 + 毎時エージェント + Claude 遠隔操作を置き、MQL5 VPS(口座ごと課金)と手元 PC 依存をなくす
> docs/322 §5 Q110(設計・セル 0)。2026-10-07 ユーザー「クラウドリモートで EA の自動化した方がコスパ良いですよね」→「110 を進めてください」で前倒し。実施(購入・移行)はユーザー判断。
> 背景: 記録版(docs/327)の切替作業で、プロファイル → VPS→移行 の手順が口座ごとに手作業で、取り違え(14074882 の EA を別口座の端末に装着 → HALT)と反映漏れ(旧版のまま移行)が起きた。VPS 側のログを取るために WebRequest + Apps Script を足す必要があったのも、EA が「手の届かない機械」で動いているため。

## 1. いまの構成と費用
| 項目 | 現状 | 問題 |
|---|---|---|
| EA の実行 | 口座ごとに MQL5 VPS(MetaQuotes)。1 か月 $15 / 年契約 $12.8(公式) | 稼働 9 口座で **月 $115〜135**。ログ・設定は VPS 内で、手元から見えない |
| 端末 | 手元 PC に業者ごと 1 本(FTMO / FN / Fintokei)+ 追加分 | 1 端末 1 口座しかログインできず、記録は 3〜4 口座分のみ。EA 更新は「ログイン → プロファイル → 移行」を口座ごとに手で行う |
| 記録 | 手元 PC の毎時エージェント → Google Drive → 朝の取り込み | PC の電源・スリープ・タスク設定に依存(docs/317 §5b の停止事故) |
| 遠隔操作 | なし(手順を文章で渡し、スクリーンショットで確認) | 1 口座の切替に 30 分以上かかることがある |

## 2. 集約後の構成
```
[Windows VPS(ロンドン・4 vCPU / 8 GB)]
  ├ MT5 端末 ×10(業者インストーラを口座ごとに別フォルダへ・常時ログイン・自動売買 ON)
  │   └ EA は端末上で直接稼働(manifest の apply で Default プロファイルを書き換え → 端末再起動)
  ├ C:\chien\ops  毎時エージェント(terminals.json・chien_deploy・Drive for desktop で chien_ops へ)
  ├ claude remote-control(ログオン時に常駐。切替・付け替え・ログ確認を私がその場で実行)
  └ 監視: エージェントが端末の生死を見て再起動、Drive 無更新 3 時間で朝の「エージェント停滞」
```
- MQL5 VPS は不要になる(1 か月は並走させて解約)。Apps Script 送信(Q111)は不要になるが、端末が VPS 上で動くので `InpLogUrl` は空のまま記録版を使ってよい(ログは同じ機械のファイル)。
- 手元 PC は何も持たなくてよい(閲覧用の端末があれば十分)。

## 3. 費用(目安・2026-10 時点の公開価格)
| 候補 | 仕様 | 月額 | 備考 |
|---|---|---|---|
| Kamatera(ロンドン DC) | 4 vCPU / 8 GB Windows | 約 $42 + Windows ライセンス(目安 $10〜15) | CPU 占有率が安定。$100 の試用枠あり |
| Vultr(ロンドン) | Regular 4 core / 8 GB | $40 + Windows ライセンス | 同上 |
| Contabo(ロンドン) | Cloud VPS 10: 4 vCPU / 8 GB | €5.45 + Windows(目安 €7〜10) | 最安だが CPU 共有が濃い。端末 10 本は CPU をほぼ使わないので実用上は足りる見込み |

- 月額 **$15〜55**(業者とライセンスで差)。MQL5 VPS 9 口座 $115〜135 に対し **月 $60〜120 の削減**。
- 端末 10 本のメモリは 1 本 150〜300 MB → 3 GB 程度。8 GB で余裕。ディスクは 1 本 1 GB 弱 + ログ。
- 遅延: FTMO・FundedNext の MT5 サーバーはロンドン(FN の MQL5 VPS が LD4 に割当てられていた)。Fintokei(AXSE)は別拠点の可能性があるが、Mon/Roll は定時成行で遅延 100 ms は結果に影響しない(docs/323 の滑り 1〜2 bps は主にスプレッド)。

## 4. 手順(私が遠隔で行える部分 = ◎、ユーザーが行う部分 = ●)
| 段階 | 作業 | 担当 | 所要 |
|---|---|---|---|
| P0 | VPS 購入(Windows Server 2022、ロンドン)。RDP の初期パスワードを変更。Windows Update 自動・タイムゾーン UTC | ● | 30 分 |
| P1 | RDP で入り、Google Drive for desktop をインストールして同じ Google アカウントでログイン(`chien_ops` が G: に見える状態)。Claude Code を入れて `claude remote-control` を起動(以後は私が操作) | ● | 30 分 |
| P2 | 業者の MT5 インストーラを口座ごとに別フォルダへ 10 本(`C:\chien\mt5\<口座>`)。各端末でマスターでログイン・「ログイン情報を保存」・自動売買は**まだ OFF** | ●(インストーラ実行とログイン)/ ◎(フォルダ作成・確認) | 60 分 |
| P3 | `chien_setup.bat` 実行 → 端末 10 本を検出 → 毎時タスク登録。Drive に 10 口座のフォルダができることを確認 | ◎ | 15 分 |
| P4 | **観察運転**: EA は付けず(自動売買 OFF)、毎時の記録が 24 時間続くことを確認 | ◎ | 1 日 |
| P5 | **口座ごとの切替**(火〜木の日中 JST): MQL5 VPS の EA を「停止」→ 新 VPS の端末に manifest の `apply` で EA を装着 → 自動売買 ON → `[INIT …]` と建玉の引き継ぎ(同 Magic)を確認。1 口座 10 分 | ◎(停止の操作だけ ●、または私が端末の VPS タブから) | 2 時間 |
| P6 | 並走期間: MQL5 VPS の契約は月末まで残す(戻すときは移行 1 回)。月末に解約 | ● | — |

- **二重稼働の禁止**: 同じ口座で MQL5 VPS と新 VPS の EA が同時に動くと、Mon ショット(建玉有無を見ない)が二重に建つ。P5 は必ず「停止 → 装着」の順。
- 端末の自動起動: タスクスケジューラ「ログオン時」に 10 本の `terminal64.exe` を起動。Windows は自動ログオン(RDP を閉じてもセッションは残す)。
- エージェント 1.8 で追加: `mt5.initialize` に失敗した端末を起動し直す(現状は失敗を記録するだけ)。

## 5. 安全・規約
- 業者規約: FTMO / FundedNext / Fintokei とも VPS と EA は許可。同一人物の複数口座が同一 IP から接続するのは問題ない(禁止されているのは他人との口座共有・コピー)。
- パスワードは VPS 内の `terminals.json` と端末の保存情報のみ。リポジトリには置かない。私は `terminals.json` を読まない・送らない(現行どおり)。
- RDP は Windows ファイアウォールで自宅 IP(と必要なら携帯回線)だけ許可、パスワード 20 文字以上。可能なら Windows 標準の NLA を有効のまま。
- 単一障害点: VPS 停止 = 全口座の EA 停止。対策は (1) 業者側の自動再起動、(2) 毎時エージェントの無更新検知(朝のダイジェストで「停滞」)、(3) 緊急時は手元 PC からログインして MQL5 VPS に再移行(手順は docs/317)。
- 費用を払う代わりに「EA が動いている機械を自分で持つ」ので、EA の時刻依存(サーバー時刻 EET)は端末設定で変わらない。

## 6. リポジトリ側の変更(実施時)
| 変更 | 内容 |
|---|---|
| `ops/vps/chien_ops_agent.py` 1.8 | 端末の自動再起動(initialize 失敗時に `terminal64.exe` を起動して 60 秒待つ)。`portable` 不要 |
| `ops/config/deploy_manifest.json` | 口座ごとに `apply: true`(端末停止 → Default プロファイル書き換え → 再起動)。`prepare_profile` は不要に。`terminal` は `C:\chien\mt5\<口座>` のフォルダ名で一致させる |
| `ops/vps/install_task.ps1` | 端末 10 本のログオン時起動タスクを追加 |
| docs/317 | 段階 3「VPS 集約」を追記。手元 PC のエージェントは停止 |
| Q111(記録版の送信) | 不要(`InpLogUrl` 空のまま)。Apps Script は残しても害なし |

## 7. 判断事項(ユーザー)
1. 業者と予算: 推奨は **Kamatera ロンドン(4 vCPU / 8 GB / Windows Server 2022)**、月 $50 前後。安く済ませるなら Contabo。
2. 切替日: 週半ば(火〜木)の日中 JST。候補は 10/14(水)〜10/16(木)。月曜 13〜20 JST と水曜 05 JST 前後は避ける。
3. 並走期間: MQL5 VPS は 10/31 まで残して解約(FN 14166201 の期限値 10/31 と同時に整理)。

購入して RDP に入れる状態になったら「VPS 用意できた」と送ってください。P1 から私が遠隔で進めます。

Sources: [MetaQuotes VPS 価格](https://www.metatrader5.com/en/news/2300.md) / [Kamatera 4 core 8 GB](https://vpsbenchmarks.com/hosters/kamatera/plans/avail_8gb_4cores) / [Vultr Regular 8 GB](https://vpsbenchmarks.com/hosters/vultr/plans/regular_8gb_4cores) / [Contabo Cloud VPS 10](https://www.comparevps.com/contabo-servers) / [2026 VPS 価格比較](https://vpssos.com/how-much-do-1-vcpu2gb-2-vcpu-4gb-and-4-vcpu-8gb-servers-cost/)

## 8.【2026-10-07 追記】別枝(money-earning-methods)の自宅 PC タスクの扱い
ユーザー「ここら辺の自動化も纏めて集約できますか」。あちらの自動化は (1) Cloudflare Worker + D1 + Discord(判定・通知・保存・既にクラウド)、(2) Claude Routine の `relay.mjs`(クラウド)、(3) **自宅 PC の夜間タスク `gameclub_watch`(22:40)** = ゲームトレード / ゲームクラブの一覧取得と SOLD 収集 → Worker へ送信、の 3 層。(3) だけが PC 依存で、理由はサイトがクラウド IP(GitHub Actions・Cloudflare)を 403 / ボット確認で弾くため。
- VPS 設置日に VPS の IP から両サイトを取得して試す。通れば `gametrade-watch/pc/install-gameclub.ps1` を VPS で実行してタスクを移し、自宅 PC のタスクを外す。
- 弾かれる場合: (a) その夜間タスクだけ自宅 PC に残す(現状どおり)、(b) Tailscale の exit node を自宅(PC かルーター)に置き、VPS からの取得だけ自宅回線を出口にする。(b) は常時起動の小さな機械が自宅に要る。
- 取引側(端末 10 本・毎時エージェント・遠隔操作)の集約はこれと独立に進める。

## 9.【2026-10-07 実施記録】P0〜P3 完了(同日 22:30〜翌 00:45 JST)
| 段階 | 結果 |
|---|---|
| P0 | お名前.com デスクトップクラウド Premium 8GB(月 7,260 円・1 か月払い)を購入。Windows Server。 |
| P1 | RDP → Claude Code(native)導入・`claude auth login`・`C:\chien` を信頼・`claude remote-control` で接続(bridge 環境)。以後は研究側セッションが VPS 側セッション「VPS セットアップ(Q110 P1–P2)」に指示(persistent_session_id 宛の Routine を fire)して進めた。つまずき: PATH 未登録(`%USERPROFILE%\.local\bin` をユーザー PATH に追加)、ISE では対話画面が動かない、既定ブラウザが IE(Edge で開き直し)、ログインコードは `#` 以降を含めて最新の試行のものを貼る、コンソールの「選択」モードでキー入力が止まる、`Trust? [y/N]` と `Enable Remote Control? (y/n)` は `y` が要る。 |
| P2 | VPS 側セッションが 3 社のインストーラで導入 → `C:\chien\mt5\<口座>` に 10 本複製(**ポータブルモード**・各フォルダ内に MQL5/config)・デスクトップに `MT5_<業者>_<口座>` ショートカット 10 個。ユーザーが 10 本にマスターでログイン(保存)・自動売買 OFF。Google Drive for desktop ログイン(G:)。Python 3.12(`C:\Program Files\Python312`)。 |
| P3 | `chien_setup.bat run` → agent 1.7b(ポータブル配置は `portable=True` で接続・terminals.json に記録)が 10 端末を自動検出 → 手動 1 回実行で Drive `chien_ops\<口座>\` 10 口座分に positions / open_positions / equity_log / ea_log_extract を出力(15:41〜15:43 UTC)。毎時タスク `chien_ops_agent` 登録。`_diag/host.txt` の python が VPS のパスになっていることを確認。 |

- Drive の新規フォルダ ID: 521100397 `1rFJ5TL_Tbe4A0LpG8wx73QjxQ4Zy-L7K` / 531407058 `11gUePK80zY54r9asy104Bwk6H25QcpHt` / 531466484 `1lkLf00rNBlWmonO-4V5DvjI-DLxTf_0Q` / 6071612 `1TGibINorzKW52I3OoFz23Iz1zQOEl7mD` / 14074882 `1fsAo_b2lMpg1FdwEDXZIvdx8OxDl0wry`(既存: 11988011 / 14166201 / 531343523 / 6104736 / 6104739 は従来の ID)。朝の取り込みはこれで 10 口座分を読める。
- 手元 PC の毎時タスクは VPS と同じフォルダに書くため**無効化**する(`schtasks /change /tn chien_ops_agent /disable`)。ユーザーに依頼済み。
- 次: P4 観察運転(10/8 いっぱい・EA なし・自動売買 OFF)→ 10/9(木)以降の日中に P5 の口座ごと切替。P5 前にリポジトリ側の変更(§6: manifest `apply: true`・端末のログオン時起動タスク・agent 1.8 の端末再起動)を入れる。

## 8.【2026-10-11】P5(口座ごとの切替)の前提と進め方 — ユーザー「VPS に切り替えたいですね」
P4 観察運転は 10/7 15:41 UTC から継続中(10 端末・毎時)。4 日間で取得失敗は 10/10 22:00 UTC の 1 回(1 端末・翌時に自動復旧・docs/349 §6f)。agent は 1.7c(−6 の 1 回再試行・Q130)。

**§6 のリポジトリ側変更のうち、このセッションでは書けなかったもの**(auto モードの分類器が「本番配備」として拒否。理由は妥当で、取引機の端末を自動で起動・自動売買 ON にするコードは人の承認の下で入れるべき):
1. `chien_deploy.start_terminal` をポータブル対応(`/portable`)にし、装着時に自動売買 ON を起動 ini(`/config:` の `[Experts] Enabled=1 AllowLiveTrading=1`)で渡す。
2. agent 1.8: `initialize` 失敗時に端末を起動し直して 60 秒待つ(§6)。
3. `install_task.ps1` v4: 端末 10 本のログオン時起動タスク `chien_mt5_<口座>`。
これらはユーザーが通常モードのセッションで入れるか、手で入れる(各 10〜20 行)。入れずに P5 を始めることも可能で、その場合は端末の再起動と自動売買 ON がユーザーの手作業になる(VPS 再起動時のみ)。

**P5 の手順(口座ごと・火〜木の日中 JST・月曜 13〜20 JST と水曜 05 JST 前後は避ける)**
1. ユーザー: その口座の MT5 で VPS タブ → MQL5 VPS の EA を**停止**(同期を切る)。これで MQL5 VPS 側の建玉管理が止まる(建玉自体はサーバーに残る)。
2. ユーザー → 私に「切替 <口座>」。私は manifest の該当口座を `apply: true` にしてプッシュ。
3. VPS の毎時エージェントが端末を止め、Default プロファイルの chart.chr に新 EA を装着し、端末を再起動(ポータブル対応が無い間は、起動引数 `/portable` を付けた再起動と自動売買 ON の確認をユーザーが行う)。
4. 検証: Drive `chien_ops/<口座>/ea_log_extract.csv` に `[INIT …]`(新版・mult)が出る・`open_positions.csv` の建玉が同 Magic で引き継がれている・status.json の `attached_eas`。私が次の毎時で確認して報告。
5. 1 口座目(推奨: 失格コストが最小の FTMO 100k 531343523 宝くじ)で 1 週間問題なければ、残りを 2〜3 口座ずつ。
6. MQL5 VPS は口座ごとに「更新しない」で自然失効(月払い)。緊急時は docs/317 の手順で MQL5 VPS に戻せる。

**二重稼働の禁止**(§4): 必ず「MQL5 VPS 停止 → apply」の順。逆にすると Mon ショットが二重に建つ。

## 9.【2026-10-11 16:15 UTC(日曜 01:15 JST)】ユーザー「全て(日曜)で進めてください」— 10 口座を日曜中に VPS 端末へ一括切替
窓: 月曜 06:00 JST(市場再開)まで。順序は必ず **①受け側の準備 → ②MQL5 VPS 全停止 → ③manifest apply:true(私) → ④市場再開前に検証**。③は②の完了報告(ユーザー「停止完了」)の後にだけ行う(二重稼働の禁止・§4)。
| 手順 | 担当 | 内容 | 確認 |
|---|---|---|---|
| ① コード | ユーザー(VPS セッション) | §6/§8 の 3 点: (a) `chien_deploy.start_terminal` をポータブル判定(`MQL5` フォルダ同居)で `/portable` 付き起動にし、装着時は起動 ini(`/config:<端末フォルダ>\chien_start.ini`・`[Experts] Enabled=1 AllowLiveTrading=1 AllowDllImport=0`)で自動売買 ON、(b) agent 1.8: `initialize` 失敗時(1.7c の −6 再試行の後)に端末を `start_terminal` で起動し直して 60 秒待って再試行・status.json に `restarted`、(c) `install_task.ps1` に端末 10 本のログオン時起動タスク `chien_mt5_<口座>`(`/portable`)。変更は `C:\chien\ops\` の実ファイルに入れ、`chien_setup.bat` は実行しない(GitHub の旧版で上書きされる)。リポジトリへの反映は後日 | `python chien_ops_agent.py --config terminals.json` を手動 1 回実行して status.json の `agent_version` が 1.8 |
| ② 停止 | ユーザー | 各口座の MT5 → VPS タブ → MQL5 VPS の **EA を停止**(移行の同期を切る)。9 口座(511030 を含む稼働中すべて)。建玉は触らない | 10 口座分終わったら私に「停止完了」 |
| ③ apply | 私 | manifest の 10 口座を `apply: true` にしてプッシュ(`algo_on` 既定 true)。毎時エージェントが端末停止 → Default プロファイルに EA 装着 → `/portable` + 自動売買 ON で再起動 | 次の毎時実行(各正時 UTC) |
| ④ 検証 | 私 | Drive `chien_ops/<口座>/ea_log_extract.csv` の `[INIT …]`(新版・mult)、`status.json` の `attached_eas`、`open_positions.csv` の建玉が同 Magic で残っていること。失敗した口座は apply を戻し、MQL5 VPS 再移行を案内 | 月曜 06:00 JST まで。22:00 JST の Mon 建てで最終確認 |
| ⑤ 失効 | ユーザー | MQL5 VPS は更新しない(月払い)。戻すときは docs/317 の手順 | 月末 |
保険: ④で 1 口座でも不安があれば、その口座だけ MQL5 VPS に戻す(ログイン → プロファイル → VPS→移行・3 操作)。全体の中止は「apply を全 false に戻す + MQL5 VPS 再移行」で、建玉はどちらでも同 Magic で引き継がれる。

### 9a.【2026-10-12 06:20 JST】時刻の訂正と状況
- §9 の見出し「16:15 UTC(日曜 01:15 JST)」は誤りで、正しくは **月曜 01:15 JST**(10/11 は日曜)。「日曜中に一括」と書いた時点で市場再開(月曜 06:00 JST)まで 5 時間しか無かった。ユーザーからの「停止完了」は無く、MQL5 VPS の EA は止めていない前提で月曜の市場再開を迎えた(= 安全側)。
- VPS 側は ①のコードが入り agent **1.8** で 16:43 UTC に手動実行成功(全 10 端末 ok・新 EA 5 本コンパイル OK・プロファイル生成済み)。ただし **その後の毎時実行の記録が Drive に無い**(status.json / equity_log とも 16:43 UTC のまま 4 時間以上更新なし)。`_diag/task.txt` の登録内容は `Task To Run = C:\Users\iq87jun\...\Python311\python.exe` で、手動実行の python は `C:\Program Files\Python312\python.exe`(host.txt)。install_task.ps1 を PATH に python の無いシェルから実行したため、存在しない Python311 のパスで毎時タスクが登録し直された可能性が高い → 毎時タスクが静かに失敗。対処: install_task.ps1 v3.1(実在する python.exe を探す・無ければ中止)をプッシュ。VPS 側では install_task.ps1 だけを取り直して再実行(chien_setup.bat は agent 1.8 を上書きするので使わない)。
- 次の一括切替は、毎時記録の復旧を確認した上で、平日日中(火〜木)に口座ごと、または次の週末に §9 の手順で。

### 9b.【2026-10-12 06:50 JST】ユーザー「11 月からで良いです」— 一括切替は 11/1 改訂と同時に
- VPS 集約(P5)と、未配備の新 EA(EA9 v1.03 ×2.5・EA10L v1.04 ×8.0・FN v1.34 ×1.5 ETH なし・ルビー v1.03 ×10・トパーズ EA11 v1.14 ×6 ETH なし)の反映は **10/31(土)〜11/1(日)の週末**に §9 の手順で一括。それまで MQL5 VPS の EA(現行版・現行倍率)は止めない。MQL5 VPS の契約は 10 月分で更新を止める(月末失効)。
- 11/1 の月次改正案(docs/322 Q88 ほか)と同じ週末になるので、改正案で倍率・レグを再確認してから apply する(新 EA は manifest の ensure に入っているだけで apply は false)。
- 先物(MFFU)の枚数 7/3/7 は VPS の config.json で独立(ユーザーが VPS セッションで変更した時点で有効)。
- それまでの VPS 側の作業は「毎時記録の復旧(install_task.ps1 v3.1)」だけ。切替の自己チェック(10/12 20:16 JST)は削除。

### 9c.【2026-10-12 08:10 JST】ユーザー「次の土日に変更します」— 一括切替は 10/17(土)〜10/18(日)
§9 の手順どおり(①受け側の確認 → ②MQL5 VPS 全停止 → ③apply → ④月曜 10/19 06:00 JST の市場再開前に検証)。前提: 毎時記録の復旧(install_task.ps1 v3.1)と 10 端末のアルゴ取引 ON の確認を平日のうちに済ませる。§9b(11/1 案)は取り消し。MQL5 VPS は 10 月分で更新を止める。

### 9d.【2026-10-13】ユーザー「では切替で VPS は土曜日に切ります」— 10/17(土)に MQL5 VPS を全停止することで確定
手順(§9 のまま): ①平日のうちに受け側(自前 VPS)の前提 = 毎時記録の復旧(install_task.ps1 v3.1 の再登録)・10 端末のアルゴ取引 ON・MFFU 設定 5/2/5 を確認 → ②10/17(土)ユーザーが MQL5 VPS の EA を全口座で停止 → 「停止完了」 → ③manifest の apply を true に切り替え、agent が 10 端末に docs/349 §9 の EA(EA8 v1.37・EA3 v1.19・パール v1.10・EA9 v1.04・EA10L v1.05・FN v1.35・B 案 v1.04・EA11 v1.15・FN 14074882 v1.11)を配備 → ④10/18(日)に 10 端末の `[INIT]`/`[INIT Q131]` 行と口座・倍率・DynK を照合し、10/19(月)06:00 JST の市場再開前に報告。
土曜に止める前は MQL5 VPS 側を動かしたまま(二重稼働を避けるため apply は「停止完了」の後)。日曜の検証で不一致があれば manifest を false に戻して月曜は MQL5 VPS で続行(後退手順)。

### 9f.【2026-10-17 23:xx JST】ユーザー「停止完了」— MQL5 VPS 全停止 → manifest apply:true(手順③)
- manifest v2: 10 口座の `apply` を true(`ftmo_std100k_new` は未購入のため false のまま)。自前 VPS 端末に付いたままの旧版(10/12 時点の status.json: EA8 v1.35・EA3 v1.17・FN v1.33・EA10L v1.04・EA9 v1.03・パール v1.08・B 案 v1.03・EA11 v1.13)を `remove` に正確な名前で追加(無いと新旧 2 本が同じ端末に乗る)。Instant v1.16 と 14074882 v1.10 は既存の remove パターンで消える。
- 配備される EA(docs/349 §9・docs/241 §1y〜§1z): EA8 v1.37・EA3 v1.19・パール v1.10・EA9 v1.04・EA10L v1.05・FN 14166201 v1.35・B 案 v1.04・EA11 v1.15・14074882 v1.11・Instant G v1.16(不変)。
- 前提①(毎時タスクの再登録)が未達のため、配備は agent の次回実行(再登録後の毎時、または VPS 側での手動 1 回実行)で走る。走れば status.json の `deploy.compiled` に新版、`actions` に remove / attach、各端末の `[INIT]` 行に新版が出る。
- 10/18(日)の検証: status.json の更新時刻・10 端末の compiled ok・`[INIT]`/`[INIT Q131]` の倍率・DynK(EA8/EA3 1.5・パール 1.0・他 0)・自動売買 ON を照合し、月曜 06:00 JST 前に報告。不一致なら apply:false に戻す(後退: MQL5 VPS の「スタート」で復帰)。

### 9g.【2026-10-18 05:06 JST】配備実行の確認 — 10 端末すべて新版をコンパイル(0 errors)・chart01 に装着・再起動。毎時タスクは Python312 で再登録済み(次回 06:00)
- 経緯: ユーザーが 04:09 JST に install_task.ps1 v3.1 で再登録 → `schtasks /run`。agent 1.8 は 05:00 JST に走り(task.txt: Task To Run = Program Files\Python312、前回の実行 05:00:01、状態 実行中)、05:06 JST に status.json を更新。04:09 の手動実行は反映されず(原因未特定・毎時トリガの 05:00 で実行)。
- status.json(generated 20:06 UTC): 10 端末 ok・失敗 0・HALT 0。`deploy.compiled`: EA8 v1.37・EA10L v1.05・パール v1.10・EA3 v1.19・EA9 v1.04・FN 14166201 v1.35・B 案 v1.04・EA11 v1.15 が「0 errors, 0 warnings」、Instant G v1.16・14074882 v1.10 は up to date。`apply.actions`: 10 端末とも「attach <新版> to chart01.chr (expertmode=5)」、error なし、chart01.chr のバックアップを `chien_backup/20261018_05xxxx/` に保存。remove 行は出ていないが、装着後の棚卸し(agent_tail の `chart01.chr = …`)は各端末とも新版 1 本のみで、旧版の残存なし。
- 残高・建玉(MQL5 VPS 停止前の最終状態): 521100397 52,214 / 531407058 51,724 / 531343523 92,704(建玉 1)/ 531466484 99,991(建玉 1・equity 99,863)/ 11988011 19,756 / 14074882 94,687(建玉 1)/ 14166201 104,103(建玉 2・equity 105,710)/ 6071612 5,147,178 / 6104736 10,033,220 / 6104739 34,611,653(建玉 2・equity 34,921,513)。先週の決済: Instant +2・14166201 +9・トパーズ +5・1-Step +1(MQL5 VPS 側での取引)。
- 未確認(07:50 JST のダイジェストと月曜 05:00 JST の最終検証で): 各端末の `[INIT]`/`[INIT Q131]`(倍率・DynK)と自動売買 ON(status.json の `last_init` は再起動直後で空)。

### 9h.【2026-10-18 07:50 JST】ダイジェストでの検証 — FTMO 5・FN 2 は新版の INIT を確認、Fintokei 3 端末は EA の初期化ログが無い(要確認)
- 毎時タスクは 06:00・07:00 JST も正常(status.json 07:00 JST・10 端末 ok・失敗 0・HALT 0)。
- **INIT 行(ea_log_extract・05:0x JST の再起動時)**: EA8 521100397 `initBal=50000 mult=6.0 Σw=0.999`・Brk GER40.cash 名目 100000(×2.0)・JpHoliday 10.12 を含む / EA3 531407058 `initBal=51724 mult=6.0`(InpInitialBalance 未指定で現残高が基準 → 床 46,552 と FTMO の 45,000 より保守的。11/1 改訂で入力に 50000 を明示)/ EA10L 531343523 `initBal=100000 mult=10.0`・Hold XAU w=0.3 holdMult=3.0 名目 90000・Brk GER40 名目 600000(×6.0)/ EA9 531466484 `mult=3.0 Σw=1.668(≈5.0x)`・1-Step トレーリング床 90000 / Instant 11988011 `mult=4.0 trail=6.0%` / 14074882 `mult=4.0 Σw=1.100` / FN 14166201 `mult=2.2 Σw=0.644 + Roll legs=5 mult=4.5`。`[INIT Q131]` は初回のサイズ計算時に出る(OnInit では出ない)ので未確認は正常。
- **注意 1**: EA9 / Instant G の INIT の「推定 lots」が GBPJPY・EURJPY(EA9)、GBPJPY・AUDJPY(Instant)で 0.00(週末で気配・ティック値が取れず `LotsForNotional` が 0 を返した)。実際のロットは建て時に再計算されるので、月曜の最初の `[Mon ENTRY]` でロットが 0 でないことを確認する。
- **注意 2**: FN 14166201 v1.35 の `InpExpiry=2026.10.31 23:59`(期限後は新規停止)。11/1 改訂で延長しないと 11 月から建たない(docs/322 の 11/1 項目に追加)。
- **注意 3(要確認)**: パール 6071612・ルビー 6104736・トパーズ 6104739 の 3 端末は `log_lines=0`・`last_init` 空で、EA の初期化ログが今日の MQL5\Logs に無い。チャートファイルには新版が付いている(attached_eas)が、再起動後に EA が読み込まれていない可能性(FTMO・FN は同じ手順で INIT が出ている)。VPS の 3 端末で「エキスパート」タブを見て INIT 行が無ければ端末を再起動する。月曜 05:00 JST の最終検証で再確認。
- 全 EA が EURUSD H1 チャート上で動いている(端末の既定プロファイル Default の chart01 が EURUSD)。多銘柄 EA は銘柄を内部で解決するので動作に影響なし。

### 9i.【2026-10-19(月)05:00 JST】最終検証 — FTMO 5・FN 2 は稼働確認、Fintokei 3 端末(パール・ルビー・トパーズ)は EA 初期化ログが依然として無し
- status.json 05:00 JST: 10 端末 ok・失敗 0・HALT 0・毎時更新は正常。FTMO 5 + FN 2 は §9h の INIT を保持(log_lines 4〜13)。
- パール 6071612・ルビー 6104736・トパーズ 6104739: `log_lines=0`・`last_init=""` のまま(10/18 05:0x JST の再起動から 24 時間、EA の `[INIT …]`・`[STOP]` とも MQL5\Logs に無い)。チャートファイルには新版が付いている(attached_eas)。原因候補: 再起動後に端末がチャート/EA を読み込んでいない(起動時ダイアログ・プロファイル不一致・/portable 無しで別データフォルダを開いた)。遠隔からは特定できない。
- 影響: この 3 口座は月曜の Mon4 ショットが建たない可能性(機会損失・損失ではない)。MQL5 VPS は停止済みなので二重稼働は無い。
- 対処(ユーザー・06:00 JST 前が望ましいが遅れても可): A) VPS の 3 端末を閉じて開き直し、「エキスパート」タブに `[INIT RecentFit]`/`[INIT EA11]` が出るのを確認(推奨)。B) A が無理なら MQL5 VPS の該当 3 口座だけ「スタート」で旧版に戻す(その場合は manifest の 3 口座を apply:false にして二重稼働を防ぐ → 「スタート」の連絡後に私が実施)。
- 11/1 改訂への引き継ぎ: agent に「再起動後 10 分以内に `[INIT` が無い端末を `restarted` と同様に再起動する」自己修復を足す(docs/322 Q103 系)。
