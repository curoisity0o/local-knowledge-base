"""
QueryClassifier 测试
"""

import pytest
from unittest.mock import MagicMock
from src.agents.classifier import QueryClassifier, SIMPLE, COMPLEX


class TestQueryClassifier:
    """查询分类器测试"""

    def test_classify_simple_factual(self):
        """测试简单事实问题"""
        llm = MagicMock()
        llm.generate.return_value = {"text": "simple"}
        classifier = QueryClassifier(llm)

        assert classifier.classify("什么是RAG") == SIMPLE

    def test_classify_complex_comparison(self):
        """测试复杂对比问题"""
        llm = MagicMock()
        llm.generate.return_value = {"text": "complex"}
        classifier = QueryClassifier(llm)

        assert classifier.classify("RAG和向量搜索有什么区别") == COMPLEX

    def test_classify_llm_failure_fallback(self):
        """测试 LLM 失败时 fallback 到 simple"""
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("LLM 不可用")
        classifier = QueryClassifier(llm)
        classifier._fallback = SIMPLE

        assert classifier.classify("任意问题") == SIMPLE

    def test_classify_unparseable_output_fallback(self):
        """测试 LLM 输出无法解析时 fallback"""
        llm = MagicMock()
        llm.generate.return_value = {"text": "我无法判断这个问题"}
        classifier = QueryClassifier(llm)
        classifier._fallback = SIMPLE

        assert classifier.classify("某个问题") == SIMPLE

    def test_classify_no_llm_fallback(self):
        """测试无 LLM 时 fallback"""
        classifier = QueryClassifier(llm_manager=None)
        classifier._fallback = SIMPLE

        assert classifier.classify("什么是AI") == SIMPLE

    def test_classify_empty_query(self):
        """测试空查询"""
        classifier = QueryClassifier(llm_manager=None)

        assert classifier.classify("") == SIMPLE
        assert classifier.classify("   ") == SIMPLE

    def test_classify_case_insensitive(self):
        """测试大小写不敏感"""
        llm = MagicMock()
        llm.generate.return_value = {"text": "Complex"}
        classifier = QueryClassifier(llm)

        assert classifier.classify("比较A和B") == COMPLEX

    def test_classify_llm_called_with_prompt(self):
        """测试 LLM 调用时传入了正确的 prompt"""
        llm = MagicMock()
        llm.generate.return_value = {"text": "simple"}
        classifier = QueryClassifier(llm)
        classifier.classify("测试问题")

        llm.generate.assert_called_once()
        prompt = llm.generate.call_args[0][0]
        assert "测试问题" in prompt
        assert "simple" in prompt.lower()
        assert "complex" in prompt.lower()
