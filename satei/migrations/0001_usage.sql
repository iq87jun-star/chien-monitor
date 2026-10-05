-- 画像読み取り(/api/read)の1日あたりの利用回数。who は日付と IP のハッシュ(IP そのものは残さない)
CREATE TABLE IF NOT EXISTS usage (day TEXT NOT NULL, who TEXT NOT NULL, n INTEGER NOT NULL, PRIMARY KEY (day, who));
