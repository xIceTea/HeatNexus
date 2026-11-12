@echo off
rem ============================================================
rem  HeatNexus - Anlagen-Sonde
rem  Doppelklick genuegt. IP-Adressen und Passwort werden
rem  abgefragt, das Passwort bleibt bei der Eingabe verdeckt.
rem  Fehlt Python, bietet das Skript die Installation ueber
rem  winget an, die Paketverwaltung von Windows.
rem ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."
title HeatNexus - Anlagen-Sonde

for /f %%a in ('echo prompt $E^| cmd') do set "E=%%a"
set "N=%E%[0m"
set "W=%E%[1;38;2;240;244;248m"
set "B=%E%[38;2;58;168;232m"
set "G=%E%[38;2;150;160;175m"
set "F=%E%[38;2;70;85;105m"
set "O1=%E%[38;2;245;166;35m"
set "O2=%E%[38;2;242;130;45m"
set "O3=%E%[38;2;236;90;60m"
set "OK=%E%[38;2;80;200;120m"
set "ACHTUNG=%E%[38;2;245;166;35m"

echo.
echo   %F%╭──────────────────────────────────────────────╮%N%
echo   %F%│%N%                                              %F%│%N%
echo   %F%│%N%   %O1%▌%O2%▌%O3%▌%B%i%N%   %W%HeatNexus%N%  %B%Anlagen-Sonde%N%            %F%│%N%
echo   %F%│%N%          %G%Windhager · Home Assistant · Lokal%N%  %F%│%N%
echo   %F%│%N%                                              %F%│%N%
echo   %F%╰──────────────────────────────────────────────╯%N%
echo.

set "PY="
call :python_suchen
if not defined PY call :python_anbieten
if not defined PY goto ohne_python

echo   %OK%✓%N% Python gefunden
echo.
set "HEATNEXUS_KOPF_GEZEIGT=1"
%PY% tools\heatnexus_probe.py interactive %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo   %OK%✓ Fertig.%N% Die Dateien liegen im Ordner %W%probe%N%.
) else (
  echo   %ACHTUNG%Der Lauf wurde mit Fehlercode %RC% beendet.%N%
)
echo.
pause
exit /b %RC%

:ohne_python
echo   %ACHTUNG%Python 3 wurde nicht gefunden.%N%
echo   Bitte von https://www.python.org/downloads/ installieren
echo   und bei der Installation "Add python.exe to PATH" anhaken.
echo   Danach probe.cmd erneut starten.
echo.
pause
exit /b 1

rem Prüft, ob Python wirklich startet. Der Platzhalter aus dem Microsoft Store
rem liegt zwar im Pfad, startet aber kein Python.
:python_suchen
py -3 --version >nul 2>&1 && (set "PY=py -3" & exit /b 0)
python --version >nul 2>&1 && (set "PY=python" & exit /b 0)
set "LAUNCHER=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
if exist "%LAUNCHER%" "%LAUNCHER%" -3 --version >nul 2>&1 && set "PY="%LAUNCHER%" -3"
exit /b 0

rem Bietet die Installation über winget an; ohne winget bleibt es beim Hinweis.
:python_anbieten
where winget >nul 2>&1 || exit /b 0
echo   %ACHTUNG%Python fehlt.%N% Die Sonde braucht Python 3.
echo   Es lässt sich jetzt über winget installieren, die Paketverwaltung von Windows.
echo.
choice /C JN /N /M "  Python jetzt installieren? [J/N] "
if errorlevel 2 exit /b 0
echo.
winget install --exact --id Python.Python.3.13
echo.
call :python_suchen
exit /b 0
