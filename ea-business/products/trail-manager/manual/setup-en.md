# TrailManager — Setup Guide (English)

## 1. Install
1. Put `TrailManager.ex5` into `MQL5/Experts/` (or open `TrailManager.mq5` in MetaEditor and **compile with F7**).
   - It references `LicenseClient.mqh`; keep the bundled copy in the same folder when building from source.
2. Restart MT5 or refresh the Navigator.
3. Drag it onto the chart of the symbol you want managed.

## 2. Allow algo trading
- Toggle **Algo Trading** ON in the toolbar.
- Tick **Allow Algo Trading** in the attach dialog.

## 3. (Self-hosted build only) License setup
1. Tools > Options > Expert Advisors > tick **Allow WebRequest for listed URL**.
2. Add the license URL (e.g. `https://api.riskguard.app`).
3. Set `InpLicenseKey` and `InpLicenseServer`.

> Not required for the MQL5 Market build.

## 4. Verify
- The panel shows `TrailManager | <symbol> | mode:FIXED | managing:N | ON`.
- As an existing position gains, the SL moves to break-even then trails.
- PAUSE/RESUME stops/starts management.
- Test FIXED/ATR/STEP modes on a **demo account** first.
