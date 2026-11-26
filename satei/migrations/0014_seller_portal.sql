-- 代理出品の売り手ページ(game-souba.com/dairi/?t=…)とチャット(src/seller.js)
--   consign.portal … 売り手ページのリンクに入れるランダムな文字列(管理画面で作る)
--   consign.asks   … 購入希望のお問い合わせの数(管理画面で入れる。売り手ページに出す)
--   consign_msg    … 売り手とのメッセージ。from_me = 1 はメルル。seen = 1 はメルルが読んだ(売り手からのもの)
ALTER TABLE consign ADD COLUMN portal TEXT;
ALTER TABLE consign ADD COLUMN asks INTEGER NOT NULL DEFAULT 0;
CREATE UNIQUE INDEX IF NOT EXISTS consign_portal ON consign (portal);
CREATE TABLE IF NOT EXISTS consign_msg (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  consign_id INTEGER NOT NULL,
  from_me INTEGER NOT NULL,
  body TEXT NOT NULL,
  at TEXT NOT NULL,
  seen INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS consign_msg_consign ON consign_msg (consign_id, id);
