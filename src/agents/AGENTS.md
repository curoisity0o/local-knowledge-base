# AGENTS.md - Agent System

LangGraph-based agent system: base agent, RAG agent, and tools.

## Files

| File | Purpose | Key |
|------|---------|-----|
| `base_agent.py` | Base agent class | `BaseAgent` |
| `rag_agent.py` | RAG-specific agent | `RAGAgent` |
| `tools.py` | Tool functions | `safe_eval` (⚠️ SECURITY-CRITICAL), `ToolRegistry` |
| `__init__.py` | Package marker | Only `__init__.py` in src/ |

## Key Patterns

### Tool Registration
```python
from langchain.tools import Tool
from src.agents.tools import safe_eval

tools = [
    Tool(name="safe_eval", func=safe_eval, description="Safely evaluate math expressions")
]
```

### Agent Initialization
```python
from src.agents.rag_agent import RAGAgent
agent = RAGAgent(provider="local", model="deepseek-v2:lite")
```

## ⚠️ safe_eval Security (CRITICAL)

`tools.py:safe_eval()` is security-critical:
- **ALLOWED**: `+`, `-`, `*`, `/`, `**`, `%`, `(`, `)`
- **BLOCKED**: `__import__`, `eval`, `exec`, attribute access, function calls, variables
- **Test required**: `tests/agents/test_tools.py` must verify:
  - Basic math works: `safe_eval("1 + 2 * 3") == 7`
  - Dangerous ops blocked: `safe_eval("__import__('os')")` raises `ValueError`

## Testing
`tests/agents/test_tools.py` — mirrors `src/agents/tools.py`
