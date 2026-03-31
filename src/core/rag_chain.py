"""
RAG Chain 模块
完整的RAG流水线实现
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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

            # 2. 添加到向量存储
            ids = []
            if self.vector_store:
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

            # 1. 检索相关文档
            if self.vector_store:
                retrieved_docs = self._retrieve_documents(
                    question, k=effective_top_k, mode=retrieval_mode
                )

                # 2. CRAG: 评估检索质量，质量低时改写查询重试
                if self.crag_enabled and retrieved_docs:
                    retrieved_docs = self._corrective_retrieve(
                        question, retrieved_docs, effective_top_k
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

            # 3. 构建上下文
            context = self._build_context(retrieved_docs)

            # 4. 构建去重的来源列表
            seen_sources = set()
            unique_sources = []
            for doc in retrieved_docs:
                src = doc.metadata.get("source", "未知")
                if src not in seen_sources:
                    seen_sources.add(src)
                    unique_sources.append(src)

            # 5. 生成回答
            if self.llm_manager and context:
                prompt = self._build_prompt(question, context, history)
                result = self.llm_manager.generate(prompt, provider=provider)
                answer = result.get("text", "生成失败")
                metadata = result.get("metadata", {})
            elif self.llm_manager:
                # 无检索结果但有 LLM，直接回答
                history_context = self._build_history_section(history)
                if history_context:
                    prompt = (
                        f"【对话历史】\n{history_context}\n\n"
                        f"用户问题：{question}\n\n"
                        f"知识库中没有找到相关信息，请结合对话历史如实回答。"
                    )
                else:
                    prompt = question
                result = self.llm_manager.generate(prompt, provider=provider)
                answer = result.get("text", "生成失败")
                metadata = result.get("metadata", {})
                unique_sources = []
            else:
                answer = "知识库为空且 LLM 未初始化，请先添加文档并配置 LLM。"
                metadata = {"provider": "none"}

            return {
                "success": True,
                "question": question,
                "answer": answer,
                "sources": unique_sources,
                "num_sources": len(unique_sources),
                "processing_time": time.time() - start_time,
                "metadata": metadata,
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
        new_scored = [(doc, 1.0) for doc in new_docs]
        fused = reciprocal_rank_fusion([original_scored, new_scored])
        result = [doc for doc, _ in fused[:k]]

        logger.info(
            f"CRAG: 改写重试完成，'{rewritten[:20]}...' → {len(result)} 个文档"
        )
        return result

    def _rewrite_query(self, question: str) -> str:
        """改写查询: 优先 LLM，fallback 到关键词提取。"""
        # 尝试 LLM 改写
        if self.llm_manager is not None:
            try:
                prompt = (
                    f"请用不同方式重新表述以下问题，保持核心含义不变，"
                    f"直接输出改写后的问题，不要解释。\n\n问题：{question}"
                )
                result = self.llm_manager.generate(prompt)
                rewritten = result.get("text", "").strip()
                if rewritten and rewritten != question and len(rewritten) > 2:
                    logger.info(f"CRAG: LLM 改写 '{question[:20]}' → '{rewritten[:20]}'")
                    return rewritten
            except Exception as e:
                logger.warning(f"CRAG: LLM 改写失败: {e}")

        # 规则 fallback: 提取关键词重新组合
        return self._keyword_rewrite(question)

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


    def _build_context(self, documents: List[Document]) -> str:
        """构建上下文，自动裁剪以适配模型 context window。"""
        if not documents:
            return ""

        # 先构建全部文档块
        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.metadata.get("source", "未知来源")
            content = doc.page_content
            context_parts.append(f"【文档 {i}】来源: {source}\n\n{content}\n")

        full_context = "\n---\n".join(context_parts)
        estimated_tokens = estimate_tokens(full_context)

        if estimated_tokens <= self.max_context_tokens:
            return full_context

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
            return first[:text_budget] + "\n...(文档过长已截断)"

        dropped = len(context_parts) - len(truncated_parts)
        logger.info(f"上下文裁剪完成: 保留 {len(truncated_parts)} 个文档，丢弃 {dropped} 个")
        return "\n---\n".join(truncated_parts)

    @staticmethod
    def _build_history_section(
        history: Optional[List[Dict[str, str]]],
    ) -> str:
        """构建历史对话文本区段"""
        if not history:
            return ""
        parts = []
        for msg in history[-6:]:  # 最近6轮
            role = "用户" if msg.get("role") == "user" else "助手"
            parts.append(f"{role}：{msg.get('content', '')}")
        return "\n".join(parts)

    def _build_prompt(
        self,
        question: str,
        context: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """构建提示词（统一入口，含反幻觉约束、引用标注、历史对话）"""
        history_section = self._build_history_section(history)
        history_block = f"\n\n【对话历史】\n{history_section}\n" if history_section else ""

        # 反幻觉约束
        hallucination_warning = """
【重要约束】
1. 只使用参考文档中明确包含的信息，不要捏造、推断或补充文档中没有的概念、术语或数据
2. 如果文档中没有提到某个概念，直接回答"文档中没有提到"，不要尝试解释或推测
3. 引用格式：只能引用文档中明确存在的来源（如"根据文档1"、"论文指出"），不要生成虚假引用
4. 如果问题无法基于文档回答，明确说明"根据提供的文档，无法回答这个问题"
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



