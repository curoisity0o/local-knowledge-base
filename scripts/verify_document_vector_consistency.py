#!/usr/bin/env python3
"""
文档-向量一致性验证脚本

验证文件系统和向量存储之间的一致性：
- 每个文件在向量存储中有对应向量
- 删除文件后向量也被删除
- 无孤儿向量（向量对应不存在的文件）
"""

import os
import sys
import requests
from pathlib import Path
from typing import List, Set, Dict, Tuple

# 配置
API_BASE_URL = "http://localhost:8000"
RAW_DOCS_DIR = "./data/raw_docs"


class ConsistencyVerifier:
    """一致性验证器"""

    def __init__(self):
        self.files_in_directory: Set[str] = set()
        self.sources_in_vectorstore: Set[str] = set()
        self.issues: List[str] = []

    def get_files_from_directory(self) -> Set[str]:
        """获取文档目录中的所有文件"""
        print("📂 扫描文档目录...")

        docs_path = Path(RAW_DOCS_DIR)
        if not docs_path.exists():
            print(f"   目录不存在: {docs_path}")
            return set()

        files = set()
        for file_path in docs_path.iterdir():
            if file_path.is_file():
                # 存储绝对路径
                files.add(str(file_path.resolve()))

        print(f"   找到 {len(files)} 个文件")
        return files

    def get_sources_from_vectorstore(self) -> Set[str]:
        """获取向量存储中的所有源文件"""
        print("🔍 查询向量存储...")

        try:
            # 通过 API 获取文档列表
            response = requests.get(
                f"{API_BASE_URL}/api/v1/documents/list",
                timeout=30
            )

            if response.status_code != 200:
                print(f"   API 响应异常: {response.status_code}")
                return set()

            data = response.json()
            sources = set()

            for doc in data.get("documents", []):
                if doc.get("vector_status") == "indexed":
                    sources.add(doc.get("file_path", ""))

            print(f"   找到 {len(sources)} 个已索引的源")
            return sources

        except requests.exceptions.ConnectionError:
            print("   ❌ 无法连接到 API 服务")
            return set()
        except Exception as e:
            print(f"   ❌ 查询失败: {e}")
            return set()

    def check_orphan_vectors(self):
        """检查孤儿向量（向量对应不存在的文件）"""
        print("\n🔎 检查孤儿向量...")

        orphan_sources = self.sources_in_vectorstore - self.files_in_directory

        if orphan_sources:
            print(f"   ⚠️ 发现 {len(orphan_sources)} 个孤儿向量:")
            for source in orphan_sources:
                print(f"      - {source}")
                self.issues.append(f"孤儿向量: {source}")
        else:
            print("   ✅ 没有发现孤儿向量")

    def check_missing_vectors(self):
        """检查缺失向量（文件没有对应向量）"""
        print("\n🔎 检查缺失向量...")

        missing_vectors = self.files_in_directory - self.sources_in_vectorstore

        if missing_vectors:
            print(f"   ⚠️ 发现 {len(missing_vectors)} 个文件未索引:")
            for source in missing_vectors:
                filename = Path(source).name
                print(f"      - {filename}")
                self.issues.append(f"未索引文件: {source}")
        else:
            print("   ✅ 所有文件都已索引")

    def check_consistency(self) -> bool:
        """执行一致性检查"""
        print("=" * 50)
        print("开始一致性验证")
        print("=" * 50)

        # 获取数据
        self.files_in_directory = self.get_files_from_directory()
        self.sources_in_vectorstore = self.get_sources_from_vectorstore()

        # 执行检查
        self.check_orphan_vectors()
        self.check_missing_vectors()

        # 总结
        print("\n" + "=" * 50)
        print("验证结果")
        print("=" * 50)

        if self.issues:
            print(f"❌ 发现 {len(self.issues)} 个一致性问题:")
            for issue in self.issues:
                print(f"   - {issue}")
            return False
        else:
            print("✅ 文件系统与向量存储完全一致")
            return True

    def suggest_fixes(self):
        """提供修复建议"""
        if not self.issues:
            return

        print("\n" + "=" * 50)
        print("修复建议")
        print("=" * 50)

        # 孤儿向量清理建议
        orphan_sources = self.sources_in_vectorstore - self.files_in_directory
        if orphan_sources:
            print("\n清理孤儿向量:")
            for source in orphan_sources:
                filename = Path(source).name
                print(f"   curl -X DELETE http://localhost:8000/api/v1/documents/{filename}")

        # 缺失向量重建建议
        missing_vectors = self.files_in_directory - self.sources_in_vectorstore
        if missing_vectors:
            print("\n重建缺失向量:")
            print("   curl -X POST http://localhost:8000/api/v1/documents/process")


def main():
    """主函数"""
    verifier = ConsistencyVerifier()

    try:
        is_consistent = verifier.check_consistency()

        if not is_consistent:
            verifier.suggest_fixes()
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 验证失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
