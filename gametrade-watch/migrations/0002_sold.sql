-- 売れたアカウント(査定ツールの値付けの学習用)。sold-relay.mjs が POST /sold・/sold/details で送る
CREATE TABLE IF NOT EXISTS sold (
  site TEXT NOT NULL,
  id TEXT NOT NULL,
  game TEXT NOT NULL,
  name TEXT NOT NULL,
  price INTEGER NOT NULL,
  url TEXT,
  image TEXT,
  info TEXT,          -- 一覧の「冒険者ランク：60ランク」などの JSON 配列
  description TEXT,   -- 出品ページの説明文の全文(/sold/details で後から入る)
  images TEXT,        -- 出品ページの画像 URL の JSON 配列
  first_seen TEXT NOT NULL,
  detail_at TEXT,
  PRIMARY KEY (site, id)
);
CREATE INDEX IF NOT EXISTS sold_game ON sold (game, first_seen);
