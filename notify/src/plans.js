// プランごとの登録できるカード数。有料プラン(pro)は Stripe の決済完了時に付与する(src/billing.js)
export const LIMITS = { free: 3, pro: 50 };

export const limitOf = (plan) => LIMITS[plan] ?? LIMITS.free;
