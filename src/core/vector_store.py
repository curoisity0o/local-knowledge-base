"""
简化版向量存储模块
避免复杂的导入问题
"""

import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document

from .config import get_config

logger = logging.getLogger(__name__)


class LanguageDetector:
    """语言检测器"""

    def __init__(self):
        self._detector = None
        import re

        self._chinese_pattern = re.compile(r"[\u4e00-\u9fff]")

    def _ensure_initialized(self):
        if self._detector is None:
            from langdetect import DetectorFactory, detect

            # 确保结果一致
            DetectorFactory.seed = 0
            self._detector = detect

    def detect(self, text: str) -> str:
        """
        检测文本语言

        Args:
            text: 输入文本

        Returns:
            语言代码: 'zh-cn', 'en', 'ja', 'ko', etc.
        """
        if not text or len(text.strip()) < 10:
            return "unknown"

        self._ensure_initialized()
        try:
            lang = self._detector(text)
            return lang
        except Exception as e:
            logger.warning(f"语言检测失败: {e}")
            return "unknown"

    def is_chinese(self, text: str) -> bool:
        """判断是否为中文"""
        # 方法1: 检测中文字符
        chinese_chars = self._chinese_pattern.findall(text)
        if len(chinese_chars) >= 2:  # 至少2个中文字符
            return True

        # 方法2: langdetect 检测
        lang = self.detect(text)
        return lang in ["zh-cn", "zh-tw", "zh-hans", "zh-hant"]

    def is_english(self, text: str) -> bool:
        """判断是否为英文"""
        return self.detect(text) == "en"


class QueryTranslator:
    """Query翻译器 - 用于跨语言检索"""

    def __init__(self):
        self._llm = None
        self._enabled = get_config("rag.cross_lingual.translation_enabled", True)

    def _get_llm(self):
        """获取翻译用的LLM"""
        if self._llm is None:
            try:
                from langchain_ollama import OllamaLLM

                model = get_config("llm.local.ollama.model", "deepseek-v2:lite")
                self._llm = OllamaLLM(model=model, base_url="http://localhost:11434")
                logger.info("Query翻译器初始化成功")
            except Exception as e:
                logger.warning(f"Query翻译器初始化失败: {e}")
                self._enabled = False
        return self._llm

    def translate(self, query: str, target_lang: str = "en") -> str:
        """
        翻译Query

        Args:
            query: 原始查询
            target_lang: 目标语言 (默认英文)

        Returns:
            翻译后的查询
        """
        if not self._enabled:
            return query

        llm = self._get_llm()
        if llm is None:
            return query

        try:
            prompt = f"""Translate the following text to {target_lang}.
Only output the translation, nothing else.

Text: {query}

Translation:"""

            result = llm.invoke(prompt)
            # 清理结果
            result = result.strip()
            logger.info(f"Query翻译: '{query[:30]}...' -> '{result[:30]}...'")
            return result
        except Exception as e:
            logger.warning(f"Query翻译失败: {e}")
            return query


# 全局实例
_language_detector: Optional[LanguageDetector] = None
_query_translator: Optional[QueryTranslator] = None


def get_language_detector() -> LanguageDetector:
    """获取语言检测器单例"""
    global _language_detector
    if _language_detector is None:
        _language_detector = LanguageDetector()
    return _language_detector


def get_query_translator() -> QueryTranslator:
    """获取Query翻译器单例"""
    global _query_translator
    if _query_translator is None:
        _query_translator = QueryTranslator()
    return _query_translator


