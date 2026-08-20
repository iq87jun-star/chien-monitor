# ドメイン発掘調査レポート(2026-08-20)

トレカ・カードゲーム関連のキーワード候補113件+閉店・破産事業者のドメインを調査。
判定方法: RDAP / JPRS WHOIS で空き状況、Wayback Machine で運用履歴、
Web検索で旧サイトの実態とインデックス残存を確認。

## 本命: 運用履歴つきの失効ドメイン(いま取得可能)

| ドメイン | 運用履歴 | 旧サイト | 所感 |
|---|---|---|---|
| **pokeca.tokyo** | 2019-04〜2025-12 | 「ポケカミン」ポケカまとめ速報ブログ | ★最有力。2025年末まで稼働し2026年に失効したばかり。記事URL(archives/1万件台)がまだGoogleにインデックス残存。ブログ時代の被リンク・指名検索が期待でき、pokeca-kaigai.com とテーマ完全一致 |
| **cards.tokyo** | 2018-09〜2025-03 | 詳細不明(検索露出は薄い) | 短く汎用的な良名。自サイト用にも、都内カードショップへの売却余地も |
| **tcg.tokyo** | 2017-12〜2019-09 | www.tcg.tokyo で稼働(詳細不明) | 3文字+ジャンル完全一致。履歴は古め |
| **toreca-kaitori.jp** | 2013-04〜2020-08 | 買取系サイト(詳細不明) | 約7年の運用歴=ドメイン年齢の資産。買取系サイトを作るなら名前もそのまま使える |
| **tcg-kaitori.jp** | 2011-10〜2018-03 | 買取系サイト(詳細不明) | 約7年の運用歴。同上 |

注意: 1語 .tokyo はレジストリプレミアム価格の可能性があるため、**取得前に
お名前.com 等で実際の登録料金を確認すること**(pokeca.tokyo は直近まで通常運用
されていたため標準価格の可能性が高い)。

## ドロップ待ち監視対象

| ドメイン | 状態 | 備考 |
|---|---|---|
| **thetcg.co.jp** | 登録中・有効期限 **2026/09/30** | 「The TCG Shop AKIHABARA」運営の(株)The TCG。2026/05破産開始決定(負債約40億円)のため更新されない公算大。破産報道(東京新聞・Yahoo・帝国データバンク等)で知名度あり。**ただし co.jp は法人限定**のため個人では取得不可。期限後 約1か月の猶予を経て廃止→再取得可能になる |

## 取得可能だった主なキーワードドメイン(運用履歴なし=実質新規)

113件中 **80件が取得可能**。全80件のWayback履歴照会が完了し、履歴があったのは
上表の5件のみ(それ以外のハイフン系造語名はすべて履歴なし=実質新規)。
全リストは `results-2026-08-20.tsv` / `candidates.txt` を参照。
自サイト用に有望な例:

- **相場・買取系**(既存サイト群の兄弟サイト向き): toreca-souba.jp / pokeca-souba.jp /
  tcg-souba.com|.jp|.net / toreca-kaitori.jp / pokeca-kaitori.jp / tcg-kaitori.jp /
  toreca-price.com / toreca-chart.com / tcg-chart.com
- **海外系**(pokeca-kaigai.com の姉妹名): toreca-kaigai.com / tcg-kaigai.com / duel-kaigai.com
- **メディア系**: toreca-lab.jp / pokeca-lab.jp / toreca-navi.jp / tcg-navi.jp /
  toreca-soken.com / toreca-db.com / pokeca-db.com / toreca-map.com|.jp / pokeca-map.jp
- **リアル店舗系**(店舗への転売も狙える汎用名): duelcafe.com|.net|.jp|.tokyo /
  torecacafe.com|.net|.jp|.tokyo / cardcafe.jp / tcgcafe.jp|.tokyo / duelspace.jp|.tokyo /
  cardbar.jp|.tokyo / duelbar.jp / boardgamecafe.tokyo / gamecafe.tokyo /
  cardgame.tokyo / tradingcard.tokyo / toreca.tokyo / souba.tokyo
- **地域系**: toreca-akiba.com / akiba-toreca.com / cardshop-akiba.com /
  toreca-osaka.com / toreca-nagoya.com

登録済みで取得不可だった主なもの: pokeca-souba.com / toreca-kaitori.com /
pokeca-chart.com(現役サイト)/ duel.tokyo / cardshop.tokyo / kaitori.tokyo / gacha.tokyo 等。

## リスクと方針(重要)

1. **商標を含む名前は転売しない。** pokeca(ポケモン)・duel(遊戯王連想)等を
   含むドメインを第三者に売る行為は UDRP / JP-DRP で没収+悪質認定のリスク。
   これらは自サイト(ファンサイト)運用専用とする。
2. **転売の期待値は低い。** 業界水準でポートフォリオの年間成約率は1〜2%。
   保有数×年間更新料(1,000〜1,500円/件)が固定費になるため、
   「自サイトで使う前提で仕入れ、余りをSedo/お名前.comマーケットに出品しておく」
   のが現実的。
3. **被リンクの質は未検証。** 無料手段(Wayback・検索インデックス)での確認のみ。
   pokeca.tokyo を取得する場合も、まず数千円の出費で済むので実験としては低リスク。

## 再調査の方法

`candidates.txt` に候補を足して `node domain-hunt/check.mjs` を実行
(詳細は [README.md](./README.md))。thetcg.co.jp のようなドロップ待ちは
有効期限(2026/09/30)の少し後に再実行して失効を検知する。
