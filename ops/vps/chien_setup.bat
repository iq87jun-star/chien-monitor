@echo off
rem chien ops agent one-click setup v5 (ASCII only; messages come from setup.ps1)
rem Double-click only. No admin. Window stays open (cmd /k). Log: C:\chien\ops\setup.log
if not "%~1"=="run" (
  start "chien setup" cmd /k ""%~f0" run"
  exit /b
)
set "ROOT=C:\chien\ops"
set "RAW=https://raw.githubusercontent.com/iq87jun-star/chien-monitor/claude/prop-trading-new-methods-a8y3l1/ops/vps"
if not exist "%ROOT%" mkdir "%ROOT%"
echo %date% %time% bat started > "%ROOT%\bat_started.txt"
echo [1/3] download scripts from GitHub ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; foreach($f in 'chien_ops_agent.py','terminals.example.json','setup.ps1','install_task.ps1'){ Invoke-WebRequest ('%RAW%/'+$f+'?t='+(Get-Date).Ticks) -OutFile (Join-Path '%ROOT%' $f) -UseBasicParsing; Write-Host ('  ok '+$f) }"
if errorlevel 1 (
  echo DOWNLOAD FAILED. Check internet access from this VPS.
  goto :end
)
echo [2/3] run setup.ps1 (Python install, terminal discovery, first run, hourly task). log: %ROOT%\setup.log
powershell -NoProfile -ExecutionPolicy Bypass -Command "& '%ROOT%\setup.ps1' 2>&1 | Tee-Object -FilePath '%ROOT%\setup.log'"
echo [3/3] done. Check Google Drive chien_ops\ACCOUNT\ for CSV files, then tell the chat.
:end
echo.
echo Keep this window open and send a photo of it.
