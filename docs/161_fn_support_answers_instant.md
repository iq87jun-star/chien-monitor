# 161.【書面記録】FNサポート回答(2026-07-16メール) — Instant購入前質問への公式回答

> docs/154/160の懸案に対するFundedNext公式メール回答の転記(スクリーンショット7枚・ユーザー保存)。
> docs/99の方針(規約表記でなく書面回答を防衛材料にする)に基づく一次記録。

## 1. 回答の要点

| 質問(docs/154/160の懸案) | FN回答 | 当方への影響 |
|---|---|---|
| EA使用可否 | **MT4/MT5で使用可・EA使用料が別途必要**。cTrader/Match-Traderは自動売買全面不可。無料トライアル/競技口座もEA不可 | ✅ MT5選択で問題なし |
| EA手数料 | 初期残高$5k-25k=**$5** / $50k-200k=**$30** | ⚠ 購入画面はEA+$30表示 — $20kなら本来$5の可能性。決済時に「Help記事では5k-25kは$5」と確認する価値あり(VPS&EA $60はVPS込みなので別枠) |
| **Max Risk 3%の定義** | 「**SL注文の設定、全取引における最大実現損失+未実現損失の合計に基づき、初期残高に対して計算される、1回の取引における最大潜在損失**」 | ✅ ツールチップと一致(SL基準・トレード個別・対初期残高)。v1.43の全建玉災害SL+2.5%キャップで機械適合 |
| Swap-Free長期保有 | 全チャレンジで提供・**料金+10%はFNがオーバーナイト費用を負担するため**。管理手数料・保有期間制限の記載なし | ✅ 月単位保有OK(docs/154の推奨どおりSwap-Free選択) |
| トレーリングMLL仕様 | 初期残高の6%・**リアルタイムで最高残高に追従・増えるのみ・上限は初期残高**(例: $10k開始→限度$600、フロアは$10kを超えない) | ✅ **建値ロック公式確認**=docs/154のlock列・EA v1.43のガード設計と一致。「残高」追従ならequity-HWMのEAガードは保守側=安全 |
| 出金後のフロア再計算 | (今回の回答に明記なし) | 未解決(重大度低)。出金時に再質問 |

## 2. ⚠ 新発見(最重要): 「同一取引を複数の口座で行うことは認められていません」

EA記事の箇条書きに明記:
1. EAは**自分の取引スタイルに合わせたカスタム**である必要(市販EA/コピー対策) — 当方は自作=適合
2. **「同一取引を複数の口座で行うことは認められていません」**

→ 現在の当方状況: **FN200k(P1・季節R4G3)と FN100k #14074882(P1・季節R4G3)が同一戦略で並走中**。
Instant 20kに季節を載せると**同一firm内で3口座同一戦略**になる。倍率・銘柄数は違えど
エントリー時刻・方向は同一であり、「同一取引」と判定されるリスクがある。

### 対応(要ユーザー判断)

- **第一手: FNへ書面確認**(このメールに返信):
  「自分名義の複数のFundedNext口座(チャレンジ+Instant)に、自作EAを使用することは可能か。
  同一戦略を自分の口座間で使うことは『同一取引を複数の口座で』に該当するか。」
- **Plan B(該当すると回答された場合)**: FN 3口座に**別戦略を割当**(手元に検証済み3本):
  FN200k=季節R4G3(継続) / FN100k=PD間引き(EA作成済み) / Instant20k=PE v2 or PD間引き。
  相関0.39/0.42/0.12で分散効果もある(docs/139/147)。FTMOは別業者なので季節のままで無関係。
- 回答が出るまでInstantの稼働開始は保留が安全(購入自体は可)。

## 3. 返信用質問文(英語)

> Thank you for the detailed answers. One clarification: I hold multiple FundedNext accounts
> under my own name (Stellar 2-Step challenge accounts and, soon, a Stellar Instant account).
> All trading is done by my own private EA (my own strategy, not a commercial or copy-trading tool).
> Does the rule "the same trades on multiple accounts are not allowed" apply to my own accounts
> under my own profile? Specifically: (a) is running my own EA strategy on two of my own accounts
> a violation? (b) If yes, is it sufficient that the accounts trade different strategies/instruments?

## 4.【追補 2026-07-16】複数口座質問への回答(アニー・ジェーン氏・メール)

Stellar Instantのコピートレード(=同一取引)規則:
1. **同一人物のStellar Instant同士 → 許可**
2. 異なる個人間 → 厳禁
3. **Stellar InstantとStellar 1-Step/2-Step/LiteチャレンジまたはFundedNext口座の間 → 不許可**

### 確定した結論

- 当方のFN200k/FN100kはStellar 2-Step → **Instantに季節R4G3を載せて同時稼働は③に該当=不可**。
  ユーザーの「Instant=季節」案は取り下げ、**Instantには別戦略**(PD間引き/PE v2)を割り当てる。
- 2-Step同士(FN200k↔FN100k)の同一戦略については本回答は言及なし(①がInstant限定表現)。
  グレーだが、①の「同一人物間は許可」の原則が示されたこと+これまで数ヶ月並走して指摘なしを
  踏まえ、現状維持。次回のやり取りで機会があれば確認する。
- Instant用代替戦略の校正 → docs/162。

## 5.【追補2 2026-07-16】チャレンジ口座間の同一EA → 公式に「可」(Annie・ライブチャット)

- **本人名義のFNチャレンジ口座間のコピートレードは許可**(マスター/スレーブ指定・
  コピー対象の合計配分$300k以内・**VPSベースのコピーツールも自分のFNチャレンジ口座間に限り可**)。
- 禁止: 他人名義間 / **FN口座と外部口座(他プロップ・リテール)を繋ぐコピートレード** /
  クラウド型コピーサービス(Social Trader Tools/Traders Connect/Duplikum) / 代行・Pass Your Challenge。

### 結論の更新(§4を上書き)

1. **FN200k↔FN100k(2-Step同士)の季節EA並走は公式に問題なし**(コピートレードすら可なのだから、
   独立EA2インスタンスは当然に可)。§4の「グレー」は解消。
2. 依然として不可なのは **Instant↔チャレンジ間の同一取引**(§4③)のみ。
3. 「FN×外部業者を繋ぐコピー」禁止はコピーツールによる連結を指す。FTMOとFNで同じ自作EAを
   **独立に**動かすことはコピー連結ではない(各端末で独立判断・リンクなし)と解釈。注記として記録。

### 再配置の再評価(docs/162/163の数字で)

- ユーザー案「Instant=季節/200k=PD間引き/100k=PE2」は規約上成立するが、**旗艦$200kを
  失格5〜7.8%(季節1.5x)→23〜36%(PD-noE5 2.8x)へ悪化させて$20k口座に最良戦略を回す**配置になる。
- **推奨は現状維持+Instantに残り物**: 200k/100k=季節(公式に安全・変更作業ゼロ)、
  Instant=PD間引き1.0x(成功73.8%/中央16ヶ月, docs/162)か、見送ってFTMO 2口座目(docs/162 §3)。

> 規律: 書面回答の一次記録。推測と回答を混ぜない(§1=回答の転記、§2=当方の解釈と対応案)。
