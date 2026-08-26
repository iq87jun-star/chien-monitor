# プロフィール画像 生成プロンプト集

他のAI(Midjourney / DALL·E / Stable Diffusion / Imagen / Firefly など)で
別案を作るためのプロンプトです。日本語版と英語版を用意しています。
**英語版のほうが多くのツールで精度が出ます。**

---

## 共通の前提(どのプロンプトでも守りたい条件)

- **正方形**、アバター用途。小さく表示されても形が分かること
- **FX商材にありがちな配色を避ける**: 赤・金・ネオングリーン、上昇矢印、
  ドル記号、ローソク足、強気の雄牛などは使わない
- 落ち着いた**藍色(ネイビー〜ティール)**を基調に
- 文字を入れない(AIの文字生成は破綻しやすいため)
- フラットまたは微細なグラデーション。過度な3D・光沢は避ける

---

## 案A:碁石(現行案・シリーズ名「定石」由来)

### 英語

```
A minimalist square app icon: a single smooth cream-white go stone
resting on a faint go board grid, viewed from directly above.
Deep indigo navy background with a subtle vertical gradient
(#1B4E6E to #102E42). The grid lines are thin, pale blue, and low
contrast — barely visible. The stone sits slightly off-center at an
intersection in the upper-left area, with a soft realistic drop shadow
beneath it. Calm, restrained, professional. Flat vector style with
gentle shading. No text, no letters, no numbers. Square 1:1 composition.
```

### 日本語

```
ミニマルな正方形アプリアイコン。真上から見た碁盤の格子の上に、
なめらかなクリーム色の碁石が一つ置かれている。背景は深い藍色の
ネイビーで、縦方向にわずかなグラデーション。格子線は細く淡い青で、
かろうじて見える程度の低コントラスト。碁石は中央からやや左上寄りの
交点に置かれ、下に柔らかい影。落ち着いた、抑制のきいた、professional
な雰囲気。フラットなベクター調で緩やかな陰影。文字・数字は一切なし。
正方形1:1。
```

---

## 案B:曜日の減衰(戦略そのものを図案化)

月曜が最も高く、金曜に向けて下がる棒グラフ。本EAが取っている
週次アノマリーの形そのもの。意味を持つ図案です。

### 英語

```
A minimalist square app icon: five vertical bars in a row forming a
descending pattern — the first bar is tall, each following bar is
shorter, and the last two drop below a thin horizontal baseline.
The three positive bars are warm cream white; the two negative bars
are a muted steel blue at lower opacity. Deep indigo navy background
with a subtle gradient (#1B4E6E to #102E42). The baseline is a thin
pale blue line. Clean, geometric, flat vector style with softly
rounded bar corners. Restrained and data-driven, not flashy.
No text, no letters, no numbers, no axes labels. Square 1:1.
```

### 日本語

```
ミニマルな正方形アプリアイコン。5本の縦棒が横に並び、右へ向かって
段階的に低くなる。最初の棒が最も高く、最後の2本は細い水平の基準線を
下回って下向きに伸びる。プラス側の3本は温かみのあるクリーム色、
マイナス側の2本はくすんだスチールブルーで透明度をやや下げる。
背景は深い藍色のネイビーでわずかなグラデーション。基準線は細い淡青。
清潔で幾何学的、フラットなベクター調、棒の角は軽く丸める。
抑制のきいたデータ的な印象で、派手さはなし。文字・数字・軸ラベルは
一切なし。正方形1:1。
```

---

## 案C:碁石のみ(最小構成・小サイズで最も強い)

### 英語

```
A minimalist square app icon: one large cream-white go stone centered
on a deep indigo navy background, with a single thin horizontal line
and a single thin vertical line crossing behind it at very low
contrast, suggesting a board intersection. Subtle background gradient
(#1B4E6E to #0E293B). The stone has a soft radial highlight in the
upper left and a diffuse drop shadow below. Serene, confident,
understated. Flat vector with gentle shading. No text, no letters,
no numbers. Square 1:1 composition.
```

### 日本語

```
ミニマルな正方形アプリアイコン。深い藍色のネイビー背景の中央に、
大きなクリーム色の碁石を一つ。背後に細い水平線と垂直線が一本ずつ
交差し、盤の交点を示唆する(コントラストは非常に低く)。背景は
わずかなグラデーション。碁石は左上に柔らかいハイライト、下に
ぼやけた影。静謐で、自信のある、控えめな印象。フラットなベクター調で
緩やかな陰影。文字・数字は一切なし。正方形1:1。
```

---

## 使用するAIごとの調整

**Midjourney**
末尾に `--ar 1:1 --style raw --v 6` を付けると意図に近づきます。
`--no text, letters, numbers, watermark` も併記推奨。

**DALL·E / ChatGPT**
上記をそのまま貼れば動きます。「文字を入れないで」と念押しすると確実です。

**Stable Diffusion 系**
ネガティブプロンプトに次を入れてください:
`text, letters, numbers, watermark, signature, candlestick chart,
dollar sign, arrow, bull, gold, red, neon, 3d render, glossy,
photorealistic, cluttered`

**Adobe Firefly**
コンテンツタイプを「アート」、スタイルに「ベクター」「ミニマリスト」を指定。

---

## 生成後のチェックリスト

- [ ] 96px に縮小しても形が判別できるか(アバターは小さく表示される)
- [ ] 文字・記号が紛れ込んでいないか
- [ ] 正方形になっているか(トリミングが必要なら中央基準で)
- [ ] 赤・金・矢印など煽り系の要素が入っていないか
- [ ] 他社ロゴや既存商標に似ていないか

---

## 現行ファイル

| ファイル | 案 | サイズ |
|---|---|---|
| `chien_mark_{1024,512,256,96}.png` | A(碁石+格子) | 4種 |
| `markB_{1024,512,256,96}.png` | B(曜日の減衰) | 4種 |
| `markC_{1024,512,256,96}.png` | C(碁石のみ) | 4種 |
| `mark.svg` / `markB.svg` / `markC.svg` | 各案のベクター元データ | — |

SVG は色や構図の変更に対応できます。ご希望があればお申し付けください。
