# 273.【試算・問い合わせ文】ロール捕捉(swap-free 口座での水曜 3 日分フォワードポイント)— 条件が揃った場合の成績と他手法との比較、各社への確認文

> 2026-09-22。ユーザー「条件をクリアした場合、成績はどの様な形でしょうか。他手法と比較して下さい。また各社に送る文面を作成してください」。docs/272 §5 の機構(NY 17 時のバリューデート繰り上げで高金利通貨がフォワードポイント分だけ下落、水曜は 3 日分)を前提に、**スワップが課されない口座でだけ成立する**捕捉の試算。前提が崩れれば期待値ゼロ(通常口座はスワップで相殺)。
> 規則: 水曜 20:00 UTC 始値で 5 円クロス(USDJPY EURJPY GBPJPY AUDJPY CADJPY・CHFJPY は金利差が小さく除外)を等ウェイトで SHORT(円買い)、00:00 UTC 始値で買い戻し。門: 政策金利差 ≥ 1pp。実測 = bid で売り ask で買い戻し。計算は `research/queue/q27_q20_measured_jpy.py` と同じ系列(9/22 の追加集計)。

## 1. 成績(名目 = 5 本合計の建玉名目 ÷ 口座残高)

| 期間・コスト | 週数 | 平均/週 | 週σ | 最悪週 | +週率 | 年率(名目 1 倍) | Sharpe | 最大 DD(名目 1 倍) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 2022-01〜2026-08・仮定 3pip | 226 | +3.9 bps | 15.3 bps | −39.6 bps | 0.61 | +2.0% | 1.85 | −0.68% |
| 2024-01〜2026-08・実測 bid/ask | 137 | +5.1 bps | 16.6 bps | −38.2 bps | 0.69 | +2.7% | 2.24 | −0.50% |

名目倍率別(実測 2024〜。週 1 回・保有 4 時間・週の 1% 分位 −28 bps):

| 名目倍率 | 年率 | 最悪週 | 最大 DD | 週σ | 想定用途 |
|---|--:|--:|--:|--:|---|
| 2 倍 | +5.3% | −0.8% | −1.0% | 0.33% | 資金化後のスリーブ |
| **3 倍** | **+8.0%** | **−1.2%** | **−1.5%** | 0.50% | 推奨上限(BoJ 介入級の 4h 変動 −1.5% × 3 = −4.5% を日次 5% の内側に) |
| 5 倍 | +13.4% | −1.9% | −2.5% | 0.83% | 日次 3%(FTMO 1-Step)には不適 |

性質: 収益源が「金利差 × 3/360」という機械的な増分なので、方向当てではなくアクルーアル型。週 1 回・4 時間だけの露出で、それ以外の時間は無ポジション。**年率は小さく、DD も小さい。** チャレンジ通過(+10%)には名目 3 倍で約 15 ヶ月かかり、**チャレンジ用ではなく資金化後・長寿命枠のスリーブ**。

## 2. 他手法との比較(既存 docs の校正値)

