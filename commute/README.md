# commute — 通勤の天気

松本市寿中の自宅 ⇄ 塩尻市広丘堅石の信州五十六家(ランニング・自転車)の、通勤時間帯の天気を毎日 Discord に送ります。

- 毎日 17:43(日本時間)に、**今夜の帰り(22:30〜23:15)** と **明日の行き(通常 8:15〜9:00、早番 5:15〜6:00)** を送ります
- 水曜はお休み。火曜の通知に「水曜の1日の天気」(最高・最低と3時間ごとの様子)を付け、水曜の通知は木曜の行きだけ
- 雨・雪・凍結・突風・霧・寒さがあれば、ひとこと注意を付けます
- 予報は [Open-Meteo](https://open-meteo.com/)(登録不要・無料)

## お休みの日のお出かけ(自転車)

行き先・到着時刻・終了時刻を入れると、**行き・現地・帰り** の天気を Discord に送ります。

- GitHub(スマホのアプリでも可)→ Actions → **commute-trip** → Run workflow
  - 行き先: `アルプス公園`、`安曇野市穂高`、`36.26,137.95`(施設名は OpenStreetMap、住所は国土地理院で探す)
  - 日付: `明日`、`11/8` など(空なら今日。予報は 16 日先まで)
  - 到着・終了: `10:00`、`15時` など
- 出発時刻は、自転車 18km/h・道のりは直線の 1.3 倍として逆算(`bike` で変更)
- 通知の 📍 に見つかった場所が出るので、違う場所なら住所で入れ直す

## 設定(config.json)

| 項目 | 内容 |
|---|---|
| `earlyShiftRotation` | 早番の周期。3 人で回すので 21 日ごと、木曜から 7 日間(水曜は休み)。`start` は早番の週の初日(2026-11-19) |
| `earlyShift` | 周期と別の臨時の早番。`{ "from": "2026-12-03", "to": "2026-12-03" }` のように足す |
| `notEarly` | 交代などで早番でなくなった日。`"2026-12-10"` のように足す |
| `daysOff` | 水曜以外の休み(`"2026-12-31"` など) |
| `shift` | 始業・終業の時刻 |
| `bike` | お出かけの所要時間の計算(`kmh` 速さ、`roadFactor` 直線距離に対する道のりの倍率) |
| `commuteMinutes` | 通勤にかかる時間(分)。この長さの時間帯の天気を見る |

## Discord の設定

1. Discord のチャンネルの設定 → 連携サービス → ウェブフック → 新しいウェブフック → URL をコピー
2. GitHub のリポジトリ → Settings → Secrets and variables → Actions → New repository secret
   - 名前 `COMMUTE_DISCORD_WEBHOOK`、値にコピーした URL
3. Actions → commute → Run workflow で試しに送る

## 手元で試す

```sh
cd commute
npm test
node run.js                          # 今日の分を表示(Webhook 未設定なら送らない)
COMMUTE_DATE=2026-11-18 node run.js  # 日付を変えて試す(予報は 3 日先まで)
TRIP_PLACE=アルプス公園 TRIP_DATE=明日 TRIP_ARRIVE=10:00 TRIP_END=15:00 node run.js  # お出かけ
```
