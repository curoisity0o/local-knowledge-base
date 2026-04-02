"""
RAG Chain 模块
完整的RAG流水线实现
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document

from .config import get_config
from .document_processor import DocumentProcessor
from .llm_manager import LLMManager, estimate_tokens
from .vector_store import SimpleVectorStore

logger = logging.getLogger(__name__)


class RAGChain:
    """完整的RAG流水线"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # 组件
        self.document_processor: Optional[DocumentProcessor] = None
        self.vector_store: Optional[SimpleVectorStore] = None
        self.llm_manager: Optional[LLMManager] = None

        # 配置
        self.chunk_size = int(
            get_config("document_processing.chunking.chunk_size", 800)
        )
        self.chunk_overlap = int(
            get_config("document_processing.chunking.chunk_overlap", 100)
        )
        self.retrieval_top_k = int(get_config("rag.retriever.top_k", 4))
        self.score_threshold = float(get_config("rag.retriever.score_threshold", 0.0))

        # 上下文长度管理：为 context 预留的最大 token 数
        # = 模型 context window - prompt 模板开销(约300 token) - max_tokens(生成)
        model_context_window = int(
            get_config("llm.local.ollama.context_window", 4096)
        )
        max_output_tokens = int(
            get_config("rag.generation.max_tokens", 2000)
        )
        self.max_context_tokens = model_context_window - max_output_tokens - 300

        # 重排序配置
        self.reranking_enabled = get_config("rag.reranking.enabled", False)
        self.reranking_top_n = int(get_config("rag.reranking.top_n", 3))

        # 混合搜索配置
        self.hybrid_search_enabled = (
            get_config("rag.retriever.type", "dense") == "hybrid"
        )
        self.hybrid_dense_weight = float(
            get_config("rag.retriever.hybrid.dense_weight", 0.7)
        )
        self.hybrid_sparse_weight = float(
            get_config("rag.retriever.hybrid.sparse_weight", 0.3)
        )

        # 跨语言搜索配置
        self.cross_lingual_enabled = get_config("rag.cross_lingual.enabled", True)
        self.translation_enabled = get_config(
            "rag.cross_lingual.translation_enabled", True
        )

        # 父子上下文检索配置
        self.parent_child_enabled = get_config("rag.retriever.parent_child.enabled", False)

        # 多查询检索配置
        self.multi_query_enabled = get_config("rag.retriever.multi_query.enabled", False)

        # CRAG（Corrective RAG）配置
        self.crag_enabled = get_config("rag.corrective.enabled", True)
        self.crag_threshold = float(get_config("rag.corrective.quality_threshold", 0.3))
        self.crag_max_retries = int(get_config("rag.corrective.max_retries", 1))

        # History-Aware Retrieval 配置
        self.history_aware_enabled = get_config("rag.history_aware.enabled", True)
        self.history_aware_max_history = int(
            get_config("rag.history_aware.max_history_for_rewrite", 5)
        )

        # 历史管理配置
        self.history_max_turns = int(get_config("rag.history.max_turns", 20))
        self.history_token_budget_ratio = float(
            get_config("rag.history.token_budget_ratio", 0.25)
        )
        self.history_summary_threshold = int(
            get_config("rag.history.summary_threshold", 10)
        )

        # 答案溯源验证配置
        self.citation_verify_enabled = get_config(
            "rag.citation_verification.enabled", True
        )
        self.citation_warn_on_invalid = get_config(
            "rag.citation_verification.warn_on_invalid", True
        )

        # 初始化状态
        self._initialized = False

    def initialize(self) -> None:
        """初始化所有组件"""
        if self._initialized:
            return

        try:
            logger.info("初始化RAG Chain...")

            # 初始化文档处理器
            self.document_processor = DocumentProcessor()
            logger.info("文档处理器初始化完成")

            # 初始化向量存储
            self.vector_store = SimpleVectorStore()
            logger.info("向量存储初始化完成")

            # 初始化LLM管理器
            self.llm_manager = LLMManager()
            logger.info("LLM管理器初始化完成")

            self._initialized = True
            logger.info("RAG Chain初始化完成")

        except Exception as e:
            logger.error(f"RAG Chain初始化失败: {e}")
            raise

    def ingest_document(self, file_path: str) -> Dict[str, Any]:
        """摄取文档到知识库"""
        if not self._initialized:
            self.initialize()

        start_time = time.time()

        try:
            logger.info(f"开始摄取文档: {file_path}")

            # 1. 处理文档
            if not self.document_processor:
                raise RuntimeError("文档处理器未初始化")
            documents = self.document_processor.process_file(file_path)
            logger.info(f"文档处理完成，生成 {len(documents)} 个片段")

            # 2. 添加到向量存储（先删除同名旧文档，防止重复累积）
            ids = []
            if self.vector_store:
                normalized_path = str(Path(file_path).resolve())
                self.vector_store.delete_by_source(normalized_path)
                ids = self.vector_store.add_documents(documents)
                logger.info(f"文档已添加到向量存储，生成 {len(ids)} 个向量")

            return {
                "success": True,
                "file_path": file_path,
                "chunks_created": len(documents),
                "vectors_created": len(ids),
                "processing_time": time.time() - start_time,
            }

        except Exception as e:
            logger.error(f"文档摄取失败: {e}")
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e),
                "processing_time": time.time() - start_time,
            }

    def ingest_directory(
        self, directory: str, file_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """摄取整个目录的文档"""
        if not self._initialized:
            self.initialize()

        if file_types is None:
            file_types = [".pdf", ".docx", ".txt", ".md", ".html"]

        dir_path = Path(directory)
        if not dir_path.exists():
            return {"success": False, "error": f"目录不存在: {directory}"}

        # 查找所有匹配的文件
        files = []
        for ext in file_types:
            files.extend(dir_path.glob(f"**/*{ext}"))

        logger.info(f"找到 {len(files)} 个文档需要处理")

        results = []
        for file_path in files:
            result = self.ingest_document(str(file_path))
            results.append(result)

        success_count = sum(1 for r in results if r.get("success", False))

        return {
            "success": True,
            "total_files": len(files),
            "successful": success_count,
            "failed": len(files) - success_count,
            "results": results,
        }

    def query(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        provider: Optional[str] = None,
        top_k: Optional[int] = None,
        retrieval_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """查询知识库

        Args:
            question: 用户问题
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            provider: LLM 提供者，None 则自动选择
            top_k: 检索文档数量，None 则使用配置默认值
            retrieval_mode: 检索模式 (hybrid/parent_child/cross_lingual/sparse/dense)，None 用配置默认
        """
        if not self._initialized:
            self.initialize()

        start_time = time.time()

        try:
            logger.info(f"处理查询: {question[:50]}...")

            effective_top_k = top_k if top_k is not None else self.retrieval_top_k

            # 0. History-Aware: 用历史改写查询，用于检索
            retrieval_question = self._rewrite_query_with_history(question, history)

            # 1. 检索相关文档（用改写后的查询）
            if self.vector_store:
                retrieved_docs = self._retrieve_documents(
                    retrieval_question, k=effective_top_k, mode=retrieval_mode
                )

                # 2. CRAG: 评估检索质量，质量低时改写查询重试
                if self.crag_enabled and retrieved_docs:
                    retrieved_docs = self._corrective_retrieve(
                        retrieval_question, retrieved_docs, effective_top_k
                    )

                # 2. 重排序（如启用）
                if self.reranking_enabled and retrieved_docs:
                    logger.info(f"执行重排序: {len(retrieved_docs)} 个文档")
                    retrieved_docs = self.vector_store.rerank_documents(
                        question, retrieved_docs, self.reranking_top_n
                    )
                    logger.info(f"重排序完成: {len(retrieved_docs)} 个文档")
            else:
                retrieved_docs = []

            # 3. 计算相关性分数，用于排序、sources 和上下文截断
            doc_scores: Dict[str, float] = {}
            if retrieved_docs and question:
                from .vector_store import KeywordCoverageReranker
                reranker = KeywordCoverageReranker()
                for doc in retrieved_docs:
                    # 用 page_content 作为 key 去重
                    key = doc.page_content
                    if key not in doc_scores:
                        doc_scores[key] = reranker.compute_score(question, doc)

            # 3.5 相关性门控：最高分过低时视为未找到相关文档
            # 避免不相关文档进入 LLM 上下文导致生成错误答案
            if retrieved_docs and doc_scores:
                max_score = max(doc_scores.values())
                if max_score < 0.1:
                    logger.info(
                        f"检索文档相关性过低 (max_score={max_score:.3f})，"
                        f"视为未找到相关文档"
                    )
                    retrieved_docs = []

            # 4. 构建上下文（按分数排序）
            context, num_docs_in_context = self._build_context(retrieved_docs, doc_scores)

            # 5. 构建去重的来源列表（附带分数）
            seen_sources = set()
            unique_sources = []
            for doc in retrieved_docs:
                src = doc.metadata.get("source", "未知")
                if src not in seen_sources:
                    seen_sources.add(src)
                    score = doc_scores.get(doc.page_content, 0.0)
                    unique_sources.append({"source": src, "score": round(score, 3)})

            # 6. 生成回答
            images = []
            if self.llm_manager and context:
                prompt = self._build_prompt(question, context, history, num_docs=num_docs_in_context)
                result = self.llm_manager.generate(prompt, provider=provider)
                answer = result.get("text", "生成失败")
                metadata = result.get("metadata", {})

                # 7. 答案溯源验证
                citation_report = []
                if self.citation_verify_enabled:
                    answer, citation_report = self._verify_citations(
                        answer, num_docs_in_context
                    )
                else:
                    citation_report = []
            elif self.llm_manager:
                # 无检索结果：不传历史（防止历史污染回答），直接告知无法回答
                prompt = (
                    f"用户问题：{question}\n\n"
                    f"知识库中没有找到与该问题相关的文档。"
                    f"请只回答：根据提供的文档，无法回答这个问题。"
                    f"不要提供任何其他信息，不要参考对话历史，不要编造答案。"
                )
                result = self.llm_manager.generate(prompt, provider=provider)
                answer = result.get("text", "生成失败")
                metadata = result.get("metadata", {})
                unique_sources = []
                citation_report = []
            else:
                answer = "知识库为空且 LLM 未初始化，请先添加文档并配置 LLM。"
                metadata = {"provider": "none"}
                citation_report = []
                unique_sources = []

            # 8. 从检索文档中提取图片路径
            if retrieved_docs and not images:
                images = self._extract_images(retrieved_docs)

            return {
                "success": True,
                "question": question,
                "answer": answer,
                "sources": unique_sources,
                "num_sources": len(unique_sources),
                "images": images,
                "processing_time": time.time() - start_time,
                "metadata": metadata,
                "citation_report": citation_report,
            }

        except Exception as e:
            logger.error(f"查询失败: {e}")
            return {
                "success": False,
                "question": question,
                "error": str(e),
                "processing_time": time.time() - start_time,
            }

    def _retrieve_documents(
        self, question: str, k: Optional[int] = None,
        mode: Optional[str] = None,
    ) -> List[Document]:
        """统一检索入口，按配置或指定模式选择检索策略。"""
        if not self.vector_store:
            return []

        effective_k = k if k is not None else self.retrieval_top_k

        # 显式指定检索模式时，跳过配置默认策略
        if mode:
            return self._dispatch_retrieval(question, effective_k, mode)

        # 父子上下文检索（优先级最高，可与混合搜索叠加）
        if self.parent_child_enabled:
            logger.info("使用父子上下文检索")
            return self.vector_store.parent_child_search(
                question, k=effective_k
            )

        # 多查询检索
        if self.multi_query_enabled:
            logger.info("使用多查询检索（Multi-Query）")
            return self.vector_store.multi_query_search(
                question,
                k=effective_k,
                llm_manager=self.llm_manager,
            )

        # 跨语言混合搜索
        if self.cross_lingual_enabled and self.hybrid_search_enabled:
            logger.info("使用跨语言混合搜索")
            return self.vector_store.cross_lingual_hybrid_search(
                question,
                k=effective_k,
                dense_weight=self.hybrid_dense_weight,
                sparse_weight=self.hybrid_sparse_weight,
            )

        # 普通混合搜索
        if self.hybrid_search_enabled:
            logger.info("使用混合搜索（向量 + BM25）")
            return self.vector_store.hybrid_search(
                question,
                k=effective_k,
                dense_weight=self.hybrid_dense_weight,
                sparse_weight=self.hybrid_sparse_weight,
            )

        # 带阈值的相似度搜索
        # ChromaDB 默认返回 L2 距离（越小越相似），
        # score_threshold 配置语义为"最低相似度"，需将距离转为相似度后过滤
        if self.score_threshold > 0:
            docs_with_scores = self.vector_store.similarity_search_with_score(
                question, k=effective_k
            )
            filtered = []
            for doc, distance in docs_with_scores:
                # L2 距离转相似度：similarity = 1 / (1 + distance)
                similarity = 1.0 / (1.0 + distance)
                if similarity >= self.score_threshold:
                    filtered.append(doc)
            return filtered

        # 基础相似度搜索（兜底）
        return self.vector_store.similarity_search(question, k=self.retrieval_top_k)

    def _dispatch_retrieval(
        self, question: str, k: int, mode: str
    ) -> List[Document]:
        """按显式指定的模式路由到对应检索方法。"""
        dispatch = {
            "parent_child": lambda: self.vector_store.parent_child_search(
                question, k=k
            ),
            "cross_lingual": lambda: self.vector_store.cross_lingual_hybrid_search(
                question,
                k=k,
                dense_weight=self.hybrid_dense_weight,
                sparse_weight=self.hybrid_sparse_weight,
            ),
            "hybrid": lambda: self.vector_store.hybrid_search(
                question,
                k=k,
                dense_weight=self.hybrid_dense_weight,
                sparse_weight=self.hybrid_sparse_weight,
            ),
            "dense": lambda: self.vector_store.similarity_search(question, k=k),
        }
        handler = dispatch.get(mode)
        if handler is None:
            logger.warning(f"未知检索模式 '{mode}'，回退到默认策略")
            return self._retrieve_documents(question, k=k)

        logger.info(f"使用指定检索模式: {mode}")
        return handler()

    def _corrective_retrieve(
        self, question: str, retrieved_docs: List[Document], k: int,
    ) -> List[Document]:
        """CRAG: 评估检索质量，质量低时改写查询重试。"""
        from .vector_store import KeywordCoverageReranker, reciprocal_rank_fusion

        reranker = KeywordCoverageReranker()
        scores = [reranker.compute_score(question, doc) for doc in retrieved_docs]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # 置信度门控：最高分已足够高时跳过 CRAG（节省 40-60% CRAG 调用）
        max_score = max(scores) if scores else 0.0
        if max_score >= 0.8:
            logger.info(
                f"CRAG: 最高分 {max_score:.2f} >= 0.8，检索质量足够，跳过 CRAG"
            )
            return retrieved_docs

        if avg_score >= self.crag_threshold:
            logger.info(
                f"CRAG: 检索质量合格 ({avg_score:.2f} >= {self.crag_threshold})"
            )
            return retrieved_docs

        logger.info(
            f"CRAG: 检索质量低 ({avg_score:.2f} < {self.crag_threshold})，尝试改写查询"
        )

        # 改写查询
        rewritten = self._rewrite_query(question)
        if not rewritten or rewritten == question:
            logger.info("CRAG: 查询改写未生效，使用原始结果")
            return retrieved_docs

        # 重新检索（跳过 CRAG 避免无限递归）
        original_mode = self.crag_enabled
        self.crag_enabled = False
        try:
            new_docs = self._retrieve_documents(rewritten, k=k)
        finally:
            self.crag_enabled = original_mode

        if not new_docs:
            return retrieved_docs

        # RRF 融合原始结果和改写后的结果
        original_scored = [(doc, s) for doc, s in zip(retrieved_docs, scores)]
        new_scores = [reranker.compute_score(question, doc) for doc in new_docs]
        new_scored = [(doc, s) for doc, s in zip(new_docs, new_scores)]
        fused = reciprocal_rank_fusion([original_scored, new_scored])
        result = [doc for doc, _ in fused[:k]]

        logger.info(
            f"CRAG: 改写重试完成，'{rewritten[:20]}...' → {len(result)} 个文档"
        )
        return result

    def _rewrite_query(self, question: str) -> str:
        """改写查询: 使用规则方法提取关键词重新组合（快速、确定性）。

        CRAG 改写结果通过 RRF 与原始检索结果融合，
        因此即使改写效果不如 LLM，原始结果仍然保留。
        """
        return self._keyword_rewrite(question)

    def _is_topic_switch(self, question: str, history: list) -> bool:
        """两层话题切换检测：关键词重叠 + embedding 余弦相似度。

        用于在 History-Aware 改写前判断新问题是否与历史话题相关，
        避免将无关新问题与旧话题混合导致检索到错误文档。

        Returns:
            True 表示检测到话题切换，应跳过改写。
        """
        if not history:
            return True

        import re

        # Layer 1: 关键词重叠（快速，~0ms）
        recent_text = " ".join(m.get("content", "") for m in history[-4:])

        def _tokenize(text: str) -> set:
            words = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text)
            stops = {
                "的", "了", "是", "在", "有", "和", "与", "或", "不", "也", "都",
                "请", "什么", "怎么", "如何", "为什么", "哪些", "这个", "那个",
                "the", "is", "a", "an", "of", "in", "to", "and", "or", "for",
                "what", "how", "why", "can", "do", "does",
            }
            return set(w.lower() for w in words if w.lower() not in stops and len(w) > 1)

        q_tokens = _tokenize(question)
        h_tokens = _tokenize(recent_text)
        if not q_tokens or not h_tokens:
            return True
        overlap = len(q_tokens & h_tokens) / len(q_tokens)
        if overlap < 0.2:
            return True  # 关键词重叠 < 20%，视为话题切换

        # Layer 2: Embedding 余弦相似度（~5ms，复用已有 embedding 模型）
        try:
            if self.vector_store and self.vector_store.embedder is not None:
                import numpy as np

                q_emb = self.vector_store.embedder.embed_query(question)
                h_emb = self.vector_store.embedder.embed_query(recent_text[:200])
                q_norm = np.linalg.norm(q_emb)
                h_norm = np.linalg.norm(h_emb)
                if q_norm > 0 and h_norm > 0:
                    cos_sim = float(np.dot(q_emb, h_emb) / (q_norm * h_norm))
                    if cos_sim < 0.3:
                        logger.info(
                            f"话题切换检测: embedding 余弦相似度 {cos_sim:.3f} < 0.3，跳过改写"
                        )
                        return True
        except Exception as e:
            logger.debug(f"话题切换 embedding 检测失败: {e}")

        return False

    def _rewrite_query_with_history(
        self, question: str, history: Optional[List[Dict[str, str]]]
    ) -> str:
        """用对话历史将指代性问题改写为独立查询（History-Aware Retrieval）

        核心思想：检索时只用改写后的独立查询，不传入原始历史。
        原始历史仅在生成阶段使用。

        示例：
            历史: [用户: "介绍 DeepSeek-V2", 助手: "DeepSeek-V2 是..."]
            当前: "它的推理能力怎么样？"
            改写: "DeepSeek-V2 的推理能力怎么样？"
        """
        if not history or not self.history_aware_enabled:
            return question

        # 只取最近 N 轮参与改写
        recent = history[-self.history_aware_max_history * 2 :]
        if not recent:
            return question

        # 快速检测是否包含指代词（如果纯新话题则无需改写）
        import re

        pronoun_pattern = re.compile(
            r"(它|它们|他|她|这|那|这个|那个|这些|那些|其|该|上述|前者|后者|上面|之前|刚才)"
        )
        if not pronoun_pattern.search(question):
            # 无指代词 → 直接跳过改写（对齐行业做法）
            return question

        if self.llm_manager is None:
            return question

        try:
            history_text = "\n".join(
                f"{'用户' if m.get('role') == 'user' else '助手'}：{m.get('content', '')}"
                for m in recent
            )

            prompt = (
                "根据对话历史，将用户的最新问题改写为一个独立、完整的问题。\n"
                "改写后的问题应该包含所有必要的上下文信息，"
                "使其在没有对话历史的情况下也能被理解。\n"
                "只输出改写后的问题，不要解释。\n\n"
                f"对话历史：\n{history_text}\n\n"
                f"最新问题：{question}\n\n"
                "改写后的问题："
            )

            result = self.llm_manager.generate(prompt)
            rewritten = result.get("text", "").strip()

            if rewritten and len(rewritten) > 2:
                logger.info(
                    f"History-Aware: '{question[:30]}' → '{rewritten[:30]}'"
                )
                return rewritten
        except Exception as e:
            logger.warning(f"History-Aware 查询改写失败: {e}")

        return question

    @staticmethod
    def _keyword_rewrite(question: str) -> str:
        """规则改写: 提取关键词，去掉常见提问词后重组。"""
        import re

        # 移除常见提问前缀
        q = re.sub(
            r"^(请|帮我|如何|怎么|怎样|什么是|什么是叫|什么叫|什么|哪个|为什么|能否|可以|请帮我|你能|告诉我)",
            "", question,
        )
        q = re.sub(r"[？?！!。.]+$", "", q).strip()
        # 如果处理结果太短（可能是全被去掉了），返回原文
        if len(q) < 3:
            return question
        return q


    def _build_context(
        self, documents: List[Document], doc_scores: Optional[Dict[str, float]] = None,
    ) -> Tuple[str, int]:
        """构建上下文，自动裁剪以适配模型 context window。

        Args:
            documents: 检索到的文档列表
            doc_scores: 文档相关性分数映射（page_content -> score），用于按分数排序截断

        Returns:
            (context_text, actual_doc_count): 上下文文本和实际包含的文档数
        """
        if not documents:
            return "", 0

        # 按相关性分数排序，确保裁剪时丢弃低分文档
        if doc_scores and len(documents) > 1:
            documents = sorted(
                documents,
                key=lambda d: doc_scores.get(d.page_content, 0.0),
                reverse=True,
            )

        # 先构建全部文档块
        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.metadata.get("source", "未知来源")
            content = doc.page_content

            # 构建元数据头部：将存储的 metadata 展示给 LLM
            meta_items = [f"来源: {source}"]
            title = doc.metadata.get("title", "")
            if title:
                meta_items.append(f"标题: {title}")
            authors = doc.metadata.get("authors", "")
            if authors:
                if isinstance(authors, list):
                    authors = ", ".join(str(a) for a in authors)
                meta_items.append(f"作者: {authors}")
            keywords = doc.metadata.get("keywords", "")
            if keywords:
                if isinstance(keywords, list):
                    keywords = ", ".join(str(k) for k in keywords)
                meta_items.append(f"关键词: {keywords}")
            meta_header = " | ".join(meta_items)

            context_parts.append(f"【文档 {i}】{meta_header}\n\n{content}\n")

        full_context = "\n---\n".join(context_parts)
        estimated_tokens = estimate_tokens(full_context)

        if estimated_tokens <= self.max_context_tokens:
            return full_context, len(documents)

        # 超出限制：逐个添加文档直到接近预算
        logger.warning(
            f"上下文超限: 估算 {estimated_tokens} tokens > 上限 {self.max_context_tokens}，开始裁剪"
        )
        budget = self.max_context_tokens
        truncated_parts = []
        for part in context_parts:
            part_tokens = estimate_tokens(part)
            if part_tokens > budget:
                break
            truncated_parts.append(part)
            budget -= part_tokens

        if not truncated_parts:
            logger.warning("上下文裁剪后为空，返回第一个文档截断版")
            first = context_parts[0]
            # 截断到预算
            text_budget = self.max_context_tokens * 3  # 粗略字符数
            return first[:text_budget] + "\n...(文档过长已截断)", 1

        dropped = len(context_parts) - len(truncated_parts)
        logger.info(f"上下文裁剪完成: 保留 {len(truncated_parts)} 个文档，丢弃 {dropped} 个")
        return "\n---\n".join(truncated_parts), len(truncated_parts)

    def _build_history_section(
        self,
        history: Optional[List[Dict[str, str]]],
        available_context_tokens: Optional[int] = None,
    ) -> str:
        """构建历史对话文本区段（Token 感知动态窗口 + 摘要压缩）

        策略：Sliding Window + Summary 混合
        - 超过 summary_threshold 轮的旧历史用 LLM 生成摘要
        - 最近 N 轮保留原文，并按 token 预算裁剪

        Args:
            history: 对话历史列表
            available_context_tokens: 可用于历史的 token 预算。
                如果提供，按预算动态裁剪；否则退回硬上限。
        """
        if not history:
            return ""

        # 硬上限
        effective_history = history[-self.history_max_turns * 2 :]

        # 摘要压缩：超过阈值的旧历史生成摘要
        threshold_msgs = self.history_summary_threshold * 2
        if len(effective_history) > threshold_msgs and self.llm_manager is not None:
            old_part = effective_history[:-threshold_msgs]
            recent_part = effective_history[-threshold_msgs:]

            summary = self._summarize_history(old_part)
            if summary:
                # 摘要 + 最近 N 轮原文
                effective_history = [{"role": "system", "content": f"【历史摘要】{summary}"}] + recent_part
            else:
                # 摘要失败，退回简单裁剪
                effective_history = recent_part
        else:
            # 未超过阈值，直接使用（后续由 token 预算裁剪）
            pass

        # Token 预算裁剪
        if available_context_tokens is not None and available_context_tokens > 0:
            max_history_tokens = int(
                available_context_tokens * self.history_token_budget_ratio
            )
            selected = []
            used_tokens = 0
            # 从最新开始，逐条累加直到预算用完
            for msg in reversed(effective_history):
                content = msg.get("content", "")
                msg_tokens = estimate_tokens(content) + 10  # +10 给角色标签
                if used_tokens + msg_tokens > max_history_tokens:
                    break
                selected.insert(0, msg)
                used_tokens += msg_tokens
            effective_history = selected

            if len(effective_history) < len(history):
                logger.debug(
                    f"历史裁剪: {len(history)} → {len(effective_history)} 条"
                    f" (预算 {max_history_tokens} tokens)"
                )

        if not effective_history:
            return ""

        parts = []
        for msg in effective_history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                parts.append(content)
            else:
                label = "用户" if role == "user" else "助手"
                parts.append(f"{label}：{content}")
        return "\n".join(parts)

    def _summarize_history(self, old_messages: List[Dict[str, str]]) -> Optional[str]:
        """将旧对话历史压缩为摘要

        Args:
            old_messages: 早期的对话消息列表

        Returns:
            压缩后的摘要文本，失败时返回 None
        """
        if not old_messages:
            return None

        try:
            history_text = "\n".join(
                f"{'用户' if m.get('role') == 'user' else '助手'}：{m.get('content', '')}"
                for m in old_messages
            )

            # 限制输入长度，避免摘要本身成本过高
            if len(history_text) > 3000:
                history_text = history_text[:3000] + "\n...(历史过长已截断)"

            prompt = (
                "请将以下对话历史压缩为简洁的摘要（200字以内），"
                "保留关键信息：讨论了什么主题、得出了什么结论、提到了哪些重要实体。\n"
                "只输出摘要，不要解释。\n\n"
                f"对话历史：\n{history_text}\n\n摘要："
            )

            result = self.llm_manager.generate(prompt)
            summary = result.get("text", "").strip()

            if summary and len(summary) > 10:
                logger.info(f"历史摘要生成成功: {len(old_messages)} 条 → {len(summary)} 字符")
                return summary

        except Exception as e:
            logger.warning(f"历史摘要生成失败: {e}")

        return None

    def _build_prompt(
        self,
        question: str,
        context: str,
        history: Optional[List[Dict[str, str]]] = None,
        num_docs: int = 0,
    ) -> str:
        """构建提示词（统一入口，含反幻觉约束、引用标注、历史对话）

        Token 预算分配：
        - context 已经被 _build_context 裁剪到 max_context_tokens 以内
        - 历史从 context 的剩余预算中分配 token_budget_ratio 比例
        """
        # 计算历史可用 token 预算
        context_tokens = estimate_tokens(context) if context else 0
        remaining_budget = max(0, self.max_context_tokens - context_tokens)
        history_section = self._build_history_section(history, remaining_budget)
        history_block = f"\n\n【对话历史】\n{history_section}\n" if history_section else ""

        # 引用约束（根据上下文中的实际文档数量动态生成）
        citation_rule = ""
        if num_docs > 0:
            citation_rule = f"""
3. 引用格式：参考文档中的来源编号为【文档 1】到【文档 {num_docs}】。
   - 你只能引用这些编号，例如"根据文档1的信息…"、"文档2指出…"
   - 绝对禁止使用论文原始编号（如 [1]、[32]、[39] 等），这些不是系统文档编号
   - 绝对禁止编造不存在的文档编号
"""

        # 反幻觉约束
        hallucination_warning = f"""
【重要约束】
1. 只使用参考文档中明确包含的信息，不要捏造、推断或补充文档中没有的概念、术语或数据
2. 如果文档中没有提到某个概念，直接回答"文档中没有提到"，不要尝试解释或推测
{citation_rule}4. 如果问题无法基于文档回答，明确说明"根据提供的文档，无法回答这个问题"
"""

        # 短事实检测（数值/时间类问题用精简 prompt）
        question_lower = question.lower()
        is_short_fact = any(
            kw in question_lower
            for kw in ["多久", "多少", "多长时间", "takes", "耗时", "时间", "ms", "秒"]
        )

        if is_short_fact:
            return (
                f"基于以下参考文档，直接提取并回答用户问题。"
                f"如果文档中有相关数值，直接给出答案，不需要解释。"
                f"{hallucination_warning}\n"
                f"参考文档：\n{context}{history_block}\n"
                f"用户问题：{question}\n\n请直接回答："
            )

        return (
            f"基于以下参考文档回答用户问题。"
            f"{hallucination_warning}"
            f"{history_block}\n"
            f"参考文档：\n{context}\n\n"
            f"用户问题：{question}\n\n请用中文回答。"
        )

    @staticmethod
    def _extract_images(documents: List[Document]) -> List[Dict[str, str]]:
        """从检索文档中提取图片路径，resolve 到本地绝对路径。

        匹配 Markdown 图片语法：![alt](path)
        路径查找优先级：
        1. data/images/{doc_name}_images/images/{image_path}
        2. data/images/{doc_name}_images/{image_path}

        Returns:
            [{"path": "本地绝对路径", "caption": "图片说明"}, ...]
        """
        import re as _re
        project_root = Path(__file__).parent.parent.parent
        image_base = project_root / "data" / "images"

        # 收集每个 source 对应的 doc_name
        source_to_doc_name: Dict[str, str] = {}
        for doc in documents:
            src = doc.metadata.get("source", "")
            if src and src not in source_to_doc_name:
                doc_name = Path(src).stem.replace(".md", "")
                source_to_doc_name[src] = doc_name

        seen_paths: set = set()
        images: List[Dict[str, str]] = []

        for doc in documents:
            src = doc.metadata.get("source", "")
            doc_name = source_to_doc_name.get(src, "")

            for match in _re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", doc.page_content):
                caption = match.group(1).strip()
                image_path = match.group(2).strip()

                # 跳过网络 URL 和绝对路径
                if image_path.startswith("http") or image_path.startswith("/"):
                    continue

                # 在 data/images/{doc_name}_images/ 下查找
                resolved = None
                if doc_name:
                    doc_images_dir = f"{doc_name}_images"
                    path1 = image_base / doc_images_dir / "images" / Path(image_path).name
                    path2 = image_base / doc_images_dir / Path(image_path).name
                    if path1.exists():
                        resolved = str(path1)
                    elif path2.exists():
                        resolved = str(path2)

                if resolved and resolved not in seen_paths:
                    seen_paths.add(resolved)
                    images.append({"path": resolved, "caption": caption})

        logger.info(f"提取到 {len(images)} 张相关图片")
        return images[:6]  # 限制最多返回 6 张

    def _verify_citations(
        self, answer: str, num_docs: int,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """校验答案中的文档引用编号是否真实存在。

        Args:
            answer: LLM 生成的回答文本
            num_docs: 上下文中实际提供的文档数量

        Returns:
            (可能追加警告的回答, 溯源报告列表)
        """
        import re

        report = []

        # 匹配 [文档N]、[文档 N]、[N]、文档N、文档 N 等引用格式
        patterns = [
            r"\[文档\s*(\d+)\]",
            r"文档\s*(\d+)",
            r"\[(\d+)\]",
        ]
        cited_nums: set = set()
        for pattern in patterns:
            for match in re.finditer(pattern, answer):
                cited_nums.add(int(match.group(1)))

        if not cited_nums:
            return answer, report

        valid_nums = set(range(1, num_docs + 1))
        invalid = cited_nums - valid_nums

        for n in sorted(cited_nums):
            report.append({
                "ref": n,
                "valid": n in valid_nums,
            })

        if not invalid:
            logger.info(f"溯源验证通过: 引用了 {len(cited_nums)} 个文档，全部有效")
            return answer, report

        logger.warning(
            f"溯源验证发现无效引用: {invalid} (上下文仅有 {num_docs} 个文档)"
        )

        if self.citation_warn_on_invalid:
            invalid_str = ", ".join(f"[文档{n}]" for n in sorted(invalid))
            answer += (
                f"\n\n---\n⚠️ **溯源警告**: 以上回答中引用了 {invalid_str}，"
                f"但提供的参考文档中不存在这些编号，请谨慎采信相关内容。"
            )

        return answer, report

    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {"initialized": self._initialized, "components": {}}

        # 文档处理器状态
        if self.document_processor:
            status["components"]["document_processor"] = "ready"

        # 向量存储状态
        if self.vector_store:
            try:
                info = self.vector_store.get_collection_info()
                status["components"]["vector_store"] = info
            except Exception as e:
                status["components"]["vector_store"] = {"error": str(e)}

        # LLM状态
        if self.llm_manager:
            try:
                stats = self.llm_manager.get_usage_stats()
                status["components"]["llm_manager"] = {
                    "available": True,
                    "providers": stats.get("api_providers", []),
                    "local_available": stats.get("local_model") is not None,
                }
            except Exception as e:
                status["components"]["llm_manager"] = {"error": str(e)}

        return status

    def reset(self) -> None:
        """重置RAG Chain"""
        self._initialized = False
        self.document_processor = None
        self.vector_store = None
        self.llm_manager = None
        logger.info("RAG Chain已重置")


class SimpleRAGChain:
    """简化版RAG Chain - 适合快速使用"""

    def __init__(self):
        self.chain = RAGChain()

    def __enter__(self):
        self.chain.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.chain.reset()

    def add(self, file_path: str) -> Dict[str, Any]:
        """添加文档"""
        return self.chain.ingest_document(file_path)

    def ask(self, question: str) -> Dict[str, Any]:
        """提问"""
        return self.chain.query(question)

    def status(self) -> Dict[str, Any]:
        """状态"""
        return self.chain.get_status()



