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
