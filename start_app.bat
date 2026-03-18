@echo off
title Bhavya's Grocery - Starting...
color 0A

echo.
echo  ================================================
echo   BHAVYA'S GROCERY MANAGEMENT SYSTEM
echo  ================================================
echo.

:: ── Check Python is installed ──
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo  [ERROR] Python is not installed or not in PATH!
    echo  Please install Python from https://python.org
    echo.
    pause
    exit /b 1
)

:: ── Go to the folder where this .bat file is located ──
cd /d "%~dp0"
echo  [INFO] Working directory: %~dp0
echo.

:: ── Check .env file exists ──
if not exist ".env" (
    color 0E
    echo  [WARNING] .env file not found!
    echo  Make sure SUPABASE_URL and SUPABASE_KEY are set.
    echo.
)

:: ── Install requirements if needed ──
if exist "requirements.txt" (
    echo  [INFO] Checking dependencies...
    pip install -r requirements.txt -q
    echo  [INFO] Dependencies ready!
    echo.
)

:: ── Start the Flask app ──
echo  [INFO] Starting Flask server...
echo  ------------------------------------------------
echo   App running at:  http://localhost:5000
echo   Press Ctrl+C to stop the server
echo  ------------------------------------------------
echo.

:: Open browser after 2 seconds
start "" /b cmd /c "timeout /t 2 >nul && start http://localhost:5000"

:: Run the app
python app.py

:: If app crashes, show error
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo  [ERROR] App stopped with an error!
    echo  Check the output above for details.
)

echo.
pause