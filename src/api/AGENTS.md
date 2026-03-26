# AGENTS.md - API Module

FastAPI REST API — single file `main.py` (~35KB).

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Quick check (no component init) |
| GET | `/health/local` | Ollama status |
| GET | `/health/api` | API providers status |
| GET | `/health/vectorstore` | ChromaDB status |
| POST | `/api/v1/query` | RAG query |
| POST | `/api/v1/documents/upload` | Upload document |
| POST | `/api/v1/documents/process` | Process documents |
| GET | `/api/v1/stats` | System statistics |

## Key Patterns

### Request Models
```python
from pydantic import BaseModel
class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 4
    provider: Optional[str] = None  # "local" or "api"
    use_rag: Optional[bool] = True
```

### Lazy Initialization
```python
_vector_store = None
def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
```

## Running
```bash
python src/api/main.py  # http://localhost:8000
```
