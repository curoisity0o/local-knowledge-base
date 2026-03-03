# 环境配置脚本 - 针对国内网络环境优化
# 使用方法: powershell -File setup_china_env.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "本地知识库系统 - 环境配置脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 配置 pip 国内镜像
Write-Host "[1/5] 配置 pip 国内镜像..." -ForegroundColor Yellow
try {
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
    Write-Host "  [OK] pip 镜像配置完成" -ForegroundColor Green
} catch {
    Write-Host "  [WARN] pip 镜像配置失败，将使用默认源" -ForegroundColor Yellow
}

# 2. 配置 HuggingFace 镜像
Write-Host "[2/5] 配置 HuggingFace 镜像..." -ForegroundColor Yellow
$env:HuggingFaceHub = "https://hf-mirror.com"
$env:HF_ENDPOINT = "https://hf-mirror.com"
[System.Environment]::SetEnvironmentVariable("HF_ENDPOINT", "https://hf-mirror.com", [System.EnvironmentVariableTarget]::User)
Write-Host "  [OK] HuggingFace 镜像环境变量已设置" -ForegroundColor Green

# 3. 设置 Python UTF-8 编码
Write-Host "[3/5] 配置 Python UTF-8 编码..." -ForegroundColor Yellow
$env:PYTHONUTF8 = "1"
[System.Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", [System.EnvironmentVariableTarget]::User)
Write-Host "  [OK] Python UTF-8 编码已配置" -ForegroundColor Green

# 4. 安装依赖
Write-Host "[4/5] 安装 Python 依赖..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] 依赖安装完成" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] 依赖安装遇到问题" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [WARN] requirements.txt 不存在" -ForegroundColor Yellow
}

# 5. 验证 Ollama
Write-Host "[5/5] 检查 Ollama 安装..." -ForegroundColor Yellow
$ollamaCheck = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCheck) {
    Write-Host "  [OK] Ollama 已安装" -ForegroundColor Green
    Write-Host "     版本: $(ollama --version)" -ForegroundColor Gray
    
    # 列出可用模型
    Write-Host ""
    Write-Host "  已下载的模型:" -ForegroundColor Cyan
    ollama list
} else {
    Write-Host "  [WARN] Ollama 未安装" -ForegroundColor Yellow
    Write-Host "  请从 https://ollama.ai/download/windows 下载安装" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "配置完成!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "后续步骤:" -ForegroundColor Yellow
Write-Host "  1. 启动 Ollama: ollama serve" -ForegroundColor Gray
Write-Host "  2. 下载模型: ollama pull deepseek-v2-lite:16b-q4_K_M" -ForegroundColor Gray
Write-Host "  3. 启动API: python src/api/main.py" -ForegroundColor Gray
Write-Host "  4. 启动前端: streamlit run src/frontend/app.py" -ForegroundColor Gray
Write-Host ""
