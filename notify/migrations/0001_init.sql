-- 登録者(Discord のウェブフック1つ = 1登録者)
CREATE TABLE subscribers (
  id TEXT PRIMARY KEY,               -- ウェブフックのID(URL中の数字)
  webhook_url TEXT NOT NULL,         -- 通知先(トークンを含むので外部には出さない)
  key_hash TEXT NOT NULL UNIQUE,     -- 管理キーの SHA-256(キー自体は保存しない)
  plan TEXT NOT NULL DEFAULT 'free', -- free / pro(有料プランは Stripe 連携時に付与)
  active INTEGER NOT NULL DEFAULT 1, -- ウェブフックが削除されていたら 0
  created_at TEXT NOT NULL
);

-- 値下がりを見張るカード
CREATE TABLE watches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subscriber_id TEXT NOT NULL,
  card_key TEXT NOT NULL,            -- public/prices.js の key
  label TEXT NOT NULL,               -- 登録時の表示名(通知文に使う)
  target_jpy INTEGER NOT NULL,       -- この額以下になったら通知
  armed INTEGER NOT NULL DEFAULT 1,  -- 1 = 次に目標以下になったら通知する。通知後 0、相場が戻ったら 1
  notified_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (subscriber_id, card_key)
);
CREATE INDEX watches_subscriber ON watches (subscriber_id);

-- チェック済みのデータの取得時刻など
CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
