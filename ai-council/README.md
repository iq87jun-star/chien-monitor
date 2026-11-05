# ai-council — 複数の AI による作戦会議

プロップ口座とバイナリーオプションのアイデア・仕組みを、**役割の違う複数の AI** に順番に検討させ、まとめを Discord に送ります。

```
🔎 調査役(Perplexity Sonar Deep Research: 何十回も Web 検索・出典付き)
      ↓ 調べた事実
💡 発案役A(OpenAI GPT-5.6 Sol)  💡 発案役B(Google Gemini 4 Argon)   ← 互いの答えを見ずに、別々に案を出す
      ↓ 2 つの案
🛡️ 批判役(Claude Opus 5.5: 期待値・連敗・規約違反・過剰最適化の穴を探す)
      ↓
🧭 まとめ役(Claude Opus 5.5: 結論・使える案・やらないこと・確かめ方)→ Discord
```

各社の最上位の AI を、考える深さ「high」で使う設定です(1 回 5〜10 分)。

- **平日 7:47(日本時間)**: 今日の作戦メモ(重要な経済指標の時刻つき)
- **手動**: GitHub(スマホのアプリでも可)→ Actions → **ai-council** → Run workflow → `question` に相談を書く
  - 例: `ロンドン時間のブレイクアウトを 2 時間判定のバイナリーに使えるか`
  - 例: `日次 5% のルールで、1 回のリスクは何 % が妥当か`
- Discord にはまとめ役の答え、**全員の発言は添付の .md** に入ります(Actions の実行結果のまとめにも出ます)
- どの AI にも、config.json の**自分のルール**と、そこから計算した**損益分岐の勝率・何連敗で上限か**を毎回渡します
- 経済指標は [Forex Factory](https://www.forexfactory.com/calendar) の週間カレンダー

## 準備

1. [OpenRouter](https://openrouter.ai/) でアカウントを作り、クレジットを入れて API キーを作る(1 つのキーで各社の AI を呼べる)
2. Discord のチャンネルの設定 → 連携サービス → ウェブフック → 新しいウェブフック → URL をコピー
3. GitHub のリポジトリ → Settings → Secrets and variables → Actions → New repository secret
   - `OPENROUTER_API_KEY` … OpenRouter のキー
   - `AI_COUNCIL_DISCORD_WEBHOOK` … Discord の URL
4. **config.json の `profile` を自分の実際の条件に書き換える**(会社名・口座・損失上限・規約・払い戻し倍率など)
5. Actions → ai-council → Run workflow で試す

費用の目安は 1 回 $0.4〜0.6 程度、平日毎朝で月 $9〜13(答えの長さで変わる。実際の額は通知の最後に出る)。1 回の上限は `maxTokens` で決まり、全員が上限まで使っても $1.5 程度。OpenRouter で使いすぎ防止の上限を設定しておくと安心です。

安くしたいときの入れ替え例: 調査役 `perplexity/sonar-pro`、発案役A `openai/gpt-5.6-terra`、批判役 `deepseek/deepseek-v4-pro-0813`、まとめ役 `anthropic/claude-sonnet-5.5`(1 回 $0.1 程度)。

## 設定(config.json)

| 項目 | 内容 |
|---|---|
| `roles.*.model` | 各役の AI。[OpenRouter のモデル一覧](https://openrouter.ai/models) の ID に入れ替えられる。例: 批判役を `anthropic/claude-opus-5.5`、発案役を `x-ai/grok-4.7` に |
| `roles.*.maxTokens` | 答えの長さの上限(考えた分も含む。費用の上限にもなる) |
| `roles.*.reasoning` | 考える深さ `high` / `medium` / `low`(消すと各 AI の標準) |
| `profile.prop` | プロップ口座: 口座サイズ・日次/最大損失 %・利益目標・1 回のリスク %・規約・銘柄・時間足 |
| `profile.binary` | バイナリー: 払い戻し倍率(1,000 円が当たると何円戻るか ÷ 1,000)・判定時間・銘柄・1 回の額・1 日の損失上限 |
| `profile.notes` | 自分の得意・苦手、今試している手法などを自由に |
| `calendar` | 見る通貨・重要度(`High` / `Medium` / `Low`)・何時間先まで |

## 手元で試す

```sh
cd ai-council
npm test
node run.js                                    # キー未設定なら、各 AI に渡す内容だけ表示
AI_COUNCIL_QUESTION="相談内容" node run.js
OPENROUTER_API_KEY=sk-or-... node run.js       # 実際に呼ぶ(Webhook 未設定なら送らない)
```

## 注意

- AI の答えは参考意見です。必ずバックテスト・デモで確かめてから使ってください
- 口座のパスワード・ログイン情報は config.json にも相談にも書かないでください(このリポジトリと AI 各社に渡ります)
- 日本では、金融庁に登録していない海外業者のバイナリーオプションは避けてください
