# 176.【比較メモ】直近フィット・トラック2実装の比較 — 8ta3be版 vs ufzpaj版

> 2026-07-30の同一指示(「過去1年だけ伸びているEAを別枠で」)に対し、2つの独立実装が
> 並行して作られた。本docはポートフォリオ追加判断のための比較。
> - **A案** `claude/prop-trading-ea-short-term-8ta3be` — Chien_RecentFit5_EA v1.0
> - **B案** `claude/prop-trading-ea-short-term-ufzpaj` — Chien_RecentFit_2026H2_Prop
> 両者とも共通ベース e83a8b7(v1.45)上に docs/174-175 として実装。⚠ **docs/175の
> ファイル名が両案で衝突**するため、両方採用する場合は片方の番号振り直しが必要。

## 1. アプローチの本質的な違い

| 項目 | A案(RecentFit5) | B案(RecentFit 2026H2) |
|---|---|---|
| 候補母集団 | **新規パターン1602本**(曜日×時刻H1・日足TSMOM・RSI逆張り) | **既存スリーブ構築式32セルのみ**(Mon/Hold/TSMOM/v4、docs/139と同一式) |
| データ | Yahoo H1+日足(2024-08..2026-07) | Yahoo日足(2016-01..2026-07) |
| 選定窓 | FIT 10ヶ月+HOLDOUT 12週(符号のみ)+REF開示 | 直近12ヶ月かつ直近6ヶ月の両方プラス |
| 採用 | 5スリーブ(t値順・ペア×族重複排除) | Top-4(銘柄1・族2制約・逆ボラ加重) |
| 構成 | GBPUSD月曜L・GBPJPY月曜L・USDCHF木曜S・GBPUSD RSI2・GBPJPY RSI2 | Mon GBPJPY 34.8%・Mon AUDJPY 29.9%・v4 USDJPY 28.3%・Hold JP225 7.0% |
| リスク表現 | 1トレード1.25%(3×ATR SL基準)・2.0%速度版 | 倍率4.8x標準・7.2x速攻(グリッド12xまで開示) |

- **A案は「直近だけ伸びた型の新規発掘」**: S4/S5(RSI逆張り)はREF窓PF0.71〜1.00=前年
  マイナス〜フラットの純粋な直近レジームベット。指示の趣旨に最も忠実。
  代償として多重検定1602本を意図的に受容している。
- **B案は「既存の検証済み構築式の直近リランキング」**: 採用4セルは長期でも概ね機能して
  きた族(円クロス月曜・日経Hold・v4)の直近好調銘柄。「直近特化」というより
  **直近傾斜をかけた正攻法の高倍率版**に近い。探索空間が32セルと小さく後知恵バイアスは
  構造的に小さい。

## 2. MC・数字の比較(⚠ 前提が違うため直接比較不可)

| 項目 | A案(標準1.25%) | B案(標準4.8x) |
|---|---|---|
| 楽観側(直近サンプル) | 通過99.9%・中央145日 | 資金化99.9%・中央68日 |
| 悲観側 | **全期間バウンドなし**(代わりにエッジ剥落ストレス) | **全期間65.2%・失格24.8%** |
| エッジ消滅時 | 通過2.2%・**規則失格0%**(84.7%時間切れ・guard_stop6.4%) | (該当シナリオなし) |
| 悲観側EV | 未計算 | **+$1,835**(p=0.652でも正・docs/175 §4) |

- A案の売り: エッジが完全に消えても**規則失格0%**という非対称設計をストレスMCで確認済み。
  最悪ケースが「時間切れ/−8%ガード停止」=掛金喪失のみで、口座破裂・失格でない。
- B案の売り: **全期間サンプルという正直な悲観バウンド**を必ず併記する規律。悲観側でも
  EV正が立つことを明示。ただし悲観側の失格24.8%はA案のストレス時0%より重い
  (倍率4.8xと静的−10%枠の距離が近いため)。
- どちらのMCも「ガードが理想執行される」仮定を含む(docs/169のスリップ知見)。

## 3. 運用規律の比較

| 項目 | A案 | B案 |
|---|---|---|
| 撤退規則 | 月次R<0が2ヶ月連続→停止・再スイープ | **失格2回で終了**+費用2回分で打ち止め |
| 賞味期限 | なし(月次採点で管理) | **2026-10-31をEAに焼き込み**(期限後新規停止) |
| フロア | −8% | −9%(静的−10%の手前) |
| 資金化後 | 0.5〜0.68xに減率 | 0.7x目安・報酬都度出金 |
| 残タスク | **MT5パリティ未確認**・Dukascopy追試未 | デモ実測・JP225スワップ/配当コスト未確認 |

