-- 有料プラン(Stripe)の契約情報
ALTER TABLE subscribers ADD COLUMN stripe_customer_id TEXT;
ALTER TABLE subscribers ADD COLUMN stripe_subscription_id TEXT;
CREATE INDEX subscribers_stripe_subscription ON subscribers (stripe_subscription_id);
