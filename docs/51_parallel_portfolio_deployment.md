# 51. 並行ポートフォリオ デプロイ — E-Mon+E5 を1チャート挿入(プロップ/インスタント/別業者)

> ユーザー要望「対象は**両方/別業者**(プロップ審査・インスタント・FTMO等)」への回答。
> 並行ポート(docs/50: E-Mon核+E5衛星)を、既存3戦略オールインワン(docs/45)と**同じ操作感**で1チャートに。
> 成果物: `mql5/Chien_Parallel_AllInOne_PROP.mq5` / `mql5/Chien_Parallel_AllInOne_INSTANT.mq5` ＋ プリセット4種。

## 0. どっちを使う?

| あなたの口座 | 使うファイル | 既定シナリオ |
|---|---|---|
| **プロップ審査(FundedNext/FTMO 2-step)** | `mql5/Chien_Parallel_AllInOne_PROP.mq5` | 静的−10% / +8%目標 / 日次−4% / 攻め3.0x |
| **インスタント(Blueberry等・即時資金化)** | `mql5/Chien_Parallel_AllInOne_INSTANT.mq5` | −10%トレーリング / 無目標 / 攻め2.0x |

→ **該当する方を1つだけチャートにドロップするだけ**。残高は自動取得。銘柄名だけ業者仕様に合わせる。

> ★ これは**既存ポート(v7+v4+E5)とは別口座**で動かす。狙いは docs/50 の通り **E-Mon ⇄ v7 = +0.22(低相関)**
> ＝既存口座と同時にDDしない並行の器。別業者にすれば「業者1社の破綻/規約変更」リスクも分散できる。

## 1. 中身(1つのEAで2戦略・全銘柄を内部運用)

| 戦略 | 銘柄 | ロジック | 決済 | Magic |
|---|---|---|---|---|
| **E-Mon(核)** | 指数3つ(NAS100/US500/GER40) | 月曜 09/14UTC LONG・リスク予算化(多ショット) | 24h時間決済(SL=2.5ATR_H1保険) | base+1 |
| **E5(衛星)** | 金+株価指数4 | 月初 TSMOM 逆ボラ加重で両建て | 翌月反転で入替(SL=2.5ATR_MN1) | base+2 |
| 口座ガード | 全体 | 総合−10%枠の内側(既定−9%)で全停止 | — | — |

- **E-Mon は v7 と同型**(月曜 open→翌open LONG・週次リスク予算をショット数で割って合算DDを器に収める)。
  v7 が円3クロスなのに対し E-Mon は株価指数3つ＝**資産クラスを変えた v7 のアナログ**。
- **2戦略は Magic 分離**(base+1/+2)。E-Mon と E5 は指数(US500/NAS100/GER40)を共有するが別管理で混線しない。
- 2戦略は **無相関〜微負(E-Mon⇄E5 −0.06・実10年・docs/50)**→分散でDD効率↑。

## 2. 手順(MT5)

1. `Chien_Parallel_AllInOne_PROP.mq5`(または `_INSTANT.mq5`)を MetaEditor でコンパイル(F7)。
2. 「アルゴリズム取引」ON。**どれでもいいチャート1枚**に該当EAをドラッグ →「Allow Algo Trading」✓ → OK。
3. それだけ。残高自動・倍率/比率/ルールは既定で入る。**1チャートに1つだけ**(複数や他EAと同口座でMagic衝突回避)。

### 業者で銘柄名が違う場合のみ編集
- `InpEMonSymbols`(指数3つ) / `InpE5Symbols`(金+指数)を実銘柄名に。
  (US500=SPX500/USA500, NAS100=USTEC/US100, GER40=DE40/DAX40, XAUUSD=GOLD 等。別名総当りも内蔵)。
- **★指数の取引時間に注意**: 月曜の建て時刻 `InpEntryHoursUTC=9,14`(欧州/米セッション)。業者の指数取引
  時間が違う/休場だと建たない。実セッション開始に合わせて調整(例: 米指数中心なら `13,14,15`)。

## 3. 既定サイズ(★攻めの戦法・業者破綻リスク前提・docs/46と同方針)

> 方針: 業者の破綻/規約変更/出金拒否を織り込み、「長期生存」より**速く通し・速く出金・口座に大金を
> 置かない前傾運用**(ユーザー選択)。全停止フロアを**−9%**まで使い倍率を上げる。比率は E-Mon:E5≈67:33。

