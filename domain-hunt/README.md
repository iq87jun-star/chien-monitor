# domain-hunt — 中古・キーワードドメイン発掘ツール

pocketduel.tokyo(閉店デュエルカフェの旧ドメイン再取得)の成功パターンを再現するための
ドメイン発掘チェッカー。テーマに合うドメイン候補を `candidates.txt` に列挙し、

1. **空き状況** を各レジストリで機械判定
   (.com/.net = Verisign RDAP / .tokyo = GMOレジストリ RDAP / .jp系 = JPRS WHOIS)
2. 空いているものは **Wayback Machine で過去の運用履歴** を照会
   → 履歴がある = 失効した中古ドメイン。被リンク・指名検索・インデックスが
   残っている可能性があり、新規ドメインより SEO の立ち上がりが速い見込み
3. 登録済みの .jp 系は WHOIS の有効期限を抽出し、**失効90日以内なら
   ドロップ待ち監視対象** として報告(閉店・破産した事業者のドメインを狙う)

## 使い方

```bash
node domain-hunt/check.mjs        # GitHub Actions などプロキシなし環境
NODE_USE_ENV_PROXY=1 node domain-hunt/check.mjs   # プロキシ環境
```

結果は `results.json` に保存される(`available` / `availableWithHistory` /
`watchlist` / `all`)。レジストリのレート制限が厳しいため、候補100件で
15〜30分程度かかる。archive.org は特に厳しく、429 が返った分は
`waybackFirst/Last` が null になる(=履歴不明)。

## 運用のポイント

- **取得前に必ず登録料金を確認する。** `toreca.tokyo` のような1語 .tokyo は
  レジストリプレミアム価格(数万円〜)の場合がある。RDAP の 404 は
  「未登録」を意味するだけで、標準価格での取得可否までは保証しない。
- **商標を含むドメインは転売しない。** pokeca(ポケモン)・yugioh(KONAMI)等を
  含む名前の転売は UDRP / JP-DRP(ドメイン名紛争)で没収リスクがある。
  自サイトのファンサイト運用に限定する(既存の pokeca-kaigai.com と同じ位置づけ)。
- **co.jp は法人でないと登録できない**(1法人1ドメイン)。watchlist に co.jp が
  出ても個人では取得不可。
- 中古ドメインの実力(被リンクの質)は Ahrefs / Majestic 等の有料ツールでしか
  正確に測れない。取得判断の最終確認には無料枠や試用を使う。

## 調査結果

最新の調査結果は [REPORT.md](./REPORT.md) を参照。
