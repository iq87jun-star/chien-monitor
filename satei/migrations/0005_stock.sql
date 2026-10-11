-- 在庫(メルルが持っているアカウント)と分割払いの管理(src/stock.js)
CREATE TABLE IF NOT EXISTS stock (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  game TEXT NOT NULL,
  chars TEXT,            -- [{name, cons, mochi}]
  assets TEXT,           -- 原石・モラ・星5武器など(自由記入)
  cost INTEGER,          -- 仕入れ値
  source TEXT,           -- 仕入れ元(X / Discord / gameclub など)
  bought_at TEXT,        -- 仕入れ日(YYYY-MM-DD)
  status TEXT NOT NULL,  -- 未出品 / 出品中 / 商談中 / 売却済み
  price INTEGER,         -- 今の出品価格
  floor INTEGER,         -- 下げてよい下限
  price_at TEXT,         -- 価格を最後に決めた日(値下げの目安に使う)
  listings TEXT,         -- [{site, url, checked_on}]
  sold_price INTEGER,
  sold_at TEXT,
  memo TEXT
);
CREATE TABLE IF NOT EXISTS split (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  game TEXT NOT NULL,
  chars TEXT,
  assets TEXT,
  buyer TEXT NOT NULL,   -- 購入者の呼び名
  contact TEXT,          -- 連絡先(Discord のユーザー名・X の @ など)
  middle TEXT,           -- 仲介・間に入る人
  total INTEGER NOT NULL,
  due_day INTEGER,       -- 毎月の支払日
  status TEXT NOT NULL,  -- 支払い中 / 完済 / 引き渡し済み / 中止
  handover TEXT,         -- 引き渡しのチェック {mail, link, pass}
  memo TEXT
);
-- 分割の1回ごとの支払い(予定日・金額・入金日)
CREATE TABLE IF NOT EXISTS split_pay (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  split_id INTEGER NOT NULL,
  due_on TEXT NOT NULL,
  amount INTEGER NOT NULL,
  paid_on TEXT,
  memo TEXT
);
CREATE INDEX IF NOT EXISTS split_pay_split ON split_pay (split_id, due_on);
