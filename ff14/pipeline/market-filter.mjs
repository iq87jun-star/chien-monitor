// X 投稿でネタにしてよい品目の足切り
// 取引が薄い品目は、1ギル出品や一時的な高値の観測1件で変動率が数千%に跳ねる(例: 最安出品1ギルで+4,100%)。
// サイトの表示はそのままにして、X に出す数字だけをこの条件で絞る。

export const MIN_VELOCITY = 3; // 1日あたりの推定取引数
export const MIN_SAMPLES = 3; // 7日窓内の観測回数
export const MIN_LISTING_RATIO = 0.2; // 最安出品 / 平均取引価格 がこれ未満なら投げ売り・誤出品とみなす
export const MAX_GAIN_PCT = 500;
export const MAX_DROP_PCT = -90;

export function isReliable(item) {
  return (
    item != null &&
    item.velocity >= MIN_VELOCITY &&
    item.samples >= MIN_SAMPLES &&
    item.minListing != null &&
    item.minListing >= item.price * MIN_LISTING_RATIO &&
    item.change7d > MAX_DROP_PCT &&
    item.change7d < MAX_GAIN_PCT
  );
}
