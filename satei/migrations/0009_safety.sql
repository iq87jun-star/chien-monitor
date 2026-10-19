-- 詐欺対策(src/stock.js・src/consign.js)
--   handover  … 引き渡し前のチェック {proof, pay, link, mail, pass, receipt}(全部そろうと引き渡し完了にできる)
--   handed_on … 引き渡した日。watch … 引き渡し後の見守り(ログインできているかの確認)をした回数
ALTER TABLE stock ADD COLUMN handover TEXT;
ALTER TABLE stock ADD COLUMN handed_on TEXT;
ALTER TABLE stock ADD COLUMN watch INTEGER NOT NULL DEFAULT 0;
ALTER TABLE split ADD COLUMN handed_on TEXT;
ALTER TABLE split ADD COLUMN watch INTEGER NOT NULL DEFAULT 0;
ALTER TABLE consign ADD COLUMN handover TEXT;
ALTER TABLE consign ADD COLUMN handed_on TEXT;
ALTER TABLE consign ADD COLUMN watch INTEGER NOT NULL DEFAULT 0;
-- 要注意リスト(過去にトラブルがあった X の @ID)。査定・購入希望・分割で同じ人が来たら知らせる
CREATE TABLE IF NOT EXISTS caution (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  handle TEXT NOT NULL UNIQUE, -- @ なし・小文字
  reason TEXT
);
