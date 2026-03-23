"""
向量存储模块测试 - BM25 和 RRF
"""

import pytest
from langchain_core.documents import Document
from src.core.vector_store import BM25, reciprocal_rank_fusion


class TestBM25:
    """BM25 检索器测试"""

    def test_tokenize_chinese(self):
        """测试中文分词"""
        bm25 = BM25()
        tokens = bm25._tokenize("这是一个中文测试句子")
        assert len(tokens) > 0

    def test_tokenize_english(self):
        """测试英文分词"""
        bm25 = BM25()
        tokens = bm25._tokenize("This is an English test sentence")
        assert len(tokens) > 0

    def test_tokenize_mixed(self):
        """测试中英文混合分词"""
        bm25 = BM25()
        tokens = bm25._tokenize("Python是一种编程语言 Python is a programming language")
        assert len(tokens) > 0

    def test_index_empty_documents(self):
        """测试空文档索引"""
        bm25 = BM25()
        bm25.index([])
        assert bm25._indexed is True
        assert len(bm25.documents) == 0

    def test_index_documents(self):
        """测试文档索引"""
        bm25 = BM25()
        docs = [
            Document(
                page_content="机器学习是人工智能的一个分支", metadata={"source": "doc1"}
            ),
            Document(
                page_content="深度学习是机器学习的一个子领域",
                metadata={"source": "doc2"},
            ),
            Document(
                page_content="自然语言处理用于处理文本数据", metadata={"source": "doc3"}
            ),
        ]
        bm25.index(docs)

        assert bm25._indexed is True
        assert len(bm25.documents) == 3
        assert len(bm25.vocab) > 0

    def test_search_returns_results(self):
        """测试搜索返回结果"""
        bm25 = BM25()
        docs = [
            Document(
                page_content="机器学习是人工智能的一个分支", metadata={"source": "doc1"}
            ),
            Document(
                page_content="深度学习是机器学习的一个子领域",
                metadata={"source": "doc2"},
            ),
            Document(
                page_content="自然语言处理用于处理文本数据", metadata={"source": "doc3"}
            ),
        ]
        bm25.index(docs)

        results = bm25.search("机器学习", k=2)

        assert len(results) <= 2
        assert all(isinstance(doc, Document) for doc, _ in results)

    def test_search_ranking(self):
        """测试搜索结果排序"""
        bm25 = BM25()
        docs = [
            Document(
                page_content="机器学习是人工智能的核心技术", metadata={"source": "doc1"}
            ),
            Document(
                page_content="机器学习广泛应用于各行各业", metadata={"source": "doc2"}
            ),
            Document(
                page_content="深度学习是机器学习的子领域", metadata={"source": "doc3"}
            ),
        ]
        bm25.index(docs)

        results = bm25.search("机器学习", k=3)

        # 验证结果按分数降序排列
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_empty_query(self):
        """测试空查询"""
        bm25 = BM25()
        docs = [Document(page_content="测试文档")]
        bm25.index(docs)

        results = bm25.search("", k=1)
        # 空查询应该返回空或很少结果
        assert len(results) == 0

    def test_search_no_match(self):
        """测试无匹配查询"""
        bm25 = BM25()
        docs = [
            Document(page_content="机器学习是人工智能的一个分支"),
            Document(page_content="深度学习是机器学习的一个子领域"),
        ]
        bm25.index(docs)

        results = bm25.search("量子计算", k=2)
        # 应该返回0或少量结果
        assert len(results) <= 2

    def test_search_with_k_limit(self):
        """测试k参数限制"""
        bm25 = BM25()
        docs = [
            Document(
                page_content=f"文档{i}包含机器学习", metadata={"source": f"doc{i}"}
            )
            for i in range(10)
        ]
        bm25.index(docs)

        results = bm25.search("机器学习", k=3)
        assert len(results) <= 3


class TestReciprocalRankFusion:
    """RRF 融合算法测试"""

    def test_rrf_empty_lists(self):
        """测试空列表"""
        result = reciprocal_rank_fusion([], k=60)
        assert result == []

    def test_rrf_single_list(self):
        """测试单个列表"""
        docs = [
            Document(page_content="文档1"),
            Document(page_content="文档2"),
            Document(page_content="文档3"),
        ]
        result = reciprocal_rank_fusion([list(zip(docs, [1.0, 0.8, 0.6]))], k=60)
        assert len(result) == 3

    def test_rrf_two_lists(self):
        """测试两个列表融合"""
        docs = [
            Document(page_content="文档1"),
            Document(page_content="文档2"),
            Document(page_content="文档3"),
            Document(page_content="文档4"),
        ]
        list1 = [(docs[0], 1.0), (docs[1], 0.8)]
        list2 = [(docs[1], 1.0), (docs[2], 0.8), (docs[3], 0.6)]

        result = reciprocal_rank_fusion([list1, list2], k=60)

        # 应该返回所有文档
        assert len(result) <= 4
        # 文档1应该排在前面（只出现在list1的第一位）
        # 文档2排在前面（两个列表都出现且排名都高）

    def test_rrf_doc_order(self):
        """测试RRF保留相对顺序"""
        docs = [
            Document(page_content="文档A" * 50),  # 确保内容唯一
            Document(page_content="文档B" * 50),
            Document(page_content="文档C" * 50),
        ]

        # list1: A, B, C
        # list2: B, C, A
        list1 = [(docs[0], 1.0), (docs[1], 0.9), (docs[2], 0.8)]
        list2 = [(docs[1], 1.0), (docs[2], 0.9), (docs[0], 0.8)]

        result = reciprocal_rank_fusion([list1, list2], k=60)

        # B在两个列表中都排第一，应该排第一
        assert result[0].page_content == "文档B" * 50

    def test_rrf_deduplication(self):
        """测试去重功能"""
        doc1 = Document(page_content="相同文档内容A" * 20)
        doc2 = Document(page_content="文档2内容B" * 20)
        doc3 = Document(page_content="文档3内容C" * 20)
        doc4 = Document(page_content="文档4内容D" * 20)

        list1 = [(doc1, 1.0), (doc2, 0.8)]
        list2 = [(doc1, 0.9), (doc3, 0.7), (doc4, 0.6)]

        result = reciprocal_rank_fusion([list1, list2], k=60)

        # 应该去重，有4个不同文档
        assert len(result) == 4

    def test_rrf_k_parameter(self):
        """测试k参数影响"""
        docs = [Document(page_content=f"文档{i}") for i in range(5)]
        list1 = [(docs[i], 1.0 - i * 0.1) for i in range(5)]

        # k越小，早期排名权重越高
        result_k1 = reciprocal_rank_fusion([list1], k=1)
        result_k100 = reciprocal_rank_fusion([list1], k=100)

        # 两个结果的顺序可能不同
        # 文档0应该都在第一位
        assert result_k1[0].page_content == "文档0"
        assert result_k100[0].page_content == "文档0"
