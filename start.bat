@echo off
setlocal enabledelayedexpansion

chcp 65001 >nul 2>&1

echo ========================================
echo   Local Knowledge Base System
echo ========================================
echo.
echo [1/2] Starting API Server...
start "API Server" cmd /k "set PYTHONPATH=D:\code\LLM\local-knowledge-base && conda activate myllm && cd /d D:\code\LLM\local-knowledge-base && python src\api\main.py"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Frontend...
start "Streamlit" cmd /k "set PYTHONPATH=D:\code\LLM\local-knowledge-base && conda activate myllm && cd /d D:\code\LLM\local-knowledge-base && streamlit run src\frontend\app.py"

echo.
echo ========================================
echo   Done!
echo   - API: http://localhost:8000
echo   - Frontend: http://localhost:8501
echo ========================================
echo.
pause
