-- フォロー候補(src/follow.js)。毎朝 Chrome の Claude が集めた表を取り込み、フォロー → 14日後にフォローバックを確認する
CREATE TABLE IF NOT EXISTS follow (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  handle TEXT NOT NULL UNIQUE,  -- @ なし
  following INTEGER,
  followers INTEGER,
  joined TEXT,                  -- 作られた年月(表の文字のまま)
  note TEXT,                    -- 投稿の内容・自己紹介の一言
  grade TEXT NOT NULL,          -- ◎ ○ △ ×
  kind TEXT,                    -- 売りたい / フォロバ
  reason TEXT,                  -- 判定の理由
  status TEXT NOT NULL,         -- 候補 / フォロー済み / 返ってきた / 返ってこない / 外した / 除外
  found_on TEXT NOT NULL,
  followed_on TEXT,
  checked_on TEXT
);
CREATE INDEX IF NOT EXISTS follow_status ON follow (status, found_on);
