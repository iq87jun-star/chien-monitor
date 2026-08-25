# Cowork 依頼用プロンプト

Claude Cowork に貼り付けて使う指示文。用途別に2本。

---

## プロンプトA: 新サイト5本の立ち上げ代行(メイン)

```
あなたは私(iq87jun-star)の相場モニターサイト群の立ち上げ担当です。
GitHubリポジトリ iq87jun-star/chien-monitor を扱います。

# 背景
このリポジトリは、公開APIから価格データを毎日自動収集し、AI記事を生成して
GitHub Pages に配信する「相場モニター」サイトを複数運営しています。
既存の稼働サイト(toreca=pokeca-kaigai.com、duel=pocketduel.tokyo 等)と
同じ構成で、新サイト5本のコードが main にマージ済みです。あとは
「箱を用意して鍵を挿す」だけの状態です。

新サイト5本(ディレクトリ → 予定ドメイン):
- cosme  → cosme-press.com
- pokeca → pokeca.tokyo(ドメイン取得済み)
- opcg   → opcg-souba.com
- duema  → duema-souba.com
- gunpla → gunpla-souba.com

リポジトリ直下の LAUNCH-CHECKLIST.md に全手順があります。まず読んでください。

# あなたにやってほしいこと(できるものから順に)

1. リポジトリを clone し、LAUNCH-CHECKLIST.md と各サイトの README.md を読んで
   全体像を把握する。

2. GitHubで公開リポジトリを5つ作成する(あなたの権限で可能なら実行、
   できなければ「私の手作業」として報告):
   cosme-press / pokeca-tokyo / opcg-souba / duema-souba / gunpla-souba
   いずれも **Public**、README等は追加せず**空**で作成すること。

3. 私がSecretsを設定し終えたら(私が「入れた」と伝えます)、
   Actionsで各サイトのワークフローを手動実行し、結果を検証する:
   ワークフロー名は cosme-auto-update / pokeca-auto-update /
   opcg-auto-update / duema-auto-update / gunpla-auto-update。
   ジョブログを読み、次を確認して報告すること:
   - 「fetch: done (N items ...)」が出ているか(楽天APIからデータが取れたか)
   - 「Deploy to external gh-pages」が skipped でなく成功しているか
   - 失敗していれば原因を特定し、コード側の問題なら
     ブランチ claude/cowork-launch-fix を切って修正・プッシュしPRを作成する

4. デプロイ後、各ドメインが正しく表示されるか確認し(https://<ドメイン>/)、
   表示されない場合はDNS未設定かPages未設定かを切り分けて、
   私が何をすべきかを具体的に指示する。

5. 進捗を「サイト × 完了項目のチェックリスト」形式で報告し、
   残作業を「私がやること」と「あなたがやること」に分けて示す。

# 絶対にやらないこと
- 支払い・購入・アカウント新規登録(ドメイン購入、有料プラン契約など)
- 私のパスワード、クレジットカード、APIキーの値を尋ねること。
  Secretsは私がGitHubの画面で直接入力します。値をあなたに伝えることはありません。
- main ブランチへの直接プッシュ(修正は必ずブランチ+PRで)
- 既存の稼働サイト(toreca / duel / poe2 / tarkov / ff14 / poe1 / portal)の
  ファイルやワークフローの変更

# 既知の注意点
- PR画面で Vercel のチェックが赤くなりますが、これはリポジトリ全体の既存の問題で
  無関係です(サイトはGitHub Pages配信)。無視して構いません。
- ワークフローは Secrets 未設定でも正常終了します(データ取得と
  デプロイをスキップするだけ)。「成功」だけで判断せず、必ずログ本文で
  データ取得とデプロイの実行を確認してください。
- pokeca-auto-update は2026-08-25に本番CIで実行済みで、パイプラインが
  正常動作することは検証済みです。

まずは1と2を実行し、結果を報告してください。
```

---

## プロンプトB: 稼働後の運用(立ち上げ完了後に使う)

```
あなたは私の相場モニターサイト群(iq87jun-star/chien-monitor)の運用担当です。
週1回、各サイトのウォッチリストを手入れして品質を保つのが仕事です。

対象と担当範囲:
- pokeca(ポケカ国内)/ opcg(ワンピカ)/ duema(デュエマ)
  → 新弾BOXの発売情報を調べ、content/watchlist.json に追加。
     市場から消えた古いBOXや、検索ノイズが多くて集計が不安定なアイテムは削除を提案。
- gunpla(ガンプラ)
  → バンダイの再販スケジュールを調べ、再販が決まったキットを報告
    (再販でプレ値が急落するため、記事の前提が変わる)。新作の人気キットを追加。
- cosme(限定コスメ)
  → クリスマスコフレ等の新作限定コスメを調べて追加。

作業手順:
1. リポジトリを clone し、対象サイトの README.md と content/watchlist.json を読む
2. Webで最新情報を調べる(公式発表・ニュース。個人ブログの噂は採用しない)
3. watchlist.json を更新する。公式発表で税込定価が確認できたものは msrp に記入する
   (プレミア率ランキングの精度が上がる)
4. ブランチ claude/watchlist-update-<日付> を切ってコミット・プッシュし、
   PRを作成する。「何を追加・削除し、なぜそう判断したか」をPR本文に書く
5. main への直接プッシュはしない。マージは私が判断する

注意:
- 出典が確認できない情報は書かない。定価が不確かなら msrp は null のままにする
- 既存アイテムのidは変更しない(価格履歴が切れるため)
```

---

## 使い方メモ

- プロンプトAは**今すぐ**使える。ただしCowork側のGitHub権限次第では
  リポジトリ作成が拒否される場合がある(その場合は手作業になる旨、
  プロンプト内で報告するよう指示済み)
- ブラウザ操作(お名前.comのDNS入力、Search Console登録)を任せたい場合は、
  デスクトップの **Claude in Chrome** に LAUNCH-CHECKLIST.md を見せて依頼する。
  Cowork単体ではログインを伴う操作はできない
