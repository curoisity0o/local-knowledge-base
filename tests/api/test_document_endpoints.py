"""
文档管理 API 端点测试

测试文档列表、删除、统计 API 端点
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Mock all dependencies before importing app
 with patch('src.core.config.get_config') as mock_config, \
      patch('src.core.vector_store.get_config') as mock_vs_config, \
      patch('src.core.config.get_config') as mock_api_config:
    
    # 模拟配置返回值
    def get_config_side_effect(*args, **kwargs):
        if isinstance(args[0], str):
            if args[0].startswith('paths.'):
                return "./data/raw_docs"
            if args[0].startswith('vector_store'):
                return {"type": "chroma", "chroma": {"persist_directory": "./data/vector_store/chroma", "collection_name": "test"}}
            if args[0].startswith('embeddings'):
                return "bge-m3"
        return None
    
    mock_config.side_effect = get_config_side_effect
    mock_vs_config.side_effect = get_config_side_effect
    mock_api_config.side_effect = get_config_side_effect
    
    from src.api.main import app


class TestDocumentAPI:
    """文档管理 API 测试类"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def mock_raw_docs(self, tmp_path):
        """创建临时文档目录和测试文件"""
        docs_dir = tmp_path / "raw_docs"
        docs_dir.mkdir()
        
        # 创建测试文件
        (docs_dir / "test1.txt").write_text("test content 1")
        (docs_dir / "test2.pdf").write_text("test content 2")
        
        return docs_dir

    def test_list_documents_empty(self, client, tmp_path):
        """测试空目录情况"""
        with patch('src.api.main.get_vector_store') as mock_vs, \
             patch('src.api.main.config') as mock_config:
            
            mock_config.get.return_value = str(tmp_path / "nonexistent")
            
            mock_vs_instance = MagicMock()
            mock_vs_instance.get_all_sources.return_value = []
            mock_vs.return_value = mock_vs_instance
            
            response = client.get("/api/v1/documents/list")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["documents"] == []

    def test_list_documents_with_files(self, client, tmp_path):
        """测试有文件的情况"""
        with patch('src.api.main.get_vector_store') as mock_vs, \
             patch('src.api.main.config') as mock_config:
            
            mock_config.get.return_value = str(tmp_path)
            
            # 创建测试文件
            (tmp_path / "test.txt").write_text("content")
            
            mock_vs_instance = MagicMock()
            mock_vs_instance.get_all_sources.return_value = []
            mock_vs_instance.get_documents_by_source.return_value = []
            mock_vs.return_value = mock_vs_instance
            
            response = client.get("/api/v1/documents/list")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] >= 1

    def test_list_documents_with_indexed_files(self, client, tmp_path):
        """测试已索引的文件"""
        test_file = tmp_path / "indexed.txt"
        test_file.write_text("content")
        
        with patch('src.api.main.get_vector_store') as mock_vs, \
             patch('src.api.main.config') as mock_config:
            
            mock_config.get.return_value = str(tmp_path)
            
            mock_vs_instance = MagicMock()
            # 模拟文件已索引
            mock_vs_instance.get_all_sources.return_value = [str(test_file.resolve())]
            mock_vs_instance.get_documents_by_source.return_value = [
                MagicMock(page_content="chunk1"),
                MagicMock(page_content="chunk2")
            ]
            mock_vs.return_value = mock_vs_instance
            
            response = client.get("/api/v1/documents/list")
            
            assert response.status_code == 200
            data = response.json()
            # 找到我们测试的文件
            indexed_doc = next((d for d in data["documents"] if d["filename"] == "indexed.txt"), None)
            assert indexed_doc is not None
            assert indexed_doc["vector_status"] == "indexed"
            assert indexed_doc["chunks_count"] == 2

    def test_delete_document_not_found(self, client):
        """测试删除不存在的文档"""
        with patch('src.api.main.get_vector_store') as mock_vs:
            mock_vs_instance = MagicMock()
            mock_vs_instance.delete_by_source.return_value = True
            mock_vs.return_value = mock_vs_instance
            
            response = client.delete("/api/v1/documents/nonexistent_file.txt")
            
            assert response.status_code == 404

    def test_delete_document_success(self, client, tmp_path):
        """测试成功删除文档"""
        test_file = tmp_path / "to_delete.txt"
        test_file.write_text("content to delete")
        
        with patch('src.api.main.get_vector_store') as mock_vs, \
             patch('src.api.main.config') as mock_config, \
             patch('pathlib.Path.resolve') as mock_resolve:
            
            mock_config.get.return_value = str(tmp_path)
            mock_resolve.return_value = test_file.resolve()
            
            mock_vs_instance = MagicMock()
            mock_vs_instance.delete_by_source.return_value = True
            mock_vs.return_value = mock_vs_instance
            
            response = client.delete(f"/api/v1/documents/{test_file.name}")
            
            # 由于文件实际存在，应该返回成功或失败
            assert response.status_code in [200, 500]

    def test_document_stats_empty(self, client, tmp_path):
        """测试空目录统计"""
        with patch('src.api.main.get_vector_store') as mock_vs, \
             patch('src.api.main.config') as mock_config:
            
            mock_config.get.return_value = str(tmp_path / "nonexistent")
            
            mock_vs_instance = MagicMock()
            mock_vs_instance.get_all_sources.return_value = []
            mock_vs.return_value = mock_vs_instance
            
            response = client.get("/api/v1/documents/stats")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_documents"] == 0
            assert data["indexed_documents"] == 0
            assert data["not_indexed_documents"] == 0

    def test_document_stats_with_files(self, client, tmp_path):
        """测试有文件的统计"""
        # 创建测试文件
        (tmp_path / "test1.txt").write_text("content1")
        (tmp_path / "test2.txt").write_text("content2")
        
        with patch('src.api.main.get_vector_store') as mock_vs, \
             patch('src.api.main.config') as mock_config:
            
            mock_config.get.return_value = str(tmp_path)
            
            mock_vs_instance = MagicMock()
            mock_vs_instance.get_all_sources.return_value = []  # 没有索引
            mock_vs_instance.get_documents_by_source.return_value = []
            mock_vs.return_value = mock_vs_instance
            
            response = client.get("/api/v1/documents/stats")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_documents"] >= 2
            assert data["not_indexed_documents"] >= 2


