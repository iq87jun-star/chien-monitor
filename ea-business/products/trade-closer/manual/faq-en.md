# TradeCloser — FAQ (English)

**Q. Can it open trades?**
A. No. It is closing/management only and never enters.

**Q. CLOSE ALL vs CLOSE SYMBOL?**
A. CLOSE ALL closes every position in scope (all/magic per settings); CLOSE SYMBOL closes **only the current chart symbol**.

**Q. Basket auto-close doesn't fire.**
A. Check that one of `InpTargetProfit*` / `InpStopLoss*` is > 0, that positions exist in scope, and that Algo Trading is ON. With both money and % set, the nearer (stricter) trigger fires.

**Q. Some legs aren't partially closed.**
A. If the computed volume rounds below the broker minimum, that position is skipped. Raise `InpPartialPercent` or close manually.

**Q. What does PANIC do?**
A. Closes all positions in scope and deletes all pendings at once — an emergency stop.

**Q. Partial/no execution.**
A. Execution depends on server conditions; the Experts log reports counts. Re-run to handle the remainder.

**Q. Will it make money?**
A. It assists with closing; it does not predict markets or guarantee profit.
