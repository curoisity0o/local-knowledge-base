# 模型下载脚本
# 使用方法: powershell -File scripts/download_models.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "模型下载脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Ollama
$ollamaCheck = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaCheck) {
    Write-Host "[ERROR] Ollama 未安装!" -ForegroundColor Red
    Write-Host "请先从 https://ollama.ai/download/windows 安装 Ollama" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/3] 下载 LLM 模型 (DeepSeek-V2-Lite)..." -ForegroundColor Yellow
Write-Host "  模型大小: 约 4GB (4-bit 量化)" -ForegroundColor Gray
Write-Host "  预计时间: 10-30 分钟 (取决于网络)" -ForegroundColor Gray
ollama pull deepseek-v2-lite:16b-q4_K_M

if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] DeepSeek-V2-Lite 下载完成" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] 下载失败，尝试备用模型..." -ForegroundColor Yellow
    Write-Host "  尝试下载 qwen2.5:7b..." -ForegroundColor Gray
    ollama pull qwen2.5:7b-instruct-q4_K_M
}

Write-Host ""
Write-Host "[2/3] 下载嵌入模型 (如需要)..." -ForegroundColor Yellow
Write-Host "  嵌入模型将通过 langchain 自动下载" -ForegroundColor Gray
Write-Host "  默认使用: shibing624/text2vec-chinese-sentence (约400MB)" -ForegroundColor Gray

Write-Host ""
Write-Host "[3/3] 验证安装..." -ForegroundColor Yellow
Write-Host ""
Write-Host "已下载的模型:" -ForegroundColor Cyan
ollama list

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "模型下载完成!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "启动服务:" -ForegroundColor Yellow
Write-Host "  API服务: python src/api/main.py" -ForegroundColor Gray
Write-Host "  前端界面: streamlit run src/frontend/app.py" -ForegroundColor Gray
Write-Host ""
