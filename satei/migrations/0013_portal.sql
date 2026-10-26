-- 分割払いのお客様ページ(game-souba.com/shiharai/?t=…)とチャット(src/portal.js)
--   split.portal … お客様ページのリンクに入れるランダムな文字列(管理画面で作る)
--   split_msg    … お客様とのメッセージ。from_me = 1 はメルル。seen = 1 はメルルが読んだ(お客様からのもの)
ALTER TABLE split ADD COLUMN portal TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS split_portal ON split (portal);
CREATE TABLE IF NOT EXISTS split_msg (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  split_id INTEGER NOT NULL,
  from_me INTEGER NOT NULL,
  body TEXT NOT NULL,
  at TEXT NOT NULL,
  seen INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS split_msg_split ON split_msg (split_id, id);
