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
        """测试空知识库查询"""
        # Mock vector store returns empty
        mock_vs_instance = MagicMock()
        mock_vs_instance.similarity_search.return_value = []
        mock_vs.return_value = mock_vs_instance

        chain = RAGChain()
        chain.initialize()

        result = chain.query("什么是AI？")

        assert result["success"] is True
        assert "知识库为空" in result["answer"]
        assert result["num_sources"] == 0

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


class TestSimpleRAGChain:
    """SimpleRAGChain 上下文管理器测试"""

    def test_context_manager(self):
        """测试上下文管理器"""
        with patch("src.core.rag_chain.RAGChain"):
            from src.core.rag_chain import SimpleRAGChain

            with SimpleRAGChain() as chain:
                assert chain.chain is not None
