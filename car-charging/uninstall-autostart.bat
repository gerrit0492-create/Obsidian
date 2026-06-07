@echo off
REM ---------------------------------------------------------------------------
REM Stop the Car Charging dashboard from starting automatically at login.
REM (Removes the scheduled task created by install-autostart.bat.)
REM ---------------------------------------------------------------------------
setlocal
set "TASK=Car Charging dashboard"

schtasks /delete /f /tn "%TASK%"
if errorlevel 1 (
    echo.
    echo  Could not find/remove the task "%TASK%". It may already be gone.
) else (
    echo.
    echo  Removed. The dashboard will no longer start automatically at login.
)
echo.
pause
