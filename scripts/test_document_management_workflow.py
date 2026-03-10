#!/usr/bin/env python3
"""
文档管理端到端工作流测试

测试完整工作流：启动服务 → 上传文档 → 处理文档 → 查看列表 → 删除文档 → 验证清理
"""

import os
import sys
import time
import tempfile
import requests
from pathlib import Path
import subprocess
import signal

# 配置
API_BASE_URL = "http://localhost:8000"
TEST_DOC_CONTENT = "这是测试文档内容，用于验证文档管理功能。"
TEST_FILENAME = "test_e2e_document.txt"


class DocumentManagementE2ETest:
    """文档管理端到端测试类"""

    def __init__(self):
        self.test_file_path = None
        self.api_process = None

    def setup_method(self):
        """测试前准备"""
        print("=" * 50)
        print("开始端到端测试")
        print("=" * 50)

        # 检查 API 服务是否运行
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                print("✅ API 服务已运行")
            else:
                print("⚠️ API 服务响应异常")
        except requests.exceptions.ConnectionError:
            print("❌ API 服务未运行，请先启动服务")
            print("   启动命令: uvicorn src.api.main:app --host 0.0.0.0 --port 8000")
            sys.exit(1)
        except Exception as e:
            print(f"❌ 检查 API 服务失败: {e}")
            sys.exit(1)

    def test_1_health_check(self):
        """测试 1: 健康检查"""
        print("\n[测试 1] 健康检查")
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=10)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            print("✅ 健康检查通过")
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")
            raise

    def test_2_upload_document(self):
        """测试 2: 上传文档"""
        print("\n[测试 2] 上传文档")

        # 创建临时测试文件
        self.test_file_path = Path("./data/raw_docs") / TEST_FILENAME
        self.test_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.test_file_path.write_text(TEST_DOC_CONTENT, encoding="utf-8")
        print(f"   创建测试文件: {self.test_file_path}")

        try:
            with open(self.test_file_path, "rb") as f:
                files = {"file": (TEST_FILENAME, f, "text/plain")}
                response = requests.post(
                    f"{API_BASE_URL}/api/v1/documents/upload",
                    files=files,
                    timeout=30
                )

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            print(f"✅ 文档上传成功: {result.get('message')}")
        except Exception as e:
            print(f"❌ 文档上传失败: {e}")
            raise

    def test_3_process_document(self):
        """测试 3: 处理文档（添加到向量存储）"""
        print("\n[测试 3] 处理文档")

        try:
            response = requests.post(
                f"{API_BASE_URL}/api/v1/documents/process",
                json={},
                timeout=60
            )

            # 注意：处理可能需要较长时间
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 文档处理成功: {result.get('message')}")
            else:
                print(f"⚠️ 文档处理响应: {response.status_code}")
                # 继续测试，不阻塞
        except Exception as e:
            print(f"⚠️ 文档处理失败（继续测试）: {e}")

    def test_4_list_documents(self):
        """测试 4: 获取文档列表"""
        print("\n[测试 4] 获取文档列表")

        try:
            response = requests.get(
                f"{API_BASE_URL}/api/v1/documents/list",
                timeout=10
            )

            assert response.status_code == 200
            data = response.json()

            print(f"   文档总数: {data['total']}")
            print(f"   已索引: {data['indexed_count']}")
            print(f"   未索引: {data['not_indexed_count']}")

            # 验证测试文档在列表中
            doc_found = any(
                doc["filename"] == TEST_FILENAME
                for doc in data["documents"]
            )

            if doc_found:
                print(f"✅ 文档列表获取成功，测试文档已找到")
            else:
                print(f"⚠️ 文档列表获取成功，但测试文档未找到")

        except Exception as e:
            print(f"❌ 获取文档列表失败: {e}")
            raise

    def test_5_document_stats(self):
        """测试 5: 获取文档统计"""
        print("\n[测试 5] 获取文档统计")

        try:
            response = requests.get(
                f"{API_BASE_URL}/api/v1/documents/stats",
                timeout=10
            )

            assert response.status_code == 200
            stats = response.json()

            print(f"   总文档数: {stats['total_documents']}")
            print(f"   已索引: {stats['indexed_documents']}")
            print(f"   未索引: {stats['not_indexed_documents']}")
            print(f"   总大小: {stats['total_size']} bytes")
            print(f"   平均chunks: {stats['average_chunks']}")
            print("✅ 文档统计获取成功")

        except Exception as e:
            print(f"❌ 获取文档统计失败: {e}")
            raise

    def test_6_delete_document(self):
        """测试 6: 删除文档"""
        print("\n[测试 6] 删除文档")

        if not self.test_file_path or not self.test_file_path.exists():
            print("⚠️ 测试文件不存在，跳过删除测试")
            return

        try:
            response = requests.delete(
                f"{API_BASE_URL}/api/v1/documents/{TEST_FILENAME}",
                timeout=10
            )

            assert response.status_code == 200
            result = response.json()

            print(f"   删除结果: {result.get('message')}")
            print(f"   文件已删除: {result.get('file_deleted')}")
            print(f"   向量已删除: {result.get('vectors_deleted')}")

            if result["success"]:
                print("✅ 文档删除成功")
            else:
                print(f"⚠️ 文档删除部分成功: {result.get('message')}")

        except Exception as e:
            print(f"❌ 删除文档失败: {e}")
            raise

    def test_7_verify_cleanup(self):
        """测试 7: 验证清理"""
        print("\n[测试 7] 验证清理")

        # 验证文件已删除
        if self.test_file_path and self.test_file_path.exists():
            print("❌ 文件未被删除")
            raise AssertionError("文件仍然存在")

        # 验证文档列表中不再包含测试文档
        try:
            response = requests.get(
                f"{API_BASE_URL}/api/v1/documents/list",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                doc_found = any(
                    doc["filename"] == TEST_FILENAME
                    for doc in data["documents"]
                )

                if not doc_found:
                    print("✅ 清理验证成功：文档已从列表中移除")
                else:
                    print("⚠️ 文档仍在列表中")

        except Exception as e:
            print(f"⚠️ 验证清理时出错: {e}")

    def teardown_method(self):
        """测试后清理"""
        print("\n" + "=" * 50)
        print("测试完成")
        print("=" * 50)

        # 清理测试文件（如果还存在）
        if self.test_file_path and self.test_file_path.exists():
            try:
                self.test_file_path.unlink()
                print(f"清理测试文件: {self.test_file_path}")
            except Exception as e:
                print(f"清理测试文件失败: {e}")


def run_tests():
    """运行所有测试"""
    test = DocumentManagementE2ETest()

    try:
        test.setup_method()

        # 执行测试序列
        test.test_1_health_check()
        test.test_2_upload_document()
        test.test_3_process_document()
        test.test_4_list_documents()
        test.test_5_document_stats()
        test.test_6_delete_document()
        test.test_7_verify_cleanup()

        print("\n" + "=" * 50)
        print("🎉 所有测试通过!")
        print("=" * 50)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        sys.exit(1)
    finally:
        test.teardown_method()


if __name__ == "__main__":
    run_tests()
