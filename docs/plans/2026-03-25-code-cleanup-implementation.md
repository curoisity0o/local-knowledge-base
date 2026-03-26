# 代码清理实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复代码质量问题，添加缺失配置，清理无用文件，为执行IMPROVEMENT_PLAN.md准备干净代码库

**Architecture:** 分四个阶段实施：1) 代码质量修复，2) 开发配置添加，3) 文件清理，4) 验证结果

**Tech Stack:** Python 3.10+, LangChain, ChromaDB, FastAPI, Streamlit, pytest, black, ruff

---

### 任务1：修复裸露的except语句

**Files:**
- Modify: `src/frontend/app.py:345`
- Modify: `src/frontend/app.py:380`

**Step 1: 检查当前代码**

```python
# 第345行附近
except:
    st.session_state.api_connected = False

# 第380行附近  
except:
    pass
```

**Step 2: 运行诊断确认问题**

Run: `python -c "import ast; ast.parse(open('src/frontend/app.py').read())" && echo "语法检查通过"`
Expected: 语法检查通过，但LSP显示类型错误

**Step 3: 修复第345行的except语句**

```python
except Exception as e:
    logger.warning(f"API健康检查失败: {e}")
    st.session_state.api_connected = False
```

**Step 4: 修复第380行的except语句**

```python
except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
    logger.debug(f"API连接重试失败: {e}")
```

**Step 5: 运行诊断验证修复**

Run: `lsp_diagnostics(filePath="src/frontend/app.py")`
Expected: 减少或消除错误

**Step 6: 提交**

```bash
git add src/frontend/app.py
git commit -m "fix: 替换裸露的except语句为具体异常处理"
```

---

### 任务2：修复类型忽略注释

**Files:**
- Modify: `src/core/llm_manager.py:142`
- Modify: `src/core/llm_manager.py:198`
- Modify: `src/core/llm_manager.py:212`

**Step 1: 检查当前代码**

```python
# 第142行
max_tokens=openai_config.get("max_tokens", 2000),  # type: ignore

# 第198行  
max_tokens=deepseek_config.get("max_tokens", 2000),  # type: ignore

# 第212行
max_tokens=kimi_config.get("max_tokens", 2000),  # type: ignore[arg-type]
```

**Step 2: 添加正确的类型导入**

```python
# 在文件顶部添加
from typing import Optional, Union
```

**Step 3: 修复第142行类型提示**

```python
max_tokens: Optional[int] = openai_config.get("max_tokens", 2000),
```

**Step 4: 修复第198行类型提示**

```python
max_tokens: Optional[int] = deepseek_config.get("max_tokens", 2000),
```

**Step 5: 修复第212行类型提示**

```python
max_tokens: Union[int, None] = kimi_config.get("max_tokens", 2000),
```

**Step 6: 运行类型检查**

Run: `python -c "from src.core.llm_manager import LLMManager; print('导入成功')"`
Expected: 导入成功，无类型错误

**Step 7: 提交**

```bash
git add src/core/llm_manager.py
git commit -m "fix: 使用正确类型注解替换type:ignore注释"
```

---

### 任务3：添加缺失的__init__.py文件

**Files:**
- Create: `src/__init__.py`
- Create: `src/core/__init__.py`
- Create: `src/api/__init__.py`
- Create: `src/frontend/__init__.py`
- Create: `src/utils/__init__.py`

**Step 1: 创建src/__init__.py**

```bash
echo "" > src/__init__.py
```

**Step 2: 创建src/core/__init__.py**

```bash
echo '"""核心模块"""' > src/core/__init__.py
```

**Step 3: 创建src/api/__init__.py**

```bash
echo '"""API模块"""' > src/api/__init__.py
```

**Step 4: 创建src/frontend/__init__.py**

```bash
echo '"""前端模块"""' > src/frontend/__init__.py
```

**Step 5: 创建src/utils/__init__.py**

```bash
echo '"""工具模块"""' > src/utils/__init__.py
```

**Step 6: 验证导入**

Run: `python -c "import src.core.config; import src.api.main; import src.frontend.app; import src.utils.mineru_importer; print('所有导入成功')"`
Expected: "所有导入成功"

**Step 7: 提交**

```bash
git add src/__init__.py src/core/__init__.py src/api/__init__.py src/frontend/__init__.py src/utils/__init__.py
git commit -m "feat: 添加缺失的__init__.py文件标记Python包"
```

---

### 任务4：创建pyproject.toml

**Files:**
- Create: `pyproject.toml`

**Step 1: 检查当前项目配置**

