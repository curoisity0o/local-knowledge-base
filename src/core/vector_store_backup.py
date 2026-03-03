"""
向量存储模块
负责向量数据库的初始化和操作
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging

from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma, FAISS
try:
    from langchain_community.vectorstores import Qdrant
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Qdrant not available, install with: pip install qdrant-client")

from .config import get_config

logger = logging.getLogger(__name__)

class VectorStoreManager:
    """向量存储管理器"""
    
    def __init__(self, config=None):
        self.config = config or get_config("vector_store", {})
        self.embedder = None
        self.vector_store = None
        self.store_type = self.config.get("type", "chroma")
        
        # 初始化嵌入模型
        self._init_embedder()
    
    def _init_embedder(self) -> None:
        """初始化嵌入模型"""
        try:
            embedding_config = get_config("embeddings", {})
            model_name = embedding_config.get("model", "BAAI/bge-m3")
            device = embedding_config.get("device", "cpu")
            
            logger.info(f"初始化嵌入模型: {model_name}, 设备: {device}")
            
            self.embedder = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={"device": device},
                encode_kwargs={
                    "normalize_embeddings": embedding_config.get("normalize_embeddings", True),
                    "batch_size": embedding_config.get("batch_size", 32),
                }
            )
            
            logger.info("嵌入模型初始化成功")
            
        except Exception as e:
            logger.error(f"初始化嵌入模型失败: {e}")
            raise
    
    def _create_chroma_store(self, collection_name: Optional[str] = None) -> Chroma:
        """创建 Chroma 向量存储"""
        chroma_config = self.config.get("chroma", {})
        
        persist_directory = chroma_config.get(
            "persist_directory", 
            "./data/vector_store/chroma"
        )
        
        # 确保目录存在
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        collection_name = collection_name or chroma_config.get(
            "collection_name", 
            "knowledge_base"
        )
        
        logger.info(f"创建 Chroma 向量存储: {persist_directory}, 集合: {collection_name}")
        
        return Chroma(
            embedding_function=self.embedder,
            persist_directory=persist_directory,
            collection_name=collection_name,
        )
    
    def _create_qdrant_store(self, collection_name: Optional[str] = None) -> Qdrant:
        """创建 Qdrant 向量存储"""
        qdrant_config = self.config.get("qdrant", {})
        
        url = qdrant_config.get("url", "http://localhost:6333")
        collection_name = collection_name or qdrant_config.get(
            "collection_name", 
            "knowledge_base"
        )
        
        logger.info(f"创建 Qdrant 向量存储: {url}, 集合: {collection_name}")
        
        return Qdrant.from_documents(
            documents=[],  # 空文档，稍后添加
            embedding=self.embedder,
            url=url,
            collection_name=collection_name,
            prefer_grpc=qdrant_config.get("prefer_grpc", False),
        )
    
    def _create_faiss_store(self) -> FAISS:
        """创建 FAISS 向量存储"""
        faiss_config = self.config.get("faiss", {})
        index_path = faiss_config.get("index_path", "./data/vector_store/faiss.index")
        
        logger.info(f"创建 FAISS 向量存储: {index_path}")
        
        return FAISS(
            embedding_function=self.embedder.embed_query,
            index_path=index_path,
        )
    
    def create_vector_store(self, store_type: Optional[str] = None, 
                           collection_name: Optional[str] = None) -> Any:
        """创建向量存储实例"""
        store_type = store_type or self.store_type
        
        try:
            if store_type == "chroma":
                self.vector_store = self._create_chroma_store(collection_name)
            elif store_type == "qdrant":
                self.vector_store = self._create_qdrant_store(collection_name)
            elif store_type == "faiss":
                self.vector_store = self._create_faiss_store()
            else:
                raise ValueError(f"不支持的向量存储类型: {store_type}")
            
            logger.info(f"向量存储创建成功: {store_type}")
            return self.vector_store
            
        except Exception as e:
            logger.error(f"创建向量存储失败: {e}")
            raise
    
    def get_vector_store(self, store_type: Optional[str] = None, 
                        collection_name: Optional[str] = None) -> Any:
        """获取向量存储实例，如果不存在则创建"""
        if self.vector_store is None:
            return self.create_vector_store(store_type, collection_name)
        return self.vector_store
    
    def add_documents(self, documents: List[Document], 
                     store_type: Optional[str] = None,
                     collection_name: Optional[str] = None) -> List[str]:
        """添加文档到向量存储"""
        try:
            vector_store = self.get_vector_store(store_type, collection_name)
            
            logger.info(f"添加 {len(documents)} 个文档到向量存储")
            
            # 添加文档
            ids = vector_store.add_documents(documents)
            
            # 如果是 Chroma，持久化
            if store_type == "chroma" or self.store_type == "chroma":
                if hasattr(vector_store, '_persist'):
                    vector_store._persist()
            
            logger.info(f"文档添加成功，生成 {len(ids)} 个向量")
            return ids
            
        except Exception as e:
            logger.error(f"添加文档到向量存储失败: {e}")
            raise
    
    def similarity_search(self, query: str, k: int = 4, 
                         filter: Optional[Dict] = None) -> List[Document]:
        """相似度搜索"""
        try:
            vector_store = self.get_vector_store()
            
            logger.info(f"执行相似度搜索: '{query[:50]}...', k={k}")
            
            results = vector_store.similarity_search(
                query=query,
                k=k,
                filter=filter,
            )
            
            logger.info(f"搜索完成，找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"相似度搜索失败: {e}")
            return []
    
    def similarity_search_with_score(self, query: str, k: int = 4,
                                    filter: Optional[Dict] = None) -> List[Tuple[Document, float]]:
        """带分数的相似度搜索"""
        try:
            vector_store = self.get_vector_store()
            
            logger.info(f"执行带分数的相似度搜索: '{query[:50]}...', k={k}")
            
            results = vector_store.similarity_search_with_score(
                query=query,
                k=k,
                filter=filter,
            )
            
            logger.info(f"搜索完成，找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"带分数的相似度搜索失败: {e}")
            return []
    
    def max_marginal_relevance_search(self, query: str, k: int = 4, 
                                     fetch_k: int = 20) -> List[Document]:
        """最大边际相关性搜索"""
        try:
            vector_store = self.get_vector_store()
            
            logger.info(f"执行 MMR 搜索: '{query[:50]}...', k={k}, fetch_k={fetch_k}")
            
            results = vector_store.max_marginal_relevance_search(
                query=query,
                k=k,
                fetch_k=fetch_k,
            )
            
            logger.info(f"MMR 搜索完成，找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"MMR 搜索失败: {e}")
            return []
    
    def hybrid_search(self, query: str, k: int = 4, 
                     dense_weight: float = 0.7,
                     sparse_weight: float = 0.3) -> List[Document]:
        """混合搜索（密集 + 稀疏）"""
        try:
            # 密集向量搜索
            dense_results = self.similarity_search_with_score(query, k * 2)
            
            # TODO: 实现稀疏搜索（BM25）
            # sparse_results = self.sparse_search(query, k * 2)
            
            # 简单版本：只使用密集向量
            # 未来可以添加真正的混合搜索
            
            # 按分数排序
            dense_results.sort(key=lambda x: x[1], reverse=True)
            final_results = [doc for doc, score in dense_results[:k]]
            
            logger.info(f"混合搜索完成，找到 {len(final_results)} 个结果")
            return final_results
            
        except Exception as e:
            logger.error(f"混合搜索失败: {e}")
            return self.similarity_search(query, k)
    
    def delete_documents(self, ids: List[str]) -> None:
        """删除文档"""
        try:
            vector_store = self.get_vector_store()
            
            if hasattr(vector_store, 'delete'):
                vector_store.delete(ids=ids)
                logger.info(f"删除 {len(ids)} 个文档")
            else:
                logger.warning("当前向量存储不支持删除操作")
                
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
    
    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            vector_store = self.get_vector_store()
            
            info = {
                "store_type": self.store_type,
                "embedding_model": self.embedder.model_name if self.embedder else "unknown",
            }
            
            # 尝试获取文档数量
            try:
                if hasattr(vector_store, '_collection'):
                    collection = vector_store._collection
                    if hasattr(collection, 'count'):
                        info["document_count"] = collection.count()
            except:
                pass
            
            # 尝试获取更多信息
            if self.store_type == "chroma":
                info["persist_directory"] = self.config.get("chroma", {}).get("persist_directory")
                info["collection_name"] = self.config.get("chroma", {}).get("collection_name")
            
            return info
            
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {}
    
    def clear_collection(self) -> None:
        """清空集合"""
        try:
            if self.store_type == "chroma":
                # Chroma 清空：删除持久化目录
                persist_directory = self.config.get("chroma", {}).get("persist_directory")
                if persist_directory and Path(persist_directory).exists():
                    import shutil
                    shutil.rmtree(persist_directory)
                    logger.info(f"清空 Chroma 集合: {persist_directory}")
                    
                    # 重新创建空集合
                    self.vector_store = None
                    self.create_vector_store()
            else:
                logger.warning(f"清空操作不支持存储类型: {self.store_type}")
                
        except Exception as e:
            logger.error(f"清空集合失败: {e}")


# 便捷函数
def create_vector_store_manager(config=None) -> VectorStoreManager:
    """创建向量存储管理器实例"""
    return VectorStoreManager(config)

def add_documents_to_store(documents: List[Document], config=None) -> List[str]:
    """添加文档到向量存储"""
    manager = create_vector_store_manager(config)
    return manager.add_documents(documents)

def search_similar_documents(query: str, k: int = 4, config=None) -> List[Document]:
    """搜索相似文档"""
    manager = create_vector_store_manager(config)
    return manager.similarity_search(query, k)