@echo off
rem ============================================================
rem  HeatNexus - Anlagen-Sonde
rem  Doppelklick genuegt. IP-Adressen und Passwort werden
rem  abgefragt, das Passwort bleibt bei der Eingabe verdeckt.
rem  Fehlt Python, bietet das Skript die Installation ueber
rem  winget an, die Paketverwaltung von Windows.
rem  Ein Ordner, der auf probe.cmd gezogen wird, wird geschwaerzt.
rem  Schalter: --en / --de (Sprache), --experte (alle Aktionen).
rem ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."
title HeatNexus

for /f %%a in ('echo prompt $E^| cmd') do set "E=%%a"
set "N=%E%[0m"
set "W=%E%[1;38;2;240;244;248m"
set "B=%E%[38;2;58;168;232m"
set "G=%E%[38;2;150;160;175m"
set "OK=%E%[38;2;80;200;120m"
set "ACHTUNG=%E%[38;2;245;166;35m"

rem Sprache: Systemsprache, Schalter --en oder --de gehen vor.
set "SPRACHE=en"
set "ORT="
for /f "tokens=3" %%l in ('reg query "HKCU\Control Panel\International" /v LocaleName 2^>nul ^| find "LocaleName"') do set "ORT=%%l"
if /i "%ORT:~0,2%"=="de" set "SPRACHE=de"
echo "%*" | find /i "--en" >nul && set "SPRACHE=en"
echo "%*" | find /i "--de" >nul && set "SPRACHE=de"
set "HEATNEXUS_SPRACHE=%SPRACHE%"
call :texte_%SPRACHE%

