-- 査定ツールの利用記録(個人を特定できる情報は残さない。src/events.js)
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  kind TEXT NOT NULL,      -- read / estimate / dm
  game TEXT NOT NULL,
  sid TEXT NOT NULL,       -- 画面を開くたびに作るランダムな ID
  ok INTEGER NOT NULL,
  chars TEXT,              -- [{name, cons, mochi}]
  n INTEGER,
  low INTEGER,
  high INTEGER
);
CREATE INDEX IF NOT EXISTS events_at ON events (at);
