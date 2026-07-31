@echo off
rem ============================================================
rem  HeatNexus - Anlagen-Probe
rem  Doppelklick genuegt. IP-Adressen und Passwort werden
rem  abgefragt, das Passwort bleibt bei der Eingabe verdeckt.
rem ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo.
  echo Python 3 wurde nicht gefunden.
  echo Bitte von https://www.python.org/downloads/ installieren
  echo und bei der Installation "Add python.exe to PATH" anhaken.
  echo.
  pause
  exit /b 1
)

%PY% tools\heatnexus_probe.py interactive %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" echo Der Lauf wurde mit Fehlercode %RC% beendet.
pause
exit /b %RC%
