#!/bin/bash
# 本地知识库系统 - 一键启动脚本

set -e

echo "=========================================="
echo "本地知识库系统 - 启动脚本"
echo "=========================================="

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查Python环境
echo -e "${YELLOW}[1/5] 检查Python环境...${NC}"
if ! command -v python &> /dev/null; then
    echo "错误: Python未安装"
    exit 1
fi
python --version

# 检查依赖
echo -e "${YELLOW}[2/5] 检查依赖...${NC}"
pip install -q -r requirements.txt

# 检查Ollama
echo -e "${YELLOW}[3/5] 检查Ollama...${NC}"
if command -v ollama &> /dev/null; then
    echo "Ollama已安装: $(ollama --version)"
    # 检查模型
    if ollama list | grep -q "deepseek-v2-lite"; then
        echo -e "${GREEN}DeepSeek模型已下载${NC}"
    else
        echo -e "${YELLOW}提示: 建议下载DeepSeek模型: ollama pull deepseek-v2-lite:16b-q4_K_M${NC}"
    fi
else
    echo -e "${YELLOW}提示: Ollama未安装，如需本地模型请安装${NC}"
fi

# 检查数据目录
echo -e "${YELLOW}[4/5] 检查数据目录...${NC}"
mkdir -p data/raw_docs
mkdir -p data/processed
mkdir -p data/vector_store
mkdir -p logs

# 启动服务
echo -e "${YELLOW}[5/5] 启动服务...${NC}"
echo ""

# 检查是否已有服务运行
if lsof -i:8000 &> /dev/null; then
    echo "端口8000已被占用，API服务可能已在运行"
fi

if lsof -i:8501 &> /dev/null; then
    echo "端口8501已被占用，Streamlit可能已在运行"
fi

# 启动API服务 (后台)
echo -e "${GREEN}启动API服务...${NC}"
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

# 等待API服务启动
sleep 3

# 启动Streamlit (后台)
echo -e "${GREEN}启动Streamlit前端...${NC}"
streamlit run src/frontend/app.py --server.port 8501 --server.address 0.0.0.0 &
STREAMLIT_PID=$!

echo ""
echo "=========================================="
echo -e "${GREEN}服务启动完成!${NC}"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  - API文档: http://localhost:8000/docs"
echo "  - Streamlit: http://localhost:8501"
echo ""
echo "停止服务:"
echo "  kill $API_PID $STREAMLIT_PID"
echo ""

# 等待
wait