class BM25:
    """BM25 稀疏检索器 - 用于关键词匹配"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Document] = []
        self.doc_texts: List[str] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0.0
        self.doc_freq: Dict[str, int] = defaultdict(int)  # 词项文档频率
        self.idf: Dict[str, float] = {}  # 逆文档频率
        self.vocab: Dict[str, List[Tuple[int, int]]] = defaultdict(
            list
        )  # 词项 -> [(doc_idx, term_freq)]
        self._indexed = False

    def _tokenize(self, text: str) -> List[str]:
        """简单分词（按空格和标点）"""
        # 中英文混合分词
        tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+|\d+|[^\s\w]", text.lower())
        # 过滤单字符和纯数字
        return [t for t in tokens if len(t) > 1 or re.search(r"[\u4e00-\u9fff]", t)]

    def _calculate_idf(self):
        """计算IDF"""
        n = len(self.documents)
        for term, df in self.doc_freq.items():
            # 使用改进的IDF公式，避免零值
            self.idf[term] = max(0, (n - df + 0.5) / (df + 0.5))
        self._indexed = True

    def index(self, documents: List[Document]):
        """索引文档"""
        self.documents = documents
        self.doc_texts = [doc.page_content for doc in documents]
        self.doc_lengths = [len(self._tokenize(text)) for text in self.doc_texts]
        self.avg_doc_length = sum(self.doc_lengths) / max(len(self.doc_lengths), 1)

        # 构建倒排索引
        for doc_idx, text in enumerate(self.doc_texts):
            tokens = self._tokenize(text)
            term_freq = defaultdict(int)
            for token in tokens:
                term_freq[token] += 1

            for term, freq in term_freq.items():
                self.vocab[term].append((doc_idx, freq))
                self.doc_freq[term] += 1

        self._calculate_idf()
        logger.info(f"BM25索引完成: {len(documents)} 个文档, {len(self.vocab)} 个词项")

    def search(self, query: str, k: int = 10) -> List[Tuple[Document, float]]:
        """
        BM25搜索

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            [(文档, 分数)] 列表，按分数降序排列
        """
        if not self._indexed:
            logger.warning("BM25未索引，请先调用index()")
            return []

        query_tokens = self._tokenize(query)
        doc_scores: Dict[int, float] = defaultdict(float)

        for token in query_tokens:
            if token not in self.vocab:
                continue

            idf = self.idf.get(token, 0)
            for doc_idx, term_freq in self.vocab[token]:
                doc_len = self.doc_lengths[doc_idx]
                # BM25公式
                numerator = term_freq * (self.k1 + 1)
                denominator = term_freq + self.k1 * (
                    1 - self.b + self.b * doc_len / max(self.avg_doc_length, 1)
                )
                score = idf * (numerator / denominator)
                doc_scores[doc_idx] += score

        # 按分数排序
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:k]

        results = [(self.documents[idx], score) for idx, score in sorted_docs]
        logger.info(
            f"BM25搜索完成: query='{query[:30]}...', 返回 {len(results)} 个结果"
        )
        return results


def reciprocal_rank_fusion(
    result_lists: List[List[Tuple[Document, float]]], k: int = 60
) -> List[Document]:
    """
    倒数排名融合 (Reciprocal Rank Fusion)

    将多个检索结果列表融合为一个统一的排名列表。
    该算法对于在不同检索方法中获得高排名的文档给予更高的综合分数。

    Args:
        result_lists: 多个检索结果列表，每个元素是 [(文档, 分数)] 列表
        k: 融合参数，通常设置为60

    Returns:
        融合后的文档列表（按融合分数降序）
    """
    doc_scores: Dict[str, Tuple[float, Document]] = {}

    for result_list in result_lists:
        for rank, (doc, _) in enumerate(result_list):
            # 使用文档内容作为唯一标识（避免ID不一致问题）
            doc_key = doc.page_content[:100]  # 取前100字符作为key
            # RRF公式: 1 / (k + rank)
            rrf_score = 1.0 / (k + rank + 1)
            if doc_key in doc_scores:
                doc_scores[doc_key] = (doc_scores[doc_key][0] + rrf_score, doc)
            else:
                doc_scores[doc_key] = (rrf_score, doc)

    # 按RRF分数排序
    sorted_docs = sorted(doc_scores.values(), key=lambda x: x[0], reverse=True)

    # 返回排序后的文档列表
    results = [doc for _, doc in sorted_docs]

    logger.info(f"RRF融合完成: {len(result_lists)} 个结果列表 -> {len(results)} 个文档")
    return results


class Reranker:
    """重排序器 - 使用CrossEncoder对检索结果进行重排序"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-large"):
        self.model_name = model_name
        self._model = None
        self._initialized = False

    def _ensure_initialized(self):
        """延迟初始化模型"""
        if self._initialized:
            return

        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"初始化重排序模型: {self.model_name}")
            self._model = CrossEncoder(self.model_name, max_length=512)
            self._initialized = True
            logger.info("重排序模型初始化成功")
        except ImportError:
            logger.warning("sentence-transformers 未安装，重排序功能不可用")
            raise
        except Exception as e:
            logger.error(f"重排序模型初始化失败: {e}")
            raise

    def rerank(
        self, query: str, documents: List[Document], top_n: int = 3
    ) -> List[Document]:
        """
        对文档进行重排序

        Args:
            query: 查询文本
            documents: 待重排序的文档列表
            top_n: 返回的顶部文档数量

        Returns:
            重排序后的文档列表（按相关性从高到低）
        """
        if not documents:
            return []

        self._ensure_initialized()

        try:
            # 构建query-document对
            pairs = [(query, doc.page_content) for doc in documents]

            # 批量预测相关性分数
            scores = self._model.predict(pairs)

            # 如果是单个数值，转换为列表
            if isinstance(scores, (int, float)):
                scores = [scores]

            # 按分数排序（降序）
            doc_score_pairs = list(zip(documents, scores, strict=False))
            doc_score_pairs.sort(key=lambda x: x[1], reverse=True)

            # 返回顶部N个文档
            reranked_docs = [doc for doc, _ in doc_score_pairs[:top_n]]

            logger.info(f"重排序完成: {len(documents)} -> {len(reranked_docs)} 个文档")
            return reranked_docs

        except Exception as e:
            logger.error(f"重排序失败: {e}")
            # 重排序失败时返回原始文档
            return documents[:top_n]


