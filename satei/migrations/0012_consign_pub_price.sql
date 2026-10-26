-- 代理出品を在庫一覧に出す時の価格(希望額=売主の下限とは別に決める)。空なら「価格はお問い合わせください」
ALTER TABLE consign ADD COLUMN pub_price INTEGER;
