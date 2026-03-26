# 配置文件参数说明

本文档详细解释 `config/settings.yaml` 中所有配置参数的作用及参考值。

---

## 目录

1. [应用设置 (app)](#1-应用设置-app)
2. [数据路径 (paths)](#2-数据路径-paths)
3. [文档处理 (document_processing)](#3-文档处理-document_processing)
4. [向量存储 (vector_store)](#4-向量存储-vector_store)
5. [嵌入模型 (embeddings)](#5-嵌入模型-embeddings)
6. [RAG配置 (rag)](#6-rag配置-rag)
7. [Agent配置 (agents)](#7-agent配置-agents)
8. [LLM配置 (llm)](#8-llm配置-llm)
9. [成本控制 (cost_control)](#9-成本控制-cost_control)
10. [服务器配置 (server)](#10-服务器配置-server)
11. [监控和日志 (monitoring)](#11-监控和日志-monitoring)
12. [硬件配置 (hardware)](#12-硬件配置-hardware)

---

## 1. 应用设置 (app)

```yaml
app:
  name: "local-knowledge-base"     # 应用名称
  version: "1.0.0"                 # 版本号
  environment: "${ENVIRONMENT:-development}"  # 运行环境
  debug: false                     # 调试模式
  log_level: "${LOG_LEVEL:-INFO}"  # 日志级别
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `name` | 应用名称 | 一般无需修改 |
| `version` | 版本号 | 一般无需修改 |
| `environment` | 运行环境 | `development` / `production` |
| `debug` | 调试模式 | `false`（生产环境）|
| `log_level` | 日志级别 | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## 2. 数据路径 (paths)

```yaml
paths:
  data_dir: "${DATA_DIR:-./data}"
  raw_docs: "${RAW_DOCS_DIR:-${paths.data_dir}/raw_docs}"
  processed: "${PROCESSED_DIR:-${paths.data_dir}/processed}"
  vector_store: "${VECTOR_STORE_DIR:-${paths.data_dir}/vector_store}"
  logs: "./logs"
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `data_dir` | 数据根目录 | `./data` |
| `raw_docs` | 原始文档目录 | `./data/raw_docs` |
| `processed` | 处理后文档目录 | `./data/processed` |
| `vector_store` | 向量数据库目录 | `./data/vector_store` |
| `logs` | 日志目录 | `./logs` |

---

## 3. 文档处理 (document_processing)

### 3.1 支持的格式

```yaml
document_processing:
  supported_formats:
    - "pdf"
    - "docx"
    - "txt"
    - "md"
    - "html"
    - "csv"
```

| 格式 | 说明 |
|------|------|
| `pdf` | PDF 文档 |
| `docx` | Word 文档 |
| `txt` | 纯文本 |
| `md` | Markdown |
| `html` | 网页 |
| `csv` | CSV 表格 |

### 3.2 分块设置 (chunking)

```yaml
  chunking:
    chunk_size: "${CHUNK_SIZE:-800}"
    chunk_overlap: "${CHUNK_OVERLAP:-100}"
    max_chunks_per_doc: "${MAX_CHUNKS_PER_DOC:-99999}"
```

| 参数 | 说明 | 参考值 | 环境变量 |
|------|------|--------|----------|
| `chunk_size` | **每个 chunk 的字符数** | 短文档: 500<br>中等: 800<br>长文档: 1000 | `CHUNK_SIZE` |
| `chunk_overlap` | 相邻 chunk 重叠字符数 | 80-150 | `CHUNK_OVERLAP` |
| `max_chunks_per_doc` | 单文档最大 chunk 数 | 99999（不限制） | `MAX_CHUNKS_PER_DOC` |

**调整建议：**
- **技术文档/论文**：chunk_size 500-600（保持语义完整）
- **小说/叙事文本**：chunk_size 800-1000（允许更多上下文）
- **FAQ/问答**：chunk_size 300-500（问题答案紧凑）

### 3.3 文本分割器 (text_splitter)

```yaml
  text_splitter:
    type: "recursive_character"
    separators: ["\n\n", "\n", "。", "？", "！", "；", "?", "!", ";", "…", "……"]
    keep_separator: true
```

| 参数 | 说明 |
|------|------|
| `type` | 分割器类型，一般无需修改 |
| `separators` | 中文友好的分隔符优先级 |
| `keep_separator` | 是否保留分隔符 |

### 3.4 预处理 (preprocessing)

```yaml
  preprocessing:
    remove_extra_whitespace: true    # 移除多余空白
    normalize_unicode: true          # Unicode 标准化
    handle_mixed_language: true      # 处理中英文混合
```

| 参数 | 说明 | 推荐 |
|------|------|------|
| `remove_extra_whitespace` | 合并连续空白字符 | `true` |
| `normalize_unicode` | Unicode 规范化（NFKC） | `true` |
| `handle_mixed_language` | 中英文之间添加空格 | `true` |

---

## 4. 向量存储 (vector_store)

```yaml
vector_store:
  type: "${VECTOR_DB_TYPE:-chroma}"
  
  chroma:
    persist_directory: "${CHROMA_PERSIST_DIR:-${paths.vector_store}/chroma}"
    collection_name: "${CHROMA_COLLECTION_NAME:-knowledge_base}"
    embedding_function: "bge-m3"
    
  qdrant:
    url: "http://localhost:6333"
    collection_name: "knowledge_base"
    prefer_grpc: false
    
  faiss:
    index_path: "${paths.vector_store}/faiss.index"
    index_type: "IndexFlatIP"
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `type` | 向量数据库类型 | `chroma`（轻量本地）<br>`qdrant`（需额外服务）<br>`faiss`（Facebook 向量库） |
| `persist_directory` | Chroma 数据持久化目录 | - |
| `collection_name` | 集合名称 | 建议不同知识库用不同名称 |

**推荐：**
- 个人/小团队使用：`chroma`（无需额外服务）
- 生产环境：`qdrant`（支持分布式）

---

## 5. 嵌入模型 (embeddings)

```yaml
embeddings:
  model: "${EMBEDDING_MODEL:-shibing624/text2vec-chinese-sentence}"
  device: "cpu"
  batch_size: 32
  normalize_embeddings: true
  max_length: 512
  
  hf_mirror: "${HF_MIRROR:-https://hf-mirror.com}"
  
  cache:
    enabled: true
    ttl_seconds: 3600
    max_size_mb: 1000
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `model` | 嵌入模型 | `shibing624/text2vec-chinese-sentence`（轻量）<br>`BAAI/bge-m3`（高质量） |
| `device` | 运行设备 | `cpu` 或 `cuda` |
| `batch_size` | 批处理大小 | 32（内存够可调大） |
| `normalize_embeddings` | 是否归一化向量 | `true` |
| `max_length` | 最大token长度 | 512 |
| `hf_mirror` | HuggingFace 镜像 | 国内用 `https://hf-mirror.com` |

**模型选择：**
- **轻量快速**：`shibing624/text2vec-chinese-sentence`（约400MB）
- **高质量**：`BAAI/bge-m3`（需配置镜像，约1.5GB）
- **本地 Ollama**：`bge-m3`（通过 ollama 拉取）

---

## 6. RAG配置 (rag)

### 6.1 检索器 (retriever)

```yaml
rag:
  retriever:
    type: "hybrid"  # hybrid, dense, sparse
    top_k: "${RETRIEVAL_TOP_K:-4}"
    score_threshold: "${RETRIEVAL_SCORE_THRESHOLD:-0.7}"
    
    dense:
      search_type: "similarity"  # similarity, mmr
      fetch_k: 20
      
    sparse:
      bm25_k1: 1.5
      bm25_b: 0.75
      
    hybrid:
      fusion_method: "weighted"  # weighted, reciprocal_rank_fusion
      dense_weight: 0.7
      sparse_weight: 0.3
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `type` | 检索类型 | `dense`（向量检索）<br>`sparse`（BM25）<br>`hybrid`（混合） |
| `top_k` | 召回文档数量 | 3-6 |
| `score_threshold` | 相似度阈值 | 0.5-0.8 |

**检索类型选择：**
- **dense**：语义相似检索，适合语义理解
- **sparse**：关键词检索，适合精确匹配
- **hybrid**：两者结合，推荐使用

### 6.2 重排序 (reranking)

```yaml
  reranking:
    enabled: "${ENABLE_RERANKING:-false}"
    model: "${RERANKER_MODEL:-BAAI/bge-reranker-large}"
    top_n: 3
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `enabled` | 是否启用 | `false`（默认） |
| `model` | 重排序模型 | `BAAI/bge-reranker-large` |
| `top_n` | 重排后保留数量 | 3 |

**说明**：重排序需要额外模型，会增加延迟，但能提升答案质量。个人使用建议关闭。

### 6.3 生成 (generation)

```yaml
  generation:
    prompt_template: |
      基于以下参考文档回答用户问题...
    temperature: 0.1
    max_tokens: 2000
    streaming: true
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `temperature` | 创造性程度 | 0.1-0.3（准确）<br>0.7-1.0（创意） |
| `max_tokens` | 最大生成token数 | 1000-2000 |
| `streaming` | 是否流式输出 | `true` |

---

## 7. Agent配置 (agents)

```yaml
agents:
  enabled: "${ENABLE_AGENTS:-true}"
  
  base_agent:
    max_iterations: "${AGENT_MAX_ITERATIONS:-5}"
    early_stopping: true
    reflection_enabled: true
    
  tools:
    enabled_tools: "${AGENT_TOOLS:-['retrieval', 'calculator', 'web_search']}"
    
    retrieval:
      top_k: 4
      include_sources: true
      
    calculator:
      precision: 4
      
    web_search:
      max_results: 3
      timeout: 10
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `enabled` | 是否启用 Agent | `true` |
| `max_iterations` | Agent 最大迭代次数 | 3-10 |
| `early_stopping` | 达到目标后提前停止 | `true` |
| `reflection_enabled` | 启用反思机制 | `true` |
| `enabled_tools` | 启用的工具 | `retrieval`, `calculator`, `web_search` |

---

## 8. LLM配置 (llm)

### 8.1 本地模型 (local)

```yaml
llm:
  local:
    provider: "ollama"
    
    ollama:
      base_url: "http://localhost:11434"
      model: "deepseek-v2:lite"
      temperature: 0.1
      context_window: 64000
      num_predict: 1024
      streaming: true
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `provider` | 本地模型提供者 | `ollama` |
| `base_url` | Ollama 服务地址 | `http://localhost:11434` |
| `model` | 模型名称 | `deepseek-v2:lite`, `qwen2.5:7b` |
| `temperature` | 温度参数 | 0.1-0.3 |
| `context_window` | 上下文窗口大小 | 视模型而定 |
| `num_predict` | 最大生成token数 | 1024-2048 |

**本地模型推荐：**
- **DeepSeek-V2-Lite**：轻量（约4GB），中文效果好
- **Qwen2.5-7B**：质量更高（约7GB）

### 8.2 API模型 (api)

```yaml
  api:
    enabled: true
    default_provider: "deepseek"
    fallback_enabled: true
    
    openai:
      api_key: "${OPENAI_API_KEY}"
      model: "gpt-4o-mini"
      base_url: "https://api.openai.com/v1"
      
    deepseek:
      api_key: "${DEEPSEEK_API_KEY}"
      model: "deepseek-chat"
      base_url: "https://api.deepseek.com"
      
    kimi:
      api_key: "${KIMI_API_KEY}"
      model: "moonshot-v1-8k-vision-preview"
      base_url: "https://api.moonshot.cn/v1"
      
    anthropic:
       api_key: "${ANTHROPIC_API_KEY}"
       model: "claude-3-haiku-20240307"
```

| 提供商 | 模型 | 特点 |
|--------|------|------|
| OpenAI | `gpt-4o-mini` | 性价比高 |
| DeepSeek | `deepseek-chat` | 中文优化，价格低 |
| Kimi | `moonshot-v1-8k-vision-preview` | 国内服务 |
| Anthropic | `claude-3-haiku` | 速度快 |

**环境变量配置：**
```bash
# 在 .env 文件中配置
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
KIMI_API_KEY=xxx
ANTHROPIC_API_KEY=sk-ant-xxx
```

---

## 9. 成本控制 (cost_control)

```yaml
cost_control:
  enabled: true
  budget_daily: 10.0  # 美元
  auto_switch_to_local: true
  daily_api_limit: 50
  
  providers:
    openai:
      input_price_per_1k: 0.0015
      output_price_per_1k: 0.0060
      
    deepseek:
      input_price_per_1k: 0.00014
      output_price_per_1k: 0.00028
      
    anthropic:
      input_price_per_1k: 0.00080
      output_price_per_1k: 0.00400
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `enabled` | 是否启用成本控制 | `true` |
| `budget_daily` | 每日预算（美元） | 10.0 |
| `auto_switch_to_local` | 超预算自动切换本地模型 | `true` |
| `daily_api_limit` | 每日 API 调用次数限制 | 50 |

---

## 10. 服务器配置 (server)

```yaml
server:
  api:
    host: "${API_HOST:-0.0.0.0}"
    port: "${API_PORT:-8000}"
    workers: 2
    reload: true
    
  frontend:
    streamlit:
      port: "${STREAMLIT_PORT:-8501}"
      theme: "light"
      
    gradio:
      port: 7860
      share: false
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `host` | API 监听地址 | `0.0.0.0`（允许外部访问）<br>`127.0.0.1`（仅本地） |
| `port` | API 端口 | 8000 |
| `workers` | 工作进程数 | CPU 核数 |
| `reload` | 开发模式热重载 | `true`（开发）<br>`false`（生产） |
| `streamlit.port` | Streamlit 端口 | 8501 |

---

## 11. 监控和日志 (monitoring)

```yaml
monitoring:
  enabled: true
  
  metrics:
    enable_prometheus: true
    port: 9090
    
  logging:
    file: "${paths.logs}/app.log"
    max_size_mb: 100
    backup_count: 5
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
  health_check:
    endpoint: "/health"
    interval_seconds: 30
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `enabled` | 是否启用监控 | `true` |
| `enable_prometheus` | 启用 Prometheus 指标 | `true` |
| `metrics.port` | Prometheus 端口 | 9090 |
| `logging.file` | 日志文件路径 | - |
| `logging.max_size_mb` | 单个日志文件最大 MB | 100 |
| `logging.backup_count` | 保留历史日志数 | 5 |

---

## 12. 硬件配置 (hardware)

```yaml
hardware:
  cuda:
    visible_devices: "${CUDA_VISIBLE_DEVICES:-0}"
    allow_tf32: true
    
  memory:
    max_gpu_memory: "${MAX_GPU_MEMORY:-10GB}"
    cpu_worker_threads: "${CPU_WORKER_THREADS:-6}"
    
  optimization:
    enable_flash_attention: true
    enable_tensor_parallel: false
    enable_paged_attention: true
```

| 参数 | 说明 | 参考值 |
|------|------|--------|
| `visible_devices` | 使用的 GPU 编号 | `0`（单卡）<br>`0,1`（多卡） |
| `allow_tf32` | 允许 TF32 运算 | `true` |
| `max_gpu_memory` | 最大 GPU 显存使用 | 根据显卡调整 |
| `cpu_worker_threads` | CPU 工作线程数 | CPU 核心数 |
| `enable_flash_attention` | 启用 Flash Attention | 需要 Ampere+ 显卡 |
| `enable_tensor_parallel` | 启用张量并行 | 多卡时启用 |
| `enable_paged_attention` | 启用分页 Attention | vLLM 需要 |

---

## 常用环境变量速查

```bash
# 文档处理
export CHUNK_SIZE=800
export CHUNK_OVERLAP=100

# 检索
export RETRIEVAL_TOP_K=4
export RETRIEVAL_SCORE_THRESHOLD=0.7

# 模型
export EMBEDDING_MODEL=shibbing624/text2vec-chinese-sentence

# API
export OPENAI_API_KEY=sk-xxx
export DEEPSEEK_API_KEY=sk-xxx

# 服务
export API_HOST=0.0.0.0
export API_PORT=8000
```

---

## 快速参考表

| 场景 | chunk_size | top_k | temperature |
|------|------------|-------|-------------|
| 简单问答 | 500 | 3 | 0.1 |
| 技术文档 | 600 | 4 | 0.1 |
| 复杂分析 | 800 | 5 | 0.2 |
| 创意写作 | 1000 | 3 | 0.7 |
