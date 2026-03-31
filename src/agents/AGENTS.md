# AGENTS.md - Agent System

基于 LangGraph 的 Agent 系统，包含查询分类器、GraphAgent、传统 Agent 和工具集。

## Files

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `classifier.py` | 查询复杂度分类器 | `QueryClassifier`, `SIMPLE`, `COMPLEX` |
| `graph_agent.py` | LangGraph Agentic RAG | `GraphAgent`, `AgentState`, `_extract_json` |
| `base_agent.py` | 传统 Agent 基类（保留） | `BaseAgent`, `AgentConfig`, `AgentState` |
| `rag_agent.py` | 传统 RAG Agent（保留） | `RAGAgent`, `MultiStepRAGAgent`, `ResearchAgent` |
| `tools.py` | 工具函数和注册表 | `ToolRegistry`, `safe_eval` (⚠️ SECURITY-CRITICAL) |
| `__init__.py` | Package marker | |

## Architecture

```
用户查询
  │
  ▼
QueryClassifier (LLM 单次分类)
  │
  ├── simple ──→ RAGChain (src/core/rag_chain.py)
  │
  └── complex ──→ GraphAgent (LangGraph StateGraph)
                    │
                    ├── analyze_query: LLM 分析意图，选择工具
                    ├── execute_tools: 执行选中的工具
                    ├── reflect: 评估信息是否充分
                    │     ├── more → 回到 analyze_query (循环)
                    │     └── enough → synthesize
                    └── synthesize: 综合结果生成最终答案
```

## Tools / Skills

| Tool | Description | Category |
|------|-------------|----------|
| `hybrid_search` | 向量 + BM25 混合搜索 | Retrieval |
| `parent_context_search` | 父子上下文检索 | Retrieval |
| `search_knowledge` | 基础向量搜索 | Retrieval |
| `retrieve_documents` | 带分数的检索 | Retrieval |
| `list_documents` | 列出知识库文档 | Retrieval |
| `knowledge_summary` | 主题综合摘要 | Analysis |
| `decompose_query` | 复杂问题分解为子问题 | Analysis |
| `compare_documents` | 两个主题的结构化对比 | Comparison |
| `trace_source` | 答案逐句溯源到检索文档 | Verification |
| `read_file` | 安全文件读取 | Utility |
| `calculate` | 安全数学计算 | Utility |

## Usage

### API 调用 Agent 模式

```python
POST /api/v1/query
{
    "question": "RAG和向量搜索有什么区别",
    "use_agent": true   # 启用 Agent 模式
}
```

`use_agent=true` 时系统会先用 LLM 分类：
- `simple` → 走 RAGChain（快速，1-2s）
- `complex` → 走 GraphAgent（多步推理，3-10s）

### 代码调用

```python
from src.agents.classifier import QueryClassifier, SIMPLE, COMPLEX
from src.agents.graph_agent import GraphAgent

# 分类
classifier = QueryClassifier(llm_manager)
label = classifier.classify("什么是RAG")  # → "simple"

# GraphAgent
agent = GraphAgent(llm_manager=llm, vector_store=vs)
result = agent.process("对比RAG和向量搜索的优缺点")
print(result["answer"])
print(result["iterations"])  # 迭代次数
```

## Configuration

```yaml
# config/settings.yaml
agent:
  enabled: true
  classifier:
    fallback: "simple"    # LLM 分类失败时默认走 RAGChain
  graph:
    max_iterations: 3     # 反思循环最大迭代次数
```

## ⚠️ safe_eval Security (CRITICAL)

`tools.py:safe_eval()` is security-critical:
- **ALLOWED**: `+`, `-`, `*`, `/`, `**`, `%`, `(`, `)`
- **BLOCKED**: `__import__`, `eval`, `exec`, attribute access, function calls, variables
- **Test required**: `tests/agents/test_tools.py` must verify safe_eval behavior

## Testing

```
tests/agents/test_classifier.py   — QueryClassifier 分类器测试
tests/agents/test_skills.py       — compare_documents + trace_source 测试
tests/agents/test_graph_agent.py  — GraphAgent LangGraph 端到端测试
tests/agents/test_tools.py        — safe_eval 安全性测试
```
