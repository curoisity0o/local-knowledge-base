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

# 中英文停用词集合，供 BM25 分词和关键词提取共用
BM25_STOPWORDS: frozenset = frozenset({
    # 中文停用词
    "的", "了", "是", "在", "有", "和", "与", "或", "不", "也",
    "都", "就", "要", "会", "能", "可以", "什么", "怎么", "如何",
    "为什么", "哪", "哪些", "这个", "那个", "一个", "没", "被",
    "把", "让", "给", "到", "从", "对", "而", "但", "却",
    # 英文停用词
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "as", "into",
    "about", "how", "what", "which", "who", "when", "where", "why",
})


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



class QueryTranslator:
    """Query 双向翻译器 — 支持中英文互译，带 LRU 缓存。

    翻译失败或 LLM 不可用时返回原始查询（零开销降级）。
    """

    # 翻译方向
    ZH_TO_EN = "en"
    EN_TO_ZH = "zh"

    def __init__(self):
        self._llm = None
        self._enabled = get_config("rag.cross_lingual.translation_enabled", True)
        # LRU 缓存: query → translated query
        self._cache: Dict[str, str] = {}
        self._max_cache_size = int(
            get_config("rag.cross_lingual.cache_size", 100)
        )

    def _get_llm(self):
        """延迟初始化翻译 LLM"""
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

    def _add_to_cache(self, query: str, translated: str) -> None:
        """添加到缓存，超出上限时淘汰最早的条目"""
        if len(self._cache) >= self._max_cache_size:
            # 删除最早的一个条目
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[query] = translated

    def translate(self, query: str, target_lang: str = "en") -> str:
        """
        翻译查询。

        Args:
            query: 原始查询
            target_lang: 目标语言 ("en" 或 "zh")

        Returns:
            翻译后的查询，失败时返回原始查询
        """
        if not self._enabled or not query.strip():
            return query

        cache_key = f"{target_lang}:{query}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        llm = self._get_llm()
        if llm is None:
            return query

        lang_name = "英文" if target_lang == "en" else "中文"
        try:
            prompt = f"""将以下文本翻译为{lang_name}，只输出翻译结果，不要其他内容。

文本：{query}

翻译："""
            result = llm.invoke(prompt).strip()
            if not result or result == query:
                return query

            self._add_to_cache(query, result)
            logger.info(
                f"Query翻译: '{query[:30]}...' -> '{result[:30]}...'"
            )
            return result
        except Exception as e:
            logger.warning(f"Query翻译失败: {e}")
            return query

    def translate_to_en(self, query: str) -> str:
        """中文查询 → 英文翻译（命中缓存则直接返回）"""
        return self.translate(query, target_lang=self.ZH_TO_EN)

    def translate_to_zh(self, query: str) -> str:
        """英文查询 → 中文翻译（命中缓存则直接返回）"""
        return self.translate(query, target_lang=self.EN_TO_ZH)


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
        """分词：中文用 jieba，英文用空格分割。jieba 未安装时 fallback 到正则。"""
        text_lower = text.lower()
        if re.search(r"[\u4e00-\u9fff]", text_lower):
            try:
                import jieba
                tokens = list(jieba.cut(text_lower))
            except ImportError:
                # fallback：正则分词
                tokens = re.findall(
                    r"[\u4e00-\u9fff]+|[a-zA-Z]+|\d+", text_lower
                )
        else:
            tokens = text_lower.split()

        # 过滤停用词、单字符空白、纯数字
        return [
            t for t in tokens
            if len(t) > 1 and not t.isspace() and not t.isdigit()
            and t not in BM25_STOPWORDS
        ]

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
) -> List[Tuple[Document, float]]:
    """
    倒数排名融合 (Reciprocal Rank Fusion)

    将多个检索结果列表融合为一个统一的排名列表。
    该算法对于在不同检索方法中获得高排名的文档给予更高的综合分数。

    Args:
        result_lists: 多个检索结果列表，每个元素是 [(文档, 分数)] 列表
        k: 融合参数，通常设置为60

    Returns:
        融合后的 [(文档, RRF分数)] 列表（按融合分数降序）
    """
    doc_scores: Dict[str, Tuple[float, Document]] = {}

    for result_list in result_lists:
        for rank, (doc, _) in enumerate(result_list):
            # 使用完整内容作为唯一标识，避免前缀碰撞
            doc_key = doc.page_content
            # RRF公式: 1 / (k + rank)
            rrf_score = 1.0 / (k + rank + 1)
            if doc_key in doc_scores:
                doc_scores[doc_key] = (doc_scores[doc_key][0] + rrf_score, doc)
            else:
                doc_scores[doc_key] = (rrf_score, doc)

    # 按RRF分数排序
    sorted_docs = sorted(doc_scores.values(), key=lambda x: x[0], reverse=True)

    logger.info(f"RRF融合完成: {len(result_lists)} 个结果列表 -> {len(sorted_docs)} 个文档")
    return [(doc, score) for score, doc in sorted_docs]


