"""
RAG Chain 模块
完整的RAG流水线实现
"""

from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import logging
import time

from langchain_core.documents import Document

from .config import get_config
from .document_processor import DocumentProcessor
from .vector_store import SimpleVectorStore
from .llm_manager import LLMManager

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

    def query(self, question: str, use_history: bool = False) -> Dict[str, Any]:
        """查询知识库"""
        if not self._initialized:
            self.initialize()

        start_time = time.time()

        try:
            logger.info(f"处理查询: {question[:50]}...")

            # 1. 检索相关文档
            if self.vector_store:
                if self.score_threshold > 0:
                    docs_with_scores = self.vector_store.similarity_search_with_score(
                        question, k=self.retrieval_top_k
                    )
                    # 过滤低分文档
                    filtered_docs = [
                        (doc, score)
                        for doc, score in docs_with_scores
                        if score <= self.score_threshold
                    ]
                    retrieved_docs = [doc for doc, _ in filtered_docs]
                else:
                    retrieved_docs = self.vector_store.similarity_search(
                        question, k=self.retrieval_top_k
                    )
            else:
                retrieved_docs = []

            # 2. 构建上下文
            context = self._build_context(retrieved_docs)

            # 3. 生成回答
            if self.llm_manager and context:
                prompt = self._build_prompt(question, context)
                result = self.llm_manager.generate(prompt)
                answer = result.get("text", "生成失败")
                metadata = result.get("metadata", {})
            elif context:
                answer = f"基于检索到的文档：\n\n{context[:500]}..."
                metadata = {"provider": "retrieval_only"}
            else:
                answer = "知识库为空，请先添加文档。"
                metadata = {"provider": "none"}

            return {
                "success": True,
                "question": question,
                "answer": answer,
                "sources": [
                    {
                        "content": doc.page_content[:200] + "..."
                        if len(doc.page_content) > 200
                        else doc.page_content,
                        "source": doc.metadata.get("source", "未知"),
                        "page": doc.metadata.get("page", None),
                    }
                    for doc in retrieved_docs
                ],
                "num_sources": len(retrieved_docs),
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

    def _build_context(self, documents: List[Document]) -> str:
        """构建上下文"""
        if not documents:
            return ""

        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.metadata.get("source", "未知来源")
            content = doc.page_content
            context_parts.append(f"【文档 {i}】来源: {source}\n\n{content}\n")

        return "\n---\n".join(context_parts)

    def _build_prompt(self, question: str, context: str) -> str:
        """构建提示词"""
        return f"""请基于以下参考文档回答用户问题。

参考文档：
{context}

用户问题：{question}

请根据参考文档内容回答。回答要准确、简洁，并注明来源。如果文档中没有相关信息，请如实说明。"""

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


# 便捷函数
def create_rag_chain(config: Optional[Dict] = None) -> RAGChain:
    """创建RAG Chain"""
    return RAGChain(config)


def simple_rag(file_path: str, question: str) -> str:
    """简单的RAG问答"""
    with SimpleRAGChain() as chain:
        # 添加文档
        chain.add(file_path)
        # 提问
        result = chain.ask(question)
        return result.get("answer", result.get("error", "失败"))