Run: `ls -la | grep -E "pyproject|setup|requirements"`
Expected: 看到requirements.txt但无pyproject.toml

**Step 2: 创建pyproject.toml内容**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "local-knowledge-base"
version = "0.1.0"
description = "本地知识库系统基于LangChain + RAG + Agent架构"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "langchain>=0.1.0",
    "langchain-community>=0.0.10",
    "chromadb>=0.4.22",
    "fastapi>=0.104.1",
    "streamlit>=1.29.0",
    "pydantic>=2.5.0",
    "requests>=2.31.0",
    "pytest>=7.4.0",
]

[project.optional-dependencies]
dev = [
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
    "pytest-cov>=4.1.0",
]

[tool.black]
line-length = 88
target-version = ['py310']
include = '\.pyi?$'
extend-exclude = '''
/(
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | _build
  | buck-out
  | build
  | dist
)/
'''

[tool.ruff]
line-length = 88
target-version = "py310"
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
]
ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]  # unused import
```

**Step 3: 写入文件**

```bash
# 使用上面的内容创建pyproject.toml
```

**Step 4: 验证TOML语法**

Run: `python -c "import tomllib; tomllib.loads(open('pyproject.toml').read()); print('TOML语法正确')"`
Expected: "TOML语法正确"

**Step 5: 提交**

```bash
git add pyproject.toml
git commit -m "feat: 添加pyproject.toml配置开发工具"
```

---

### 任务5：创建pytest.ini

**Files:**
- Create: `pytest.ini`

**Step 1: 创建pytest.ini内容**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

**Step 2: 写入文件**

```bash
# 使用上面的内容创建pytest.ini
```

**Step 3: 验证配置**

Run: `pytest --version`
Expected: 显示pytest版本，无配置错误

**Step 4: 运行快速测试验证**

Run: `pytest tests/core/test_config.py -v`
Expected: 9个测试通过

**Step 5: 提交**

```bash
git add pytest.ini
git commit -m "feat: 添加pytest.ini配置测试"
```

---

### 任务6：创建.editorconfig

**Files:**
- Create: `.editorconfig`

**Step 1: 创建.editorconfig内容**

```ini
root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.{py,pyi}]
max_line_length = 88

[*.{js,ts,jsx,tsx}]
indent_size = 2
max_line_length = 100

[*.md]
trim_trailing_whitespace = false
max_line_length = 80

[*.{yaml,yml}]
indent_size = 2