B案の「費用上限2回・失格2回撤退・期限焼き込み」はEV計算と直結した明確な損切り線で、
宝くじトラックの規律として優れる。A案は月次採点ベースで柔軟だが費用上限が未定義。

## 4. 重複・干渉(両方採用する場合の論点)

1. **GBPJPY月曜LONGが両案に含まれる**(A案S2=08:00UTC 12h / B案Mon=4時刻24h)。
   両方走らせるとGBPJPY月曜への集中が発生し、成否も相関する(独立な2枚の宝くじではない)。
2. 両案ともFTMO PD口座のv7(GBPJPY月曜)と同一日・同方向になり得る点を自己申告済み。
   同一業者内の複数口座並走はコピー取引規則に触れる恐れ → **正攻法と別業者**が安全
   (両方採用ならさらに互いも別業者に分ける必要)。
3. ファイル衝突: `docs/175_recentfit_results_deploy_card.md` が両案で同名別内容。
   `research/results/` 配下も命名が近い。両方マージするなら番号・命名の整理が必須。
4. チャレンジ費用: 両方買えば掛金2倍。B案の「費用2回分」予算とは別トラック扱いになるが、
   合算の費用上限を先に決めておくべき。

## 5. 判定の目安

- **1つだけ選ぶなら**:
  - **統計的な正直さ・速度・撤退規律を重視 → B案**(悲観バウンド併記・中央68日・
    期限/費用上限焼き込み。ただし悲観側失格25%は掛金リスクとして受容する)。
  - **指示の趣旨(直近レジームの純粋ベット)と失格回避を重視 → A案**(S4/S5が本命。
    エッジ消滅でも失格0%の非対称性が確認済み。ただし多重検定1602本+MT5パリティ未確認
    という数字の脆さを受容する)。
- **両方採用**は「レジーム継続への2重ベット」であり分散にはならない(GBPJPY月曜相関)。
  やるなら別業者2口座+合算費用上限の事前定義+片方のdocs番号振り直しが前提。
- どちらを選んでも、採用前の必須残タスク(A: MT5パリティ / B: JP225実効コスト実測)を
  先に消化すること。

## 6.【追補】業者・プラン選定(コスパ比較)

前提: 現在の稼働(docs/172/173)は FN(100k季節+Instant PD=**v7入り**)・FTMO(PD 2.0x=**v7入り**)・
Fintokei(パール500万=季節RG3・指数/金系)。RecentFitのGBPJPY月曜LONGとの重複が業者ごとに異なる。

| 業者 | 費用($100k級) | 規則の型 | RecentFitとの適合 |
|---|---|---|---|
| FN Stellar 2-step | $549返金あり(VIBES30%→≈$385)+**通過時15%報酬**+分配80-95% | 静的−10%・日次balance基準(docs/170実証)。**両案MCの校正先そのもの** | ⚠ FN Instantのv7がGBPJPY月曜LONG=**Instant↔チャレンジ同一取引禁止(docs/161§4③)に抵触の恐れ**。書面確認が先 |
| FTMO 2-step | ≈$540返金あり・分配80→90% | FNとほぼ同型・頑健性1位(docs/94) | ✗ **同社PD口座のv7と同一日同方向**。このトラックには最も不向き |
| Fintokei通常チャレンジ | 審査料1.25万円〜(WELCOME30JP 30%)・分配80% | **日次equity基準(書面確認済docs/173)**・目標8%→6%・静的10% | ○ **A案なら銘柄重複ゼロ**(季節RG3=指数/金系)。EA・他社並走の書面OK取得済み。B案はJP225が季節側と重複懸念 |
| 新規業者(5%ers/Alpha等) | 各社 | 未校正・書面なし | △ 分離は完全だが規約調査・MC再校正のコストで割高 |

### 判定

1. **紙の上の最良EV = FN Stellar**(MCが同社規則で校正済み・返金+15%通過報酬で「宝くじ」の
   当たりが最も太い)。ただし**Instant v7との同一取引の書面確認(docs/161様式)が取れるまで購入禁止**。
   docs/170(DLL失格)の教訓=規則の曖昧さは書面で潰してから金を入れる。
