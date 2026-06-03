# 36. 確定推奨の運用構成（MQL設定書）— v7+E5 併用

> docs/35の確定推奨を実運用に落とす設定。構成: **v7 EA(`FundedNext_Stellar_EA_v8_dualfirm`)** を円3クロスに、
> **E5 EA(`Chien_E5_RP_Trend_EA`)** を 金+株価指数 に各1アタッチし、リスク予算で比率を作る。
> プリセット: `mql5/presets/*.set`。⚠ E5はSTRONG-LEAD(未検証)＝デモ合格(docs/29)まで本資金禁止。

## 0. シナリオ別 確定設定
| シナリオ | 口座 | v7倍率(週次) | 比率 v7:E5 | E5 legRisk | 期待(Drive10年) |
|---|---|--:|---|--:|---|
| **①プロップ突破** | FundedNext $100k | **2.5%** | **65:35** | **1.23%** | Phase1中央3ヶ月/合計約6ヶ月・審査中失格16% |
| **②プロップ資金化後** | FundedNext $100k | **1.5%** | **75:25** | **0.46%** | 年失格6.5%・手取り≈¥1.4M(¥100k口座) |
| **③インスタント運用** | Blueberry $50k | **1.5%** | **75:25** | **0.46%** | 年失格6.5%・手取り≈¥862k(5年失格38%) |

- legRisk = (E5share/v7share)×(0.55/0.6)×週次% （E5 legRisk0.55%≡v7週次0.6%のアンカー）。
- **①→②**: 審査突破後は必ず倍率を2.5%→1.5%・比率65:35→75:25へ落とす（資金化後の生存優先）。
- ③で収益重視なら 65:35(E5 legRisk 0.74%)も可。**真の低失格**を狙うなら中庸サイズ
  （v7週次0.9%相当・目標DD−6%・65:35→5年失格2.8%, docs/32）。

## 1. v7 EA（FundedNext_Stellar_EA_v8_dualfirm）設定
円3クロス **EURJPY / GBPJPY / USDJPY** の各H1チャートに1つずつ。
| 入力 | ①突破 | ②資金化後 | ③インスタント |
|---|---|---|---|
| InpFirmPreset | FIRM_CURRENT_PROP_2_5X(=0) | FIRM_MANUAL(=2) | FIRM_INSTANT_1_5X(=1) |
| InpInitialBalance | 100000 | 100000 | 50000 |
| InpWeeklyRiskPct | (presetが2.5%) | 1.5 | (presetが1.5%) |
| InpUseTrailingDD | (preset:静的) | false | (preset:トレーリング) |
| InpUseProfitStop | (preset:+8%停止) | **false**(資金化後は無目標) | (preset:なし) |
| InpUseDailyStop | (preset:有) | true | (preset:なし) |
| InpMaxLossLimitPct | 10 | 10 | 10 |
- 全インスタンスで InpWeeklyRiskPct（=倍率）は同一に。3ペア×4時刻=週12ショットは自動。

## 2. E5 EA（Chien_E5_RP_Trend_EA）設定
**XAUUSD / US500 / NAS100 / GER40** の各チャートに1つずつ（業者のCFD銘柄名に合わせる）。
| 入力 | ①突破 | ②資金化後 | ③インスタント |
|---|---|---|---|
| InpAcknowledgeLEAD | true | true | true |
| InpLegMonthlyRiskPct | **1.23** | **0.46** | **0.46** |
| InpInitialBalance | 100000 | 100000 | 50000 |
| InpAccountFloorDDPct | 8 | 8 | 8 |
| InpAllowShort | true | true | true |
- legRiskは各レッグ独立の月次目標σ。4銘柄で同一値に。

## 3. プリセットファイル（mql5/presets/）
| ファイル | EA | シナリオ |
|---|---|---|
| `v7_prop_breakthrough_2.5x.set` | v8_dualfirm | ①突破 |
| `v7_prop_funded_1.5x.set` | v8_dualfirm | ②資金化後 |
| `v7_instant_1.5x.set` | v8_dualfirm | ③インスタント |
| `e5_prop_breakthrough_65_35.set` | E5 | ① (legRisk1.23) |
| `e5_prop_funded_75_25.set` | E5 | ② (legRisk0.46) |
| `e5_instant_75_25.set` | E5 | ③ (legRisk0.46) |

