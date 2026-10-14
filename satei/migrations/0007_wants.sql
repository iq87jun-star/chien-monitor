-- 購入希望者(src/stock.js)。欲しいキャラ・予算を控えて、合う在庫・代理出品を探す
CREATE TABLE IF NOT EXISTS want (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  name TEXT NOT NULL,     -- 呼び名
  contact TEXT,           -- X / Discord のユーザー名など
  game TEXT NOT NULL,
  wants TEXT,             -- [{name, cons}](cons は欲しい凸数の下限)
  budget INTEGER,         -- 予算の上限
  split INTEGER,          -- 分割希望 1/0
  status TEXT NOT NULL,   -- 希望中 / 提案済み / 成約 / 見送り
  proposed TEXT,          -- 提案した在庫・代理出品(自由記入。例: 在庫3,4)
  next_at TEXT,           -- 次に連絡する日
  memo TEXT
);
