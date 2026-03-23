# AGENTS.md - Tests

Unit and integration tests — mirror `src/` structure.

## Structure
```
tests/
├── agents/
│   └── test_tools.py           # safe_eval security tests
├── api/
│   └── test_document_endpoints.py
└── core/
    └── test_vector_store_extended.py
```

## Running Tests
```bash
pytest tests/ -v
pytest tests/agents/test_tools.py -v
pytest tests/agents/test_tools.py::test_safe_eval_basic_operations -v
```

## Conventions

- Mirror `src/` structure: `tests/agents/test_tools.py` → `src/agents/tools.py`
- **Chinese test names**: `def test_safe_eval_basic_operations(): """测试安全表达式求值基本操作"""`
- **Security-first**: Test dangerous operations explicitly

## safe_eval Security Tests (REQUIRED)
```python
def test_safe_eval_basic_operations():
    assert safe_eval("1 + 2") == 3
    assert safe_eval("10 / 2") == 5

def test_safe_eval_dangerous_operations():
    with pytest.raises(ValueError):
        safe_eval("__import__('os')")  # BLOCKED
    with pytest.raises(ValueError):
        safe_eval("eval('1+1')")       # BLOCKED
```

## Missing Config
- **No `pytest.ini`** — uses defaults
- **No `conftest.py`** — no shared fixtures
- **No `requirements-dev.txt`** — dev tools in main requirements.txt
