# 310 FN Instant のニュース規則: サポート回答(2026-09-26)と EA 対応

docs/299 §3 の問い合わせ(9/26 01:57 UTC 送信)に対する回答(9/26 02:05 UTC・support@fundednext.com・Sandro Jerome)。Gmail スレッド 1a0db6e1db96b916。

## 1. 回答の要旨(転記)
1. Stellar Instant でもニュース取引は**許可**。ただし「listed high-impact news event」の**前後 5 分(計 10 分)に約定した取引**は News Profit Split Rule の対象で、その取引の利益の **40% のみ**が口座利益に計上される。市場注文・待機注文(TP/SL による約定を含む)の両方。Performance Rewards の資格と口座指標に影響し得る。違反(breach)ではない。
2. FN は MLL(トレーリング最大損失)に **1% の equity バッファ**を設け、ニュース時の利益控除で意図せず MLL に触れないようにしている。
3. 対象銘柄は通貨別の一覧(添付画像 `docs/assets_fn_affected_instruments_20260926.png`)。当方に関係する行: USD → USDJPY・NDX100・SPX500・XAUUSD・BTCUSD・ETHUSD ほか、EUR → EURJPY、GBP → GBPJPY・UK100、JPY → AUDJPY/CADJPY/CHFJPY/EURJPY/GBPJPY/NZDJPY/USDJPY・JPN225、AUD → AUDJPY・XAUUSD、CAD → CADJPY、CHF → CHFJPY、NZD → NZDJPY。**high-impact イベントの一覧は画像に無い**(銘柄表のみ)。
4. 適用は「窓内の約定」のみ。窓を跨いで保有すること自体は対象外(質問 4 への回答は「Market executions(opening or closing)/ Pending orders」)。

## 2. 当方への影響
- 3 件の通知(8/3 14:00 UTC・8/18 06:00 UTC・9/15 06:00 UTC)は、Mon の 24h 時間決済が正時の指標(06:00 UTC = 英国指標 07:00 BST、14:00 UTC = 米 ISM)に重なったもの。失格ではなく、その取引の利益 60% 没収。
- 回避は簡単: **建て時刻を正時から 12 分ずらす**(hh:12 に建て、24h 後の hh:12 に決済)。指標は毎正時・30 分・45 分にあるので、±5 分窓([55,05]・[25,35]・[40,50])から外れる分は 06〜20 分。
- 指数レッグ(Instant G)は現物寄り +5 分(13:35 UTC)が 13:30 の窓に入る → **+8 分(13:38 / 14:38)** に変更。13:45 の米 PMI 窓(13:40〜13:50)からも外れる。
- ロール(#14166201 v1.31)の 20:00 → 00:00 UTC は米指標(12:30/14:00 UTC)・日本指標(23:30/23:50 UTC)の窓外。変更なし。Hold の SL/TP 約定が窓に入る可能性は残る(稀・許容)。

## 3. EA 変更
| EA | 版 | 変更 |
|---|---|---|
| Instant G | 1.13 → **1.14** | `InpMonEntryMinute=12`(FX ショットを hh:12 に)・`InpIdxEntryOffsetMin` 5 → 8 |
| #14074882 ギャンブル | 1.07 → **1.08** | `InpMonEntryMinute=12` |
FTMO・Fintokei の EA は対象外(FTMO のニュース制限は資金口座のみ・別規則)。研究上の影響: ショット時刻が 12 分ずれるだけで、docs/250(Q7)のショット分解の範囲内。