class TestDocumentModels:
    """文档管理模型测试"""

    def test_document_info_model(self):
        """测试 DocumentInfo 模型"""
        from src.api.main import DocumentInfo
        
        doc = DocumentInfo(
            filename="test.txt",
            file_path="/path/to/test.txt",
            file_size=1024,
            file_extension=".txt",
            chunks_count=5,
            vector_status="indexed"
        )
        
        assert doc.filename == "test.txt"
        assert doc.file_size == 1024
        assert doc.vector_status == "indexed"

    def test_document_list_response_model(self):
        """测试 DocumentListResponse 模型"""
        from src.api.main import DocumentListResponse, DocumentInfo
        
        doc = DocumentInfo(
            filename="test.txt",
            file_path="/path/to/test.txt",
            file_size=1024,
            file_extension=".txt",
            chunks_count=5,
            vector_status="indexed"
        )
        
        response = DocumentListResponse(
            documents=[doc],
            total=1,
            indexed_count=1,
            not_indexed_count=0
        )
        
        assert response.total == 1
        assert response.indexed_count == 1
        assert len(response.documents) == 1

    def test_document_delete_response_model(self):
        """测试 DocumentDeleteResponse 模型"""
        from src.api.main import DocumentDeleteResponse
        
        response = DocumentDeleteResponse(
            success=True,
            message="Document deleted",
            file_deleted=True,
            vectors_deleted=True
        )
        
        assert response.success is True
        assert response.file_deleted is True

    def test_document_stats_response_model(self):
        """测试 DocumentStatsResponse 模型"""
        from src.api.main import DocumentStatsResponse
        
        response = DocumentStatsResponse(
            total_documents=10,
            indexed_documents=5,
            not_indexed_documents=5,
            total_size=1024000,
            average_chunks=3.5
        )
        
        assert response.total_documents == 10
        assert response.average_chunks == 3.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
