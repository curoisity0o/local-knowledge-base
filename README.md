# 本地知识库系统 (Local Knowledge Base System)

基于 LangChain + RAG + Agent 架构的本地化知识库系统，支持本地模型和云 API 双模式。

## ✨ 特性

- **双模式LLM支持**: 
  - 本地模式：Ollama 模型 (DeepSeek-V2-Lite / Qwen2.5-7B)
  - API 模式：OpenAI / DeepSeek / Kimi / Anthropic
- **完整RAG流水线**: 文档加载 → 文本分割 → 向量化 → 检索 → 增强生成
- **智能Agent系统**: 基于 LangGraph 的多工具 Agent，支持复杂任务分解
- **多格式文档支持**: PDF, DOCX, TXT, Markdown, 网页等
- **中文优化**: 针对中英文混合文献的文本处理和嵌入模型
- **可视化界面**: Streamlit Web 界面 + FastAPI REST API
- **隐私保护**: 完全本地运行选项，敏感数据不出境

## 🛠️ 技术栈

### 核心框架
- **LangChain**: LLM应用开发框架
- **LangGraph**: Agent工作流编排
- **ChromaDB**: 向量数据库 (本地轻量)

### 模型
- **本地LLM**: Ollama 管理 (DeepSeek-V2-Lite / Qwen2.5-7B)
- **嵌入模型**: Ollama bge-m3 (中文优化)
- **API**: OpenAI GPT-4o, DeepSeek, Kimi (Moonshot), Anthropic Claude

### 前端 & API
- **Streamlit**: 快速原型 Web 界面
- **FastAPI**: RESTful API 服务
- **Gradio**: 备选 Web 界面

### 文档处理
- **PyPDF / pdfplumber**: PDF 解析
- **Unstructured**: 复杂文档解析
- **Sentence Transformers**: 文本嵌入

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
cd D:\code\LLM
git clone <repository-url> local-knowledge-base
cd local-knowledge-base

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Ollama (管理本地模型)
# 访问 https://ollama.ai/ 下载安装

# 拉取 LLM 模型 (选择其一)
ollama pull deepseek-v2:lite
# 或
ollama pull qwen2.5:7b

# 拉取嵌入模型
ollama pull bge-m3
```

### 2. 配置环境

```bash
# 复制环境变量示例
cp .env.example .env

# 编辑 .env 文件，配置 API 密钥（可选）
# API 模式需要: OPENAI_API_KEY / DEEPSEEK_API_KEY 等
```

### 3. 启动服务

```bash
# 终端1: 启动 Ollama (如使用本地模式)
ollama serve

# 终端2: 启动 API 服务
python src/api/main.py

# 终端3: 启动 Streamlit 前端
streamlit run src/frontend/app.py
```

### 4. 使用界面

1. 打开浏览器访问 http://localhost:8501
2. 选择模式：**local** (本地 Ollama) 或 **api** (云 API)
3. 上传文档到 `data/raw_docs/` 目录
4. 点击"处理文档"按钮
5. 开始问答

## 📁 项目结构

```
local-knowledge-base/
├── config/                 # 配置文件
│   ├── settings.yaml      # 应用设置
│   └── models.yaml        # 模型配置
├── data/                  # 数据目录
│   ├── raw_docs/         # 原始文档
│   ├── processed/        # 处理后的文档
│   └── vector_store/     # 向量数据库存储
├── src/                   # 源代码
│   ├── core/             # 核心模块
│   │   ├── document_processor.py
│   │   ├── vector_store.py
│   │   ├── rag_chain.py
│   │   └── llm_manager.py  # 双模式LLM管理
│   ├── agents/           # Agent系统
│   │   ├── base_agent.py
│   │   ├── rag_agent.py
│   │   └── tools.py
│   ├── api/              # API服务
│   │   ├── main.py
│   │   ├── routes.py
│   │   └── schemas.py
│   └── frontend/         # 前端界面
│       ├── app.py
│       └── components/
├── docs/                  # 项目文档
├── tests/                 # 测试代码
├── scripts/              # 工具脚本
├── .env.example          # 环境变量示例
├── requirements.txt      # Python依赖
└── README.md            # 项目说明
```

## ⚙️ 硬件要求

### 最低配置
- CPU: 4核以上 (推荐 i5-13600KF 或更高)
- 内存: 16GB RAM
- 存储: 50GB SSD
- GPU: 可选 (有GPU可加速)

### 推荐配置 (您的配置)
- CPU: i5-13600KF (14核20线程)
- 内存: 32GB DDR4/5
- GPU: RTX 4070 SUPER 12GB
- 存储: 3.7TB (SSD推荐)

### 资源分配
- DeepSeek-V2-Lite (4-bit): ~3-4GB 显存
- 嵌入模型 (BGE-M3): 1-2GB 显存或CPU运行
- ChromaDB: 2-4GB 内存
- 应用框架: 1-2GB 内存

## ⚙️ 配置说明

### 模型模式选择

界面选择（frontend/app.py）：
- **local**: 使用本地 Ollama 模型
- **api**: 使用云 API (需要配置 API Key)

### 配置文件 (config/settings.yaml)

```yaml
llm:
  local:
    provider: "ollama"  # 只支持 ollama
    ollama:
      base_url: "http://localhost:11434"
      model: "deepseek-v2:lite"  # 或 qwen2.5:7b
      
  api:
    enabled: true
    # 配置 API Key（通过环境变量）
    # OPENAI_API_KEY, DEEPSEEK_API_KEY, KIMI_API_KEY 等