class KeywordCoverageReranker:
    """轻量级重排序器 — 基于查询关键词在文档中的覆盖率评分。

    零额外模型依赖，适合无法加载 CrossEncoder 的场景。
    """

    @staticmethod
    def _extract_keywords(query: str) -> List[str]:
        """从查询中提取关键词"""
        # 用 BM25 同款分词逻辑提取
        text_lower = query.lower()
        if re.search(r"[\u4e00-\u9fff]", text_lower):
            try:
                import jieba
                tokens = list(jieba.cut(text_lower))
            except ImportError:
                tokens = re.findall(
                    r"[\u4e00-\u9fff]+|[a-zA-Z]+|\d+", text_lower
                )
        else:
            tokens = text_lower.split()
        # 过滤停用词和单字符
        return [t for t in tokens if len(t) > 1 and t not in BM25_STOPWORDS]

    @staticmethod
    def compute_score(query: str, document: Document) -> float:
        """计算查询关键词在文档中的覆盖率分数 (0~1)。

        score = 匹配的关键词数 / 总关键词数
        """
        keywords = KeywordCoverageReranker._extract_keywords(query)
        if not keywords:
            return 0.0

        doc_lower = document.page_content.lower()
        matched = sum(1 for kw in keywords if kw in doc_lower)
        return matched / len(keywords)

    def rerank(
        self, query: str, documents: List[Document], top_n: int = 3
    ) -> List[Document]:
        """按关键词覆盖率重排序"""
        if not documents:
            return []

        scored = [
            (doc, self.compute_score(query, doc)) for doc in documents
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        result = [doc for doc, _ in scored[:top_n]]
        logger.info(
            f"关键词覆盖率重排序: {len(documents)} -> {len(result)} 个文档"
        )
        return result


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
            # 新增文档后 BM25 索引需要重建
            self._bm25_cache = None
            return ids
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise

    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        """相似度搜索"""
        self._ensure_initialized()

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

            # 2. 稀疏检索（BM25）- 使用缓存的 BM25 索引
            try:
                bm25, all_documents = self._get_bm25_index()
                if bm25 and all_documents:
                    sparse_results = bm25.search(query, k=fetch_k)
                    logger.info(f"稀疏检索: {len(sparse_results)} 个结果")
                else:
                    sparse_results = []
            except Exception as e:
                logger.warning(f"BM25检索失败: {e}")
                sparse_results = []

            # 3. RRF融合
            if sparse_results:
                result_lists = [dense_results, sparse_results]
                fused_results = reciprocal_rank_fusion(result_lists, k=k)
                fused_docs = [doc for doc, _ in fused_results[:k]]
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
            fused_results = reciprocal_rank_fusion(all_results, k=k)
            fused_docs = [doc for doc, _ in fused_results[:k]]
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

            # 从配置读取 BM25 参数
            k1 = float(get_config("rag.retriever.sparse.bm25_k1", 1.5))
            b = float(get_config("rag.retriever.sparse.bm25_b", 0.75))
            bm25 = BM25(k1=k1, b=b)
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

        # 如果有BM25结果，融合（返回带 RRF 分数的结果）
        if sparse_results:
            return reciprocal_rank_fusion([dense_results, sparse_results], k=k)
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
            try:
                rerank_model = get_config("rag.reranking.model", "BAAI/bge-reranker-large")
                self.reranker = Reranker(model_name=rerank_model)
            except Exception as e:
                logger.warning(f"CrossEncoder 初始化失败，使用轻量关键词覆盖率重排序: {e}")
                self.reranker = KeywordCoverageReranker()
                self._reranker_type = "keyword_coverage"
            else:
                self._reranker_type = "cross_encoder"
        else:
            self._reranker_type = getattr(self, "_reranker_type", "cross_encoder")

        try:
            return self.reranker.rerank(query, documents, top_n)
        except Exception as e:
            # CrossEncoder 失败时降级到关键词覆盖率
            if isinstance(self.reranker, Reranker):
                logger.warning(f"CrossEncoder 重排序失败，降级到关键词覆盖率: {e}")
                fallback = KeywordCoverageReranker()
                self.reranker = fallback
                self._reranker_type = "keyword_coverage"
                return fallback.rerank(query, documents, top_n)
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

    def parent_child_search(self, query: str, k: int = 4) -> List[Document]:
        """父子上下文检索：命中子块，返回父块内容以提供更完整上下文。

        当文档以父子分块方式摄入（metadata 中含 parent_content）时，
        此方法会检索精准的子块，然后将结果扩展为父块内容，
        从而在高精度召回的同时保留足够的上下文。

        若子块不包含 parent_content，则直接返回子块。

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            包含父块（或子块）内容的 Document 列表
        """
        self._ensure_initialized()

        if self.vector_store is None:
            return []

        try:
            # 检索子块（使用混合搜索，多取一些，父块去重后可能减少）
            try:
                child_docs = self.hybrid_search(query, k=k * 2)
            except Exception:
                child_docs = self.similarity_search(query, k=k * 2)

            seen_parent_ids: set = set()
            result_docs: List[Document] = []

            for child in child_docs:
                parent_id = child.metadata.get("parent_id")
                parent_content = child.metadata.get("parent_content")

                if parent_id and parent_content:
                    # 父子分块模式：用父块内容替换子块内容，并去重
                    if parent_id not in seen_parent_ids:
                        seen_parent_ids.add(parent_id)
                        parent_meta = dict(child.metadata)
                        parent_meta.pop("parent_content", None)  # 避免嵌套
                        result_docs.append(
                            Document(
                                page_content=parent_content, metadata=parent_meta
                            )
                        )
                else:
                    # 普通分块模式：直接返回子块
                    result_docs.append(child)

                if len(result_docs) >= k:
                    break

            logger.info(
                "父子上下文检索完成: query='%s...', 返回 %d 个结果",
                query[:30],
                len(result_docs),
            )
            return result_docs

        except Exception as e:
            logger.error(f"父子上下文检索失败: {e}")
            return self.similarity_search(query, k=k)

    def multi_query_search(
        self,
        query: str,
        k: int = 4,
        llm_manager=None,
        num_queries: int = 3,
    ) -> List[Document]:
        """多查询检索：用 LLM 生成查询变体，分别检索后用 RRF 合并去重。

        当某个查询角度未能召回相关文档时，换角度的查询变体可补充覆盖，
        从而提升整体召回率。

        Args:
            query: 原始查询
            k: 最终返回结果数量
            llm_manager: LLMManager 实例，用于生成变体（可选）
            num_queries: 生成的查询变体数量

        Returns:
            融合后的 Document 列表
        """
        self._ensure_initialized()

        if self.vector_store is None:
            return []

        query_variants: List[str] = [query]

        # 尝试用 LLM 生成多个查询变体
        if llm_manager is not None:
            try:
                prompt = (
                    f"请为以下问题生成 {num_queries} 个不同角度的查询语句，"
                    f"每行一个，直接输出查询语句，不要编号或解释。\n\n问题：{query}"
                )
                result = llm_manager.generate(prompt)
                text = result.get("text", "")
                variants = [
                    line.strip()
                    for line in text.splitlines()
                    if line.strip() and line.strip() != query
                ][:num_queries]
                if variants:
                    query_variants.extend(variants)
                    logger.info("生成查询变体: %s", variants)
            except (RuntimeError, ValueError, AttributeError, KeyError) as e:
                logger.warning(f"生成查询变体失败，使用原始查询: {e}")

        # 对每个变体执行相似度搜索，收集结果列表
        all_result_lists: List[List[Tuple[Document, float]]] = []
        for variant in query_variants:
            docs_with_scores = self.similarity_search_with_score(variant, k=k)
            if docs_with_scores:
                all_result_lists.append(docs_with_scores)

        if not all_result_lists:
            return []

        # 使用 RRF 融合多路结果
        merged = reciprocal_rank_fusion(all_result_lists)
        return [doc for doc, _ in merged[:k]]




# 便捷函数
def create_vector_store(config=None) -> SimpleVectorStore:
    """创建向量存储实例"""
    return SimpleVectorStore(config)
