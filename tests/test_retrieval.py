"""
检索测试脚本 - 测试 Foam-Agent 作者查询
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.vector_store import SimpleVectorStore
from src.core.config import get_config


def test_retrieval():
    print("=" * 60)
    print("检索测试: Foam-Agent 作者")
    print("=" * 60)

    # 显示当前配置
    print("\n当前配置:")
    print(f"  retriever.type: {get_config('rag.retriever.type')}")
    print(f"  retriever.top_k: {get_config('rag.retriever.top_k')}")
    print(f"  retriever.score_threshold: {get_config('rag.retriever.score_threshold')}")

    try:
        # 初始化向量存储
        print("\n初始化向量存储...")
        vector_store = SimpleVectorStore()

        # 检查文档数量
        info = vector_store.get_collection_info()
        print(f"  集合状态: {info}")

        # 测试查询
        queries = [
            "Foam-Agent 作者是谁",
            "Foam-Agent author",
            "Ling Yue Nithin Somasekharan",
            "who created Foam-Agent",
        ]

        for query in queries:
            print(f"\n{'-' * 60}")
            print(f"查询: {query}")
            print("-" * 60)

            # 使用混合搜索
            try:
                results = vector_store.hybrid_search(query, k=10)
                print(f"返回 {len(results)} 个结果:\n")

                for i, doc in enumerate(results[:5], 1):
                    content = doc.page_content[:300].replace("\n", " ")
                    source = doc.metadata.get("source", "未知")
                    print(f"[{i}] 来源: {source}")
                    print(f"    内容: {content}...")
                    print()
            except Exception as e:
                print(f"混合搜索失败: {e}")
                # 降级到普通向量搜索
                print("尝试普通向量搜索...")
                results = vector_store.similarity_search(query, k=10)
                print(f"返回 {len(results)} 个结果:\n")
                for i, doc in enumerate(results[:5], 1):
                    content = doc.page_content[:300].replace("\n", " ")
                    source = doc.metadata.get("source", "未知")
                    print(f"[{i}] 来源: {source}")
                    print(f"    内容: {content}...")
                    print()

    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_retrieval()
