@echo off
rem enter theoption REAL API key (hidden input) then read-only connection check (health/balance). No trading.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0to_setkey_real.ps1"
pause
