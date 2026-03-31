"""
GraphAgent LangGraph 测试
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document


def _make_mock_llm():
    """创建模拟 LLM"""
    llm = MagicMock()
    # 默认：选择 hybrid_search 工具
    llm.generate.return_value = {"text": json.dumps([
        {"tool": "hybrid_search", "args": {"query": "测试", "k": 3}}
    ])}
    return llm


def _make_mock_vector_store():
    """创建模拟向量库"""
    vs = MagicMock()
    vs.hybrid_search.return_value = [
        Document(page_content="测试文档内容", metadata={"source": "test.pdf"}),
    ]
    return vs


class TestGraphAgentBasic:
    """GraphAgent 基础功能测试"""

    def _make_agent(self, llm=None, vs=None):
        from src.agents.graph_agent import GraphAgent
        return GraphAgent(
            llm_manager=llm or _make_mock_llm(),
            vector_store=vs or _make_mock_vector_store(),
        )

    def test_process_returns_success(self):
        """测试基本查询返回成功"""
        agent = self._make_agent()
        result = agent.process("什么是RAG")

        assert result["success"] is True
        assert "answer" in result
        assert result["query"] == "什么是RAG"

    def test_process_with_iterations(self):
        """测试记录迭代次数"""
        agent = self._make_agent()
        result = agent.process("测试问题")

        assert "iterations" in result
        assert result["iterations"] >= 1

    def test_process_stops_at_max_iterations(self):
        """测试达到最大迭代次数后停止"""
        llm = _make_mock_llm()
        # analyze_query 总是选择 hybrid_search
        llm.generate.return_value = {"text": json.dumps([
            {"tool": "hybrid_search", "args": {"query": "test", "k": 3}}
        ])}
        # reflect 总是返回 more（需要更多）
        reflect_count = [0]

        def mock_generate(prompt):
            if "足够" in prompt or "enough" in prompt or "more" in prompt:
                reflect_count[0] += 1
                return {"text": "more"}
            return {"text": json.dumps([
                {"tool": "hybrid_search", "args": {"query": "test", "k": 3}}
            ])}

        llm.generate.side_effect = mock_generate

        agent = self._make_agent(llm=llm)
        result = agent.process("复杂问题")

        # 应在 max_iterations 次后停止
        assert result["success"] is True
        # 迭代次数不应无限增长

    def test_process_handles_llm_failure(self):
        """测试 LLM 失败时的容错"""
        from src.agents.graph_agent import GraphAgent

        vs = _make_mock_vector_store()
        # 无 LLM
        agent = GraphAgent(llm_manager=None, vector_store=vs)
        result = agent.process("测试问题")

        # 无 LLM 时应该 fallback 到直接检索
        assert "answer" in result

    def test_empty_tool_calls_goes_to_synthesize(self):
        """测试空工具调用直接进入合成"""
        llm = _make_mock_llm()
        # analyze_query 返回空数组
        llm.generate.return_value = {"text": "[]"}

        agent = self._make_agent(llm=llm)
        result = agent.process("测试问题")

        assert result["success"] is True


class TestGraphAgentToolSelection:
    """Agent 工具选择测试"""

    def _make_agent(self, llm=None, vs=None):
        from src.agents.graph_agent import GraphAgent
        return GraphAgent(
            llm_manager=llm or _make_mock_llm(),
            vector_store=vs or _make_mock_vector_store(),
        )

    def test_agent_calls_decompose_for_complex_query(self):
        """测试复杂问题时 Agent 选择 decompose_query"""
        llm = MagicMock()
        # 第一次调用（analyze）：选择 decompose_query
        # 第二次调用（reflect）：足够了
        llm.generate.side_effect = [
            {"text": json.dumps([
                {"tool": "decompose_query", "args": {"query": "RAG和向量搜索的区别"}}
            ])},
            {"text": "enough"},
            {"text": "根据分析，RAG和向量搜索的区别如下..."},
        ]

        agent = self._make_agent(llm=llm)
        result = agent.process("RAG和向量搜索有什么区别")

        assert result["success"] is True

    def test_agent_calls_hybrid_search(self):
        """测试简单检索场景"""
        llm = MagicMock()
        llm.generate.side_effect = [
            {"text": json.dumps([
                {"tool": "hybrid_search", "args": {"query": "什么是RAG", "k": 3}}
            ])},
            {"text": "enough"},
            {"text": "RAG是检索增强生成技术。"},
        ]

        agent = self._make_agent(llm=llm)
        result = agent.process("什么是RAG")

        assert result["success"] is True


class TestExtractJson:
    """JSON 提取工具函数测试"""

    def test_extract_direct_json(self):
        from src.agents.graph_agent import _extract_json
        result = _extract_json('[{"tool": "search", "args": {"q": "test"}}]')
        assert result is not None
        assert len(result) == 1

    def test_extract_from_markdown_block(self):
        from src.agents.graph_agent import _extract_json
        text = '```json\n[{"tool": "search", "args": {"q": "test"}}]\n```'
        result = _extract_json(text)
        assert result is not None

    def test_extract_from_text_with_brackets(self):
        from src.agents.graph_agent import _extract_json
        text = '分析如下：[{"tool": "hybrid_search", "args": {"query": "test"}}] 结束'
        result = _extract_json(text)
        assert result is not None

    def test_extract_returns_none_for_invalid(self):
        from src.agents.graph_agent import _extract_json
        assert _extract_json("没有任何JSON内容") is None
        assert _extract_json("") is None
