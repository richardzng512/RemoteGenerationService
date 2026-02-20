@echo off
echo ============================================================
echo   RemoteGenerationService - Setup
echo ============================================================
echo.

:: Check Python
python --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python found:
python --version

:: Create virtual environment
if not exist ".venv" (
    echo.
    echo Creating virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate and install dependencies
echo.
echo Installing dependencies...
call .venv\Scripts\activate.bat
pip install --upgrade pip --quiet
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

:: Create directories
if not exist "outputs\images" mkdir outputs\images
if not exist "outputs\videos" mkdir outputs\videos
if not exist "workflows" mkdir workflows
if not exist "data" mkdir data
if not exist "static\img" mkdir static\img

:: Create .env if not exists
if not exist ".env" (
    copy .env.example .env >NUL
    echo Created .env from template. Edit it if needed.
)

echo.
echo ============================================================
echo   Setup complete!
echo   Run: start_windows.bat to launch the service
echo ============================================================
pause
