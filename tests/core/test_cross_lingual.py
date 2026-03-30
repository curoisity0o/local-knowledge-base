"""
BGE-M3 跨语言检索验证测试

验证 BGE-M3 多语言嵌入模型对中英文交叉查询的检索效果。
需要 Ollama 服务运行 + bge-m3 模型已下载。

运行方式：
    pytest tests/core/test_cross_lingual.py -v -m integration
"""

import os
import tempfile

import pytest
from langchain_core.documents import Document

pytestmark = pytest.mark.integration


# ---------- 测试文档集 ----------

ZH_DOCS = [
    Document(
        page_content="机器学习是人工智能的一个核心分支，通过数据训练模型来做出预测或决策。",
        metadata={"source": "zh_ai.txt", "lang": "zh"},
    ),
    Document(
        page_content="深度学习使用多层神经网络来学习数据的层次化表示，广泛应用于图像识别和自然语言处理。",
        metadata={"source": "zh_dl.txt", "lang": "zh"},
    ),
    Document(
        page_content="RAG（检索增强生成）结合了信息检索和文本生成，通过外部知识库增强大语言模型的回答质量。",
        metadata={"source": "zh_rag.txt", "lang": "zh"},
    ),
    Document(
        page_content="向量数据库专门用于存储和检索高维向量，是语义搜索和推荐系统的关键基础设施。",
        metadata={"source": "zh_vectordb.txt", "lang": "zh"},
    ),
]

EN_DOCS = [
    Document(
        page_content="Machine learning is a core branch of artificial intelligence that trains models on data "
        "to make predictions or decisions.",
        metadata={"source": "en_ai.txt", "lang": "en"},
    ),
    Document(
        page_content="Deep learning uses multi-layer neural networks to learn hierarchical representations "
        "of data, widely used in image recognition and natural language processing.",
        metadata={"source": "en_dl.txt", "lang": "en"},
    ),
    Document(
        page_content="RAG (Retrieval Augmented Generation) combines information retrieval with text generation "
        "to enhance the quality of answers from large language models using external knowledge bases.",
        metadata={"source": "en_rag.txt", "lang": "en"},
    ),
    Document(
        page_content="Vector databases are specialized for storing and retrieving high-dimensional vectors, "
        "serving as key infrastructure for semantic search and recommendation systems.",
        metadata={"source": "en_vectordb.txt", "lang": "en"},
    ),
]


def _check_ollama():
    """检查 Ollama 是否可用"""
    import subprocess

    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        if "bge-m3" in result.stdout:
            return True
        pytest.skip("bge-m3 模型未安装，请运行: ollama pull bge-m3")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Ollama 服务不可用")


def _create_temp_store(documents):
    """创建临时向量存储并索引文档"""
    _check_ollama()

    try:
        from langchain_chroma import Chroma
    except ImportError:
        from langchain_community.vectorstores import Chroma

    from src.core.vector_store import SimpleVectorStore

    tmpdir = tempfile.mkdtemp(prefix="bge3_test_")
    store = SimpleVectorStore.__new__(SimpleVectorStore)
    store.config = {}
    store.embedder = None
    store.vector_store = None
    store.reranker = None
    store._initialized = False
    store.store_type = "chroma"

    try:
        from langchain_ollama import OllamaEmbeddings
    except ImportError:
        from langchain_community.embeddings import OllamaEmbeddings

    store.embedder = OllamaEmbeddings(
        model="bge-m3", base_url="http://localhost:11434"
    )

    store.vector_store = Chroma(
        embedding_function=store.embedder,
        persist_directory=tmpdir,
        collection_name="test_cross_lingual",
    )
    store._initialized = True
    store.vector_store.add_documents(documents)

    yield store

    # 清理（忽略 Windows 文件锁）
    import shutil
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


# ---------- 测试用例 ----------


class TestCrossLingualBaseline:
    """基线测试：同语言查询应能命中对应文档"""

    def test_zh_query_zh_docs(self):
        """中文查询 → 中文文档（基线）"""
        for store in _create_temp_store(ZH_DOCS):
            results = store.similarity_search("什么是机器学习", k=2)
            contents = [d.page_content for d in results]
            assert any("机器学习" in c for c in contents), (
                f"中文基线失败: 未命中中文文档。结果: {contents}"
            )

    def test_en_query_en_docs(self):
        """英文查询 → 英文文档（基线）"""
        for store in _create_temp_store(EN_DOCS):
            results = store.similarity_search("what is machine learning", k=2)
            contents = [d.page_content for d in results]
            assert any("machine learning" in c.lower() for c in contents), (
                f"英文基线失败: 未命中英文文档。结果: {contents}"
            )


