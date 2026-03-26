# AGENTS.md - Frontend Module

Streamlit Web UI — single file `app.py` (~43KB).

## Features
- Document upload and management
- RAG query interface (local/API mode)
- Chunk viewing with pagination (10 per page)
- Source display with deduplication
- API connection status

## Key Patterns

### Streamlit Session State
```python
import streamlit as st
if "messages" not in st.session_state:
    st.session_state.messages = []
if "provider" not in st.session_state:
    st.session_state.provider = "local"
```

### API Calls
```python
import requests
response = requests.post(
    "http://localhost:8000/api/v1/query",
    json={"question": question, "provider": provider}
)
```

### Chunk Pagination
```python
chunks_per_page = 10
total_pages = (total_chunks - 1) // chunks_per_page + 1
page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
start_idx = (page - 1) * chunks_per_page
```

## ⚠️ Anti-Patterns
- `app.py:345,380` — **Bare `except:` clauses** (silently swallow exceptions)
  - Fix: Use specific exception types + logging

## Running
```bash
streamlit run src/frontend/app.py  # http://localhost:8501
```