## 4. 手順・確認
1. デモ口座で①(突破)構成を投入 → v7×3チャート＋E5×4チャート。
2. **併用後の実測 最大DD** を監視: 目標は枠内（①は審査中−10%、②③は運用−10%）。乖離あれば legRisk と
   v7倍率を比例調整（maxDDは予算に線形）。正確な各レッグ予算は `notebooks/v7e5_portfolio_mc.ipynb`
   の「EA予算への変換」(Drive)で確定。
3. プロップ: ①で突破 → **資金化後ただちに②へ切替**（倍率↓・比率↑v7）。
4. E5は指数/金CFDの実スプレッド・スワップ・配当をデモで確認（バックテスト未計上）。

> 免責: E5はSTRONG-LEAD(未検証)。数値はシミュレーション(月次MC・Yahoo日足含む)で将来を保証しない。
> 本資金投入はデモ前進検証(docs/29)の合格後・小サイズから。倍率/比率は審査と運用で変えてよい。

## 5. MT5 セットアップ手順（①プロップ突破 / ③インスタント）
### 事前
1. MetaEditorで `FundedNext_Stellar_EA_v8_dualfirm.mq5` と `Chien_E5_RP_Trend_EA.mq5` をコンパイル(F7)→ `MQL5/Experts/` に .ex5。
2. `mql5/presets/*.set` を `MQL5/Presets/` にコピー（チャートのInputsタブ→Loadで読み込み）。
3. ツールバーの「アルゴリズム取引(AutoTrading)」をON。

### ①プロップ突破（FundedNext $100k・MT5）
- **v7**: EURJPY / GBPJPY / USDJPY の **H1チャート**を3枚開き、各に v8_dualfirm をドラッグ →
  preset `v7_prop_breakthrough_2.5x.set` を Load（FirmPreset=CURRENT_PROP_2_5X / InitialBalance=100000）。
- **E5**: XAUUSD / US500 / NAS100 / GER40 のチャートを4枚開き、各に Chien_E5_RP_Trend をドラッグ →
  preset `e5_prop_breakthrough_65_35.set` を Load（legRisk=1.23 / InitialBalance=100000）。
- 各チャートで「Allow Algo Trading」にチェック。Magic: v7=920580 / E5=930610（自動で衝突しない）。

### ③インスタント運用（Blueberry $50k）
- **v7**: 同じ3つのJPY H1チャートに `v7_instant_1.5x.set`（FirmPreset=INSTANT_1_5X / InitialBalance=50000）。
- **E5**: 同じ4銘柄に `e5_instant_75_25.set`（legRisk=0.46 / InitialBalance=50000）。

### ★必ず確認（重要）
- **プラットフォーム**: これらは **MT5専用EA**。FundedNext Stellar は MT5 提供あり(①OK)。
  **Blueberry Funded は TradeLocker 等の可能性**があり、MT5非対応プランだと .ex5 は動かない。
  申込前に**MT5が使えるプラン/サーバか確認**（不可ならEAの移植が別途必要）。
- **銘柄名**: 業者ごとに指数/金の名称が異なる（US500=SPX500/US500, NAS100=USTEC/NAS100,
  GER40=DE40/GER40, XAUUSD=GOLD 等）。実銘柄名に合わせてE5を当てる。
- **ニュースフィルタ**: MT5の経済指標カレンダーが有効な口座で動作（v7のInpUseNewsFilter）。
- まず**デモ**で1〜2週、約定・スプレッド・スワップ・実DDを確認してから本番。

## 6. 業者情報（公式）
- **FundedNext**（プロップ・①②）: https://fundednext.com/ （Stellar 2-Step / MT5提供）
- **Blueberry Funded**（インスタント・③）: https://blueberryfunded.com/
  - インスタント: https://blueberryfunded.com/instant-funding/ （Instant Elite / Instant Lite）
- ⚠ **クーポン**: docs/25 の「30%クーポン」は**コスト試算用に置いた仮定**で、実在の有効コードではない。
  割引コードは propfirmmatch.com 等のアグリゲータが掲載（時期で変動・"40% OFF"等の表示あり）するが、
  **当方は有効性を検証できない**。**購入時に公式決済画面で実際の割引額を必ず確認**すること。
  捏造コードは載せない（誤情報防止）。
