-- 代理出品の管理(src/consign.js)。管理番号 = consign.id
CREATE TABLE IF NOT EXISTS consign (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  handle TEXT,           -- X のユーザー名(@ なし)
  game TEXT NOT NULL,
  chars TEXT,            -- [{name, cons, mochi}](査定ツールから)
  low INTEGER,           -- 査定額の幅
  high INTEGER,
  wish INTEGER,          -- 希望額
  status TEXT NOT NULL,  -- 新規 / 検討中 / 代理出品OK / 出品中 / 成約 / 見送り
  next_at TEXT,          -- 次に連絡する日(YYYY-MM-DD)
  post_url TEXT,         -- 紹介した投稿の URL
  memo TEXT,
  sid TEXT,
  source TEXT            -- tool(査定ページから)/ manual(集計画面で追加)
);
CREATE TABLE IF NOT EXISTS templates (key TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, sort INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS dm_log (id INTEGER PRIMARY KEY AUTOINCREMENT, consign_id INTEGER NOT NULL, template TEXT, at TEXT NOT NULL);
