# AGENTS.md - Local Knowledge Base System

**Project**: Python RAG (LangChain + ChromaDB + Ollama) | **Conda**: `myllm`

## Commands

```bash
pip install -r requirements.txt
pytest tests/ -v
black src/ tests/ scripts/
ruff check src/ tests/ scripts/
python src/api/main.py        # API server (localhost:8000)
streamlit run src/frontend/app.py  # Frontend (localhost:8501)
```

## Structure

```
local-knowledge-base/
├── src/
│   ├── core/           # config, llm_manager, vector_store, document_processor, rag_chain
│   ├── agents/         # base_agent, rag_agent, tools (safe_eval security-critical)
│   ├── api/            # FastAPI main.py (~35KB)
│   ├── frontend/       # Streamlit app.py (~43KB)
│   └── utils/          # mineru_importer
├── tests/              # Mirror src/ structure
├── scripts/            # Utility scripts
├── config/             # settings.yaml, models.yaml
└── data/               # raw_docs, processed, vector_store (gitignored)
```

## Conventions

### Imports: stdlib → third-party → local

```python
from src.core.config import get_config  # Absolute from src/
```

### Type Hints (Python 3.10+ compatible)

```python
Optional[Dict[str, Any]]  # NOT dict[str, any]
List[Document]            # NOT list[Document]
```

### Naming

- Classes: `PascalCase` | Functions: `snake_case` | Constants: `UPPER_SNAKE_CASE`
- Private: `_prefix`

### Error Handling

- `logging.getLogger(__name__)` for all modules
- **NEVER bare** **`except:`** — always specify exception type
- Use `logger.error()` / `logger.warning()` appropriately

### Lazy Initialization

```python
_vector_store = None
def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
```

## Key Patterns

### Dual-Mode LLM 

- `local`: Ollama (base\_url in settings.yaml)
- `api`: OpenAI/DeepSeek/Kimi/Anthropic (API keys in .env)

### Config Access

```python
model = get_config("llm.local.ollama.model", "deepseek-v2:lite")
chunk_size = get_config("document_processing.chunking.chunk_size", 800)
```

## Anti-Patterns (THIS PROJECT)

| Issue                                | Location                              | Fix                          |
| ------------------------------------ | ------------------------------------- | ---------------------------- |
| Bare `except:`                       | `src/frontend/app.py:345,380`         | Use specific exception types |
| Type suppressions (`# type: ignore`) | `src/core/llm_manager.py:142,198,212` | Use proper type hints        |

## Missing: `__init__.py` Files

**5 packages lack markers**: `src/`, `src/core/`, `src/api/`, `src/frontend/`, `src/utils/`
Only `src/agents/__init__.py` exists.

## Missing: Standard Config Files

- **No** **`pyproject.toml`** — dev tools (black, ruff, mypy) use defaults
- **No** **`pytest.ini`** / `conftest.py` — pytest runs with no config
- **No** **`.editorconfig`**

## Testing

- Mirror `src/` structure: `tests/agents/test_tools.py` → `src/agents/tools.py`
- Chinese test names: `def test_safe_eval_basic_operations(): """测试安全表达式求值基本操作"""`
- `safe_eval` security: Must block dangerous operations (`__import__`, `eval`, etc.)

## API Endpoints

| Method | Endpoint                    | Description           |
| ------ | --------------------------- | --------------------- |
| GET    | `/health`                   | Quick check (no init) |
| GET    | `/health/local`             | Ollama status         |
| GET    | `/health/api`               | API providers status  |
| GET    | `/health/vectorstore`       | ChromaDB status       |
| POST   | `/api/v1/query`             | RAG query             |
| POST   | `/api/v1/documents/upload`  | Upload                |
| POST   | `/api/v1/documents/process` | Process               |
| GET    | `/api/v1/stats`             | Statistics            |

