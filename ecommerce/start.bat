@echo off
REM ---------------------------------------------------------------------------
REM One-click launcher for the E-commerce planner (Windows).
REM If Smart App Control blocks a double-click, open cmd here and run:
REM     python -m streamlit run app.py
REM ---------------------------------------------------------------------------
cd /d "%~dp0"
title E-commerce planner

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install "Python 3.12" from the Microsoft Store, then try again.
    pause
    exit /b 1
)

echo Installing dependencies (first run only)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

echo.
echo Starting the planner - a browser tab will open at http://localhost:8501
echo Keep this window open while you use it. Close it to stop.
echo.
python -m streamlit run app.py
pause
