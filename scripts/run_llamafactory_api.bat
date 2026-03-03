# 使用LLaMA-Factory启动API服务
# 使用本地ModelScope模型

@echo off
echo ========================================
echo 使用LLaMA-Factory启动本地LLM API服务
echo ========================================
echo.

set MODEL_PATH=D:\code\LLM\model_cache\deepseek-ai\DeepSeek-V2-Lite
set API_PORT=8001

echo 模型路径: %MODEL_PATH%
echo API端口: %API_PORT%
echo.

echo 启动API服务...
llamafactory-cli api ^
    --model_name_or_path %MODEL_PATH% ^
    --infer_backend huggingface ^
    --template deepseek ^
    --quantization_bit 0 ^
    --use_flash_attn auto ^
    --output_dir output ^
    --api_port %API_PORT% ^
    --trust_remote_code

pause
