"""
RAG系统测试脚本
测试完整的RAG流水线（不依赖外部LLM）
"""

import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.config import get_config
from src.core.document_processor import DocumentProcessor
from src.core.vector_store import SimpleVectorStore
from src.agents.rag_agent import RAGAgent


def test_document_processor():
    """测试文档处理器"""
    print("[TEST] 文档处理器...")
    processor = DocumentProcessor()

    # 测试处理文本文件
    test_file = "data/raw_docs/demo_knowledge.txt"
    if os.path.exists(test_file):
        docs = processor.process_file(test_file)
        print(f"  [OK] 成功处理文档，生成 {len(docs)} 个片段")

        # 打印第一个片段
        if docs:
            print(f"  片段示例: {docs[0].page_content[:100]}...")
        return docs
    else:
        print(f"  [SKIP] 测试文件不存在: {test_file}")
        return []


def test_vector_store(documents):
    """测试向量存储"""
    print("[TEST] 向量存储...")

    if not documents:
        print("  [SKIP] 没有文档可测试")
        return None

    try:
        # 创建向量存储
        vector_store = SimpleVectorStore()

        # 添加文档
        print(f"  正在添加 {len(documents)} 个文档到向量存储...")
        ids = vector_store.add_documents(documents)
        print(f"  [OK] 成功添加 {len(ids)} 个向量")

        # 测试搜索
        print("  测试搜索功能...")
        results = vector_store.similarity_search("什么是RAG", k=2)
        print(f"  [OK] 搜索返回 {len(results)} 个结果")

        return vector_store
    except Exception as e:
        print(f"  [FAIL] 向量存储测试失败: {e}")
        return None


def test_rag_agent(vector_store):
    """测试RAG Agent"""
    print("[TEST] RAG Agent...")

    if not vector_store:
        print("  [SKIP] 向量存储未初始化")
        return

    try:
        # 创建RAG Agent（不指定LLM管理器）
        agent = RAGAgent(
            llm_manager=None,  # 不使用LLM
            vector_store=vector_store,
        )

        # 测试处理查询（仅检索，不生成）
        print("  测试检索功能...")
        result = agent.process("什么是RAG？")

        if result.get("success"):
            print(f"  [OK] 查询成功")
            print(f"  结果: {result.get('response', '')[:200]}...")
        else:
            print(f"  [WARN] 查询返回: {result}")

        return agent
    except Exception as e:
        print(f"  [FAIL] RAG Agent测试失败: {e}")
        return None


def test_rag_chain():
    """测试RAG Chain"""
    print("[TEST] RAG Chain...")

    try:
        from src.core.rag_chain import RAGChain

        chain = RAGChain()
        chain.initialize()

        # 获取状态
        status = chain.get_status()
        print(f"  [OK] RAG Chain初始化成功")
        print(f"  组件状态: {status.get('components', {})}")

        return chain
    except Exception as e:
        print(f"  [FAIL] RAG Chain测试失败: {e}")
        return None


def main():
    """主测试函数"""
    print("=" * 50)
    print("本地知识库系统 - 组件测试")
    print("=" * 50)
    print()

    # 1. 测试文档处理器
    documents = test_document_processor()
    print()

    # 2. 测试向量存储
    vector_store = test_vector_store(documents)
    print()

    # 3. 测试RAG Agent
    test_rag_agent(vector_store)
    print()

    # 4. 测试RAG Chain
    test_rag_chain()
    print()

    print("=" * 50)
    print("测试完成!")
    print("=" * 50)
    print()
    print("后续步骤:")
    print("  1. 安装Ollama: https://ollama.ai/download/windows")
    print("  2. 下载模型: ollama pull deepseek-v2-lite:16b-q4_K_M")
    print("  3. 配置API密钥(可选): 编辑 .env 文件")
    print("  4. 启动服务: python src/api/main.py")
    print()


if __name__ == "__main__":
    main()
