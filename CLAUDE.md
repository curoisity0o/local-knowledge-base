# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Local Knowledge Base System — a Python RAG application built with LangChain + ChromaDB + LangGraph. Supports dual-mode LLM (local via Ollama, or cloud API via OpenAI/DeepSeek/Kimi/Anthropic). Backend is FastAPI, frontend is Streamlit (primary) or Gradio.

**Conda environment**: `myllm` | **Python**: 3.10+

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run API server (localhost:8000)
python src/api/main.py

# Run Streamlit frontend (localhost:8501)
streamlit run src/frontend/app.py

# Run Gradio frontend (localhost:7860)
python src/frontend/gradio_app.py

# Start everything (Windows)
start.bat

# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/core/test_rag_chain.py -v

# Run only unit tests (skip slow/integration)
pytest tests/ -v -m "not slow and not integration"

# Lint
black src/ tests/ scripts/
ruff check src/ tests/ scripts/

# Type check
mypy src/
```

## Architecture

```
src/
├── core/           # Config, LLM manager, vector store, document processor, RAG chain
├── agents/         # LangGraph agents (base_agent, rag_agent, tools)
├── api/            # FastAPI REST API (main.py is the entry point)
├── frontend/       # Streamlit (app.py) and Gradio (gradio_app.py) UIs
└── utils/          # MinerU PDF importer
config/
├── settings.yaml   # App settings, RAG config, document processing, agent config
└── models.yaml     # Model definitions, embedding/reranker options, hardware-aware defaults
data/               # raw_docs, processed, vector_store (gitignored)
tests/              # Mirrors src/ structure
```

**Data flow**: Raw documents → DocumentProcessor (chunking with parent-child or semantic support) → VectorStore (ChromaDB) → RAG retrieval (hybrid: dense + BM25 sparse with RRF fusion, CRAG self-correction) → Citation verification → LLM generation.

**Agent mode** (`src/agents/`): QueryClassifier routes queries — `simple` → RAGChain, `complex` → GraphAgent (LangGraph StateGraph with analyze→execute→reflect→synthesize loop). Enabled via `use_agent=true` in `/api/v1/query`.

**Dual-mode LLM** (`src/core/llm_manager.py`): `local` mode uses Ollama (DeepSeek-V2-Lite/Qwen2.5-7B), `api` mode uses cloud providers. Configurable via `settings.yaml` under `llm.default_mode` (auto/local_only/api_only/local_first).

**Config access pattern**:
```python
from src.core.config import get_config
model = get_config("llm.local.ollama.model", "deepseek-v2:lite")
```

**Lazy initialization pattern** is used for expensive resources (vector store, LLM):
```python
_vector_store = None
def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
```

## Key Configuration (config/settings.yaml)

- **RAG retriever**: `hybrid` (dense 0.7 + sparse 0.3 weight), `top_k: 10`, `score_threshold: 0.5`
- **Chunking**: Parent-child mode enabled by default (parent 1500 chars, child 400 chars)
- **Cross-lingual search**: Enabled — Chinese queries auto-translated for English doc retrieval
- **Reranking**: Disabled by default (requires BAAI/bge-reranker-large)
- **CRAG**: Enabled — retrieval self-correction with query rewrite on low quality
- **Citation verification**: Enabled — validates [文档N] references, warns on invalid
- **Agent mode**: `use_agent=true` in /api/v1/query — QueryClassifier routes simple→RAGChain, complex→GraphAgent (LangGraph)
- **Agent tools**: hybrid_search, parent_context_search, decompose_query, knowledge_summary, compare_documents, trace_source, etc.

## Conventions

- **Imports**: stdlib → third-party → local. Use absolute imports from `src/` (e.g., `from src.core.config import get_config`)
- **Type hints**: Use `Optional[Dict[str, Any]]` and `List[Document]` (Python 3.10+ style from typing module)
- **Naming**: PascalCase classes, snake_case functions, UPPER_SNAKE_CASE constants, `_prefix` for private
- **Logging**: `logging.getLogger(__name__)` in all modules. Never use bare `except:` — always specify exception type
- **Test naming**: Chinese test descriptions are used (e.g., `def test_safe_eval_basic_operations(): """测试安全表达式求值基本操作"""`)

## API Endpoints

| Method | Endpoint                    | Description           |
|--------|-----------------------------|-----------------------|
| GET    | `/health`                   | Quick health check    |
| GET    | `/health/local`             | Ollama status         |
| GET    | `/health/api`               | API providers status  |
| GET    | `/health/vectorstore`       | ChromaDB status       |
| POST   | `/api/v1/query`             | RAG query             |
| POST   | `/api/v1/documents/upload`  | Upload document       |
| POST   | `/api/v1/documents/process` | Process documents     |
| GET    | `/api/v1/documents/list`    | List documents        |
| GET    | `/api/v1/stats`             | Usage statistics      |

## Security Notes

- `src/agents/tools.py` contains `safe_eval` — must block dangerous operations (`__import__`, `eval`, `exec`, etc.)
- Path traversal protection is implemented in document upload endpoints
