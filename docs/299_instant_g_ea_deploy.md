# 299 FN Instant 20k #11988011 → G 構成 EA(Mon2 ×4 + Mon NAS100/US500 ×1)の配備カード(2026-09-26)

ユーザー決定「Instant G で作成」(docs/298 の G 案)。本書は EA の仕様・装着条件・FN への確認メール草案。

## 1. ファイル

`mql5/【FN_Instant20k_口座11988011】RecentFit_G_Mon2x4+MonNAS100_US500x1.mq5` v1.10(Instant v1.02 からの派生)

| 項目 | 値 |
|---|---|
| InpMonLegs | `GBPJPY:0.537,AUDJPY:0.463,NAS100:0.125,US500:0.125` |
| InpMult | 4.0(FX 合計 = 残高の 4.0 倍、指数 = 各 0.5 倍 → 2 本で 1.0 倍。グロス 5.0 倍) |
| InpV4Legs | 空(v4 USDJPY は 5 年 −0.7%・docs/290。旧 v4 建玉は同 Magic 943202 なので新 EA が引き継いで 8 日で時間決済) |
| InpInitialBalance | 20000 固定(docs/241 §1d の教訓) |
| InpExpiry | 2026-12-31(四半期レビューで更新) |
| Magic | 943200 系(旧 Instant v1.02 と同じ → 旧 EA は必ず外す。両方付けると二重建て) |
| ガード | 旧版と同一: トレーリング MLL(フロア = min(HWM − 6% × 初期, 建値))+2% で新規停止・+1% で全決済恒久停止、balance 日次 −4% |

### 1a. v1.10 で追加した仕組み
1. **指数レッグ**: 銘柄の桁数 ≤ 3 かつ非 JPY を指数と判定し 1 pip = 1 ポイント。スプレッド上限は bps 指定(`InpIdxMaxSpreadBps` 3.0。NAS100/US500 の通常値 ≈ 1 bps)。
2. **指数の建て時刻**: 研究定義(docs/298 の mon_cell)は米国現物の寄り(9:30 ET)→翌日寄りの o2o なので、FX の 4/6/8/10 UTC 4 分割ではなく **13:30(夏)/14:30(冬)UTC + 5 分から 60 分窓で単発**、24h 保有(火曜同時刻に決済)。米国夏時間は EA 内で判定(3 月第 2 日曜〜11 月第 1 日曜)。
3. **銘柄別名**: FN の `SPX500` / `NDX100` を `US500` / `NAS100` から解決(季節RG3 と同じ別名表)。初期化ログ `[銘柄解決] Mon US500 → SPX500` で確認。
4. **スキップ日** `InpMonSkipDates`(UTC "YYYY.MM.DD" CSV)+ `InpMonSkipIdxOnly`(既定 true = 指数レッグのみ見送り)。FN Instant のニュース規則が確認できるまで、月曜が高インパクト日に当たる日(FOMC 声明日は水曜なので通常は該当しないが、ISM 製造業の月曜など)をここに入れる運用。
5. 初期化時に各レッグの 1 ショット想定元本と推定ロット、min/step を出力(`[INIT G v1.10] Mon NDX100 w=0.125 指数 … 推定lots=0.50`)。ロットが min 未満なら建てずにスキップするので、初回ログで 4 本とも lots>0 を確認すること。

想定ロット(残高 20,000・現在価格): NAS100 ≈ 10,000 / 20,000 = 0.50 lot、US500 ≈ 10,000 / 6,600 = 1.5 lot(契約サイズ 1 の場合。FN の契約サイズが 10 ならその 1/10)。GBPJPY ≈ 4 ショット × 0.13 lot、AUDJPY ≈ 4 × 0.19 lot。

## 2. 装着条件(規約・順序)

