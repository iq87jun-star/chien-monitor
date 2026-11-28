-- 仲介の預かり金(メルルが買い手のお金を預かり、完済・引き渡し・見守りのあと売り手に支払う)
--   split.escrow    … 1 = 仲介でお金を預かっている分割
--   split.fee       … 仲介手数料(売り手に払う額から引く)
--   split.payout_on … 売り手に支払った日(返金・精算した日も)
ALTER TABLE split ADD COLUMN escrow INTEGER NOT NULL DEFAULT 0;
ALTER TABLE split ADD COLUMN fee INTEGER;
ALTER TABLE split ADD COLUMN payout_on TEXT;
-- これまでメモの先頭に【仲介】と書いていた分割は、預かりとして扱う
UPDATE split SET escrow = 1 WHERE memo LIKE '【仲介】%';
