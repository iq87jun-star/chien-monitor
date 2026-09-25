# Cowork 用の作業指示(Edge・Firefox: 3つの拡張の出品の入力)

この文書を Cowork にそのまま渡して使う。人が行う作業(★)と、Cowork に任せる作業を分けてある。
Cowork は「止まる」と書かれた所で必ず作業を止め、人に確認すること。

入力する内容はすべて [edge-firefox-inputs.md](edge-firefox-inputs.md) にある(画面の項目の順に並べた表)。

| 作業 | ストア | 内容 |
|---|---|---|
| E1〜E3 | Microsoft Edge アドオン(パートナーセンター) | トレカ・求人・物件の新規登録と入力 |
| F1〜F3 | Firefox アドオン(AMO) | トレカ・求人・物件の新規登録と入力 |

Chrome ウェブストアと違い、Edge・Firefox の管理画面は Cowork から操作できる見込み(まだ試していない)。
**最初の画面で操作できなかったら、その時点で止まって報告する**(その場合は Chrome と同じく、人が入力し、
Cowork はコピー用のページを作る形に切り替える)。

## 守ること(Cowork 向け)

- アカウントの作成・パスワード・2段階認証・規約への同意・支払い情報は扱わない(人が行う)
- **最後の提出ボタン(Edge の「公開」/Publish、Firefox の「バージョンを提出」/Submit Version)は押さない**。
  その手前まで入力し、止まって人に知らせる
- 文章は `edge-firefox-inputs.md` の表と ``` で囲まれた部分だけを使い、自分で文章を作らない。
  特に**説明文にサイト名を書き足さない**(Chrome でキーワード スパムとして却下された)
- 「連絡先メールアドレス」「サポートメール」は**人に聞いてから**入れる(ストアのページで公開される)
- ファイルを選ぶ画面(アップロード)を Cowork が操作できない場合は、止まってファイル名を人に伝え、人に選んでもらう

## 事前準備(★人が行う)

1. Microsoft Edge アドオンの開発者登録(無料):
   https://partner.microsoft.com/dashboard/microsoftedge/overview に Microsoft アカウントでログインし、
   開発者として登録する(アカウントの種類は「個人」でよい)
2. Firefox アドオンの開発者登録(無料):
   https://addons.mozilla.org/developers/ に Mozilla アカウントでログインし、開発者の規約に同意する
3. Chrome で GitHub にログインしておく
4. ファイルを用意する([cowork/README.md](../../cowork/README.md) の「ファイルの取り方」):
   - `cowork-files` の `chrome/`(Edge 用。Chrome と同じ zip)と `firefox/`(Firefox 用)
   - 画像(アイコン・スクリーンショット)は、リポジトリ全体(「Code」→「Download ZIP」)の中
   - 求人の zip は **0.1.2**(`job-salary-checker-0.1.2.zip`)。0.1.1 以前が出てきたら古いので取り直す
5. Cowork に「https://github.com/iq87jun-star/chien-monitor/blob/main/extension/store/cowork-edge-firefox.md の
   作業をして」と伝え、連絡先に使うメールアドレスを伝える

## 作業E: Edge アドオン(Cowork)

3つの拡張それぞれで行う(E1 トレカ → E2 求人 → E3 物件)。

1. パートナーセンターの Edge アドオンの画面で「新しい拡張機能を作成」(Create new extension)を押す
2. 「パッケージ」: `chrome/` の zip をアップロードする(展開しない)。検証が終わるまで待つ
3. 「可用性」「プロパティ」「ストア掲載情報」を、`edge-firefox-inputs.md` のその拡張の「Microsoft Edge アドオン」の表の
   とおりに入力する。各画面で「保存」を押す
   - 説明は、その拡張の「説明(Edge・Firefox 共通)」の ``` の中だけを貼る
   - 検索語句は表の「/」で区切られた語を1つずつ入れる
4. 「提出」の画面で、「認定のための注記」に表の英文をそのまま貼る
5. **止まる**: 「公開」(Publish)は押さずに、入力した画面の一覧・警告・未入力の項目を人に報告する

## 作業F: Firefox アドオン(Cowork)

3つの拡張それぞれで行う(F1 トレカ → F2 求人 → F3 物件)。

1. 開発者ハブで「新しいアドオンを申請」(Submit a New Add-on)を押す
2. 公開方法は「このサイトで公開する」(On this site)
3. `firefox/` の `…-firefox.zip` をアップロードする。自動の検証の結果を待つ。
   **エラーや警告が出たら止まり**、文言をそのまま人に報告する
4. 対応プラットフォーム・ソースコードの提出・名前・URL・概要・説明・カテゴリ・サポート・ライセンス・
   プライバシーポリシー・審査担当者へのメモを、`edge-firefox-inputs.md` のその拡張の「Firefox アドオン(AMO)」の表の
   とおりに入力する
5. **止まる**: 「バージョンを提出」(Submit Version)は押さずに、入力した内容と警告を人に報告する

スクリーンショットは Firefox では提出の後に「製品ページの編集」で入れる(表の最後の行)。提出を人が行った後に頼まれたら入れる。

## 報告(Cowork)

作業が終わった時・止まった時は、人に知らせるのに加えて、[cowork/README.md](../../cowork/README.md) の
「報告の出し方」のとおり GitHub の Issue(「Cowork の作業報告」)に結果を書き、Issue の番号を人に伝える。

| 作業 | 拡張 | 結果(入力済み/止まった) | 止まった理由・警告の文言 |
|---|---|---|---|

## 最終提出(★人が行う)

Cowork の報告を確認し、問題がなければ、Edge は「公開」、Firefox は「バージョンを提出」を押す。
審査は Edge が数日〜1週間程度、Firefox は自動の検証の後、数日程度かかることがある。
結果はメールで届く。却下や質問のメールが来たら、Claude Code に伝えて直してもらう。