class TestCrossLingualZH2EN:
    """中文查询 → 英文文档（跨语言）"""

    def test_zh_query_finds_en_machine_learning(self):
        """中文"机器学习" → 应命中英文 ML 文档"""
        for store in _create_temp_store(EN_DOCS):
            results = store.similarity_search("机器学习", k=3)
            contents = [d.page_content for d in results]
            found_ml = any("machine learning" in c.lower() for c in contents)
            print(f"\n中文查询'机器学习' → 英文文档结果:")
            for i, d in enumerate(results):
                print(f"  [{i}] {d.metadata.get('source', '?')}: {d.page_content[:80]}...")
            assert found_ml, (
                f"跨语言 ZH→EN 失败: '机器学习' 未命中英文 ML 文档。结果: {contents}"
            )

    def test_zh_query_finds_en_rag(self):
        """中文"检索增强生成" → 应命中英文 RAG 文档"""
        for store in _create_temp_store(EN_DOCS):
            results = store.similarity_search("检索增强生成", k=3)
            contents = [d.page_content for d in results]
            found_rag = any("rag" in c.lower() or "retrieval" in c.lower() for c in contents)
            print(f"\n中文查询'检索增强生成' → 英文文档结果:")
            for i, d in enumerate(results):
                print(f"  [{i}] {d.metadata.get('source', '?')}: {d.page_content[:80]}...")
            assert found_rag, (
                f"跨语言 ZH→EN 失败: '检索增强生成' 未命中英文 RAG 文档。结果: {contents}"
            )

    def test_zh_query_finds_en_vector_db(self):
        """中文"向量数据库" → 应命中英文 vector database 文档"""
        for store in _create_temp_store(EN_DOCS):
            results = store.similarity_search("向量数据库", k=3)
            contents = [d.page_content for d in results]
            found_vdb = any("vector" in c.lower() for c in contents)
            print(f"\n中文查询'向量数据库' → 英文文档结果:")
            for i, d in enumerate(results):
                print(f"  [{i}] {d.metadata.get('source', '?')}: {d.page_content[:80]}...")
            assert found_vdb, (
                f"跨语言 ZH→EN 失败: '向量数据库' 未命中英文 vector DB 文档。结果: {contents}"
            )


class TestCrossLingualEN2ZH:
    """英文查询 → 中文文档（跨语言反向）"""

    def test_en_query_finds_zh_machine_learning(self):
        """英文"machine learning" → 应命中中文机器学习文档"""
        for store in _create_temp_store(ZH_DOCS):
            results = store.similarity_search("machine learning", k=3)
            contents = [d.page_content for d in results]
            found_ml = any("机器学习" in c for c in contents)
            print(f"\n英文查询'machine learning' → 中文文档结果:")
            for i, d in enumerate(results):
                print(f"  [{i}] {d.metadata.get('source', '?')}: {d.page_content[:80]}...")
            assert found_ml, (
                f"跨语言 EN→ZH 失败: 'machine learning' 未命中中文文档。结果: {contents}"
            )

    def test_en_query_finds_zh_rag(self):
        """英文"retrieval augmented generation" → 应命中中文 RAG 文档"""
        for store in _create_temp_store(ZH_DOCS):
            results = store.similarity_search("retrieval augmented generation", k=3)
            contents = [d.page_content for d in results]
            found_rag = any("RAG" in c or "检索增强" in c for c in contents)
            print(f"\n英文查询'retrieval augmented generation' → 中文文档结果:")
            for i, d in enumerate(results):
                print(f"  [{i}] {d.metadata.get('source', '?')}: {d.page_content[:80]}...")
            assert found_rag, (
                f"跨语言 EN→ZH 失败: 'RAG' 未命中中文文档。结果: {contents}"
            )


class TestCrossLingualMixed:
    """混合文档集：中英文同库检索"""

    def test_zh_query_in_mixed_corpus(self):
        """中文查询在混合文档集中应同时找到中英文结果"""
        for store in _create_temp_store(ZH_DOCS + EN_DOCS):
            results = store.similarity_search("深度学习", k=5)
            contents = [d.page_content for d in results]
            langs = [d.metadata.get("lang", "?") for d in results]
            print(f"\n中文查询'深度学习' → 混合文档集结果:")
            for i, d in enumerate(results):
                print(f"  [{i}] [{d.metadata.get('lang', '?')}] {d.page_content[:80]}...")

            found_zh = any("深度学习" in c for c in contents)
            found_en = any("deep learning" in c.lower() for c in contents)
            # 至少要命中中文文档（基线）
            assert found_zh, f"混合检索失败: 未命中中文'深度学习'文档"
            # 理想情况下也能命中英文文档
            if found_en:
                print("  → 同时命中了英文 deep learning 文档（跨语言有效）")
            else:
                print("  → 未命中英文文档（跨语言可能不足，考虑补充翻译层）")

    def test_en_query_in_mixed_corpus(self):
        """英文查询在混合文档集中应同时找到中英文结果"""
        for store in _create_temp_store(ZH_DOCS + EN_DOCS):
            results = store.similarity_search("vector database", k=5)
            contents = [d.page_content for d in results]
            print(f"\n英文查询'vector database' → 混合文档集结果:")
            for i, d in enumerate(results):
                print(f"  [{i}] [{d.metadata.get('lang', '?')}] {d.page_content[:80]}...")

            found_en = any("vector" in c.lower() for c in contents)
            found_zh = any("向量" in c for c in contents)
            assert found_en, f"混合检索失败: 未命中英文 vector database 文档"
            if found_zh:
                print("  → 同时命中了中文向量数据库文档（跨语言有效）")
            else:
                print("  → 未命中中文文档（跨语言可能不足，考虑补充翻译层）")
