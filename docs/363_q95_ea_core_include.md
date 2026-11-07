# docs/363 Q95: EA 共通部の include 化 — chien_core.mqh 1.0(10 本で本体が完全一致する 28 関数)+ 試作 EA3 v1.20(include 版 = v1.19 と同一)(工学・セル 0)

2026-10-19(月)朝の定例。docs/322 Q95(order 12)。新規: `mql5/include/chien_core.mqh`、`mql5/【FTMO50k_口座531407058】EA3_Mon4_6.0倍_dyn1_inc_v1.20.mq5`(試作・未配備)。配備(manifest・docs/241)は変更なし。

## 1. 調査(機械的)
配備中の 10 本(EA3 v1.19・EA8 v1.37・EA9 v1.04・EA10L v1.05・EA11 v1.15・パール v1.10・B 案 v1.04・FN 14166201 v1.35・14074882 v1.11・Instant G v1.16)のトップレベル関数を波括弧対応で切り出し、空白とコメントを除いた本文を比較。
| 区分 | 関数 |
|---|---|
| 10 本すべてにあり本体が完全一致(28・243 行)→ **chien_core.mqh** | ChienCsv ChienPush ChienLog(2 つの多重定義) ChienSend ChienFlush ChienSnapshot ChienDeals ChienLogTimer ChienLogInit ChienLogDeinit ParseLegs SplitHours LotsForNotional CountPos CloseAllMine Notify HolidayBlocked SpreadCapFor DayStart RestoreOrResetDay AtrAt BalGuardActive BalGuardCheck ManageMonExit V4Signal ManageV4Exit V4Fail |
| 10 本すべてにあるが本体が分岐(13)→ EA 側に残す | OnInit(9 種) EntriesMon(6) EntriesHold(5) FlushNotify(5) OnTimer(5) ResolveSymbol(4) EntriesV4(3) IsMine(3) PipOf(3) ResetDay(3) MoneyPerUnit(2) OnDeinit(2) OnTick(2) |
| 一部の EA のみ | Roll / Brk / Sess / 1-Step トレーリング / Q131 DynFactor など |
- 一致 28 関数が参照する `Inp*`・`g_*` は 46 個で、10 本すべてに宣言がある。一致関数から呼ぶ分岐関数は ResolveSymbol / MoneyPerUnit / IsMine / ResetDay / FlushNotify の 5 つ(EA 側で定義。MQL5 は前方参照可で、現行 EA も OnTick(545 行)→ EntriesHold(811 行)の前方参照で動いている)。
- **分岐している 13 関数が docs/249 型(コピー起因の不整合)の温床**。特に MoneyPerUnit(2 種)・PipOf(3 種)・ResolveSymbol(4 種)はロット計算と銘柄解決なので、11/1 改訂で「差分の理由(口座通貨・接尾辞・指数の pip 定義)」を入力化して 1 本に寄せる(第 2 段)。

## 2. 成果物
- `mql5/include/chien_core.mqh` 1.0: 一致 28 関数を EA3 v1.19 の原文のまま(コメント込み)出現順に収めた。`#ifndef CHIEN_CORE_MQH` ガード。EA 側の入力・グローバル宣言の後に `#include "chien_core.mqh"`(同じフォルダ `MQL5\Experts\chien\`)。
- 試作 `EA3_Mon4_6.0倍_dyn1_inc_v1.20.mq5`(602 行 ← 849 行): v1.19 から一致 28 関数を削除し、最後の一致関数(V4Fail)があった位置に include を置いた(参照する宣言はすべてその前にある)。**検証**: include を展開したテキストと v1.19 の「関数集合・各本文・関数外テキスト」が一致(version 文字列の差のみ)。つまり取引ロジック・入力・Magic は v1.19 と同一で、コンパイル結果が同じになる設計。

## 3. 残作業と提案
1. **コンパイル確認**: ここでは MetaEditor が無いので未コンパイル。VPS 側で `metaeditor64 /compile` するか、Q94 のテスター(`chien_tester.py`)で v1.19 と v1.20_inc を同じ期間で走らせ `tester_parity.py` で「取引数 100%・損益差 0」を確認(受け入れ基準・docs/362 §4)。
2. **配備側の対応**(11/1 改訂): `chien_deploy.compile_ea` は EA 1 ファイルだけ GitHub から取るので、manifest の ensure に `includes: ["include/chien_core.mqh"]` を足して同じフォルダへ取り込む(別ファイル版 +0.01 で)。それまで include 版は配備候補にしない。
3. **他の 9 本**: 同じ生成手順(`q95_build.py` 相当)で include 版を作れる(各 EA の一致関数の位置が違うだけ)。第 1 段は 10 本とも「一致 28 関数の include 化」のみで挙動不変、第 2 段で分岐 13 関数の統一。
4. 11 月改訂への含意: 以後の共通修正(ログ・ガード・ロット計算)は chien_core.mqh の 1 箇所で済み、コピー漏れが構造的に無くなる。

累積セル数: 9,750(Q95 はセル 0)。次回: Q96(P1 通過 → P2 のロック自動切替・設計)。
