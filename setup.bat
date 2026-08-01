@echo off
echo.
echo ============================================================
echo     MEDICAL RAG SYSTEM - SETUP SCRIPT
echo ============================================================
echo.

echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found! Please install Python 3.9+
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%
echo.

echo Creating virtual environment...
python -m venv backend\venv
echo Virtual environment created
echo.

echo Activating virtual environment...
call backend\venv\Scripts\activate.bat
echo Virtual environment activated
echo.

echo Installing dependencies...
python -m pip install --upgrade pip >nul 2>&1
pip install -r backend\requirements.txt
echo Dependencies installed
echo.

echo Setting up environment configuration...
if not exist .env (
    copy .env.example .env
    echo .env file created
    echo.
    echo IMPORTANT: Edit .env and add your OpenAI API key
    echo    OPENAI_API_KEY=sk-your-api-key-here
) else (
    echo .env file already exists
)

echo.
echo ============================================================
echo                 SETUP COMPLETE!
echo ============================================================
echo.
echo Next steps:
echo 1. Edit .env and add your OpenAI API key: notepad .env
echo 2. Start backend: backend\venv\Scripts\activate ^&^& python backend\main.py
echo 3. Open frontend\index.html in your browser
echo.
echo Read: 00_READ_ME_FIRST.txt / START_HERE.md / docs\QUICKSTART.md
echo.
echo Good luck!
echo.
pause
