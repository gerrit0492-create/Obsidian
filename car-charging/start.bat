@echo off
REM ---------------------------------------------------------------------------
REM One-click launcher for the Car Charging dashboard (Windows).
REM Just double-click this file. First run installs what's needed (takes a
REM minute); after that it opens the dashboard in your browser straight away.
REM ---------------------------------------------------------------------------
cd /d "%~dp0"
title Car Charging dashboard

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo  Python was not found.
    echo  Install "Python 3.12" from the Microsoft Store, then double-click this again.
    echo.
    pause
    exit /b 1
)

echo Installing dependencies (first run only)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo  Could not install the dependencies. Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)

echo.
echo  Starting the dashboard - a browser tab will open at http://localhost:8501
echo  Keep this window open while you use it. Close it to stop the app.
echo.
python -m streamlit run app.py

pause
