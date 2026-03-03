@echo off
chcp 65001 >nul
echo ========================================
echo  本地知识库系统启动脚本
echo ========================================

REM 检查Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查Ollama
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [警告] 未找到Ollama，本地模型将不可用
    echo 请从 https://ollama.ai/ 下载安装
)

REM 激活虚拟环境（如果有）
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo 已激活虚拟环境
)

REM 安装依赖
echo.
echo 正在检查依赖...
pip install -r requirements.txt >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请手动运行: pip install -r requirements.txt
    pause
    exit /b 1
)

REM 检查环境变量
if not exist ".env" (
    echo [警告] 未找到 .env 文件，正在创建示例配置...
    copy .env.example .env >nul
    echo 请编辑 .env 文件配置API密钥和路径
)

REM 拉取模型（可选）
echo.
echo 是否拉取DeepSeek-V2-Lite模型？(y/n，建议第一次运行时选择y)
set /p pull_model=
if /i "%pull_model%"=="y" (
    echo 正在拉取DeepSeek-V2-Lite模型，这可能需要一些时间...
    ollama pull deepseek-v2-lite:16b-q4_K_M
    echo 正在拉取BGE-M3嵌入模型...
    ollama pull bge-m3
)

REM 启动服务
echo.
echo 请选择启动模式：
echo  1. 完整测试 (运行所有组件测试)
echo  2. 启动API服务
echo  3. 启动Streamlit前端
echo  4. 启动完整系统 (API + 前端)
echo  5. 交互式Python环境
set /p choice=

if "%choice%"=="1" (
    echo 正在运行完整测试...
    python src/main.py
) else if "%choice%"=="2" (
    echo 正在启动API服务...
    uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
) else if "%choice%"=="3" (
    echo 正在启动Streamlit前端...
    streamlit run src/frontend/app.py
) else if "%choice%"=="4" (
    echo 正在启动完整系统...
    start "API服务" cmd /k "uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"
    timeout /t 5
    echo 正在启动前端...
    streamlit run src/frontend/app.py
) else if "%choice%"=="5" (
    echo 启动交互式Python环境...
    python -i -c "print('已导入核心模块'); from core.config import config; from core.document_processor import DocumentProcessor; from core.vector_store import SimpleVectorStore; from core.llm_manager import LLMManager; print('模块已导入，可以使用: config, DocumentProcessor, SimpleVectorStore, LLMManager')"
) else (
    echo 无效选择
)

pause