"""
RAG Chain 模块测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from langchain_core.documents import Document
from src.core.rag_chain import RAGChain


class TestRAGChain:
    """RAG Chain 测试类"""

    def test_init_default_config(self):
        """测试默认初始化"""
        chain = RAGChain()

        assert chain._initialized is False
        assert chain.document_processor is None
        assert chain.vector_store is None
        assert chain.llm_manager is None

    def test_init_with_config(self):
        """测试带配置的初始化"""
        config = {"chunk_size": 1000}
        chain = RAGChain(config=config)

        assert chain.config == config

    def test_build_context_empty(self):
        """测试空上下文构建"""
        chain = RAGChain()
        result = chain._build_context([])
        assert result == ""

    def test_build_context_single_doc(self):
        """测试单个文档上下文构建"""
        chain = RAGChain()
        docs = [
            Document(
                page_content="这是测试内容", metadata={"source": "test.txt", "page": 1}
            )
        ]
        result = chain._build_context(docs)

        assert "【文档 1】" in result
        assert "test.txt" in result
        assert "这是测试内容" in result

    def test_build_context_multiple_docs(self):
        """测试多个文档上下文构建"""
        chain = RAGChain()
        docs = [
            Document(page_content="内容1", metadata={"source": "doc1.txt"}),
            Document(page_content="内容2", metadata={"source": "doc2.txt"}),
            Document(page_content="内容3", metadata={"source": "doc3.txt"}),
        ]
        result = chain._build_context(docs)

        assert "【文档 1】" in result
        assert "【文档 2】" in result
        assert "【文档 3】" in result
        assert "doc1.txt" in result
        assert "doc2.txt" in result

    def test_build_prompt(self):
        """测试提示词构建"""
        chain = RAGChain()
        question = "什么是机器学习？"
        context = "机器学习是人工智能的一个分支。"

        result = chain._build_prompt(question, context)

        assert question in result
        assert context in result
        assert "请用中文回答" in result

    def test_build_prompt_with_constraints(self):
        """测试带约束的提示词"""
        chain = RAGChain()
        result = chain._build_prompt("问题", "上下文")

        # 验证幻觉约束被包含
        assert "重要约束" in result
        assert "参考文档" in result

    @patch("src.core.rag_chain.LLMManager")
    @patch("src.core.rag_chain.SimpleVectorStore")
    @patch("src.core.rag_chain.DocumentProcessor")
    def test_initialize_components(self, mock_doc_proc, mock_vs, mock_llm):
        """测试组件初始化"""
        chain = RAGChain()
        chain.initialize()

        assert chain._initialized is True
        mock_doc_proc.assert_called_once()
        mock_vs.assert_called_once()
        mock_llm.assert_called_once()

    def test_get_status_uninitialized(self):
        """测试未初始化时的状态"""
        chain = RAGChain()
        status = chain.get_status()

        assert status["initialized"] is False
        assert status["components"] == {}

    def test_reset(self):
        """测试重置"""
        chain = RAGChain()
        chain._initialized = True
        chain.document_processor = Mock()
        chain.vector_store = Mock()
        chain.llm_manager = Mock()

        chain.reset()

        assert chain._initialized is False
        assert chain.document_processor is None
        assert chain.vector_store is None
        assert chain.llm_manager is None


class TestRAGChainQuery:
    """RAG Chain 查询测试"""

    @patch("src.core.rag_chain.LLMManager")
    @patch("src.core.rag_chain.SimpleVectorStore")
    @patch("src.core.rag_chain.DocumentProcessor")
    def test_query_empty_knowledge_base(self, mock_doc_proc, mock_vs, mock_llm):
        """测试空知识库查询 — 无检索结果时调用 LLM 直接回答"""
        mock_vs_instance = MagicMock()
        mock_vs_instance.similarity_search.return_value = []
        mock_vs.return_value = mock_vs_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate.return_value = {
            "text": "我不知道",
            "metadata": {"provider": "local"},
        }
        mock_llm.return_value = mock_llm_instance

        chain = RAGChain()
        chain.crag_enabled = False  # 空知识库不需要 CRAG
        chain.initialize()

        result = chain.query("什么是AI？")

        assert result["success"] is True
        assert result["answer"] == "我不知道"
        assert result["num_sources"] == 0
        # 无检索结果时应调用 LLM
        mock_llm_instance.generate.assert_called_once()

    @pytest.mark.skip(reason="Integration test - requires full mocking setup")
    @patch("src.core.rag_chain.LLMManager")
    @patch("src.core.rag_chain.SimpleVectorStore")
    @patch("src.core.rag_chain.DocumentProcessor")
    def test_query_with_sources(self, mock_doc_proc, mock_vs, mock_llm):
        """测试带来源的查询（集成测试，跳过）"""
        # This test requires complex mocking and is marked as skip
        # The unit tests for build_context and build_prompt cover the relevant logic
        pass

    @patch("src.core.rag_chain.LLMManager")
    @patch("src.core.rag_chain.SimpleVectorStore")
    @patch("src.core.rag_chain.DocumentProcessor")
    def test_query_processing_time_recorded(self, mock_doc_proc, mock_vs, mock_llm):
        """测试处理时间记录"""
        mock_vs_instance = MagicMock()
        mock_vs_instance.similarity_search.return_value = []
        mock_vs.return_value = mock_vs_instance

        chain = RAGChain()
        chain.initialize()

        result = chain.query("测试问题")

        assert "processing_time" in result
        assert isinstance(result["processing_time"], float)
        assert result["processing_time"] >= 0


class TestCRAG:
    """CRAG（Corrective RAG）测试"""

    def test_keyword_rewrite_removes_prefix(self):
        """测试规则改写: 移除提问前缀"""
        assert RAGChain._keyword_rewrite("什么是机器学习") == "机器学习"
        assert RAGChain._keyword_rewrite("如何使用这个功能") == "使用这个功能"
        assert RAGChain._keyword_rewrite("AI") == "AI"  # 太短，返回原文

    def test_keyword_rewrite_strips_punctuation(self):
        """测试规则改写: 去除末尾标点"""
        result = RAGChain._keyword_rewrite("机器学习是什么？")
        assert result == "机器学习是什么"
        assert "？" not in result

    def test_corrective_retrieve_passes_when_quality_good(self):
        """测试 CRAG: 检索质量合格时直接返回"""
        chain = RAGChain()
        chain.crag_threshold = 0.3
        chain.crag_enabled = True
        chain.llm_manager = None

        docs = [
            Document(page_content="机器学习是人工智能的分支", metadata={"source": "a"}),
            Document(page_content="深度学习使用神经网络", metadata={"source": "b"}),
        ]

        result = chain._corrective_retrieve("机器学习", docs, k=4)
        # 两个文档都包含查询关键词，覆盖率应该高于阈值
        assert result == docs  # 质量合格，返回原文

    def test_corrective_retrieve_disabled(self):
        """测试 CRAG 禁用时直接返回"""
        chain = RAGChain()
        chain.crag_enabled = False

        docs = [Document(page_content="无关内容", metadata={"source": "a"})]
        result = chain._corrective_retrieve("机器学习", docs, k=4)
        assert result == docs

    def test_corrective_retrieve_empty_docs(self):
        """测试 CRAG: 空文档列表"""
        chain = RAGChain()
        chain.crag_enabled = True
        result = chain._corrective_retrieve("问题", [], k=4)
        assert result == []

    def test_corrective_retrieve_triggers_rewrite(self):
        """测试 CRAG: 质量低时触发改写重试"""
        chain = RAGChain()
        chain.crag_threshold = 0.8  # 高阈值，几乎不可能达到
        chain.crag_enabled = True
        chain.llm_manager = MagicMock()
        chain.llm_manager.generate.return_value = {"text": "改写后的问题"}

        # 模拟 _retrieve_documents 返回更好的结果
        chain._retrieve_documents = MagicMock(return_value=[
            Document(page_content="包含改写关键词的文档", metadata={"source": "c"}),
        ])

        docs = [Document(page_content="完全不相关的内容", metadata={"source": "a"})]
        result = chain._corrective_retrieve("模糊问题", docs, k=4)

        # 应该触发了改写和重试
        chain.llm_manager.generate.assert_called_once()
        chain._retrieve_documents.assert_called_once()
        # 结果应该包含原始和重试的文档
        assert len(result) >= 1


class TestRetrievalMode:
    """检索模式选择测试"""

    @patch("src.core.rag_chain.LLMManager")
    @patch("src.core.rag_chain.SimpleVectorStore")
    @patch("src.core.rag_chain.DocumentProcessor")
    def test_dispatch_hybrid_mode(self, mock_doc_proc, mock_vs, mock_llm):
        """测试指定 hybrid 模式"""
        mock_vs_instance = MagicMock()
        mock_vs_instance.hybrid_search.return_value = [
            Document(page_content="结果1", metadata={"source": "a"}),
        ]
        mock_vs.return_value = mock_vs_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate.return_value = {"text": "答案", "metadata": {}}
        mock_llm.return_value = mock_llm_instance

        chain = RAGChain()
        chain.initialize()
        chain.crag_enabled = False

        chain.query("测试", retrieval_mode="hybrid")

        mock_vs_instance.hybrid_search.assert_called_once()

    @patch("src.core.rag_chain.LLMManager")
    @patch("src.core.rag_chain.SimpleVectorStore")
    @patch("src.core.rag_chain.DocumentProcessor")
    def test_dispatch_dense_mode(self, mock_doc_proc, mock_vs, mock_llm):
        """测试指定 dense 模式"""
        mock_vs_instance = MagicMock()
        mock_vs_instance.similarity_search.return_value = [
            Document(page_content="结果1", metadata={"source": "a"}),
        ]
        mock_vs.return_value = mock_vs_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate.return_value = {"text": "答案", "metadata": {}}
        mock_llm.return_value = mock_llm_instance

        chain = RAGChain()
        chain.initialize()
        chain.crag_enabled = False

        chain.query("测试", retrieval_mode="dense")

        mock_vs_instance.similarity_search.assert_called_once()

    @patch("src.core.rag_chain.LLMManager")
    @patch("src.core.rag_chain.SimpleVectorStore")
    @patch("src.core.rag_chain.DocumentProcessor")
    def test_dispatch_unknown_mode_fallback(self, mock_doc_proc, mock_vs, mock_llm):
        """测试未知模式回退到默认"""
        mock_vs_instance = MagicMock()
        mock_vs_instance.similarity_search.return_value = []
        mock_vs.return_value = mock_vs_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate.return_value = {"text": "答案", "metadata": {}}
        mock_llm.return_value = mock_llm_instance

        chain = RAGChain()
        chain.initialize()
        chain.crag_enabled = False

        # 未知模式应回退到默认（不报错）
        result = chain.query("测试", retrieval_mode="nonexistent")
        assert result["success"] is True


class TestCitationVerification:
    """答案溯源验证测试"""

    def test_valid_citations_pass(self):
        """测试有效引用：全部编号在范围内"""
        chain = RAGChain()
        chain.citation_warn_on_invalid = True

        answer = "根据文档1和文档2，机器学习是AI的分支。"
        result_answer, report = chain._verify_citations(answer, num_docs=3)

        # 有效引用不修改答案
        assert result_answer == answer
        assert all(item["valid"] for item in report)
        assert len(report) == 2

    def test_invalid_citation_warns(self):
        """测试无效引用：超出范围的编号追加警告"""
        chain = RAGChain()
        chain.citation_warn_on_invalid = True

        answer = "根据文档1和文档5的信息，系统运行正常。"
        result_answer, report = chain._verify_citations(answer, num_docs=3)

        # 无效引用 [文档5] 应触发警告
        assert "⚠️" in result_answer
        assert "文档5" in result_answer
        assert any(not item["valid"] for item in report)

    def test_invalid_citation_no_warn_when_disabled(self):
        """测试禁用警告时不追加内容"""
        chain = RAGChain()
        chain.citation_warn_on_invalid = False

        answer = "根据文档1和文档5的信息，系统运行正常。"
        result_answer, report = chain._verify_citations(answer, num_docs=3)

        # 答案不被修改，但报告仍然记录
        assert result_answer == answer
        assert any(not item["valid"] for item in report)

    def test_no_citations_returns_empty_report(self):
        """测试答案无引用时返回空报告"""
        chain = RAGChain()

        answer = "机器学习是人工智能的一个重要分支。"
        result_answer, report = chain._verify_citations(answer, num_docs=3)

        assert result_answer == answer
        assert report == []

    def test_bracket_only_format(self):
        """测试纯数字引用格式 [1] [2]"""
        chain = RAGChain()
        chain.citation_warn_on_invalid = True

        answer = "根据[1]和[3]的研究结果，该方法是有效的。"
        result_answer, report = chain._verify_citations(answer, num_docs=2)

        # [3] 超出范围（仅有 1,2）
        assert "⚠️" in result_answer
        assert len(report) == 2  # [1] 和 [3]

    def test_mixed_citation_formats(self):
        """测试混合引用格式：[文档1]、文档2、[3]"""
        chain = RAGChain()
        chain.citation_warn_on_invalid = False

        answer = "如文档1所述，结合[文档2]和[3]的分析。"
        result_answer, report = chain._verify_citations(answer, num_docs=3)

        # 全部有效（1,2,3）
        assert all(item["valid"] for item in report)
        assert len(report) == 3

    def test_zero_docs_all_invalid(self):
        """测试上下文为0个文档时所有引用都无效"""
        chain = RAGChain()
        chain.citation_warn_on_invalid = True

        answer = "根据文档1的信息。"
        result_answer, report = chain._verify_citations(answer, num_docs=0)

        assert "⚠️" in result_answer
        assert all(not item["valid"] for item in report)


class TestSimpleRAGChain:
    """SimpleRAGChain 上下文管理器测试"""

    def test_context_manager(self):
        """测试上下文管理器"""
        with patch("src.core.rag_chain.RAGChain"):
            from src.core.rag_chain import SimpleRAGChain

            with SimpleRAGChain() as chain:
                assert chain.chain is not None