1. **FN100k #14074882 を季節RG3 からギャンブル版(docs/292)へ切り替えた後**にのみ装着。切替前は RG3 の E-Mon(US500/NAS100 月曜買い)と Instant の指数 Mon が FN 内で同一取引(同日・同銘柄・同方向)になり禁止事項に当たる。
2. 旧 Instant EA(v1.02)をチャートから外してから本 EA を付ける(同 Magic のため建玉は引き継がれる)。
3. FN Instant のニュース規則(docs/182: 2026-08-03 の "News Event Trading Notice")は書面未確認。確認が取れるまでは §3 のメールを送るか、`InpMonSkipDates` に該当月曜を入れる。
4. 初回ログで確認する行: `[基準残高]`/`[INIT RecentFit INSTANT] initBal=20000 mult=4.0 Σw=1.250`、`[銘柄解決] Mon NAS100 → NDX100`、`[銘柄解決] Mon US500 → SPX500`、`[INIT G v1.10] … 推定lots=` が 4 本とも > 0。

## 3. FN サポートへの確認メール(**2026-09-26 送信済み**・ユーザー指示「送信してもらえますか」)

宛先 support@fundednext.com(通知の差出人 notification@ は返信不可)。Gmail スレッド id 1a0db6e1db96b916。実際に送った本文は下記草案に §3a の 3 件の通知情報と「40% 調整のみか / 繰り返しで違反になるか」の問いを加えたもの。

### 3a. 通知の実態(受信箱で確認)
| 受信日 | 注文 | ニュース時刻(GMT+3) | UTC | 曜日 |
|---|---|---|---|---|
| 2026-08-03 | 191525318 | 17:00 | 14:00 | 月 |
| 2026-08-18 | 194288501 | 09:00 | 06:00 | 火 |
| 2026-09-15 | 199394175 | 09:00 | 06:00 | 火 |

文面は「ニュースイベント中に取引した。方針によりその取引の利益の 40% を残高に計上する」。禁止ではなく利益 60% 没収型。火曜 06:00 UTC の 2 件は Instant EA の月曜 06:00 UTC ショットの 24h 時間決済が英国指標(06:00 UTC)に重なったもの。対策候補(回答待ち): Mon の時刻を 4/7/9/10 のように 06 を避ける、または決済を +23h/+25h にずらす。

```
Subject: Instant account 11988011 – clarification of the news-trading rule

Hello FN Support,

On 3 August 2026 I received a "News Event Trading Notice" on my Stellar Instant account 11988011.
Before I adjust my strategy I would like to confirm exactly how the news rule applies to this account type.

1. Does the news restriction apply to Stellar Instant accounts, or only to funded/challenge accounts?
2. Which instruments are covered – all instruments, or only those directly affected by the news release
   (for example US indices for US data)?
3. What is the restricted window (e.g. 2 minutes before/after the release) and which calendar is used?
4. Does the rule apply only to opening and closing trades inside the window, or also to holding
   a position that was opened well before the window through the release?

My planned strategy opens long positions on US indices (NDX100 / SPX500) once a week at the US cash
open (13:30 UTC in summer, 14:30 UTC in winter) and closes them 24 hours later. It also opens JPY-cross
positions on Monday mornings (04:00–10:00 UTC) with the same 24-hour hold. No trades are opened or
closed intentionally around scheduled releases, but the 24-hour hold may run through a release.

Could you confirm whether this is compliant, and if not, which part should be changed?

Thank you,
<name>
Account 11988011
```

日本語要旨: Instant にニュース規則が適用されるか / 対象銘柄 / 窓の長さと基準カレンダー / 窓内の新規・決済のみか保有も対象か、の 4 点を尋ね、計画(指数の週 1 回 24h 保有と月曜円クロス)が適合するか確認する。

## 4. 想定成績(docs/298 再掲)

5 年 年率 +33.9% / 最大 DD −13.6% / 最悪月 −5.0%、MLL 接触 30%/年、生存時中央 +41.0%、期待値 +30.5%(現行 A 案: +17.3% / 32% / +14.7%)。接触率は変わらず年率が倍。Instant は「3 割の確率で消える宝くじトラック」(docs/185)の位置づけのまま。

## 5. 未確認事項
- FN の NDX100/SPX500 の契約サイズ・最小ロット(初回ログで確認)。
- ニュース規則(§3)。
- 指数 Mon の入り時刻を現物寄りに合わせた点は研究定義には忠実だが、季節RG3 の E-Mon(サーバ月曜 0 時 ≈ 日曜 22:00 UTC 建て)とは異なる。RG3 と同一取引にならない副次効果はあるが、§2-1 の順序は守る。