2. **すぐ動ける現実解 = Fintokei通常チャレンジ×A案**。銘柄重複ゼロ・equity日次は多日保有
   (S4/S5の3〜5日)に有利・小サイズから安く試せる。要確認2点: ①P2目標6%(FN5%前提のMCより
   遅い=再計算) ②購入画面の「オープンポジション最大許容リスク3%」がスリーブ同時保有時の
   合計リスク(1.25%×複数)に抵触しないか。
3. FTMOは業者として最頑健でも**このトラックには使わない**(v7重複が同社内で発生)。
4. 費用予算はB案§5の「チャレンジ2回分で打ち止め」を全体に適用(A/B両方買って4回分にしない)。

## 7.【追補】「同一銘柄」は禁止されていない — 規則の正確な射程と問い合わせ文面

### 7.1 現時点で分かっていること(書面ベース)

| 業者 | 確定している規則 | 出典 |
|---|---|---|
| FN | 禁止は**Instant↔チャレンジ間の「同一取引」のみ**。本人名義チャレンジ同士は同一EA・コピーすら公式可 | docs/161 §4③/§5 |
| FN | 「同一取引」の定義は**未確認**(コピー連結のみか、独立EAの偶発的な同銘柄同方向も含むか) | 本docの論点 |
| Fintokei | 他社との同一自作戦略の独立並走は可・両建て禁止のみ。**同社内複数口座の扱いは未質問** | docs/173 §1 |
| FTMO | 同社内の重複について当方の書面確認なし(頑健性評価とは別問題) | docs/94 |

→ **「同一銘柄エントリー」自体を禁じる規約はどの業者にもない**。リスクは
「同一銘柄×同方向×同時期」の組がFN§4③の「同一取引」と判定されるか、の一点。
判定基準が書面で曖昧なため、docs/99の方針どおり**購入前に書面で潰す**。

### 7.2 FN返信用質問文(英語・docs/161のメールスレッドへ返信)

> Thank you again for the previous clarifications. Before purchasing an additional
> Stellar 2-Step challenge account, I would like to confirm the exact scope of the rule
> "the same trades on multiple accounts are not allowed" between a Stellar Instant
> account and challenge accounts, as it applies to my own accounts under my own name.
>
> My situation: all my accounts are traded by my own private EAs (no copy-trading tools,
> no account linking; each EA runs independently on its own terminal). My Instant account
> runs Strategy X, which sometimes goes long GBPJPY on Monday mornings. The new challenge
> account would run a different EA (Strategy Y, my own), which may also independently
> go long GBPJPY on some Monday mornings at partially overlapping hours.
>
> Questions:
> (a) Does the "same trades" rule refer to copy-trading / linked or mirrored execution
>     only, or does it also cover independently generated trades that happen to be in
>     the same symbol and same direction at a similar time?
> (b) If two of my own independent EAs (different strategies, different lot sizes)
>     both happen to hold GBPJPY long on the same day — one on Instant, one on a
>     challenge account — would that be treated as a violation?
> (c) If (b) is a violation: is it sufficient to disable the overlapping symbol on one
>     of the accounts, so that no same-symbol-same-direction overlap can occur?
> (d) Could you confirm the objective criteria you use to judge "same trades"
>     (e.g., identical timing, correlated lot sizing), so I can stay clearly compliant?
>
> I would appreciate the answer by email for my records.

### 7.3 Fintokei質問文(日本語・docs/173のスレッドへ)

> いつもお世話になっております。追加購入の前に3点確認させてください。
> 1. 同一名義で通常チャレンジ口座を複数保有し、**それぞれ別の自作EA(別戦略)**を
>    独立に稼働させることは可能でしょうか。両者が偶発的に同一銘柄・同方向の
>    ポジションを同時期に持つ場合、規約上の問題はありますか(コピーツール等の連結は
>    一切ありません)。
> 2. 購入画面の「オープンポジション最大許容リスク3%」について、これは
>    (a)1取引ごとのSLベース最大損失、(b)同時保有中の全ポジション合計、
>    のどちらで計算されますか。複数の自作EAスリーブが同時にポジションを持つ場合の
>    計算方法を教えてください。
> 3. ステップ2の利益目標は6%という理解で正しいでしょうか(購入画面で8%→6%と
>    表示されていたため念のため)。

