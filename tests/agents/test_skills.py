"""
新增 Skill 工具测试
"""

import pytest
from unittest.mock import MagicMock
from langchain_core.documents import Document


class TestCompareDocumentsSkill:
    """compare_documents 工具测试"""

    def _make_tool(self, llm_manager=None):
        from src.agents.tools import create_compare_documents_tool
        vs = MagicMock()
        vs.hybrid_search = MagicMock(return_value=[
            Document(page_content="RAG是检索增强生成技术", metadata={"source": "a"}),
        ])
        return create_compare_documents_tool(vs, llm_manager)

    def test_compare_with_llm(self):
        """测试有 LLM 时生成对比分析"""
        llm = MagicMock()
        llm.generate.return_value = {"text": "RAG和向量搜索的区别是..."}
        tool = self._make_tool(llm)

        result = tool(topic_a="RAG", topic_b="向量搜索")
        assert "区别" in result
        llm.generate.assert_called_once()

    def test_compare_without_llm(self):
        """测试无 LLM 时返回原始检索结果"""
        tool = self._make_tool(llm_manager=None)

        result = tool(topic_a="RAG", topic_b="向量搜索")
        assert "RAG" in result
        assert "向量搜索" in result

    def test_compare_no_results(self):
        """测试两个主题都无结果"""
        from src.agents.tools import create_compare_documents_tool
        vs = MagicMock()
        vs.hybrid_search.return_value = []
        tool = create_compare_documents_tool(vs, llm_manager=None)

        result = tool(topic_a="不存在主题A", topic_b="不存在主题B")
        assert "未找到" in result


class TestTraceSourceSkill:
    """trace_source 工具测试"""

    def _make_tool(self):
        from src.agents.tools import create_trace_source_tool
        return create_trace_source_tool()

    def test_trace_full_match(self):
        """测试完全匹配的溯源"""
        tool = self._make_tool()

        answer = "RAG是检索增强生成技术。"
        documents = ["RAG是检索增强生成技术，它结合了检索和生成。"]
        result = tool(answer, documents)

        assert "1/1" in result
        assert "✓" in result

    def test_trace_partial_match(self):
        """测试部分匹配的溯源"""
        tool = self._make_tool()

        answer = "RAG是检索增强技术。向量搜索也很重要。"
        documents = [
            "RAG是检索增强生成技术。",  # 第一句有重叠
            # 第二句无相关文档
        ]
        result = tool(answer, documents)

        assert "✓" in result
        assert "✗" in result

    def test_trace_no_match(self):
        """测试无匹配的溯源"""
        tool = self._make_tool()

        answer = "量子计算是未来趋势。"
        documents = ["RAG是检索增强技术。"]
        result = tool(answer, documents)

        assert "0/1" in result
        assert "无法溯源" in result

    def test_trace_empty_answer(self):
        """测试空答案"""
        tool = self._make_tool()

        result = tool("", ["一些文档内容"])
        assert "为空" in result

    def test_trace_empty_documents(self):
        """测试空文档列表"""
        tool = self._make_tool()

        answer = "RAG是检索增强技术。"
        result = tool(answer, [])

        assert "0/1" in result
        assert "无法溯源" in result

    def test_trace_multiple_sentences(self):
        """测试多句溯源"""
        tool = self._make_tool()

        answer = "RAG是检索增强技术。ChromaDB是向量数据库。LangChain是框架。"
        documents = [
            "RAG是检索增强生成技术，广泛用于知识库。",
            "ChromaDB是一个开源向量数据库。",
        ]
        result = tool(answer, documents)

        # 前两句应能溯源，第三句不能
        assert "2/3" in result
