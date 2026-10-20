
### 9n.【2026-10-21 08:40 JST】対処の実装(ユーザー「自動化でお願いします」)— deploy 1.9(配備)+ EA 10 本の v+0.01(未接続ガード)を用意。EA の配備は「切替」の後
**deploy 1.9(`ops/vps/chien_deploy.py`・push 済み・`ops/vps/test_chien_deploy.py` 4 項目通過)**
- 装着済み判定を `path`(ex5 ファイル名)で行う(端末が `name=` を切り詰めても誤認しない)。
- 同一 EA が複数チャートに付いていれば最初の 1 枚を残して除去(531343523・531466484 の USDCHF 二重装着は次の毎時実行で自動解消 → 端末再起動)。
- manifest の `restart_token` が前回と違えば 1 回だけ端末を再起動(531407058 に `20261021-halt` を設定 → HALT 解除・残存 8 本は再起動後の TIME EXIT で決済)。
- VPS への反映は mffu_bot と同じ(VPS セッションに貼る)。差し替え前の `chien_deploy.py` の SHA256 = `49e111c84544d3e1aecdbf2ddab93e982ca2a657995802754a20f27045b658e1`(リポジトリの旧版と同一なら安全に置換できる)、新版 = `00bff6b5574f0cf23c3785b19005778c3c0ed3d253fa757e370ac61255b191a9`。

**EA v+0.01(10 本・未配備・manifest 未変更・「切替」待ち)**: OnTimer のガード判定の前に `equity<=0 || !TERMINAL_CONNECTED` なら見送り(`[WAIT]` ログ 3 回まで)、`BalGuardCheck` にも同じ条件。取引ロジック不変。`chien_core.mqh` 1.1 も同じ(include 試作用)。
| 口座 | 現行 | 修正版 |
|---|---|---|
| 521100397 | `【FTMO50k_口座521100397】EA8_Mon4_6.0倍+GER40ブレイク_2.0倍_dyn1_v1.37.mq5` | `【FTMO50k_口座521100397】EA8_Mon4_6.0倍+GER40ブレイク_2.0倍_dyn1_v1.38.mq5` |
| 531407058 | `【FTMO50k_口座531407058】EA3_Mon4_6.0倍_dyn1_v1.19.mq5` | `【FTMO50k_口座531407058】EA3_Mon4_6.0倍_dyn1_v1.20.mq5` |
| 11988011 | `【FN_Instant20k_口座11988011】RecentFit_G_Mon2x4+MonNAS100_US500x1_v1.16.mq5` | `【FN_Instant20k_口座11988011】RecentFit_G_Mon2x4+MonNAS100_US500x1_v1.17.mq5` |
| 14074882 | `【FN100k_口座14074882】RecentFit_Mon3x4+HoldXAU0.4_ギャンブル_v1.10.mq5` | `【FN100k_口座14074882】RecentFit_Mon3x4+HoldXAU0.4_ギャンブル_v1.12.mq5` |
| 14166201 | `【FN100k_口座14166201】RecentFit_Hold_UK100WTI_2.22倍+Roll5_4.5倍_v1.35.mq5` | `【FN100k_口座14166201】RecentFit_Hold_UK100WTI_2.22倍+Roll5_4.5倍_v1.36.mq5` |
| 531343523 | `【FTMO100k_口座531343523_宝くじ】EA10L_Mon4_10.0倍+GER40ブレイク_6.0倍+HoldXAU0.9_v1.05.mq5` | `【FTMO100k_口座531343523_宝くじ】EA10L_Mon4_10.0倍+GER40ブレイク_6.0倍+HoldXAU0.9_v1.06.mq5` |
| 531466484 | `【FTMO100k_1Step_口座531466484】EA9_A案_HoldXAU+MonGBPJPY+MonNAS100+Mon3_3.0倍_v1.04.mq5` | `【FTMO100k_1Step_口座531466484】EA9_A案_HoldXAU+MonGBPJPY+MonNAS100+Mon3_3.0倍_v1.05.mq5` |
| 6071612 | `【Fintokeiパール500万】RecentFit_8.0倍_dyn1_v1.10.mq5` | `【Fintokeiパール500万】RecentFit_8.0倍_dyn1_v1.11.mq5` |
| 6104736 | `【Fintokeiスイング_ルビー1000万_口座6104736】RecentFit_B案_12.0倍_v1.04.mq5` | `【Fintokeiスイング_ルビー1000万_口座6104736】RecentFit_B案_12.0倍_v1.05.mq5` |
| 6104739 | `【Fintokeiスイング_トパーズ3500万_口座6104739】EA11_Mon4x8.0+IdxMon1.0_v1.15.mq5` | `【Fintokeiスイング_トパーズ3500万_口座6104739】EA11_Mon4x8.0+IdxMon1.0_v1.16.mq5` |
「切替」で manifest の ensure を修正版に、remove に現行の正確な名前を足す → 毎時の配備エージェントがコンパイル・装着・再起動まで自動で行う(deploy 1.9 の dedupe で二重装着は起きない)。

**自動化できない 1 点**: VPS の再起動後のログオン。毎時タスクが「対話型のみ」のため、再起動のたびに人のログオンが要る。恒久対策はユーザーが VPS 側で行う(a)Windows の自動ログオン(netplwiz)か(b)`install_task.ps1` をパスワード保存型(`/RU iq87jun /RP`・「ログオンしていなくても実行」)で再登録。パスワードはこのチャットに書かない。

### 9o.【2026-10-21 08:40 JST】VPS 事業者(お名前.com デスクトップクラウド)の不正アクセス事案 — 10/20 20:00 JST からメンテナンス(終了未定)。VPS は侵害された前提で扱う
事業者メール(04:04 JST): 第三者による不正アクセスが発生し、一部の VPS に不正なプログラムが設置された。サーバー内の情報が閲覧された可能性。コントロールパネルは「メンテナンス中(10/20 20:00〜未定)」、RDP は 0x5000004 で到達不能(§9m の 04:24 到達不能と整合)。
対処(ユーザー): プロップ 10 口座の MT5 パスワード変更と不正取引・ログインの確認、TradersPost Webhook URL の再生成、Tradovate 認証情報の変更、Google アカウントから VPS をサインアウト(Drive for desktop)+ パスワード変更、claude.ai の VPS セッション無効化、VPS から push していた GitHub トークンの失効、その他 VPS 保存の口座情報の変更。
復帰後: 事業者の案内に従い、可能なら OS 再インストール → `chien_setup.bat` で C:\chien を再構築(terminals.json は新パスワードで作り直し・公開リポジトリに秘密は置かない)。再開前に §9n の deploy 1.9 を入れ、EA v+0.01 の「切替」を判断。
備考: 10/20 16:0x JST の FTMO 3 端末の再起動(§9m)は侵入との関連が否定できない。口座の損益・建玉は EA の記録と一致しており、現時点で不正取引の形跡はない。
