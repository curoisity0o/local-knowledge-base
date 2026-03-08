"""
简化版向量存储模块
避免复杂的导入问题
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging
import os

from langchain_core.documents import Document

from .config import get_config

logger = logging.getLogger(__name__)


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
                    model=ollama_model,
                    base_url="http://localhost:11434"
                )
                self._using_ollama = True
                logger.info("Ollama 嵌入模型初始化成功")
                
            except Exception as e:
                logger.error(f"Ollama 嵌入模型初始化失败: {e}")
                logger.error("请确保 Ollama 服务正在运行: ollama serve")
                logger.error("请确保已下载嵌入模型: ollama pull bge-m3")
                raise RuntimeError(f"无法初始化 Ollama 嵌入模型: {e}")

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

    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        self._ensure_initialized()

        info = {
            "store_type": self.store_type,
            "embedding_model": "ollama" if hasattr(self, '_using_ollama') else "huggingface",
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
        except Exception:
            pass

        return info


# 便捷函数
def create_vector_store(config=None) -> SimpleVectorStore:
    """创建向量存储实例"""
    return SimpleVectorStore(config)