| 手法 | 出典 | 年率 | 最大 DD / 最悪 | 失格率(MC) | 収益源 | 前提 |
|---|---|--:|--:|--:|---|---|
| **ロール捕捉 ×3(本書)** | docs/272 §5 | **+8.0%**(実測 2024〜) | **−1.5% / 週 −1.2%** | 未計算(DD が小さく日次 5% にはほぼ触れない) | 3 日分フォワードポイント(機械的) | **swap-free でスワップもロール手数料も無し・規約で禁止されていない** |
| ロール捕捉 ×5 | 同 | +13.4% | −2.5% / 週 −1.9% | — | 同 | 同 + 日次 3% 口座には不適 |
| Mon 円クロス A 案 ×2.36 | docs/228 | +12.3%(5 年)・2024 年型なら +8% | −5.6% / 月 −3.4% | 2.3%(5y) | 月曜の円クロス上昇(統計的) | 稼働中(RF5・#531343523) |
| Mon 4 ×2.52 | docs/245 | +12.4% | 月 −3〜4% | 13.3%(2-Step) | 同 | 稼働中(EA3・#531407058) |
| TSMOM BROAD_IV | docs/194 | +17.4%(OOS) | — | 11.9% | 12 ヶ月モメンタム(統計的・長寿命) | Q1 パリティ待ち |
| 非 FX Hold+v4+Mon ×1.48 | docs/182 | — | — | — | 常時 LONG(ベータ)+Mon | FN #14166201(swap-free)で稼働 |

読み方:
1. **リスク調整後は最良、絶対収益は最小。** Sharpe 2.2 は既存のどの族より高いが、これは「ほぼ確実な小さな増分」の性質で、レバレッジを上げないと年率にならない。上げると 4 時間の集中露出(円 5 本同方向)が日次規約に当たる。
2. **他の族と時間的に重ならない**(水曜 20〜00 UTC のみ)ので、Mon や Hold と同じ口座で併走でき、相関はほぼゼロ。FN の「EA は 1 口座 1 本」規則(docs/185 §10b)により、FN で使うなら NonFX EA にレグとして内蔵する形になる。
3. **前提依存が極端。** ①swap-free でない口座では期待値ゼロ、②swap-free でも「管理手数料」「ロール跨ぎの保有制限」「swap-free 悪用条項」のどれか 1 つで消える、③規約に明記が無くても、同社が事後に「悪用」と判定すれば口座失効のリスク。**書面での確認(§3)が採用の前提。**
4. 2026 年の金利差縮小(米 3.75%・日 0.75% → 3.0pp)でロール幅は 2024 年より 3 割小さくなる。年率は金利差に比例して落ちる。

## 3. 各社への確認文

方針: 手法の中身を隠さず、しかし「ロール狙い」と自ら悪用の枠に入れない。聞くのは事実(料金・制限・規約の適用範囲)と、**書面での可否**。返答は docs/185 の書面台帳に記録する。送信はユーザーが行う(私は代理で本人確認・送信をしない)。

### 3a. FundedNext(英語)

問い合わせ先(fundednext.com/contact・2026-09-22 確認):

| 経路 | 宛先 | 備考 |
|---|---|---|
| メール | **support@fundednext.com** | 9/12 の "Re: CFD / Forex" スレッド(Richard)と同じ宛先。**同じスレッドに返信すると口座と経緯が紐づく** |
| 規約の判断 | **tradingethics@fundednext.com** | 「悪用に当たるか」の判断はこちら(docs/185 §10b の出所)。support に送っても転送されるが、直接 CC する |
| ライブチャット | ダッシュボード / サイト右下(Intercom・24/7・初回応答 25〜60 秒) | 書面として残すには最後に「この回答をメールで送ってください」と依頼 |
| Telegram | @askfundednextbot | 補助 |
| ヘルプセンター | help.fundednext.com | 規約記事の URL を回答に添えてもらう |

推奨: メールで support@ 宛て、tradingethics@ を CC。件名に口座番号。

件名: Swap-free account — rollover holding rules and fees (Account 14166201)

> Hello FundedNext team,
>
> I hold a Stellar 2-Step 100K account (login 14166201) purchased with the Swap-Free add-on. Before I add a strategy that sometimes holds positions for a few hours across the daily rollover (17:00 New York), including Wednesdays, I would like written confirmation of the following:
>
> 1. On a Swap-Free account, is there any fee or charge of any kind for holding a position across the daily rollover or across the weekend (administration fee, holding fee, financing fee, commission difference)? If yes, please state the amount and how it is calculated.
> 2. Is there any minimum or maximum holding time, or any restriction on opening/closing positions around the rollover time, that applies specifically to Swap-Free accounts?
> 3. Do your rules treat a strategy that regularly holds FX positions across the rollover on a Swap-Free account (for example, short positions in JPY crosses held for a few hours on Wednesday evening) as prohibited, as "swap-free abuse", or as any other rule violation? If there is a relevant clause, please quote it.
> 4. Can the Swap-Free status be removed or changed after purchase, and under what conditions? Would the same rules apply once the account is funded?
>
> I am asking in advance so that I only run what is explicitly allowed. Thank you for confirming in writing.
>
> Regards, [氏名] (login 14166201)

### 3b. FTMO(英語・support@ftmo.com)

件名: Swap-free accounts — availability, fees and rollover holding rules

> Hello FTMO team,
>
> I have FTMO Challenge / funded accounts (logins 531343523, 521100397, 531407058, 531466484). I would like written confirmation on Swap-Free accounts:
>
> 1. For which account sizes and plans (2-Step Standard, Swing, 1-Step) is the Swap-Free option available, and can an existing account be converted?
> 2. On a Swap-Free account, is there any fee for holding positions across the daily rollover or the weekend (administration, holding, financing)? Please state the amount and calculation.
> 3. Are there holding-time limits or restrictions on trading around the rollover time on Swap-Free accounts?
> 4. Would a strategy that regularly holds FX positions (e.g., short JPY crosses) for a few hours across the Wednesday rollover on a Swap-Free account be considered prohibited or "abuse" under your rules? If so, please quote the clause.
> 5. Do the same conditions apply to funded accounts and to the FTMO Account after passing?
>
> Thank you for confirming in writing.
>
> Regards, [氏名]

### 3c. Fintokei(日本語・会員ページのお問い合わせフォーム / チャット)

件名: スワップフリー口座の有無と、ロールオーバーを跨ぐ保有に関する規約の確認

> Fintokei サポートご担当者様
>
> パール 500 万・速攻プロ 2,000 万(口座 6078225)を利用しております。スワップフリー(イスラム口座等)に関して、次の点を書面でご確認いただけますでしょうか。
>
> 1. 御社のチャレンジ口座・プロ口座に、スワップが発生しない口座タイプ(スワップフリー)はありますか。ある場合、対象プランと申込方法、費用(追加料金・管理手数料・保有手数料など)を教えてください。
> 2. スワップフリー口座で、日次ロールオーバー(NY 17 時)や週末を跨いでポジションを保有する場合に、何らかの手数料や保有時間の制限はありますか。
> 3. 例えば水曜日の夕方(UTC 20〜24 時)に円クロスの売りポジションを数時間保有し、ロールオーバーを跨ぐ取引を継続的に行うことは、御社の規約上(スワップフリーの不正利用・取引制限など)問題になりますか。該当する条項があれば引用をお願いします。
> 4. スワップフリーの条件が事後に変更・取消される場合の条件と、プロ口座(資金提供後)でも同じ条件が適用されるかを教えてください。
>
> 許可されている取引だけを行いたいため、事前に確認させていただいております。お手数ですがよろしくお願いいたします。
>
> [氏名](口座 6078225)

### 3d. 返答後の判定

| 返答 | 扱い |
|---|---|
| 手数料なし・制限なし・悪用条項に該当しないと明記 | 書面を docs/185 に記録 → Q28 として「swap-free 口座向けロール捕捉レグ」を事前登録(名目 3 倍上限・NonFX EA へ内蔵・紙上 1 ヶ月の後に採用判断) |
| 手数料あり | 手数料が 3 日分ロール幅(2〜3 bps)の半分を超えれば不採用 |
| 保有制限・悪用条項あり・回答が曖昧 | 不採用(口座失効リスクを取らない) |
| 通常口座のみ | 期待値ゼロのため不採用。監視(docs/272 §3)だけ続ける |

## 4.【9/22 追記】各社の回答状況

| 社 | 送信 | 回答 | 判定 |
|---|---|---|---|
| **Fintokei** | 9/21 23:49 UTC(jpsupport@fintokei.com) | 9/22 00:33 UTC・**書面で条件クリア**(スイングのみ swap-free・追加費用なし・保有制限なし・ロール跨ぎ継続は違反でない・事後変更なし・プロ口座も同条件)。docs/220 §8 | **採用検討へ(Q28)**。ただし既存口座は対象外で、スイングの新規購入が要る(パール 500 万 ¥49,800 / ルビー 1,000 万 ¥84,800) |
| FundedNext | 9/22 01:39 UTC(support@) | 9/22 03:19 UTC 回答(docs/185 §10b-3)。③ロール跨ぎ SHORT は "not swap-free abuse"・④資金化後も継続、は明記。**①手数料は "there is extra charge" と逆の文**(脱字の疑い) | ①の再確認後に採用検討。FN は 1 口座 1 EA |
| FTMO | 9/21 23:51 UTC(support@ftmo.com) | 未回答 | 待ち |
