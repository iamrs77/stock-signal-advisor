@echo off
REM Always-on intraday verdict logger. Leave this window running (minimized is fine)
REM during the trading day. Edit the tickers/timeframe below if you like.
REM   watch.bat                -> logs SOXL on 5m
REM   watch.bat SOXL TQQQ      -> logs SOXL and TQQQ
REM   watch.bat SOXL --tf 3m   -> logs SOXL on 3m
cd /d "%~dp0"
.venv\Scripts\python.exe -u watch.py %*
pause