[Makefile]
indent_style = tab
```

**Step 2: 写入文件**

```bash
# 使用上面的内容创建.editorconfig
```

**Step 3: 提交**

```bash
git add .editorconfig
git commit -m "feat: 添加.editorconfig统一编辑器配置"
```

---

### 任务7：检查scripts目录

**Files:**
- Examine: `scripts/deepseek_api.py`
- Examine: `scripts/test_document_management_workflow.py`
- Examine: `scripts/test_rag.py`
- Examine: `scripts/verify_document_vector_consistency.py`

**Step 1: 分析脚本用途**

Run: `grep -r "scripts/" src/ tests/ --include="*.py" || echo "未找到对scripts的引用"`
Expected: 显示哪些脚本被引用

**Step 2: 检查脚本是否可执行**

Run: `python scripts/test_rag.py --help 2>&1 | head -5`
Expected: 显示帮助信息或错误

**Step 3: 标记未使用脚本**

创建文档记录检查结果：
```markdown
# scripts目录分析结果
- deepseek_api.py: API测试脚本，可能用于测试
- test_document_management_workflow.py: 文档管理测试
- test_rag.py: RAG系统测试
- verify_document_vector_consistency.py: 向量一致性验证
建议：保留所有脚本，都在README.md或文档中提到
```

**Step 4: 提交分析结果**

```bash
git add docs/scripts-analysis.md
git commit -m "docs: 记录scripts目录分析结果"
```

---

### 任务8：检查文档文件

**Files:**
- Examine: `技术方案.md`
- Examine: `技术文档.md`
- Examine: `开发进度.md`
- Compare with: `docs/`目录内容

**Step 1: 检查内容重复**

Run: `wc -l 技术方案.md 技术文档.md 开发进度.md docs/*.md | tail -1`
Expected: 显示总行数

**Step 2: 分析文档关系**

```bash
# 检查技术方案.md和技术文档.md的重叠
grep -n "##" 技术方案.md | head -10
grep -n "##" 技术文档.md | head -10
```

**Step 3: 创建合并建议**

创建文档记录建议：
```markdown
# 文档清理建议
1. 技术方案.md: 详细技术方案，与docs/IMPROVEMENT_PLAN.md部分重叠
2. 技术文档.md: 系统技术文档，与README.md部分重叠
3. 开发进度.md: 开发记录，可保留
建议：
- 保留开发进度.md作为历史记录
- 将技术方案.md和技术文档.md精华部分合并到README.md或docs/目录
- 不立即删除，标记为待整理
```

**Step 4: 提交建议**

```bash
git add docs/document-cleanup-suggestions.md
git commit -m "docs: 添加文档清理建议"
```

---

### 任务9：明确保留mineru文件

**Files:**
- Verify: `src/core/mineru_api.py` exists
- Verify: `src/utils/mineru_importer.py` exists

**Step 1: 检查mineru文件状态**

Run: `ls -la src/core/mineru_api.py src/utils/mineru_importer.py`
Expected: 两个文件都存在

**Step 2: 创建保留说明**

```markdown
# mineru文件保留说明
根据用户要求，以下mineru相关文件明确保留：
1. src/core/mineru_api.py - MinerU API集成
2. src/utils/mineru_importer.py - MinerU导入工具
原因：用户将自行处理PDF转Markdown功能
```

**Step 3: 添加到项目文档**

```bash
echo -e "\n## 用户保留文件\n- mineru_api.py和mineru_importer.py由用户保留用于PDF处理" >> README.md
```

**Step 4: 提交**

```bash
git add README.md docs/mineru-retention-note.md
git commit -m "docs: 明确标记mineru文件为用户保留"
```

---

### 任务10：运行测试验证

**Step 1: 运行核心测试**

Run: `pytest tests/core/ -v`
Expected: 所有核心测试通过（约65个）

**Step 2: 运行代理测试**

Run: `pytest tests/agents/ -v`
Expected: 代理测试通过

**Step 3: 运行集成测试**

Run: `pytest tests/integration/ -v 2>/dev/null || echo "无集成测试"`
Expected: 集成测试通过或不存在

**Step 4: 记录测试结果**

```bash
pytest tests/ --tb=no -q > test-results.txt
echo "测试完成: $(grep -c 'passed' test-results.txt) passed, $(grep -c 'failed' test-results.txt) failed"
```

**Step 5: 提交测试结果**

```bash
git add test-results.txt
git commit -m "test: 记录清理后测试结果"
```

---

### 任务11：运行代码质量检查

**Step 1: 运行ruff检查**

Run: `ruff check src/ --output-format=concise`
Expected: 可能有一些警告，但无错误

**Step 2: 运行black格式检查**

Run: `black --check src/`
Expected: 所有文件格式正确或显示需要格式化的文件

**Step 3: 应用自动修复**

```bash
ruff check src/ --fix
black src/
```

**Step 4: 验证修复结果**

Run: `ruff check src/ && black --check src/`
Expected: 无错误，所有文件格式正确

**Step 5: 提交代码质量修复**

```bash
git add src/
git commit -m "style: 应用代码质量工具自动修复"
```

---

### 任务12：检查导入结构

**Step 1: 测试核心导入**

Run: `python -c "
import sys
sys.path.insert(0, '.')
from src.core.config import get_config
from src.core.llm_manager import LLMManager
from src.core.vector_store import SimpleVectorStore
print('核心模块导入成功')
"`
Expected: "核心模块导入成功"

**Step 2: 测试API导入**

Run: `python -c "
import sys
sys.path.insert(0, '.')
from src.api.main import app
print('API模块导入成功')
"`
Expected: "API模块导入成功"

**Step 3: 测试前端导入**

Run: `python -c "
import sys
sys.path.insert(0, '.')
try:
    from src.frontend.app import main
    print('前端模块导入成功')
except ImportError as e:
    print(f'前端导入警告: {e}')
"`
Expected: "前端模块导入成功"或显示streamlit相关警告

**Step 4: 测试工具导入**

Run: `python -c "
import sys
sys.path.insert(0, '.')
from src.utils.mineru_importer import MinerUImporter
print('工具模块导入成功')
"`
Expected: "工具模块导入成功"

**Step 5: 提交导入验证**

```bash
git add import-test-results.txt
git commit -m "test: 验证清理后导入结构"
```

---

## 执行选项

计划已完成并保存到 `docs/plans/2026-03-25-code-cleanup-implementation.md`。

**两种执行选项：**

1. **Subagent-Driven (当前会话)** - 我分派新的subagent执行每个任务，任务间进行代码审查，快速迭代

2. **并行会话 (分离)** - 在工作树中打开新会话，使用superpowers:executing-plans进行批处理执行，设置检查点

**选择哪种方法？**