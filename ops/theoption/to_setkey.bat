@echo off
rem enter theoption demo API key (hidden input) then 60s connection check. No trading.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0to_setkey.ps1"
pause
