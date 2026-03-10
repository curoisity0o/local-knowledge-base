"""
向量存储扩展功能测试

测试 SimpleVectorStore 的 delete_by_source、get_documents_by_source、get_all_sources 方法
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.core.vector_store import SimpleVectorStore
from langchain_core.documents import Document


class TestVectorStoreExtended:
    """向量存储扩展功能测试类"""

    @pytest.fixture
    def mock_vector_store(self):
        """创建模拟的向量存储"""
        vs = SimpleVectorStore.__new__(SimpleVectorStore)
        vs.config = {}
        vs.embedder = None
        vs.vector_store = MagicMock()
        vs.store_type = "chroma"
        vs._initialized = True
        vs._using_ollama = False
        return vs

    def test_get_documents_by_source(self, mock_vector_store):
        """测试根据源路径获取文档"""
        # 模拟 ChromaDB 返回的数据
        mock_results = {
            "documents": ["doc content 1", "doc content 2"],
            "metadatas": [
                {"source": "/path/to/file.txt", "page": 1},
                {"source": "/path/to/file.txt", "page": 2}
            ],
            "ids": ["id1", "id2"]
        }

        mock_collection = MagicMock()
        mock_collection.get.return_value = mock_results
        mock_vector_store.vector_store._collection = mock_collection

        # 调用方法
        docs = mock_vector_store.get_documents_by_source("/path/to/file.txt")

        # 验证结果
        assert len(docs) == 2
        assert docs[0].page_content == "doc content 1"
        assert docs[1].page_content == "doc content 2"
        mock_collection.get.assert_called_once_with(where={"source": "/path/to/file.txt"})

    def test_get_documents_by_source_empty(self, mock_vector_store):
        """测试获取不存在的源路径文档"""
        mock_results = {"documents": [], "metadatas": [], "ids": []}

        mock_collection = MagicMock()
        mock_collection.get.return_value = mock_results
        mock_vector_store.vector_store._collection = mock_collection

        docs = mock_vector_store.get_documents_by_source("/nonexistent/path.txt")

        assert len(docs) == 0

    def test_delete_by_source(self, mock_vector_store):
        """测试根据源路径删除向量"""
        # 模拟 ChromaDB 返回要删除的 IDs
        mock_results = {
            "documents": ["content"],
            "metadatas": [{"source": "/path/to/file.txt"}],
            "ids": ["id1", "id2", "id3"]
        }

        mock_collection = MagicMock()
        mock_collection.get.return_value = mock_results
        mock_vector_store.vector_store._collection = mock_collection

        # 调用删除方法
        result = mock_vector_store.delete_by_source("/path/to/file.txt")

        # 验证结果
        assert result is True
        mock_collection.get.assert_called_once_with(where={"source": "/path/to/file.txt"})
        mock_collection.delete.assert_called_once_with(ids=["id1", "id2", "id3"])

    def test_delete_by_source_not_found(self, mock_vector_store):
        """测试删除不存在的源路径"""
        mock_results = {"documents": [], "metadatas": [], "ids": []}

        mock_collection = MagicMock()
        mock_collection.get.return_value = mock_results
        mock_vector_store.vector_store._collection = mock_collection

        # 应该返回 True（幂等性：删除不存在的资源视为成功）
        result = mock_vector_store.delete_by_source("/nonexistent/path.txt")

        assert result is True

    def test_delete_by_source_no_collection(self, mock_vector_store):
        """测试没有 _collection 属性的情况"""
        mock_vector_store.vector_store = MagicMock()
        del mock_vector_store.vector_store._collection

        result = mock_vector_store.delete_by_source("/path/to/file.txt")

        assert result is False

    def test_get_all_sources(self, mock_vector_store):
        """测试获取所有源文件路径"""
        mock_results = {
            "documents": ["content1", "content2", "content3"],
            "metadatas": [
                {"source": "/path/file1.txt"},
                {"source": "/path/file2.txt"},
                {"source": "/path/file1.txt"}  # 重复源
            ],
            "ids": ["id1", "id2", "id3"]
        }

        mock_collection = MagicMock()
        mock_collection.get.return_value = mock_results
        mock_vector_store.vector_store._collection = mock_collection

        sources = mock_vector_store.get_all_sources()

        # 验证去重结果
        assert len(sources) == 2
        assert "/path/file1.txt" in sources
        assert "/path/file2.txt" in sources

    def test_get_all_sources_empty(self, mock_vector_store):
        """测试空向量存储"""
        mock_results = {"documents": [], "metadatas": [], "ids": []}

        mock_collection = MagicMock()
        mock_collection.get.return_value = mock_results
        mock_vector_store.vector_store._collection = mock_collection

        sources = mock_vector_store.get_all_sources()

        assert sources == []

    def test_get_all_sources_no_metadata_source(self, mock_vector_store):
        """测试没有 source 元数据的情况"""
        mock_results = {
            "documents": ["content"],
            "metadatas": [{}],  # 空元数据
            "ids": ["id1"]
        }

        mock_collection = MagicMock()
        mock_collection.get.return_value = mock_results
        mock_vector_store.vector_store._collection = mock_collection

        sources = mock_vector_store.get_all_sources()

        assert sources == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
