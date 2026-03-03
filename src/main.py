"""
知识库系统主入口点
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from core.config import config
from core.document_processor import DocumentProcessor
from core.vector_store import SimpleVectorStore
from core.llm_manager import LLMManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_document_processing():
    """测试文档处理"""
    print("\n=== 测试文档处理 ===")
    
    # 创建文档处理器
    processor = DocumentProcessor()
    
    # 测试目录
    test_dir = config.get("paths.raw_docs", "./data/raw_docs")
    Path(test_dir).mkdir(parents=True, exist_ok=True)
    
    # 创建测试文件
    test_file = Path(test_dir) / "test.txt"
    test_file.write_text("""
    这是测试文档。
    测试中文文本处理。
    This is English text for testing.
    
    知识库系统基于 LangChain + RAG + Agent 架构。
    支持 DeepSeek-V2-Lite 本地模型和大模型 API 混合模式。
    """)
    
    # 处理文档
    try:
        documents = processor.process_file(str(test_file))
        print(f"[OK] 文档处理成功，生成 {len(documents)} 个 chunks")
        
        for i, doc in enumerate(documents[:2]):  # 只显示前两个
            print(f"  Chunk {i+1}: {doc.page_content[:100]}...")
        
        return documents
    except Exception as e:
        print(f"[FAIL] 文档处理失败: {e}")
        return []

def test_vector_store(documents):
    """测试向量存储"""
    if not documents:
        print("\n✗ 没有文档可测试向量存储")
        return False
    
    print("\n=== 测试向量存储 ===")
    
    try:
        # 创建向量存储
        vector_store = SimpleVectorStore()
        
        # 添加文档
        ids = vector_store.add_documents(documents)
        print(f"[OK] 文档添加到向量存储，生成 {len(ids)} 个向量")
        
        # 搜索测试
        query = "什么是知识库系统？"
        results = vector_store.similarity_search(query, k=2)
        print(f"[OK] 向量搜索成功，查询: '{query}'")
        print(f"  找到 {len(results)} 个相关文档")
        
        # 显示集合信息
        info = vector_store.get_collection_info()
        print(f"  集合信息: {info}")
        
        return True
    except Exception as e:
        print(f"[FAIL] 向量存储测试失败: {e}")
        return False

def test_llm_manager():
    """测试 LLM 管理器"""
    print("\n=== 测试 LLM 管理器 ===")
    
    try:
        # 创建 LLM 管理器
        llm_manager = LLMManager()
        
        # 检查可用性
        local_available = llm_manager.is_local_available()
        api_available = llm_manager.is_api_available()
        
        print(f"[OK] 本地模型可用: {local_available}")
        print(f"[OK] API 模型可用: {api_available}")
        
        if local_available:
            # 测试本地模型
            print("\n--- 测试本地模型 ---")
            prompt = "请用中文简短介绍一下你自己。"
            
            try:
                result = llm_manager.generate(prompt, provider="local")
                print(f"[OK] 本地模型响应: {result['text'][:100]}...")
            except Exception as e:
                print(f"[FAIL] 本地模型测试失败: {e}")
        
        if api_available:
            # 测试 API 模型（如果可用且配置了 API 密钥）
            print("\n--- 测试 API 模型 ---")
            prompt = "请用英文简短介绍一下你自己。"
            
            try:
                # 尝试使用第一个可用的 API 提供商
                api_providers = list(llm_manager.api_clients.keys())
                if api_providers:
                    provider = api_providers[0]
                    result = llm_manager.generate(prompt, provider=provider)
                    print(f"[OK] {provider} API 响应: {result['text'][:100]}...")
            except Exception as e:
                    print(f"[FAIL] API 模型测试失败: {e}")
        
        # 显示使用统计
        stats = llm_manager.get_usage_stats()
        print(f"\n使用统计: {stats}")
        
        return True
    except Exception as e:
        print(f"[FAIL] LLM 管理器测试失败: {e}")
        return False

def test_rag_pipeline():
    """测试完整的 RAG 流水线"""
    print("\n=== 测试完整 RAG 流水线 ===")
    
    try:
        # 初始化所有组件
        processor = DocumentProcessor()
        vector_store = SimpleVectorStore()
        llm_manager = LLMManager()
        
        # 检查本地模型是否可用
        if not llm_manager.is_local_available():
            print("[FAIL] 本地模型不可用，跳过 RAG 测试")
            return False
        
        # 创建测试文档
        test_text = """
        知识库系统是基于 LangChain 框架构建的。
        它使用 RAG (检索增强生成) 技术来回答用户问题。
        系统支持本地模型和云 API 混合模式。
        DeepSeek-V2-Lite 是推荐的本地模型。
        """
        
        test_file = Path(config.get("paths.raw_docs", "./data/raw_docs")) / "rag_test.txt"
        test_file.write_text(test_text)
        
        # 1. 处理文档
        documents = processor.process_file(str(test_file))
        if not documents:
            print("[FAIL] 文档处理失败")
            return False
        print(f"[OK] 文档处理完成，生成 {len(documents)} 个 chunks")
        
        # 2. 添加到向量存储
        ids = vector_store.add_documents(documents)
        print(f"✓ 文档添加到向量存储")
        
        # 3. RAG 问答
        questions = [
            "什么是知识库系统？",
            "推荐使用什么本地模型？",
        ]
        
        for question in questions:
            print(f"\n问: {question}")
            
            # 3.1 检索相关文档
            retrieved = vector_store.similarity_search(question, k=2)
            if retrieved:
                context = "\n\n".join([doc.page_content for doc in retrieved])
                
                # 3.2 生成回答
                prompt = f"""基于以下参考文档回答用户问题。

参考文档：
{context}

用户问题：{question}

请用中文回答："""
                
                result = llm_manager.generate(prompt, provider="local")
                answer = result["text"]
                
                print(f"答: {answer[:200]}...")
                
                # 显示来源
                print(f"来源: {len(retrieved)} 个相关文档")
            else:
                print("答: 未找到相关文档")
        
        return True
        
    except Exception as e:
        print(f"✗ RAG 流水线测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("本地知识库系统 - 组件测试")
    print("=" * 60)
    
    # 显示配置信息
    print(f"项目根目录: {project_root}")
    print(f"数据目录: {config.get('paths.data_dir')}")
    
    # 运行测试
    documents = test_document_processing()
    
    if documents:
        test_vector_store(documents)
    
    test_llm_manager()
    test_rag_pipeline()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()