-- 在庫・代理出品をお客様向けの一覧(game-souba.com/zaiko/)に出すか(src/catalog.js)
--   pub … 1 で一覧に出す。pub_images … 在庫のスクショも出す(UID を黒塗りしてから)。pub_note … お客様向けの説明
ALTER TABLE stock ADD COLUMN pub INTEGER NOT NULL DEFAULT 0;
ALTER TABLE stock ADD COLUMN pub_images INTEGER NOT NULL DEFAULT 0;
ALTER TABLE stock ADD COLUMN pub_note TEXT;
ALTER TABLE consign ADD COLUMN pub INTEGER NOT NULL DEFAULT 0;
ALTER TABLE consign ADD COLUMN pub_note TEXT;
