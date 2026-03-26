# AGENTS.md - Core Modules

Core system: config, LLM management, vector storage, document processing, RAG pipeline.

## Files

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `config.py` | YAML + env config | `ConfigManager`, `get_config()` |
| `llm_manager.py` | Dual-mode LLM | `LLMManager`, `get_llm()` ⚠️ Type suppressions at lines 142,198,212 |
| `vector_store.py` | ChromaDB operations | `SimpleVectorStore` |
| `document_processor.py` | Document pipeline | `DocumentProcessor` |
| `rag_chain.py` | RAG pipeline | `create_rag_chain()` |
| `mineru_api.py` | MinerU integration | `MinerUImporter` |

## Key Patterns

### Lazy Initialization
```python
_processor = None
def get_processor():
    global _processor
    if _processor is None:
        _processor = DocumentProcessor()
    return _processor
```

### Dual-Mode LLM
```python
from src.core.llm_manager import LLMManager, get_llm
llm = get_llm(provider="local", model="deepseek-v2:lite")
```

### Config Access
```python
from src.core.config import get_config
model = get_config("llm.local.ollama.model", "deepseek-v2:lite")
```

## Anti-Patterns

- `llm_manager.py:142,198,212` — Has `# type: ignore` suppressions (fix: proper type hints)
- NEVER use bare `except:` — always specify exception type

## Common Imports
```python
from typing import Dict, Any, Optional, List
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI
from chromadb import Client
from src.core.config import get_config
```

## Testing
`tests/core/` mirrors this structure.