### 7.4 パール相当サイズ($≈31k/¥500万)でのコスパ比較(2026-07-30 Web調査)

価格(報告値・申込当日に公式で要確認): FN Stellar 2-Step **$25k=$199.99 / $50k=$299.99**
(返金=初回出金時・**P1+P2利益の15%ボーナス**が初回出金に上乗せ)。
Fintokeiチャレンジ(パール500万)=**¥39,800**(WELCOME30JP 30%→≈¥27,860。
「初回報酬時に参加費全額返金」は2026-06-30까지の表記があり**現在の適用有無は要確認**)。

EV試算(B案悲観バウンド p=0.652・初回報酬=口座×4%×分配80%・USDJPY159.3):

| プラン | 費用(定価) | 成功時回収 | EV/回 | EV/費用 |
|---|--:|--:|--:|--:|
| FN $25k | $199.99(≈¥32k) | 返金$200+15%ボーナス$487+報酬$800=**$1,487** | **+$900(≈¥14.3万)** | 4.5x |
| **FN $50k** | $299.99(≈¥48k) | 返金$300+ボーナス$975+報酬$1,600=**$2,875** | **+$1,770(≈¥28.2万)** | **5.9x** |
| Fintokeiパール500万 | ¥39,800 | 報酬¥160k(+返金は要確認) | **+¥9.4万〜11.2万** | 2.4〜4.0x |

- **数字の上ではFN優位**。理由は構造: ①返金 ②**15%通過ボーナス**(Fintokeiに相当物なし)
  ③手数料が口座サイズに対し逓減($50kは$25kの+50%の費用で口座2倍)。
  **パール相当予算ならFN $50kが最効率**(費用≈¥48kでEV≈¥28万/回)。
- **ただしこの優位はFNの書面回答(§7.2)が「可」の場合のみ**。「不可」ならFN側EVは0であり、
  Fintokei×A案が唯一の実行可能解(コンプラ確実性・equity日次・日本語書面の質的優位)。
- Fintokei側の注意: P2目標6%(FN5%)でpはやや低下/equity日次でやや上昇=概ね相殺と見るが、
  MC再計算が正式値。支払毎利益目標¥20,000は低く報酬サイクルは速い。

### 7.5【書面記録 2026-07-31】Fintokei回答(メール・スクショ4枚ユーザー保存)

| 質問(§7.3) | Fintokei回答(要旨転記) | 判定 |
|---|---|---|
| 複数口座で別EAの独立稼働 | 「**同時にEAを稼働させることは問題ございません**。しかしながら**複数の口座にて両建て行為は禁止**」「EAは自作及びご自身でカスタマイズするように」 | ✅ 並走OK。禁止は**口座間の両建て(同一銘柄・逆方向)のみ**。同方向重複への言及なし=同銘柄同方向は禁止対象外と読める |
| オープンポジション最大リスク3%の定義 | 「①**1つのトレードアイデア**に対する確定損失・含み損の合計が初期資金の3%を超えてはならない ②同時保有している複数ポジション(グループ)に対する合計も同様」「トレードアイデア=単一の取引、または**同じ銘柄・同じ方向で保有期間が重複する複数取引のグループ**」「グループ全体の確定損失または含み損が**いかなる瞬間においても**3%を超えた場合違反」(例: ¥1,000万口座でUSDJPY Sell×3合計−¥31万=違反) | ⚠ **銘柄×方向×期間重複のグループ単位で3%・実現損+含み損合算・常時判定**。プランにより3%の金額は変動 |
| P2目標6%・返金適用 | (このスクショ群には回答なし) | 未回収 — 再確認 |

#### RecentFitへの影響

1. **両建て禁止はクリア**: A案(GBPUSD/GBPJPY L・USDCHF S・全FX)と季節RG3(指数/金)は
   銘柄が重ならず両建て不能。B案のJP225 Holdも季節側と同方向ロングなら両建てに非該当。
2. **3%ルールの効き方(A案)**: 同銘柄・同方向・期間重複=1グループ。
   - S2(GBPJPY月曜L 12h)+S5(GBPJPY RSI L 3日)が重複した場合: 1.25%×2=**2.5%<3%だが
     余白0.5%のみ**(スリップ・ギャップで浸食され得る)。S1+S4(GBPUSD)も同型。
   - **リスク2.0%(速度優先版)はFintokeiでは使用不可**(重複時2.0%×2=4%>3%)。
   - 対応案: 1.25%を維持+EAに「同銘柄同方向の合算リスク≤2.5%キャップ(超過時は後発
     エントリーをスキップ/減額)」を追加するのが安全。