```

### RAG 参数调优
```yaml
# config/settings.yaml
rag:
  chunk_size: 800          # 中文字符建议600-1000
  chunk_overlap: 100       # 重叠字符数
  retrieval_top_k: 4       # 检索文档数量
  score_threshold: 0.7     # 相似度阈值
```

## 🤖 Agent 系统

系统内置多种 Agent 类型：

1. **检索问答 Agent**: 基础文档问答
2. **研究分析 Agent**: 多文档综合分析和报告生成
3. **文档管理 Agent**: 文档分类、去重、更新
4. **工作流 Agent**: 复杂任务分解和执行

## 📊 性能指标

| 任务 | 预期性能 (RTX 4070 SUPER) |
|------|---------------------------|
| 文档处理 (100页PDF) | 30-60秒 |
| 向量化 (1000个chunk) | 10-20秒 |
| 检索响应 | 100-300ms |
| LLM 生成 (简单) | 1-3秒 |
| LLM 生成 (复杂) | 3-7秒 |
| 端到端 RAG | 3-10秒 |

## 🔌 API 接口

### REST API 端点
- `GET /health` - 快速健康检查（不初始化组件）
- `GET /health/local` - 检查本地模型状态
- `GET /health/api` - 检查 API 状态
- `GET /health/vectorstore` - 检查向量存储状态
- `GET /health/detailed` - 详细健康检查
- `POST /api/v1/query` - 知识库问答 (支持 provider 参数: local/api)
- `POST /api/v1/documents/upload` - 上传文档
- `POST /api/v1/documents/process` - 处理文档
- `POST /api/v1/models/warmup` - 预热模型

### 查询参数
```bash
# 使用本地模型
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "你的问题", "provider": "local"}'

# 使用 API
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "你的问题", "provider": "api"}'
```

## 🧪 测试

```bash
# 运行单元测试
pytest tests/ -v

# 运行集成测试
pytest tests/integration/ -v

# 性能测试
python scripts/benchmark.py
```

## 📈 监控和日志

- 日志文件: `logs/app.log`
- 性能监控: Prometheus metrics on `/metrics`
- 健康检查: `/health`

## 📋 更新记录

详细更新内容请查看 [CHANGELOG.md](./CHANGELOG.md)

### 最新更新 (2026-03-09)

#### 功能变更
- 🔄 **简化双模式**: 移除 auto 模式，只保留 **local** 和 **api** 两选项
- 🗑️ **移除 Transformers**: 本地模型只支持 Ollama，不再回退到 HuggingFace
- 🔌 **独立健康检查**: 新增 `/health/local`、`/health/api`、`/health/vectorstore` 端点
- 📝 **引用去重**: 修复同一文档多次引用的问题

#### 配置变更
- 本地模式：`provider = "ollama"` (config/settings.yaml)
- API 模式：配置 OPENAI_API_KEY / DEEPSEEK_API_KEY 等

### 历史更新 (2026-03-08)
- 🐛 修复本地模型初始化Bug - `src/core/llm_manager.py` 第98行条件分支逻辑错误
- ✅ 系统组件全面验证通过
- ✅ Ollama服务连接正常
- ✅ API服务器启动正常

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License