class SimpleVectorStore:
    """简化版向量存储管理器"""

    def __init__(self, config=None):
        self.config = config or get_config("vector_store", {})
        self.embedder = None
        self.vector_store = None
        # 优先使用用户配置，否则使用全局配置
        self.store_type = self.config.get(
            "type", get_config("vector_store.type", "chroma")
        )

        # 重排序器
        self.reranker = None

        # 延迟初始化
        self._initialized = False

    def _ensure_initialized(self):
        """确保向量存储已初始化"""
        if self._initialized:
            return

        try:
            # 强制使用 Ollama 嵌入模型（本地运行，速度快）
            # 读取配置，优先使用 Ollama

            # 尝试加载 Ollama 嵌入
            try:
                # 先尝试新版本
                try:
                    from langchain_ollama import OllamaEmbeddings
                except ImportError:
                    from langchain_community.embeddings import OllamaEmbeddings

                # 获取模型名称
                ollama_model = get_config("embeddings.ollama_model", "bge-m3")
                if not ollama_model:
                    ollama_model = os.getenv("EMBEDDINGS_OLLAMA_MODEL", "bge-m3")

                logger.info(f"使用 Ollama 嵌入模型: {ollama_model}")

                self.embedder = OllamaEmbeddings(
                    model=ollama_model, base_url="http://localhost:11434"
                )
                self._using_ollama = True
                logger.info("Ollama 嵌入模型初始化成功")

            except Exception as e:
                logger.error(f"Ollama 嵌入模型初始化失败: {e}")
                logger.error("请确保 Ollama 服务正在运行: ollama serve")
                logger.error("请确保已下载嵌入模型: ollama pull bge-m3")
                raise RuntimeError(f"无法初始化 Ollama 嵌入模型: {e}") from e

            # 初始化向量存储
            if self.store_type == "chroma":
                try:
                    from langchain_chroma import Chroma
                except ImportError:
                    from langchain_community.vectorstores import Chroma

                persist_directory = get_config(
                    "vector_store.chroma.persist_directory",
                    "./data/vector_store/chroma",
                )
                collection_name = get_config(
                    "vector_store.chroma.collection_name", "knowledge_base"
                )

                # 确保目录存在
                Path(persist_directory).mkdir(parents=True, exist_ok=True)

                logger.info(f"创建 Chroma 向量存储: {persist_directory}")

                self.vector_store = Chroma(
                    embedding_function=self.embedder,
                    persist_directory=persist_directory,
                    collection_name=collection_name,
                )
            else:
                logger.warning(f"不支持的存储类型: {self.store_type}，使用 Chroma")
                self.store_type = "chroma"
                self._ensure_initialized()  # 递归调用，使用默认配置

            self._initialized = True
            logger.info("向量存储初始化成功")

        except ImportError as e:
            logger.error(f"导入依赖失败: {e}")
            logger.error(
                "请安装所需依赖: pip install chromadb langchain-community sentence-transformers"
            )
            raise
        except Exception as e:
            logger.error(f"初始化向量存储失败: {e}")
            raise

    def add_documents(self, documents: List[Document]) -> List[str]:
        """添加文档到向量存储"""
        self._ensure_initialized()

        # 确保向量存储已初始化
        if self.vector_store is None:
            raise RuntimeError("向量存储未正确初始化")

        try:
            logger.info(f"添加 {len(documents)} 个文档到向量存储")
            ids = self.vector_store.add_documents(documents)
            logger.info(f"文档添加成功，生成 {len(ids)} 个向量")
            return ids
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise

    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        """相似度搜索"""
        self._ensure_initialized()

        # 确保向量存储已初始化
        if self.vector_store is None:
            logger.error("向量存储未正确初始化")
            return []

        try:
            logger.info(f"执行相似度搜索: '{query[:50]}...', k={k}")
            results = self.vector_store.similarity_search(query, k=k)
            logger.info(f"搜索完成，找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"相似度搜索失败: {e}")
            return []

    def similarity_search_with_score(
        self, query: str, k: int = 4
    ) -> List[Tuple[Document, float]]:
        """带分数的相似度搜索"""
        self._ensure_initialized()

        # 确保向量存储已初始化
        if self.vector_store is None:
            logger.error("向量存储未正确初始化")
            return []

        try:
            logger.info(f"执行带分数搜索: '{query[:50]}...', k={k}")
            results = self.vector_store.similarity_search_with_score(query, k=k)
            logger.info(f"搜索完成，找到 {len(results)} 个结果")
            return results
        except Exception as e:
            logger.error(f"带分数搜索失败: {e}")
            return []

    def hybrid_search(
        self,
        query: str,
        k: int = 4,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> List[Document]:
        """
        混合搜索 - 结合稠密(向量)和稀疏(BM25)检索

        Args:
            query: 查询文本
            k: 返回结果数量
            dense_weight: 稠密检索权重
            sparse_weight: 稀疏检索权重（BM25）

        Returns:
            融合后的文档列表
        """
        self._ensure_initialized()

        if self.vector_store is None:
            logger.error("向量存储未正确初始化")
            return []

        try:
            logger.info(f"执行混合搜索: '{query[:50]}...', k={k}")

            # 1. 稠密检索（向量搜索）- 获取更多结果用于融合
            fetch_k = k * 3  # 获取更多结果以获得更好的融合效果
            dense_results = self.vector_store.similarity_search_with_score(
                query, k=fetch_k
            )
            logger.info(f"稠密检索: {len(dense_results)} 个结果")

            # 2. 稀疏检索（BM25）- 准备BM25索引
            # 获取所有文档用于BM25
            try:
                if hasattr(self.vector_store, "_collection"):
                    collection = self.vector_store._collection
                    all_docs_result = collection.get()

                    if all_docs_result and all_docs_result.get("documents"):
                        bm25 = BM25()
                        all_documents: List[Document] = []
                        doc_contents = all_docs_result["documents"]
                        metadatas = all_docs_result.get("metadatas") or []
                        for i, content in enumerate(doc_contents):
                            metadata = metadatas[i] if i < len(metadatas) else {}
                            all_documents.append(
                                Document(page_content=content, metadata=metadata)
                            )

                        bm25.index(all_documents)
                        sparse_results = bm25.search(query, k=fetch_k)
                        logger.info(f"稀疏检索: {len(sparse_results)} 个结果")
                    else:
                        sparse_results = []
                else:
                    sparse_results = []
            except Exception as e:
                logger.warning(f"BM25检索失败: {e}")
                sparse_results = []

            # 3. RRF融合
            if sparse_results:
                result_lists = [dense_results, sparse_results]
                fused_docs = reciprocal_rank_fusion(result_lists, k=k)
            else:
                # 无BM25结果，只用向量搜索
                fused_docs = [doc for doc, _ in dense_results[:k]]

            logger.info(f"混合搜索完成: 返回 {len(fused_docs)} 个文档")
            return fused_docs[:k]

        except Exception as e:
            logger.error(f"混合搜索失败: {e}")
            # 降级到纯向量搜索
            return self.similarity_search(query, k=k)

    def cross_lingual_hybrid_search(
        self,
        query: str,
        k: int = 4,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
    ) -> List[Document]:
        """
        跨语言混合搜索 - 支持中文查询检索英文文档

        策略：
        1. 检测查询语言
        2. 如果是中文，翻译成英文
        3. 同时执行中英文查询
        4. 使用RRF融合结果

        Args:
            query: 查询文本
            k: 返回结果数量
            dense_weight: 稠密检索权重
            sparse_weight: 稀疏检索权重

        Returns:
            融合后的文档列表
        """
        self._ensure_initialized()

        if self.vector_store is None:
            logger.error("向量存储未正确初始化")
            return []

        # 1. 语言检测
        detector = get_language_detector()
        lang = detector.detect(query)
        is_chinese = detector.is_chinese(query)

        logger.info(
            f"跨语言搜索: query='{query[:30]}...', lang={lang}, is_chinese={is_chinese}"
        )

        # 2. 获取所有文档用于BM25（只获取一次）
        bm25, all_documents = self._get_bm25_index()

        # 3. 执行多语言检索
        all_results: List[List[Tuple[Document, float]]] = []

        # 原始查询搜索
        all_results.append(self._search_single_query(query, k, bm25, all_documents))

        # 如果是中文，翻译后也搜索
        translated_query = None
        if is_chinese:
            translator = get_query_translator()
            translated_query = translator.translate(query, "en")
            if translated_query and translated_query != query:
                logger.info(
                    f"翻译查询: '{query[:20]}...' -> '{translated_query[:20]}...'"
                )
                all_results.append(
                    self._search_single_query(translated_query, k, bm25, all_documents)
                )

        # 4. RRF融合所有结果
        if len(all_results) > 1:
            fused_docs = reciprocal_rank_fusion(all_results, k=k)
        else:
            fused_docs = [doc for doc, _ in all_results[0][:k]]

        logger.info(f"跨语言搜索完成: 返回 {len(fused_docs)} 个文档")
        return fused_docs[:k]

    def _get_bm25_index(self):
        """获取BM25索引（带缓存）"""
        if not hasattr(self, "_bm25_cache") or self._bm25_cache is None:
            collection = self.vector_store._collection
            all_docs_result = collection.get()

            all_documents: List[Document] = []
            if all_docs_result and all_docs_result.get("documents"):
                doc_contents = all_docs_result["documents"]
                metadatas = all_docs_result.get("metadatas") or []
                for i, content in enumerate(doc_contents):
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    all_documents.append(
                        Document(page_content=content, metadata=metadata)
                    )

            bm25 = BM25()
            bm25.index(all_documents)
            self._bm25_cache = (bm25, all_documents)

        return self._bm25_cache

    def _search_single_query(
        self, query: str, k: int, bm25: Optional[BM25], all_documents: List[Document]
    ) -> List[Tuple[Document, float]]:
        """执行单次查询（向量+BM25）"""
        # 增大 fetch_k 以确保 BM25 的好结果不被向量检索的长文本淹没
        fetch_k = k * 5

        # 稠密检索
        dense_results = self.vector_store.similarity_search_with_score(query, k=fetch_k)

        # 稀疏检索
        sparse_results: List[Tuple[Document, float]] = []
        if bm25 and all_documents:
            sparse_results = bm25.search(query, k=fetch_k)

        # 如果有BM25结果，融合
        if sparse_results:
            fused_docs = reciprocal_rank_fusion([dense_results, sparse_results], k=k)
            # 返回格式转换为 [(doc, score)] 以匹配 reciprocal_rank_fusion 的输入格式
            return [(doc, 1.0) for doc in fused_docs]
        else:
            return dense_results[:k]

    def rerank_documents(
        self, query: str, documents: List[Document], top_n: int = 3
    ) -> List[Document]:
        """
        对文档进行重排序

        Args:
            query: 查询文本
            documents: 待重排序的文档列表
            top_n: 返回的顶部文档数量

        Returns:
            重排序后的文档列表（按相关性从高到低）
        """
        if not documents:
            return []

        # 延迟初始化重排序器
        if self.reranker is None:
            rerank_model = get_config("rag.reranking.model", "BAAI/bge-reranker-large")
            self.reranker = Reranker(model_name=rerank_model)

        try:
            return self.reranker.rerank(query, documents, top_n)
        except Exception as e:
            logger.warning(f"重排序失败，使用原始检索结果: {e}")
            return documents[:top_n]

    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        self._ensure_initialized()

        info = {
            "store_type": self.store_type,
            "embedding_model": (
                "ollama" if hasattr(self, "_using_ollama") else "huggingface"
            ),
            "status": "initialized" if self._initialized else "not_initialized",
        }

        # 尝试获取文档数量
        try:
            if self.vector_store is not None and hasattr(
                self.vector_store, "_collection"
            ):
                collection = self.vector_store._collection
                if hasattr(collection, "count"):
                    info["document_count"] = collection.count()
        except Exception as e:
            logger.debug(f"获取文档数量失败（可忽略）: {e}")

        return info

    def get_documents_by_source(self, source_path: str) -> List[Document]:
        """根据源文件路径获取文档

        Args:
            source_path: 源文件路径

        Returns:
            匹配的文档列表
        """
        self._ensure_initialized()

        if self.vector_store is None:
            logger.error("向量存储未正确初始化")
            return []

        try:
            # 使用 ChromaDB 的 get 方法按 source 元数据查询
            if hasattr(self.vector_store, "_collection"):
                collection = self.vector_store._collection
                results = collection.get(where={"source": source_path})

                if results and results.get("documents"):
                    documents_list = results["documents"]
                    if documents_list:
                        documents = []
                        metadatas = results.get("metadatas") or []
                        for i, content in enumerate(documents_list):
                            metadata = metadatas[i] if i < len(metadatas) else {}
                            doc = Document(page_content=content, metadata=metadata)
                            documents.append(doc)
                        return documents
            return []
        except Exception as e:
            logger.error(f"根据源路径获取文档失败: {e}")
            return []

    def delete_by_source(self, source_path: str) -> bool:
        """根据源文件路径删除向量

        Args:
            source_path: 源文件路径

        Returns:
            是否删除成功
        """
        self._ensure_initialized()

        if self.vector_store is None:
            logger.error("向量存储未正确初始化")
            return False

        try:
            # 使用 ChromaDB 的 delete 方法按 source 元数据删除
            if hasattr(self.vector_store, "_collection"):
                collection = self.vector_store._collection
                # 获取要删除的文档 IDs
                results = collection.get(where={"source": source_path})

                if results and results.get("ids"):
                    ids_to_delete = results["ids"]
                    collection.delete(ids=ids_to_delete)
                    logger.info(f"成功删除 {len(ids_to_delete)} 个向量: {source_path}")
                    return True
                else:
                    logger.info(f"未找到要删除的向量: {source_path}")
                    # 没有找到向量也返回成功（幂等性）
                    return True
            else:
                logger.error("向量存储不支持 _collection 访问")
                return False
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False

    def get_all_sources(self) -> List[str]:
        """获取所有已索引的源文件路径（去重）

        Returns:
            源文件路径列表
        """
        self._ensure_initialized()

        if self.vector_store is None:
            logger.error("向量存储未正确初始化")
            return []

        try:
            if hasattr(self.vector_store, "_collection"):
                collection = self.vector_store._collection
                # 获取所有文档的元数据
                results = collection.get()

                if results:
                    metadatas = results.get("metadatas") or []
                    sources = set()
                    for metadata in metadatas:
                        if metadata and "source" in metadata:
                            sources.add(metadata["source"])
                    return list(sources)
            return []
        except Exception as e:
            logger.error(f"获取所有源文件路径失败: {e}")
            return []


# 便捷函数
def create_vector_store(config=None) -> SimpleVectorStore:
    """创建向量存储实例"""
    return SimpleVectorStore(config)