3. **3%ルールの効き方(B案)**: Mon GBPJPYの4時刻エントリーは全て1グループ。4.8x時の
   グループ合算SLリスクとJP225 Hold(災害SLのみ)の最大潜在損失を**購入前に要計算**。
4. 残る曖昧さ: 回答②の「複数のポジション(グループ)」が**異なる銘柄も跨いだ全体合算**を
   含むのかは例示なし(例は全て同一銘柄)。追加質問で潰す:
   > 異なる銘柄(例: GBPUSDとGBPJPY)のポジションを同時に保有する場合、それぞれ別の
   > 「トレードアイデア」として各3%が上限という理解でよいでしょうか。それとも銘柄が
   > 異なっても同時保有中の全ポジション合計で3%以内でしょうか。
5. 未回収のP2目標6%・参加費返金の適用有無も同じ返信で再確認する。

#### 7.5.1【書面記録 2026-07-31 第2信】銘柄横断の「トレードグループ」3%が存在する

追加質問(§7.5 #4)への回答(メール・スクショ保存):

> 「GBPUSDとGBPJPYはそれぞれ**別のトレードアイデア**と判断し、それぞれのグループ内で
> 3%以内という認識」「**ただし**、弊社のリスク判定はトレードアイデアの他、
> **同じ時間帯に取引している取引グループ**という指標でもリスクが超えないか見ております(FAQ)」
> 「そのため『トレードグループ』としてみた際には、**どちらのお取引も同じグループとみなします**」
> 「1つのトレードアイデア **または** 1つのトレードグループにおいて、いずれかが3%を
> 超えた場合は、**警告対象**となります」

**= 銘柄が違っても、同じ時間帯に保有している全取引の確定損失+含み損の合計が
初期資金の3%を超えたら警告対象。** 実質「同時保有全体の−3%ライン」が常時存在する。

#### 影響の更新(§7.5の#2/#3を上書き)

1. **判定は実現損+含み損の「実損」ベース**(SL距離の潜在リスクではない)。つまりエントリー
   しただけでは違反にならないが、**同時保有群の合計実損が−3%に達した瞬間**が警告ライン。
   現行EAの日次ガード−4%より**1%手前に実質的な上限**ができる。
2. **A案@Fintokei**: 月曜はS1+S2+S4+S5の4本同時があり得る(潜在5%)。合計実損−3%到達は
   現実に起こり得る → 対応は(a)リスクを0.75%へ縮小(docs/175 MC: 通過98.7%・中央238日=遅い)
   か(b)**EAに「同時保有合計実損−2.5%で全決済」のグループガードを追加**して1.25%を維持
   (ガード発動頻度が増える分のMC再計算が必要)。
3. **B案@Fintokei**: JP225 Holdが常時保有でMon/v4が全て積み上がる構造上、4.8xでは
   グループ3%に常時接触圏 → **B案のFintokei配備は実質不適**。
4. **⚠ 最優先: 稼働直前のパール季節RG3 1.25xにも同じルールが適用される**。季節は
   指数月間保有+月曜レッグの同時保有があり、クラッシュ日(2024-08-05型)は全レッグが
   同時に沈む=グループ−3%警告に日次−4%ガードより先に到達し得る。**8月月初の稼働開始前に
   「同時保有合計実損」の履歴最悪値を確認し、必要なら−2.5%グループガードを追加**すること。
5. **FNとの対比が逆転気味**: FNのMax Risk 3%は書面で「**1回の取引における**最大潜在損失」
   (docs/161)=トレード個別・ポートフォリオ合算キャップなし。**A案を標準速度(1.25%)のまま
   走らせられるのは現状FNだけ**(同一取引の書面回答待ちが唯一の関門)。

#### 追加質問ドラフト(第3信)

> 1. 3%を超えた場合は「警告対象」とのことですが、警告後の取り扱いを教えてください
>    (即時失格か、警告のみか、警告が複数回続いた場合の扱い等)。
> 2. 判定は確定損失・含み損の合計とのことですが、既にSL等で決済済みの取引の確定損失は、
>    同じ時間帯に保有していた他のポジションが全て決済された後もグループに含まれますか
>    (グループの区切りのリセットタイミング)。
> 3. (前回未回答分)ステップ2の利益目標は6%でしょうか。また参加費の初回報酬時返金は
>    現在も適用されますか。

#### 7.5.2【書面記録 2026-07-31 第3信】警告扱い・グループリセット・P2=6%・返金終了

第3信(§7.5.1の追加質問)への回答(メール・スクショ保存):

| 質問 | Fintokei回答(要旨転記) | 判定 |
|---|---|---|
| 3%超過時の扱い | 「リスク3%を超えた場合は、**失格とはなりません。警告送付の対象**となります」 | ✅ **即失格ではない**(警告累積時の扱いは未言及) |
| 決済済み損失の合算 | 「同じグループに含まれていれば、**SL等で決済済みの確定損失もカウントに含む**」例: A/B/C同グループでAのみSL決済→Aの確定損+B/Cの含み損で3%超の瞬間がないか判定 | ⚠ グループ内は実現損も合算継続 |
| グループのリセット | 「A/B/C**全て決済した後**に新規D/Eを開いた場合、**D/Eは別グループ**」 | ✅ フルフラット化でリセット |
| P2目標 | 「ステップ2の利益目標は、チャレンジプランの場合**6%**」 | 確定(MC再計算の前提) |
| 参加費返金 | 「**初回の報酬申請時でのお渡しは終了**。契約金はスケーリング道場の制度にて利用可能」 | ✗ **返金なしで確定**(§7.4のEVを下方修正) |

#### 影響の更新

1. **3%は「警告」であり即失格ではない** → §7.5.1の緊急度を一段緩和。A案@Fintokeiは
   0.75%への減速までは不要で、**1.25%+グループ実損−2.5%ガード(警告自体を回避)**が実務解。
   パール季節RG3の稼働前チェックも「失格リスク」ではなく「警告リスク」の確認に格下げ
   (実施は引き続き推奨。警告累積時の措置が不明のため警告ゼロ運用を基本とする)。
2. **グループガードの実装仕様が確定**: 同グループ=フラット化までの連続保有窓。
   ガードは「窓内の実現損+含み損の合計」を追跡し−2.5%で全決済(全決済でグループが
   リセットされる仕様も書面で確定)。
3. **Fintokeiのコスパは確定的に低下**: 返金なし+P2 6%(FN 5%)+80%分配+15%ボーナス相当なし。
   §7.4のEV試算からパール行は「返金は要確認」→「返金なし」で確定(EV≈+¥9万/回のまま)。
   **FN($50k・EV≈+¥28万/回)との差は3倍**。
4. 結論: **FintokeiはFN tradingethicsがNGだった場合のバックアップに降格**。
   残る意思決定材料はFN tradingethicsの回答のみ。

### 7.6【書面記録 2026-07-31】FN回答(ライブチャット・Richard氏・スクショ保存)

> "Copy trading is considered when the **identical trade on the same instrument is
> executed at the same price, with the same lot size, risk, and other parameters**.
> However, as you explained, since you will be trading using **Expert Advisors that are
> designed with different strategies and assigned separately, this will not be regarded
> as copy trading**. Nevertheless, you must ensure that you do not execute the same trade
> on both your Challenge Phase Account and your Stellar Instant Account in order to
> avoid any violations."

#### 解釈と残リスク

1. **「同一取引」の定義が確定**: 同一銘柄×同一価格×同一ロット×同一リスク等**全て一致**した
   複製取引。**別戦略のEAを別口座に独立配置するのはコピー取引に該当しない** — RecentFit
   (A案/B案)とInstant PDは別戦略なので原則クリア。
2. **残る摩擦点は1つ**: A案S2(GBPJPY月曜08:00UTC L)とInstant PD v7(GBPJPY月曜4/6/8/10時UTC L)は
   **同一銘柄・同方向・同時刻(08:00)にエントリーが重なる**。ロット・リスク%・SLは異なるため
   定義上は「同一取引」に該当しないが、自動監視で複製と誤認される余地は残る。
   B案のMonレッグはv7と同一族・同一時刻構成のため摩擦がより大きい(FNでもB案よりA案)。
3. 対応の選択肢:
   - (a) 同じチャットで具体シナリオを追加確認(下記ドラフト)→「可」なら全スリーブ稼働
   - (b) 確認なしで走るなら**S2を無効化**(InpS2入力で可能・事前登録の型は维持したまま
     1スリーブ落とすだけ。エントリー時刻の改変はしない=後知恵改変の禁止)
4. チャット回答はスクショで記録済み(docs/161 §5と同格の扱い)。

#### FN追加確認ドラフト(同チャットへ)

> Thank you, that's very clear. One concrete scenario to be 100% safe: my Instant
> account EA (Strategy X) may open a GBPJPY BUY on Monday around 08:00 server time,
> and my new Challenge account EA (Strategy Y — a different strategy) may independently
> open a GBPJPY BUY within the same hour. Lot sizes, risk % and stop-loss levels are
> different; only the symbol, direction and approximate timing coincide. Is this
> acceptable, or would you recommend I disable the GBPJPY leg on one of the accounts?

#### 7.6.1【書面記録 2026-07-31 チャット第2信】権限部署への照会指示

追加確認(§7.6ドラフト)への回答(スクショ保存):

> "As previously explained, **this will not be considered Copy Trading**. However, since
> the support team is not authorized to confirm trading strategies, I recommend that you
> contact the **Trading Ethics and Standards Team** for further clarification:
> **tradingethics@fundednext.com**"

- チャット2回目の「非該当」回答+最終権限部署の明示。**tradingethicsからのメール回答が
  取れれば防衛記録として最強**(サポートチャットより上位の一次資料)。
- 規律: **tradingethicsの回答が届くまで購入は保留**(チャット2回の「非該当」は心証であり
  確定ではない)。

#### tradingethics@fundednext.com 宛メール(送付用・英語)

> Subject: Clarification request — my own independent EAs on my Instant and Challenge accounts (same-symbol overlap)
>
> Dear Trading Ethics and Standards Team,
>
> Your support chat team kindly referred me to you for an authoritative confirmation
> regarding a planned account setup (chat on 31 July; the agent stated it would not be
> considered copy trading, but noted your team has the final authority).
>
> My situation:
> - All accounts are under my own name and traded exclusively by my own private Expert
>   Advisors (no commercial EAs, no copy-trading tools, no account linking; each EA runs
>   independently on its own terminal).
> - My Stellar Instant account runs my Strategy X, which may open a GBPJPY BUY on Monday
>   around 08:00 server time.
> - I plan to purchase a Stellar 2-Step Challenge account that would run a different EA
>   of mine (Strategy Y), which may also independently open a GBPJPY BUY within the same
>   hour on some Mondays.
> - Lot sizes, risk percentages and stop-loss levels differ between the two accounts;
>   only the symbol, direction and approximate timing can coincide.
>
> Questions:
> (a) Is this setup acceptable — i.e., NOT treated as "the same trades on multiple
>     accounts" between my Instant and Challenge accounts?
> (b) If it is not fully acceptable, would it be sufficient to disable the GBPJPY leg
>     on one of the accounts, so that no same-symbol, same-direction overlap can occur?
> (c) Could you share the objective criteria you use to determine "same trades",
>     so I can stay clearly compliant?
>
> I would greatly appreciate a written reply by email for my records. Thank you very much.

### 7.7 判定の更新(2026-07-31時点)

| 選択肢 | 状態 |
|---|---|
| **FN Stellar($50k推奨)×A案** | **本命に確定寄り**: コピー取引の定義クリア+Max Risk3%は取引個別+EV最大(§7.4)。S2重複のみ追加確認 or 無効化で対応 |
| Fintokei×A案 | トレードグループ3%(§7.5.1)により0.75%減速 or グループガード追加が必要。第3信の回答待ち |
| FTMO / B案のFN配備 | 見送り(v7との同一族・同一時刻重複が濃い) |
| パール季節RG3(稼働直前) | **§7.5.1 #4の同時保有実損チェックを稼働前に実施**(本トラックとは独立の緊急タスク) |

### 7.8 回答が来るまでの規律

- **どの業者でも、回答前の購入・稼働開始はしない**(docs/170の教訓)。
- FN回答が「独立EAなら同銘柄同方向も可」なら → FN Stellarが第一候補に昇格(§6判定1)。
- FN回答が「同銘柄同方向は不可」なら → Fintokei×A案(銘柄重複ゼロ)が確定解。
- 回答は必ずスクショ保存し、docs/161/173と同様に新docへ一次記録する。
