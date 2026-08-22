# AI VTuber自動応答ボット「ちえん」

YouTubeライブ配信のコメントをAI VTuber「ちえん」(考えごとが多くて返事がちょっと遅い、
のんびり屋のAI VTuber)が音声で自動返答するボット。`poe1/`・`poe2/` と同じ思想
(`.mjs` パイプライン + Claude API + 検品ゲート通過分のみ公開)で構成している。

## 仕組み

```
YouTube Live Chat API ──> 選別(filter) ──> 返答生成(Claude) ──> 検品ゲート
                                                                    │
        OBS ブラウザソース <── 字幕オーバーレイ(:8787) <────────────┤
        OBS / VTube Studio <── 音声再生 <── VOICEVOX 合成 <─────────┘
```

| ファイル | 役割 |
|---|---|
| `bot/config.mjs` | 設定と**キャラクター定義**(人格の一次情報はここだけ。ここを編集すれば全体が追従する) |
| `bot/chat.mjs` | YouTube Live Chat APIからコメント取得(APIキーのみ・読み取り専用) |
| `bot/filter.mjs` | コメント選別(NGワード・URL・個人情報・連投クールダウン)と返答の検品 |
| `bot/reply.mjs` | Claude APIで返答生成(直近の会話履歴を保持して受け答えの一貫性を維持) |
| `bot/tts.mjs` | VOICEVOXで音声合成・再生(エンジン未起動ならテキストのみで継続) |
| `bot/overlay.mjs` + `overlay/index.html` | OBSブラウザソース用の字幕オーバーレイ |
| `bot/run.mjs` | 本体ループ |

## セットアップ

前提: Node.js 18以上。

```sh
cd vtuber
npm install
```

環境変数:

| 変数 | 必須 | 説明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | ○ | 返答生成に必須 |
| `YOUTUBE_API_KEY` | ○(本番のみ) | Google Cloud ConsoleでYouTube Data API v3を有効化して取得 |
| `VIDEO_ID` | ○(本番のみ) | 配信URLの `watch?v=XXXX` の部分。第1引数でも指定可 |
| `OWN_CHANNEL_ID` | 任意 | 自分(ボット)のチャンネルID。自分のコメントへの自己返信を防ぐ |
| `CLAUDE_MODEL` | 任意 | 既定 `claude-opus-5`(poe1/poe2と共通の切替方法) |
| `VOICEVOX_URL` | 任意 | 既定 `http://127.0.0.1:50021` |
| `VOICEVOX_SPEAKER` | 任意 | 話者ID。既定 `3`(ずんだもん)。`GET /speakers` で一覧確認 |
| `OVERLAY_PORT` | 任意 | 字幕サーバーのポート。既定 `8787` |

## 動かし方

1. **ドライラン**(配信・YouTube API不要。標準入力=コメント):

   ```sh
   ANTHROPIC_API_KEY=... npm run dry
   ```

2. **本番**(VOICEVOXエンジンを起動してから):

   ```sh
   ANTHROPIC_API_KEY=... YOUTUBE_API_KEY=... VIDEO_ID=... npm start
   ```

3. **配信への組み込み**:
   - OBSのブラウザソースに `http://127.0.0.1:8787` を追加(字幕が出る)
   - VTube Studioでリップシンクする場合は、仮想オーディオデバイス(VB-CABLE等)を
     既定の再生デバイスにして、VTube Studio側のマイク入力に指定する
   - OBSでアバター(VTube Studioのウィンドウ/仮想カメラ)+字幕+音声をまとめてYouTubeへ配信

## 運用上の注意

- **AI開示**: 生成AIによる配信であることを概要欄等で明示する(YouTubeのポリシー対応。
  キャラクター自身も「AIであることを隠さない」ルールで動く)。
- **クォータ**: YouTube Data APIの無料枠は既定10,000ユニット/日。ポーリング間隔はAPIの
  指示(`pollingIntervalMillis`、最低5秒)に従う実装のため通常は枠内に収まる。
- **モデレーション**: 入力(NGワード・URL・個人情報・連投)と出力(検品ゲート)の
  二段でフィルタしているが、完全ではない。配信中は人間が監視し、`config.mjs` の
  `NG_WORDS` を運用しながら追加していくこと。
- **費用**: Claude APIの費用はコメント量に比例する。`MAX_REPLIES_PER_POLL`(既定2)と
  ユーザー毎クールダウン(既定60秒)で上限を制御している。

## キャラクターを変えるには

`bot/config.mjs` の `CHARACTER` を書き換えるだけでよい。名前はプロンプト・ログ・
字幕オーバーレイのすべてに自動反映される。声は `VOICEVOX_SPEAKER` で合わせる。
