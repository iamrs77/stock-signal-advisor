@echo off
REM Double-click this file to launch the Stock Signal Advisor.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m streamlit run app.py
pause
