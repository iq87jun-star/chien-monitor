# TrailManager — FAQ (English)

**Q. Can it open trades?**
A. No. It only manages stops (break-even and trailing) on existing positions.

**Q. Can it manage positions opened by other tools or manually?**
A. Yes. Any position matching the scope (current symbol / magic) is managed, regardless of how it was opened.

**Q. FIXED vs ATR vs STEP?**
A. FIXED uses a fixed pip distance; ATR uses ATR × multiplier (volatility-adaptive); STEP moves the SL only after it can advance by at least the step (fewer modifications).

**Q. Trailing isn't working.**
A. Check that profit has reached `InpTrailStartPips`, that Algo Trading is ON, the license is valid, and it isn't PAUSED. In ATR mode, verify the period/timeframe.

**Q. Can the SL move against me?**
A. No. The SL only updates in the favourable direction.

**Q. Can I run it alongside other EAs?**
A. If another EA manages the same position's SL, they may conflict. Separate them with scope filters (e.g. magic).

**Q. Will it make money?**
A. It assists with stop management; it does not predict markets or guarantee profit.
