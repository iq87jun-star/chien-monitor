# 拡張の自動づくり(アイデア → 作成 → 提出)

Claude の定期実行(Routine)が、この手順書に従ってブラウザ拡張を増やす。人がすることは **Issue で案を選ぶ** ことと、
**Chrome ウェブストアへの新規登録(1件10分ほど・コピー用の文章は用意される)** だけ。

```
[毎週月曜 9:00 頃] アイデア係 ──(Issue「[拡張アイデア] …」に案を3つ)──> 人がコメントで「1」「2」「3」を選ぶ
[毎日 10:00 頃]   作成係   ──(選ばれた案を作る)──> PR → テスト合格でマージ → Firefox に自動提出
                                                     └→ Issue に Chrome 用の貼り付け文章と手順を書く
```

## 決まり(両方の係が守る)

- **量より質**: 新しい拡張は **30日で2つまで**(`ideas.md` の「作成日」で数える)。超える時は作らず、Issue にそう書く。
  似た拡張を大量に出すと、Chrome の「スパム・繰り返しのコンテンツ」の規定でデベロッパー アカウントごと止められ、
  公開中の拡張も巻き添えになる
- **AI が作っても減点されない種類だけ**: 計算・換算・整理など、決まった規則で答えが出る道具。
  文章・画像を生成して見せるもの、口コミ・評価を作るもの、情報を集めて転載するもの(著作権・利用規約の問題)は作らない
- **個人データを集めない**: 計算はすべてブラウザ内。外部に送らない(送る必要がある案は選ばない)。
  `data_collection_permissions` は `none` のまま
- **対象サイトの規約を守る**: ページを読んで表示を足すだけ。自動で操作・大量取得・ログインが必要なページは対象にしない
- **既存の拡張と重ならない**: `ideas.md` と、各拡張の `store/listing.md` を読んでから考える
- **説明文にサイト名を並べない**(Chrome でキーワード スパムとして却下された)。「求人サイト」「不動産ポータル」のように書く

## アイデア係(毎週)

1. `ideas.md` を読み、30日以内に作った数を数える。2つ以上なら、案は出すが Issue の最初に「今月は上限のため作成は来月」と書く
2. 次の条件をすべて満たす案を **3つ** 考える
   - 日本の、よく使われる種類のサイト(ショッピング・求人・不動産・旅行・家計・学習など)で、
     **ページに書かれている数字や文字から、利用者が自分で計算していること** を肩代わりする
   - 既存の `parser.js` 型(文章 → 数値 → 計算)で作れる。外部の API やデータの取得が要らない
     (要る場合は、公的で再配布自由なデータを自分のサイトに置く形にできるものだけ)
   - 収益の筋がある: 計算結果の下に「PR」と明記した紹介リンク(`src/offers.js`)を置ける分野か、
     計算 API(`calc-api/`)の新しい出品にもなるもの
3. GitHub に Issue を作る(テンプレート「拡張のアイデア」・ラベル `ext-idea`)。各案に次を書く:
   名前・一言で何をするか・対象の種類のサイト(例として2〜3サイト。**これは Issue の中だけ**で、説明文には書かない)・
   計算の中身・収益の筋・作る量の見込み(小/中/大)・心配な点
4. `ideas.md` の「出した案」に3行足して PR を作り、テストが通ればマージする

## 作成係(毎日)

1. ラベル `ext-idea` の開いた Issue で、**リポジトリの持ち主(iq87jun-star)** が「1」「2」「3」
   (または「1番」「案2」など)とコメントしていて、ラベル `ext-building`・`ext-done` が付いていないものを探す。
   無ければ何もしないで終わる(報告もしない)。1回の実行で作るのは **1つだけ**
2. 30日で2つの上限を確かめる。超えるなら Issue に「上限のため◯日以降に作ります」と書いて終わる
3. Issue にラベル `ext-building` を付け、「作り始めました」とコメントする
4. `job-extension/` をひな形にして、新しいフォルダ `<名前>-extension/` を作る(下の「作るもの」)
5. テストを通す: `npm test`・`npm run test:e2e`・`npx web-ext@8 lint --source-dir dist/firefox-src --warnings-as-errors`・
   `node --test scripts/amo/submit.test.mjs`・`node scripts/amo/submit.mjs <フォルダ> --dry-run`
6. ブランチを切って PR を作り、CI がすべて緑になったらマージする(赤なら直して押し直す。3回直して駄目なら Issue に状況を書いて止まる)
7. プライバシーポリシーのページを公開する: Actions の `toreca-auto-update` を手動実行し、
   `https://pokeca-kaigai.com/<名前>-extension-privacy.html` が 200 を返すまで待つ
8. Firefox に提出する: Actions の `amo-publish` を target=`<名前>-extension` で手動実行し、結果のログを確かめる
9. Issue に結果を書き、ラベルを `ext-done` に替えて閉じる。書くこと:
   - Firefox の URL と状態(審査中など)
   - **人がすること**: Chrome ウェブストアへの新規登録。`<名前>-extension/store/listing.md` の文章と、
     `cowork-files` の `chrome/<名前>-<版>.zip`・スクリーンショット・アイコンを使う(手順は `extension/store/cowork-chrome-3.md` の作業C と同じ)
10. `ideas.md` の該当行を「作成済み」にし、作成日と Firefox の URL を書く(8 の PR とは別の小さな PR でよい)

### 作るもの(`job-extension/` と同じ形)

| ファイル | 中身 |
|---|---|
| `manifest.json` | MV3。名前・概要(132文字以内)・対象サイトの `content_scripts`・`storage` 権限だけ |
| `src/parser.js` | 文章 → 数値 → 計算の純粋関数(DOM を使わない)。`globalThis.<名前>Parser` に公開 |
| `src/content.js` | 見出しを探して本文を読み、右下に枠を出す(Shadow DOM)。一覧ページでは出さない。DOM 監視は最大1.5秒で判定 |
| `src/offers.js` | 紹介リンクの設定(最初は空の配列) |
| `src/popup.html` / `popup.js` | 表示のON/OFF |
| `icons/` | `scripts/make-icons.mjs` で作る(16・48・128) |
| `test/parser.test.js` | 実際の表記の揺れを並べた単体テスト(10件以上) |
| `scripts/e2e.mjs` | モックページで拡張を読み込んで表示を確かめる。`--shots` で `store/screenshots/` に 1280x800 を2枚以上 |
| `scripts/pack.mjs` | Chrome 用と Firefox 用の zip。`GECKO_ID` は `<名前>@pokeca-kaigai.com`(一度公開したら変えない) |
| `store/listing.md` | 概要・説明(■ できること / ■ 広告について / ■ プライバシー / ■ ご注意)・プライバシーへの取り組み |
| `store/amo.json` | slug・カテゴリ・プライバシーポリシー・審査担当者へのメモ(英語)・スクリーンショット |
| `README.md` | 何をするか・開発の仕方 |
| `.github/workflows/<名前>-extension-publish.yml` | `job-extension-publish.yml` の写し(タグ `<短い名前>-v*`) |
| `toreca/public/<名前>-extension-privacy.html` | プライバシーポリシー(`job-extension-privacy.html` の写しを直す) |

## 人がすること

- 週に1回、Issue「[拡張アイデア] …」を見て、作ってほしい案の番号をコメントする(作らない週はコメントしないでよい)
- 作成係が Issue に書いた手順で、Chrome ウェブストアに新規登録する(Firefox は自動)
- 止めたい時は、この README の先頭に「停止中」と書くか、Claude に「拡張の自動づくりを止めて」と伝える
