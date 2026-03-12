@echo off
chcp 65001 >nul
echo ========================================
echo  Local Knowledge Base - Quick Start
echo ========================================
echo.

REM Go to project root
cd /d "%~dp0.."
echo [INFO] Project directory: %CD%
echo.

REM Activate conda environment
call conda activate myllm
echo [INFO] Activated conda environment: myllm
echo.

REM Check Python
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in myllm environment
    pause
    exit /b 1
)

REM Check Ollama
ollama --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Ollama not installed
)

echo [1/3] Starting API server (http://localhost:8000)...
start "API Server" cmd /k "call conda activate myllm && python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 >nul

echo [2/3] Starting Streamlit frontend (http://localhost:8501)...
start "Streamlit" cmd /k "call conda activate myllm && streamlit run src/frontend/app.py"

echo.
echo ========================================
echo  Started!
echo  - API: http://localhost:8000
echo  - Frontend: http://localhost:8501
echo  - API Docs: http://localhost:8000/docs
echo ========================================
pause
