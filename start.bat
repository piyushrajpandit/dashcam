@echo off
title DashCam Monitor Server
color 0B
cls

echo.
echo  ============================================================
echo    DASHCAM MONITOR — Starting Up
echo  ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo  Please install Python from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo  [OK] Python found!
echo.

REM Navigate to server folder
cd /d "%~dp0server"

REM Check if dependencies are installed
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo  Installing required packages (first time only)...
    echo  This will take 1-2 minutes.
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  [ERROR] Failed to install packages!
        echo  Try running as Administrator or check your internet connection.
        pause
        exit /b 1
    )
    echo.
    echo  [OK] Packages installed!
)

echo  [OK] All packages ready!
echo.

REM Get local IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /r "IPv4"') do (
    set LOCAL_IP=%%a
    goto :found_ip
)
:found_ip
set LOCAL_IP=%LOCAL_IP: =%

echo  ============================================================
echo   OPEN THIS ON YOUR ANDROID PHONE (same WiFi):
echo.
echo     http://%LOCAL_IP%:5000
echo.
echo  ============================================================
echo.
echo  Starting server... (Press Ctrl+C to stop)
echo.

python app.py

echo.
echo  Server stopped.
pause
