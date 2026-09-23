# Edge・Firefox への出品手順(3つの拡張共通)

トレカ海外相場チェッカー(`extension/`)・求人 年収チェッカー(`job-extension/`)・
物件 単価・月額チェッカー(`realty-extension/`)の3つとも同じ手順。掲載文は各拡張の
`store/listing.md` をそのまま使う(**説明文にサイト名を並べない**。Chrome でキーワード スパムとして却下された)。

## 提出するファイル

`npm run pack` で2種類できる。

| ストア | ファイル |
|---|---|
| Chrome ウェブストア・Microsoft Edge アドオン | `dist/<名前>-<version>.zip`(同じzip) |
| Firefox アドオン(AMO) | `dist/firefox/<名前>-<version>-firefox.zip` |

Firefox 用は manifest だけが違う(アドオンID・データ収集の申告・background の書き方)。
中身は `npx web-ext lint -s dist/firefox-src` で検査でき、CI(`*-publish` ワークフロー)でも毎回検査している。

## Microsoft Edge アドオン(登録無料)

1. [Microsoft パートナーセンター](https://partner.microsoft.com/dashboard/microsoftedge/overview) に
   Microsoft アカウントでログインし、Edge アドオンの開発者として登録する(登録料なし)
2. 「新しい拡張機能を作成」→ **Chrome 用と同じzip** をアップロード
3. 「可用性」: 公開範囲は「公開」、市場は「日本」だけでもよい
4. 「プロパティ」: カテゴリ(トレカは「ショッピング」、求人・物件は「生産性」)、
   プライバシーポリシーの URL(`listing.md` 末尾に記載のもの)、サポート連絡先
5. 「ストアの掲載情報」: 言語「日本語」で、説明に `listing.md` の「説明」、短い説明に「概要」を貼る。
   アイコン(128px)・スクリーンショット(1280x800)は Chrome と同じもの
6. 「公開」を押して審査に出す(数日〜最大7営業日程度)

## Firefox アドオン(AMO・登録無料)

1. [Firefox アドオン開発者ハブ](https://addons.mozilla.org/developers/) に Mozilla アカウントでログインする(登録料なし)
2. 「新しいアドオンを申請」→ 公開方法は「このサイトで公開する」→ **Firefox 用のzip** をアップロード
   (自動検査が走る。警告が出たらその内容を Claude Code のセッションに貼る)
3. 「ソースコードの提出が必要か」→ **いいえ**(圧縮・変換していない素のコードのため)
4. 掲載情報: 名前はそのまま、概要(250文字以内)に `listing.md` の「概要」、説明に「説明」を貼る。
   カテゴリ(トレカは「ショッピング」、求人・物件は「その他」または「仕事効率化」)、
   プライバシーポリシーの URL、サポートの連絡先
5. データ収集: manifest で「収集しない」と申告済み(インストール時の同意画面にそう表示される)
6. 申請する(自動審査で数分〜数日。人の審査が入ることもある)

## 注意

- Firefox のアドオンID(`toreca-checker@pokeca-kaigai.com` など、各 `scripts/pack.mjs` の `GECKO_ID`)は
  **一度公開したら変えない**(変えると別のアドオン扱いになり、利用者に更新が届かなくなる)
- Firefox は 128 以降が対象(MV3 のホスト権限がインストール時に許可されるのが 128 から)
- この開発環境には Firefox が無く、**Firefox 上での実際の動作は未確認**(lint のみ確認済み)。
  出品前に手元の Firefox で `about:debugging` →「一時的なアドオンを読み込む」で firefox 用zipを読み込み、
  表示を確かめると確実
