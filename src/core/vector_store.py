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
            # 动态导入以避免启动时错误
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain_community.vectorstores import Chroma

            # 初始化嵌入模型 - 优先使用本地ModelScope模型
            # 使用环境变量或默认路径
            model_cache_base = os.getenv("MODEL_CACHE_PATH", str(Path.home() / ".cache" / "models"))
            default_model_path = Path(model_cache_base) / "iic" / "nlp_corom_sentence-embedding_chinese-base"

            # 检查本地模型是否存在
            if default_model_path.exists() and default_model_path.is_dir():
                model_name = str(default_model_path)
                logger.info(f"使用本地ModelScope嵌入模型: {model_name}")
            else:
                # 回退到配置中的模型
                model_name = get_config("embeddings.model", "BAAI/bge-m3")
                logger.info(f"使用配置嵌入模型: {model_name}")

            device = get_config("embeddings.device", "cpu")
            normalize_embeddings = get_config("embeddings.normalize_embeddings", True)
            batch_size = get_config("embeddings.batch_size", 32)

            logger.info(f"初始化嵌入模型: {model_name}, 设备: {device}")

            self.embedder = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"device": device},
                encode_kwargs={
                    "normalize_embeddings": normalize_embeddings,
                    "batch_size": batch_size,
                },
            )

            # 初始化向量存储
            if self.store_type == "chroma":
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
            "embedding_model": self.embedder.model_name if self.embedder else "unknown",
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
