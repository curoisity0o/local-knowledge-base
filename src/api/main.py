"""
FastAPI 主应用
提供知识库系统的 REST API 接口
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import logging

from core.config import config
from core.document_processor import DocumentProcessor
from core.vector_store import SimpleVectorStore
from core.llm_manager import LLMManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="本地知识库系统 API",
    description="基于 LangChain + RAG + Agent 的本地知识库系统",
    version="1.0.0"
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局组件实例（延迟初始化）
_processor = None
_vector_store = None
_llm_manager = None

def get_processor():
    """获取文档处理器实例"""
    global _processor
    if _processor is None:
        _processor = DocumentProcessor()
    return _processor

def get_vector_store():
    """获取向量存储实例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = SimpleVectorStore()
    return _vector_store

def get_llm_manager():
    """获取 LLM 管理器实例"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager

# 请求/响应模型
class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 4
    provider: Optional[str] = None
    use_rag: Optional[bool] = True

class QueryResponse(BaseModel):
    answer: str
    sources: List[str] = []
    provider: str
    response_time: float
    tokens_used: Optional[dict] = None

class DocumentProcessRequest(BaseModel):
    file_path: Optional[str] = None
    process_directory: Optional[bool] = False

class DocumentProcessResponse(BaseModel):
    success: bool
    message: str
    chunks_count: int = 0
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    local_model_available: bool
    api_available: bool
    vector_store_ready: bool
    version: str

# API 端点
@app.get("/")
async def root():
    """根端点，返回 API 信息"""
    return {
        "name": "本地知识库系统 API",
        "version": "1.0.0",
        "description": "基于 LangChain + RAG + Agent 的本地知识库系统",
        "endpoints": {
            "health": "/health",
            "query": "/api/v1/query (POST)",
            "upload": "/api/v1/documents/upload (POST)",
            "process": "/api/v1/documents/process (POST)",
            "stats": "/api/v1/stats (GET)",
        }
    }

@app.get("/health")
async def health_check() -> HealthResponse:
    """健康检查端点"""
    llm_manager = get_llm_manager()
    vector_store = get_vector_store()
    
    return HealthResponse(
        status="healthy",
        local_model_available=llm_manager.is_local_available(),
        api_available=llm_manager.is_api_available(),
        vector_store_ready=vector_store is not None,
        version="1.0.0"
    )

@app.post("/api/v1/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """查询知识库"""
    import time
    start_time = time.time()
    
    try:
        llm_manager = get_llm_manager()
        vector_store = get_vector_store()
        
        if request.use_rag:
            # RAG 模式：检索 + 生成
            # 1. 检索相关文档
            retrieved_docs = vector_store.similarity_search(
                request.question, 
                k=request.top_k
            )
            
            if retrieved_docs:
                # 构建上下文
                context = "\n\n".join([
                    f"[来源 {i+1}]: {doc.page_content}"
                    for i, doc in enumerate(retrieved_docs)
                ])
                
                # 构建提示词
                prompt = f"""基于以下参考文档回答用户问题。

参考文档：
{context}

用户问题：{request.question}

请用中文回答，并注明引用来源："""
                
                # 2. 生成答案
                result = llm_manager.generate(
                    prompt, 
                    provider=request.provider
                )
                
                answer = result["text"]
                sources = [doc.metadata.get("source", "未知") for doc in retrieved_docs]
            else:
                # 无相关文档，直接回答
                result = llm_manager.generate(
                    request.question,
                    provider=request.provider
                )
                answer = result["text"]
                sources = []
        else:
            # 直接生成模式
            result = llm_manager.generate(
                request.question,
                provider=request.provider
            )
            answer = result["text"]
            sources = []
        
        response_time = time.time() - start_time
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            provider=result.get("metadata", {}).get("provider", "unknown"),
            response_time=response_time,
            tokens_used=result.get("tokens")
        )
        
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档"""
    try:
        # 保存上传的文件
        upload_dir = config.get("paths.raw_docs", "./data/raw_docs")
        import os
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, file.filename)
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        return {
            "success": True,
            "message": f"文件上传成功: {file.filename}",
            "file_path": file_path,
            "file_size": len(content)
        }
        
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@app.post("/api/v1/documents/process", response_model=DocumentProcessResponse)
async def process_documents(request: DocumentProcessRequest):
    """处理文档（添加到向量存储）"""
    try:
        processor = get_processor()
        vector_store = get_vector_store()
        
        if request.process_directory and request.file_path:
            # 处理整个目录
            documents = processor.process_directory(request.file_path)
        elif request.file_path:
            # 处理单个文件
            documents = processor.process_file(request.file_path)
        else:
            # 处理默认目录
            default_dir = config.get("paths.raw_docs", "./data/raw_docs")
            documents = processor.process_directory(default_dir)
        
        # 添加到向量存储
        if documents:
            ids = vector_store.add_documents(documents)
            
            return DocumentProcessResponse(
                success=True,
                message=f"成功处理 {len(documents)} 个文档块",
                chunks_count=len(documents)
            )
        else:
            return DocumentProcessResponse(
                success=False,
                message="未找到可处理的文档",
                chunks_count=0
            )
            
    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        return DocumentProcessResponse(
            success=False,
            message=f"文档处理失败: {str(e)}",
            error=str(e),
            chunks_count=0
        )

@app.get("/api/v1/stats")
async def get_system_stats():
    """获取系统统计信息"""
    try:
        llm_manager = get_llm_manager()
        vector_store = get_vector_store()
        
        # 获取使用统计
        usage_stats = llm_manager.get_usage_stats()
        
        # 获取向量存储信息
        vector_info = vector_store.get_collection_info()
        
        return {
            "llm_usage": usage_stats,
            "vector_store": vector_info,
            "config": {
                "local_model": config.get("llm.local.ollama.model"),
                "embedding_model": config.get("embeddings.model"),
                "chunk_size": config.get("document_processing.chunking.chunk_size"),
            }
        }
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

@app.get("/api/v1/models/available")
async def get_available_models():
    """获取可用模型列表"""
    try:
        llm_manager = get_llm_manager()
        
        return {
            "local_available": llm_manager.is_local_available(),
            "api_available": llm_manager.is_api_available(),
            "available_providers": llm_manager.get_available_providers(),
            "local_model": config.get("llm.local.ollama.model", "未配置"),
        }
        
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

# 启动函数
def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """启动 API 服务器"""
    logger.info(f"启动 API 服务器: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_api_server()