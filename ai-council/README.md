# ai-council — 複数の AI による点検会議

プロップ 10 口座の EA 運用と theoption の自動発注について、**役割の違う複数の AI** に毎朝リスクを点検させ、まとめを Discord に送ります。手動で新しい手法の相談もできます。

AI たちには毎回、**[portfolio.md](portfolio.md)(口座・規約・手法・検証で分かったこと)** と、**各手法の保有時間に重なる重要指標・祝日**(プログラムで計算)を渡します。検証済みの EA を裁量で止める「後付けフィルタ」は勧めず、止めるのは規約・失格ライン・発注の異常のときだけ、という前提で考えさせます。

```
🔎 調査役(Perplexity Sonar Deep Research: 何十回も Web 検索・出典付き)
      ↓ 調べた事実
🔍 点検役A(OpenAI GPT-5.6 Sol)  🔍 点検役B(Google Gemini 4 Argon)   ← 互いの答えを見ずに、別々に点検
      ↓
🛡️ 批判役(Claude Opus 5.5: 規約の読み違い・失格ラインの計算・後付けフィルタ・棄却済み手法の蒸し返しを探す)
      ↓
🧭 まとめ役(Claude Opus 5.5: 結論・🚨すぐ対応・👀注意・✅今日やること)→ Discord
```

各社の最上位の AI を、考える深さ「high」で使う設定です(1 回 5〜10 分)。

- **平日 7:47(日本時間)**: 今日の点検メモ
- **土曜 8:17(日本時間)**: 新規開拓会議。①月曜の偏り(Mon 系がリスクの 78%)を減らす新しい脚 ②新しいプロップ会社・プラン ③theoption の新しい脚、の候補を出し、批判役が棄却済み・過去の候補の蒸し返しを除いて、検証に回す最大 3 つを Q リスト(docs/244)の形でまとめる。出た候補は [explored.md](explored.md) に自動で記録(検証の結果を「→ 採用」「→ 棄却(理由)」と書き足すと次回の参考になる)。手動なら Run workflow の mode で「新規開拓」を選ぶ。会議の全文は [explore/](explore/) に日付ごとに残り(`latest.md` が最新)、まとめ役が渡す先ごとの指示文(プロップ研究 ①・theoption ③・問い合わせの下書き ②)も書き、Discord に別の通で届く(長押しでコピーしてそのまま貼る)。会議の前に、研究ブランチの検証キュー(queue.json の最近 40 件)と theoption の最近の追補見出しを自動で読み込み、棄却された仮説の近縁や重複を出さないようにする
- **手動**: GitHub(スマホのアプリでも可)→ Actions → **ai-council** → Run workflow → `question` に相談を書く
  - 例: `Mon 系のリスク寄与 78% を 50% に下げるには、どの口座の倍率をどう変えるのがよいか`
  - 例: `theoption の仲値脚を実口座に移す判断基準は妥当か`
- Discord にはまとめ役の答え、**全員の発言は添付の .md** に入ります(Actions の実行結果のまとめにも出ます)
- 経済指標は [Forex Factory](https://www.forexfactory.com/calendar) の週間カレンダー

## 準備

1. [OpenRouter](https://openrouter.ai/) でアカウントを作り、クレジットを入れて API キーを作る(1 つのキーで各社の AI を呼べる)
2. Discord のチャンネルの設定 → 連携サービス → ウェブフック → 新しいウェブフック → URL をコピー
3. GitHub のリポジトリ → Settings → Secrets and variables → Actions → New repository secret
   - `OPENROUTER_API_KEY` … OpenRouter のキー
   - `AI_COUNCIL_DISCORD_WEBHOOK` … Discord の URL
4. Actions → ai-council → Run workflow で試す

費用の目安は 1 回 $0.4〜0.6 程度、平日毎朝で月 $9〜13(答えの長さで変わる。実際の額は通知の最後に出る)。1 回の上限は `maxTokens` で決まり、全員が上限まで使っても $1.5 程度。OpenRouter で使いすぎ防止の上限を設定しておくと安心です。

安くしたいときの入れ替え例: 調査役 `perplexity/sonar-pro`、発案役A `openai/gpt-5.6-terra`、批判役 `deepseek/deepseek-v4-pro-0813`、まとめ役 `anthropic/claude-sonnet-5.5`(1 回 $0.1 程度)。

## 設定(config.json)

| 項目 | 内容 |
|---|---|
| `roles.*.model` | 各役の AI。[OpenRouter のモデル一覧](https://openrouter.ai/models) の ID に入れ替えられる。例: 批判役を `anthropic/claude-opus-5.5`、発案役を `x-ai/grok-4.7` に |
| `roles.*.maxTokens` | 答えの長さの上限(考えた分も含む。費用の上限にもなる) |
| `roles.*.reasoning` | 考える深さ `high` / `medium` / `low`(消すと各 AI の標準) |
| `portfolio` | 運用の現状を書いたファイル([portfolio.md](portfolio.md))。**口座の段階・残高・EA を変えたら更新する**(口座番号は書かない) |
| `legs` | 各手法の保有時間(日本時間の曜日・開始・時間数・見る通貨)。`days: "gotobi"` はゴトー日(祝日の前倒しは未対応) |
| `calendar` | 重要指標の通貨・重要度、何時間先まで(`hours`)、保有時間との重なりを見る範囲(`legHours`)と重要度(`legImpact`、`Holiday` は祝日) |

## パソコンからの口座データ(自動)

パソコンが毎朝(平日 7:30 ごろ)、MT5 の 10 口座と theoption の残高・建玉・失格ライン・日次上限を `status.json` にまとめ、**暗号化して** `ai-council-status` ブランチに `status.enc` として置きます(このリポジトリは公開なので、暗号化しないと残高が誰でも見えるため)。点検会議はそれを読み、失格・日次上限までの距離と、同じ銘柄・同じ向きの重複建玉を計算して AI に渡します。18 時間以上古いと「書き出しが止まっている可能性」と知らせます。

- 暗号: AES-256-GCM。`status.enc` = base64(nonce 12 バイト + 暗号文 + タグ 16 バイト)。鍵は base64 の 32 バイト
- 鍵はパソコンのファイル(リポジトリの外)と、GitHub の Secret `AI_COUNCIL_STATUS_KEY` の 2 か所だけ
- `status.json` の形:

```json
{
  "updatedAt": "2026-11-06T07:30:00+09:00",
  "prop": [
    { "name": "FN-100ギャンブル", "currency": "USD", "balance": 92873, "equity": 92500,
      "floor": 90000, "dailyLimit": 87873,
      "positions": [{ "symbol": "XAUUSD", "side": "BUY", "lots": 0.4, "profit": -200 }],
      "notes": "" }
  ],
  "theoption": { "balance": 395560,
    "recent": [{ "date": "11/5", "leg": "EURGBP 23時 LOW", "result": "勝ち", "pnl": 9500 }],
    "errors": [], "notes": "" },
  "warnings": []
}
```

`floor` は失格になる equity の水準、`dailyLimit` は今日の日次損失で失格になる equity の水準(どちらも業者の規約どおりにパソコン側で計算)。

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
