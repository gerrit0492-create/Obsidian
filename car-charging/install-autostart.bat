@echo off
REM ---------------------------------------------------------------------------
REM Make the Car Charging dashboard start automatically every time you log in.
REM
REM Run this ONCE. If Windows blocks a double-click (Smart App Control), open a
REM Command Prompt in this folder and run:  install-autostart.bat
REM To undo it later, run  uninstall-autostart.bat
REM ---------------------------------------------------------------------------
setlocal
set "TASK=Car Charging dashboard"
set "DIR=%~dp0"
if "%DIR:~-1%"=="\" set "DIR=%DIR:~0,-1%"

echo Registering a logon task that runs start.bat from:
echo   %DIR%
echo.

schtasks /create /f /tn "%TASK%" /sc onlogon /tr "\"%DIR%\start.bat\""
if errorlevel 1 (
    echo.
    echo  Could not create the startup task. Try again from an Administrator
    echo  Command Prompt, or use the Startup-folder method in README.md.
    echo.
    pause
    exit /b 1
)

echo.
echo  Done. Next time you log in, a window opens and a browser tab appears at
echo  http://localhost:8501 . Keep that window open while you use the dashboard;
echo  close it to stop the app.
echo.
echo  To turn this off again, run  uninstall-autostart.bat
echo.
pause
