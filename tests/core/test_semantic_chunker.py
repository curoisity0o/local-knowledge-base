"""
SemanticChunker 单元测试
"""

import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document
from src.core.document_processor import SemanticChunker


class TestSemanticChunkerSentenceSplit:
    """句子分割测试"""

    def test_split_chinese_sentences(self):
        """测试中文句子分割"""
        text = "这是第一句话。这是第二句话。这是第三句话。"
        sentences = SemanticChunker._split_sentences(text)
        assert len(sentences) == 3
        assert "这是第一句话。" in sentences

    def test_split_english_sentences(self):
        """测试英文句子分割"""
        text = "First sentence. Second sentence. Third sentence."
        sentences = SemanticChunker._split_sentences(text)
        assert len(sentences) == 3

    def test_split_mixed_sentences(self):
        """测试中英文混合分割"""
        text = "机器学习是AI的分支。Machine learning is a subset of AI."
        sentences = SemanticChunker._split_sentences(text)
        assert len(sentences) == 2

    def test_split_short_text(self):
        """测试短文本（保留）"""
        sentences = SemanticChunker._split_sentences("短文本")
        # "短文本" 3 个字符，满足 > 2 的过滤条件，且没有句末标点不会分割
        assert len(sentences) == 1

    def test_split_empty_text(self):
        """测试空文本"""
        sentences = SemanticChunker._split_sentences("")
        assert sentences == []


class TestSemanticChunkerNormalize:
    """chunk 后处理测试"""

    def test_normalize_merges_short_chunks(self):
        """测试合并过短的 chunk"""
        chunker = SemanticChunker(
            embedder=MagicMock(),
            min_chunk_size=50,
            max_chunk_size=500,
        )
        chunks = ["短", "中间长度的文本内容大约二十个字符左右", "另一个正常的chunk"]
        result = chunker._normalize_chunks(chunks)
        # 第一个 chunk 太短，应合并到第二个
        assert all(len(c) >= 50 or len(result) == 1 for c in result)

    def test_normalize_empty(self):
        """测试空列表"""
        chunker = SemanticChunker(min_chunk_size=200, max_chunk_size=1000)
        result = chunker._normalize_chunks([])
        assert result == []


class TestSemanticChunkerSplitText:
    """语义分块集成测试（mock embedder）"""

    def _make_chunker(self, similarities):
        """创建 mock embedder，返回指定相似度"""
        embedder = MagicMock()
        # embed_documents 返回任意 embedding（不影响相似度计算，因为被 mock）
        # 我们需要 mock _compute_similarities 而非 embedder
        chunker = SemanticChunker(
            embedder=embedder,
            breakpoint_threshold=0.3,
            min_chunk_size=10,
            max_chunk_size=500,
        )
        return chunker

    def test_single_sentence(self):
        """测试单句文本"""
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=500)
        result = chunker.split_text("只有一个句子。")
        assert len(result) == 1
        assert "只有一个句子" in result[0]

    def test_empty_text(self):
        """测试空文本"""
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=500)
        result = chunker.split_text("")
        assert result == []

    @patch.object(SemanticChunker, "_compute_similarities")
    def test_breakpoint_detection(self, mock_sim):
        """测试断点检测"""
        # 4 个句子，2-3 之间相似度低（断点）
        mock_sim.return_value = [0.9, 0.15, 0.8]
        chunker = SemanticChunker(
            min_chunk_size=5, max_chunk_size=500, breakpoint_threshold=0.3,
        )
        text = "句子一。句子二。句子三。句子四。"
        result = chunker.split_text(text)

        # 应该在 0.15 处断开，产生 2 个 chunk
        assert len(result) == 2

    @patch.object(SemanticChunker, "_compute_similarities")
    def test_no_breakpoint(self, mock_sim):
        """测试无断点（全部高相似度）"""
        mock_sim.return_value = [0.9, 0.95, 0.88]
        chunker = SemanticChunker(
            min_chunk_size=5, max_chunk_size=500, breakpoint_threshold=0.3,
        )
        text = "句子一。句子二。句子三。句子四。"
        result = chunker.split_text(text)

        # 全部高于阈值，不切分
        assert len(result) == 1

    @patch.object(SemanticChunker, "_compute_similarities")
    def test_all_breakpoints(self, mock_sim):
        """测试每个位置都是断点"""
        mock_sim.return_value = [0.1, 0.05, 0.12]
        chunker = SemanticChunker(
            min_chunk_size=5, max_chunk_size=500, breakpoint_threshold=0.3,
        )
        text = "句子一。句子二。句子三。句子四。"
        result = chunker.split_text(text)

        # 每个位置都断开，但过短的会被合并
        assert len(result) >= 1


class TestSemanticChunkerSplitDocuments:
    """文档列表分块测试"""

    @patch.object(SemanticChunker, "split_text")
    def test_split_documents_preserves_metadata(self, mock_split):
        """测试分块保留 metadata"""
        mock_split.return_value = ["chunk1内容", "chunk2内容"]
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=500)

        docs = [
            Document(page_content="原文", metadata={"source": "test.pdf", "page": 3})
        ]
        result = chunker.split_documents(docs)

        assert len(result) == 2
        assert result[0].page_content == "chunk1内容"
        assert result[0].metadata["source"] == "test.pdf"
        assert result[0].metadata["page"] == 3

    @patch.object(SemanticChunker, "split_text")
    def test_split_documents_empty(self, mock_split):
        """测试空文档列表"""
        mock_split.return_value = []
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=500)
        result = chunker.split_documents([])
        assert result == []