echo.
echo   %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;249;88;58m▄%E%[0;38;2;249;88;58m▄%E%[0;38;2;249;88;58m▄%E%[0;38;2;249;88;58m▄%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m   
echo   %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;248;126;58m▄%E%[0;38;2;248;120;58m▄%E%[38;2;248;115;58;48;2;248;118;58m▀%E%[38;2;249;111;58;48;2;249;113;58m▀%E%[38;2;249;96;57;48;2;249;90;57m▀%E%[0;38;2;249;88;58m▄%E%[0;38;2;249;88;58m▄%E%[38;2;249;87;57;48;2;249;88;58m▀%E%[38;2;248;91;62;48;2;247;90;62m▀%E%[0;38;2;246;93;65m█%E%[0;38;2;244;95;69m▄%E%[0;38;2;243;98;73m▄%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m   
echo   %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;248;145;59m▄%E%[38;2;248;139;59;48;2;248;142;59m▀%E%[0;38;2;248;133;58m▀%E%[0;38;2;248;130;58m▀%E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;249;88;58m█%E%[38;2;249;88;57;48;2;249;88;58m▀%E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;243;98;73m▀%E%[38;2;242;101;77;48;2;240;102;79m▀%E%[0;38;2;240;103;81m▄%E%[0;38;2;239;106;85m▄%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m   
echo   %E%[0m %E%[0m %E%[0m %E%[0m %E%[38;2;248;151;59;48;2;248;154;59m▀%E%[0;38;2;248;149;59m▀%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;238;242;246m▄%E%[38;2;173;84;71;48;2;238;242;246m▀%E%[38;2;245;141;122;48;2;238;242;246m▀%E%[0;38;2;238;242;246m▄%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;239;106;85m▀%E%[0;38;2;201;120;115m█%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m   %E%[0;38;2;245;166;35m▄%E%[0m %E%[0m %E%[0m %E%[0;38;2;245;166;35m▄%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;236;90;60m▄%E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;58;168;232m▄%E%[0m %E%[0m %E%[0m %E%[0;38;2;58;168;232m▄%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m
echo   %E%[0m %E%[0m %E%[0;38;2;248;164;59m▄%E%[38;2;248;157;59;48;2;248;161;59m▀%E%[0;38;2;248;155;59m▀%E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m▀%E%[0m %E%[0m %E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;182;128;132m▀%E%[38;2;121;149;179;48;2;116;153;186m▀%E%[0m %E%[0m %E%[0m %E%[0m   %E%[0;38;2;245;166;35m█%E%[0m %E%[0m %E%[0m %E%[0;38;2;245;166;35m█%E%[0m %E%[0m %E%[0;38;2;242;141;43m▄%E%[0;38;2;242;141;43m▄%E%[0;38;2;242;141;43m▄%E%[0m %E%[0m %E%[0m %E%[0;38;2;239;115;52m▄%E%[0;38;2;239;115;52m▄%E%[0;38;2;239;115;52m▄%E%[0m %E%[0m %E%[0;38;2;236;90;60m▄%E%[0;38;2;236;90;60m█%E%[0;38;2;236;90;60m▄%E%[0;38;2;236;90;60m▄%E%[0m %E%[0m %E%[0;38;2;58;168;232m█%E%[0;38;2;58;168;232m█%E%[0m %E%[0m %E%[0;38;2;58;168;232m█%E%[0m %E%[0m %E%[0;38;2;76;177;235m▄%E%[0;38;2;76;177;235m▄%E%[0;38;2;76;177;235m▄%E%[0m %E%[0m %E%[0;38;2;94;186;238m▄%E%[0m %E%[0m %E%[0m %E%[0;38;2;94;186;238m▄%E%[0m %E%[0;38;2;112;196;242m▄%E%[0m %E%[0m %E%[0m %E%[0;38;2;112;196;242m▄%E%[0m %E%[0m %E%[0;38;2;130;205;245m▄%E%[0;38;2;130;205;245m▄%E%[0;38;2;130;205;245m▄%E%[0;38;2;130;205;245m▄%E%[0m %E%[0m
echo   %E%[0m %E%[0m %E%[0;38;2;248;166;59m█%E%[0;38;2;248;162;59m▀%E%[0m %E%[0m %E%[0m %E%[0;38;2;238;242;246m▄%E%[38;2;238;242;246;48;2;236;240;244m▀%E%[0;38;2;231;235;240m▀%E%[0;38;2;238;242;246m▀%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m█%E%[38;2;231;235;240;48;2;238;242;246m▀%E%[0;38;2;238;242;246m▄%E%[0m %E%[0m %E%[0m %E%[0;38;2;116;153;186m▀%E%[38;2;90;163;207;48;2;77;168;218m▀%E%[0m %E%[0m %E%[0m   %E%[0;38;2;245;166;35m█%E%[0;38;2;245;166;35m▀%E%[0;38;2;245;166;35m▀%E%[0;38;2;245;166;35m▀%E%[0;38;2;245;166;35m█%E%[0m %E%[0;38;2;242;141;43m█%E%[0;38;2;242;141;43m▄%E%[0;38;2;242;141;43m▄%E%[0;38;2;242;141;43m▄%E%[0;38;2;242;141;43m█%E%[0m %E%[0m %E%[0;38;2;239;115;52m▄%E%[0;38;2;239;115;52m▄%E%[0;38;2;239;115;52m▄%E%[0;38;2;239;115;52m█%E%[0m %E%[0m %E%[0;38;2;236;90;60m█%E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;58;168;232m█%E%[0m %E%[0;38;2;58;168;232m▀%E%[0;38;2;58;168;232m▄%E%[0;38;2;58;168;232m█%E%[0m %E%[0;38;2;76;177;235m█%E%[0;38;2;76;177;235m▄%E%[0;38;2;76;177;235m▄%E%[0;38;2;76;177;235m▄%E%[0;38;2;76;177;235m█%E%[0m %E%[0m %E%[0;38;2;94;186;238m▀%E%[0;38;2;94;186;238m▄%E%[0;38;2;94;186;238m▀%E%[0m %E%[0m %E%[0;38;2;112;196;242m█%E%[0m %E%[0m %E%[0m %E%[0;38;2;112;196;242m█%E%[0m %E%[0;38;2;130;205;245m▀%E%[0;38;2;130;205;245m▄%E%[0;38;2;130;205;245m▄%E%[0;38;2;130;205;245m▄%E%[0m %E%[0m %E%[0m
echo   %E%[0m %E%[0;38;2;247;168;59m▄%E%[38;2;248;166;59;48;2;247;168;59m▀%E%[0;38;2;247;168;59m▄%E%[0m %E%[0m %E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m█%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;58;168;232m▄%E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m█%E%[0m %E%[0m %E%[0;38;2;74;169;220m▄%E%[0;38;2;74;169;220m█%E%[0;38;2;74;169;220m▄%E%[0m %E%[0m   %E%[0;38;2;245;166;35m█%E%[0m %E%[0m %E%[0m %E%[0;38;2;245;166;35m█%E%[0m %E%[0;38;2;242;141;43m▀%E%[0;38;2;242;141;43m▄%E%[0;38;2;242;141;43m▄%E%[0;38;2;242;141;43m▄%E%[0;38;2;242;141;43m▄%E%[0m %E%[0;38;2;239;115;52m▀%E%[0;38;2;239;115;52m▄%E%[0;38;2;239;115;52m▄%E%[0;38;2;239;115;52m▄%E%[0;38;2;239;115;52m█%E%[0m %E%[0m %E%[0;38;2;236;90;60m▀%E%[0;38;2;236;90;60m▄%E%[0;38;2;236;90;60m▄%E%[0;38;2;236;90;60m▀%E%[0m %E%[0;38;2;58;168;232m█%E%[0m %E%[0m %E%[0;38;2;58;168;232m▀%E%[0;38;2;58;168;232m█%E%[0m %E%[0;38;2;76;177;235m▀%E%[0;38;2;76;177;235m▄%E%[0;38;2;76;177;235m▄%E%[0;38;2;76;177;235m▄%E%[0;38;2;76;177;235m▄%E%[0m %E%[0;38;2;94;186;238m▄%E%[0;38;2;94;186;238m▀%E%[0m %E%[0;38;2;94;186;238m▀%E%[0;38;2;94;186;238m▄%E%[0m %E%[0;38;2;112;196;242m▀%E%[0;38;2;112;196;242m▄%E%[0;38;2;112;196;242m▄%E%[0;38;2;112;196;242m▀%E%[0;38;2;112;196;242m█%E%[0m %E%[0;38;2;130;205;245m▄%E%[0;38;2;130;205;245m▄%E%[0;38;2;130;205;245m▄%E%[0;38;2;130;205;245m▄%E%[0;38;2;130;205;245m▀%E%[0m %E%[0m
echo   %E%[0;38;2;247;168;59m▀%E%[0;38;2;247;168;59m█%E%[0;38;2;247;168;59m▄%E%[38;2;247;168;58;48;2;247;168;59m▀%E%[0;38;2;247;168;59m▀%E%[0;38;2;247;168;59m▀%E%[38;2;247;168;59;48;2;238;242;246m▀%E%[0;38;2;238;242;246m█%E%[0m %E%[38;2;247;160;40;48;2;245;144;42m▀%E%[38;2;247;160;40;48;2;245;144;42m▀%E%[0m %E%[38;2;247;160;40;48;2;245;144;42m▀%E%[38;2;247;160;40;48;2;245;144;42m▀%E%[0m %E%[38;2;247;160;40;48;2;245;144;42m▀%E%[38;2;247;160;40;48;2;245;144;42m▀%E%[0m %E%[0;38;2;58;168;232m▄%E%[0m %E%[38;2;235;240;244;48;2;238;242;246m▀%E%[38;2;237;242;246;48;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0;38;2;179;215;237m▀%E%[0;38;2;74;169;220m█%E%[0;38;2;74;169;220m▄%E%[0;38;2;74;169;220m█%E%[0;38;2;74;169;220m▀%E%[0m   
echo   %E%[0m %E%[0m %E%[38;2;247;168;58;48;2;247;168;59m▀%E%[0m %E%[0m %E%[0m %E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m█%E%[0m %E%[38;2;243;127;45;48;2;242;111;47m▀%E%[38;2;243;127;45;48;2;242;111;47m▀%E%[0m %E%[38;2;243;127;45;48;2;242;111;47m▀%E%[38;2;243;127;45;48;2;242;111;47m▀%E%[0m %E%[38;2;243;127;45;48;2;242;111;47m▀%E%[38;2;243;127;45;48;2;242;111;47m▀%E%[0m %E%[0;38;2;58;168;232m█%E%[0m %E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m█%E%[0m %E%[0m %E%[0m %E%[0;38;2;47;168;221m█%E%[0m %E%[0m %E%[0m   %B%%T_UNTER%%N%
echo   %E%[0m %E%[0m %E%[38;2;238;169;69;48;2;222;169;83m▀%E%[0;38;2;212;170;93m█%E%[0m %E%[0m %E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m█%E%[0m %E%[38;2;240;94;50;48;2;238;78;52m▀%E%[38;2;240;94;50;48;2;238;78;52m▀%E%[0m %E%[38;2;240;94;50;48;2;238;78;52m▀%E%[38;2;240;94;50;48;2;238;78;52m▀%E%[0m %E%[38;2;240;94;50;48;2;238;78;52m▀%E%[38;2;240;94;50;48;2;238;78;52m▀%E%[0m %E%[0;38;2;58;168;232m█%E%[0m %E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m█%E%[0m %E%[0m %E%[0;38;2;48;169;222m█%E%[0;38;2;47;168;221m▀%E%[0m %E%[0m %E%[0m   %G%%T_ZEILE%%N%
echo   %E%[0m %E%[0m %E%[0m %E%[0;38;2;207;171;98m▀%E%[0;38;2;176;172;128m█%E%[0m %E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m▄%E%[0;38;2;238;242;246m█%E%[0;38;2;238;242;246m█%E%[0m %E%[0;38;2;48;169;223m█%E%[0;38;2;48;169;222m▀%E%[0m %E%[0m %E%[0m %E%[0m   
echo   %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;161;173;143m▀%E%[0;38;2;110;177;193m█%E%[0;38;2;74;179;228m▄%E%[0m %E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0;38;2;47;168;220m█%E%[0;38;2;47;168;220m█%E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0;38;2;238;242;246m▀%E%[0m %E%[0;38;2;50;171;226m▄%E%[38;2;49;170;224;48;2;50;171;225m▀%E%[0;38;2;49;170;224m▀%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m   
echo   %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;74;179;228m▀%E%[0;38;2;59;180;242m▀%E%[0;38;2;58;179;241m█%E%[0;38;2;58;179;240m▄%E%[0;38;2;57;178;239m▄%E%[0;38;2;56;177;237m▄%E%[0;38;2;56;177;237m▄%E%[0;38;2;47;168;220m█%E%[38;2;46;168;220;48;2;47;168;220m▀%E%[0;38;2;53;174;232m▄%E%[0;38;2;54;175;232m▄%E%[0;38;2;52;173;230m▄%E%[0;38;2;52;173;230m▄%E%[0;38;2;51;172;228m█%E%[0;38;2;50;171;226m▀%E%[0;38;2;50;171;226m▀%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m   
echo   %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0;38;2;57;178;239m▀%E%[0;38;2;57;178;238m▀%E%[0;38;2;56;177;237m▀%E%[0;38;2;47;168;220m▄%E%[0;38;2;47;168;220m▄%E%[0;38;2;52;173;232m▀%E%[0;38;2;53;174;232m▀%E%[0;38;2;53;174;231m▀%E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m %E%[0m   
echo.

set "PY="
call :python_suchen
if not defined PY call :python_anbieten
if not defined PY goto ohne_python

echo   %OK%✓%N% %T_PY_OK%
set "HEATNEXUS_KOPF_GEZEIGT=1"

rem Ein Ordner, der auf probe.cmd gezogen wurde, wird geschwärzt.
if not "%~1"=="" if exist "%~1\" goto ordner_gezogen

echo.
echo   %W%1%N%  %T_M1%
echo   %W%2%N%  %T_M2%
echo.
set "WAHL="
set /p "WAHL=%T_WAHL% "
if "%WAHL%"=="2" goto ordner_fragen
%PY% tools\heatnexus_probe.py interactive %*
set "RC=%ERRORLEVEL%"
goto ende

:ordner_fragen
echo.
echo   %T_ZIEHEN1%
echo   %T_ZIEHEN2%
set "ORDNER="
set /p "ORDNER=%T_ORDNER% "
if not defined ORDNER set "ORDNER=probe"
set "ORDNER=%ORDNER:"=%"
goto schwaerzen

:ordner_gezogen
set "ORDNER=%~1"

:schwaerzen
echo.
%PY% tools\heatnexus_probe.py schwaerzen "%ORDNER%"
set "RC=%ERRORLEVEL%"

:ende
echo.
if not "%RC%"=="0" if not "%RC%"=="130" echo   %ACHTUNG%%T_FEHLERCODE% %RC%%N%
pause
exit /b %RC%

:ohne_python
echo   %ACHTUNG%%T_KEIN_PY1%%N%
echo   %T_KEIN_PY2%
echo   %T_KEIN_PY3%
echo   %T_KEIN_PY4%
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
echo   %ACHTUNG%%T_PY_FEHLT%%N%
echo   %T_WINGET%
echo.
set "JA="
set /p "JA=%T_PY_FRAGE% "
if /i not "%JA%"=="j" if /i not "%JA%"=="ja" if /i not "%JA%"=="y" if /i not "%JA%"=="yes" exit /b 0
echo.
winget install --exact --id Python.Python.3.13
echo.
call :python_suchen
exit /b 0

:texte_de
set "T_UNTER=Anlagen-Sonde"
set "T_ZEILE=Windhager · Home Assistant · Lokal"
set "T_PY_OK=Python gefunden"
set "T_M1=Anlage auslesen"
set "T_M2=Vorhandenen Abzug schwärzen"
set "T_WAHL=  Auswahl [1]:"
set "T_ZIEHEN1=Ziehe den Ordner %W%probe%N% in dieses Fenster und drücke Enter."
set "T_ZIEHEN2=Ohne Eingabe gilt der Ordner probe neben tools."
set "T_ORDNER=  Ordner:"
set "T_FEHLERCODE=Die Sonde endete mit Fehlercode"
set "T_KEIN_PY1=Python 3 wurde nicht gefunden."
set "T_KEIN_PY2=Bitte von https://www.python.org/downloads/ installieren"
set "T_KEIN_PY3=und bei der Installation „Add python.exe to PATH“ anhaken."
set "T_KEIN_PY4=Danach probe.cmd erneut starten."
set "T_PY_FEHLT=Python fehlt. Die Sonde braucht Python 3."
set "T_WINGET=Es lässt sich jetzt über winget installieren, die Paketverwaltung von Windows."
set "T_PY_FRAGE=  Python jetzt installieren? [j/n]"
exit /b 0

:texte_en
set "T_UNTER=Controller probe"
set "T_ZEILE=Windhager · Home Assistant · local"
set "T_PY_OK=Python found"
set "T_M1=Read the controller"
set "T_M2=Redact an existing dump"
set "T_WAHL=  Choice [1]:"
set "T_ZIEHEN1=Drag the folder %W%probe%N% into this window and press Enter."
set "T_ZIEHEN2=Without input, the folder probe next to tools is used."
set "T_ORDNER=  Folder:"
set "T_FEHLERCODE=The probe ended with error code"
set "T_KEIN_PY1=Python 3 was not found."
set "T_KEIN_PY2=Please install it from https://www.python.org/downloads/"
set "T_KEIN_PY3=and tick "Add python.exe to PATH" during setup."
set "T_KEIN_PY4=Then start probe.cmd again."
set "T_PY_FEHLT=Python is missing. The probe needs Python 3."
set "T_WINGET=It can be installed now with winget, the Windows package manager."
set "T_PY_FRAGE=  Install Python now? [y/n]"
exit /b 0