| ファイル/シナリオ | 倍率 | E-Mon週次 | E5 legRisk | フロア | ルール | プリセット |
|---|--:|--:|--:|--:|---|---|
| PROP 突破 | **3.0x** | 3.00% | 1.50% | −9% | 静的−10%・+8%停止・日次−4% | `parallel_prop_breakthrough_3x.set` |
| PROP 気長 | 1.5x | 1.50% | 0.75% | −8% | 静的−10%(守り寄り) | `parallel_prop_conservative_1_5x.set` |
| INSTANT 攻め | **2.0x** | 1.20% | 0.60% | −9% | −10%トレーリング・無目標 | `parallel_instant_2x.set` |
| INSTANT 守り | 0.6x | 0.60% | 0.30% | −8% | −10%トレーリング(資金化後) | `parallel_instant_conservative_0_6x.set` |

- **そのままドロップで攻め倍率**(PROP=3.0x / INSTANT=2.0x)。フロア−9%で−10%枠をほぼ使い切る
  (`InpAccountFloorDDPct`で調整)。他倍率は `InpScenario=PARA_MANUAL` で `InpEMonWeeklyPct`/`InpE5LegRiskPct` を直接指定。
- これらの倍率は **既存ポートの v7/E5 既定(docs/45/46)を踏襲した近似**(E-Mon が v7 の役)。E-Mon の素
  バスケット10年maxDD≈−15%(=v7と同じ)ゆえ、**週次予算で合算DDを器に収める**前提。
- ⚠ **攻めの代償**: 攻め倍率はmaxDDが−10%枠に接近→**−9%フロアが頻繁に作動**(早期撤退で−10%DQは回避するが
  stop-out増)。失格率の確定値は Drive(`notebooks/parallel_emon.ipynb`)＋デモで実測して調整。
- **攻めの要諦＝出金最優先**: 利益が出たら**毎サイクル必ず出金**。口座残高を小さく保つことが業者破綻への最大の防御。

## 4. 別業者(FTMO等)・両方運用のとき

- **FTMO 2-step**: 静的−10%(最大)/**日次−5%**/目標+10%(P1)・+5%(P2)。PROP版の `InpScenario=PARA_MANUAL` で
  `InpAccountFloorDDPct`(例8〜9)・日次は規約に合わせる。E-Mon+E5 のロジック/銘柄は不変。
- **両方(既存ポート＋並行ポートを同時運用)**: **必ず別口座**で。同口座に両EAを乗せると Magic は分離されるが
  証拠金/ガードが干渉する。並行口座は別業者にすると業者リスクも分散(docs/50 §4)。
- **INSTANT版とPROP版の Magic ベースは分離済**(INSTANT=950710系 / PROP=950720系)。既存3戦略ポート
  (940710/940720系・docs/45)とも衝突しない。

## 5. 必ず守る(本資金前)

- **E-Mon=STRONG-LEAD(7/9, docs/50)・E5=STRONG-LEAD(未検証, docs/31)**＝**共に本資金前にデモ前進検証必須**。
  `InpAcknowledgeLEAD=true` で承認(=デモ/極小である自覚)。
- **指数CFDの実スプレッド/スワップ/配当/取引時間は未計上**→デモで実測(docs/39と同じ)。特に**月曜の建て時刻**が
  業者の指数セッションと合っているか(休場で建たない事故を防ぐ)。
- デモで **E-Mon+E5 併用の実maxDDが−10%内**か数ヶ月確認 → 合格後に小サイズ本番(まず守り型)。
- **E-Mon⇄v7 の低相関が前向きにも維持される**か(既存口座と同時DDしないか)をデモ期間で観察。

## 6. 成果物
- `mql5/Chien_Parallel_AllInOne_PROP.mq5`(プロップ既定・Magic 950720系)
- `mql5/Chien_Parallel_AllInOne_INSTANT.mq5`(インスタント既定・Magic 950710系)
- `mql5/presets/parallel_prop_breakthrough_3x.set` / `parallel_prop_conservative_1_5x.set`
- `mql5/presets/parallel_instant_2x.set` / `parallel_instant_conservative_0_6x.set`
- 根拠: docs/50(E-Mon探索・9ゲート・相関) / `research/parallel_edge_hunt_10y.py` / `parallel_emon_validate.py` /
  `notebooks/parallel_emon.ipynb`(Drive確定)。

> 免責: シミュレーション・確率であり保証ではない。E-Mon/E5は本資金前デモ必須。業者規約・銘柄名・取引時間は要確認。
> 既定サイズは出発点であり、Drive10年実測＋デモで調整すること。
