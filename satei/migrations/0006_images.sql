-- 在庫・分割に付けるスクショ(管理画面からだけ見られる)。画面側で縮小した JPEG を base64 で入れる
CREATE TABLE IF NOT EXISTS image (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner TEXT NOT NULL,      -- stock / split
  owner_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  mime TEXT NOT NULL,
  w INTEGER, h INTEGER,
  data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS image_owner ON image (owner, owner_id, id);
