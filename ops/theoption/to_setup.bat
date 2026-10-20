@echo off
rem chien theoption probe one-click setup (ASCII only; messages come from to_setup.ps1). No trading. No admin.
if not "%~1"=="run" (
  start "chien theoption setup" cmd /k ""%~f0" run %~2"
  exit /b
)
set "ROOT=C:\chien\ops\theoption"
set "RAW=https://raw.githubusercontent.com/iq87jun-star/chien-monitor/ccr-dbb29a98-7cflzp/ops/theoption"
if not exist "%ROOT%" mkdir "%ROOT%"
echo [1/2] download scripts from GitHub ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; foreach($f in 'to_probe.py','to_summarize.py','to_run.ps1','to_setup.ps1','to_setkey.ps1','to_setkey.bat'){ Invoke-WebRequest ('%RAW%/'+$f+'?t='+(Get-Date).Ticks) -OutFile (Join-Path '%ROOT%' $f) -UseBasicParsing; Write-Host ('  ok '+$f) }"
if errorlevel 1 (
  echo DOWNLOAD FAILED. Check internet access from this VPS.
  goto :end
)
echo [2/2] run to_setup.ps1 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\to_setup.ps1" %~2
:end
echo.
echo Keep this window open and send a photo of it.
