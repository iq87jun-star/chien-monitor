-- 引き継ぎ情報フォーム(src/sheet.js)。管理画面で作ったリンク(token)から売主が1回だけ記入する。
-- レシートのスクショは image に owner = 'sheet' で入れる(管理画面からだけ見られる)
CREATE TABLE IF NOT EXISTS sheet (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT NOT NULL UNIQUE,
  consign_id INTEGER,      -- 代理出品・買取の管理番号(無くてもよい)
  label TEXT,              -- 管理用のメモ(例: No.44 第五人格)
  game TEXT,
  created_at TEXT NOT NULL,
  submitted_at TEXT,       -- 記入された日時(記入後は変えられない)
  data TEXT                -- 回答(JSON)
);
