# Cowork の作業の入口

Cowork(人のパソコンのブラウザを操作する Claude)に任せる作業の一覧と、共通の決まり。
人は Cowork に「https://github.com/iq87jun-star/chien-monitor/blob/main/cowork/README.md を読んで、
〇〇の作業をして」と伝えるだけでよい。Cowork の報告は GitHub の Issue に書かれ、Claude Code がそれを読んで対応する。

## 作業指示の一覧

| 作業 | 指示書 |
|---|---|
| Chrome ウェブストア: トレカの更新・求人の再申請・物件の新規登録・未確認サイトでの表示確認 | [extension/store/cowork-chrome-3.md](../extension/store/cowork-chrome-3.md) |
| スプレッドシートのアドオン: 試す・正解の値と照合・スクリーンショット・Marketplace 申請の準備 | [sheets-addon/cowork-guide.md](../sheets-addon/cowork-guide.md) |
| (参考・完了済み)トレカ海外相場チェッカーの初回登録 | [extension/store/cowork-guide.md](../extension/store/cowork-guide.md) |

## 共通の決まり(Cowork 向け)

- 指示書の「守ること」と「止まる」を必ず守る。迷ったら止まって人に聞く
- パスワード・2段階認証のコード・支払い情報は入力しない。規約への同意・審査への提出・公開のボタンは押さない
- APIキー・トークン・秘密の値は、画面から画面へコピーして貼るだけにし、Issue や会話に書き出さない

## ファイルの取り方

作業に使うファイルは、GitHub の Actions が自動で作って保存している(人から受け取る必要はない)。

1. https://github.com/iq87jun-star/chien-monitor/actions/workflows/cowork-files.yml を開く
   (GitHub にログインしている必要がある。ログインは人が行う)
2. 一覧の一番上の、緑のチェックが付いた実行(ブランチ `main`)を開く
3. ページ下の「Artifacts」の `cowork-files` を押してダウンロードし、展開する。中身は次のとおり
   - `chrome/` … Chrome ウェブストア・Edge アドオンに出す zip(**この zip は展開せずにそのままアップロードする**)
   - `firefox/` … Firefox アドオンに出す zip(同じく展開しない)
   - `sheets-addon/` … スプレッドシートのアドオンの Apps Script に貼るファイル5つ
4. 掲載文・スクリーンショット・アイコンは、リポジトリ全体に入っている。
   https://github.com/iq87jun-star/chien-monitor の「Code」→「Download ZIP」でダウンロードして展開する。
   掲載文(`listing.md` など)は GitHub の画面で開いて、そこから文章をコピーしてもよい

## 報告の出し方

作業が終わった時・止まった時は、人に知らせるのに加えて、GitHub の Issue に報告を書く。

1. https://github.com/iq87jun-star/chien-monitor/issues/new/choose を開き、「Cowork の作業報告」を選ぶ
2. タイトルの「[Cowork報告] 」の後に、作業の名前を書く(例: `[Cowork報告] Chrome 3件の提出準備`)
3. テンプレートの各欄を埋める。指示書にある報告の表は「報告の表」にそのまま貼る
4. 「Submit new issue」を押し、作られた Issue の番号(#123 など)を人に伝える

人は Claude Code に「Issue #123 に報告を出しました」と伝えれば、Claude Code が読んで修正・対応する。
