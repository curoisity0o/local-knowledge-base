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
import os
import os

from src.core.config import config
from src.core.document_processor import DocumentProcessor
from src.core.vector_store import SimpleVectorStore
from src.core.llm_manager import LLMManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="本地知识库系统 API",
    description="基于 LangChain + RAG + Agent 的本地知识库系统",
    version="1.0.0",
)

# 添加 CORS 中间件
# 从环境变量读取允许的来源，支持多个来源用逗号分隔
cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
if cors_origins == [""]:
    cors_origins = [
        "http://localhost:8501",  # Streamlit前端
        "http://localhost:3000",  # React/Vue前端
        "http://127.0.0.1:8501",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
    local_model_available: Optional[bool] = None
    api_available: Optional[bool] = None
    vector_store_ready: Optional[bool] = None
    version: str


# 文档管理模型
class DocumentInfo(BaseModel):
    """文档信息"""
    filename: str
    file_path: str
    file_size: int
    modified_time: Optional[float] = None
    file_extension: str
    chunks_count: int = 0
    vector_status: str = "not_indexed"  # "indexed" 或 "not_indexed"


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentInfo]
    total: int
    indexed_count: int
    not_indexed_count: int


class DocumentDeleteResponse(BaseModel):
    """文档删除响应"""
    success: bool
    message: str
    file_deleted: bool = False
    vectors_deleted: bool = False
    error: Optional[str] = None


class DocumentStatsResponse(BaseModel):
    """文档统计响应"""
    total_documents: int
    indexed_documents: int
    not_indexed_documents: int
    total_size: int
    average_chunks: float


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
            "document_list": "/api/v1/documents/list (GET)",
            "document_delete": "/api/v1/documents/{filename} (DELETE)",
            "document_stats": "/api/v1/documents/stats (GET)",
        },
    }


@app.get("/health")
async def health_check() -> HealthResponse:
    """健康检查端点 - 轻量级，不初始化 LLM"""
    try:
        # 简单检查 API 服务是否在线
        # 不在这里初始化 LLM，避免超时阻塞
        return HealthResponse(
            status="healthy",
            local_model_available=None,  # 未知，需要单独查询
            api_available=None,  # 未知，需要单独查询
            vector_store_ready=None,  # 未知，需要单独查询
            version="1.0.0",
        )
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return HealthResponse(
            status="error",
            local_model_available=False,
            api_available=False,
            vector_store_ready=False,
            version="1.0.0",
        )


@app.get("/health/detailed")
async def health_check_detailed() -> dict:
    """详细健康检查 - 单独检查各个组件"""
    from src.core.llm_manager import LLMManager
    from src.core.vector_store import SimpleVectorStore

    result = {
        "status": "healthy",
        "local_model_available": False,
        "api_available": False,
        "vector_store_ready": False,
    }

    # 检查本地模型
    try:
        llm = LLMManager()
        result["local_model_available"] = llm.is_local_available()
        result["api_available"] = llm.is_api_available()
    except Exception as e:
        logger.warning(f"LLM 检查失败: {e}")

    # 检查向量存储
    try:
        vs = SimpleVectorStore()
        vs._ensure_initialized()
        result["vector_store_ready"] = vs.vector_store is not None
    except Exception as e:
        logger.warning(f"向量存储检查失败: {e}")

    return result


@app.get("/health/local")
async def check_local_model() -> dict:
    """只检查本地模型状态"""
    try:
        from src.core.llm_manager import LLMManager

        llm = LLMManager()
        return {
            "available": llm.is_local_available(),
            "provider": llm.local_provider,
        }
    except Exception as e:
        logger.warning(f"本地模型检查失败: {e}")
        return {"available": False, "error": str(e)}


@app.get("/health/api")
async def check_api_model() -> dict:
    """只检查 API 状态"""
    try:
        from src.core.llm_manager import LLMManager

        llm = LLMManager()
        return {
            "available": llm.is_api_available(),
            "providers": llm.get_available_providers(),
        }
    except Exception as e:
        logger.warning(f"API 检查失败: {e}")
        return {"available": False, "error": str(e)}


@app.get("/health/vectorstore")
async def check_vectorstore() -> dict:
    """只检查向量存储状态"""
    try:
        from src.core.vector_store import SimpleVectorStore

        vs = SimpleVectorStore()
        vs._ensure_initialized()
        return {
            "ready": vs.vector_store is not None,
            "info": vs.get_collection_info() if vs.vector_store else {},
        }
    except Exception as e:
        logger.warning(f"向量存储检查失败: {e}")
        return {"ready": False, "error": str(e)}


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
                request.question, k=request.top_k or 4
            )

            if retrieved_docs:
                # 构建上下文 - 对来源去重，保留首次出现的 chunk
                seen_sources = set()
                unique_docs = []
                for doc in retrieved_docs:
                    source = doc.metadata.get("source", "未知")
                    if source not in seen_sources:
                        seen_sources.add(source)
                        unique_docs.append(doc)

                # 如果去重后文档太少，补充一些非重复的 chunk
                if len(unique_docs) < 2:
                    for doc in retrieved_docs:
                        if doc not in unique_docs:
                            unique_docs.append(doc)
                            if len(unique_docs) >= 2:
                                break

                # 构建上下文
                context = "\n\n".join(
                    [
                        f"[来源 {i + 1}]: {doc.page_content}"
                        for i, doc in enumerate(unique_docs)
                    ]
                )

                # 构建提示词
                # 根据问题类型调整 prompt
                question = request.question.lower()
                is_short_fact = any(
                    kw in question
                    for kw in [
                        "多久",
                        "多少",
                        "多长时间",
                        "takes",
                        "耗时",
                        "时间",
                        "ms",
                        "秒",
                    ]
                )

                if is_short_fact:
                    prompt = f"""基于以下参考文档，直接提取并回答用户问题。
如果文档中有相关数值，直接给出答案，不需要解释。

参考文档：
{context}

用户问题：{request.question}

请直接回答："""
                else:
                    prompt = f"""基于以下参考文档回答用户问题。

参考文档：
{context}

用户问题：{request.question}

请用中文回答，并注明引用来源："""

                # 2. 生成答案
                result = llm_manager.generate(prompt, provider=request.provider)

                answer = result["text"]
                # 返回去重后的来源
                sources = list(seen_sources)
            else:
                # 无相关文档，直接回答
                result = llm_manager.generate(
                    request.question, provider=request.provider
                )
                answer = result["text"]
                sources = []
        else:
            # 直接生成模式
            result = llm_manager.generate(request.question, provider=request.provider)
            answer = result["text"]
            sources = []

        response_time = time.time() - start_time

        return QueryResponse(
            answer=answer,
            sources=sources,
            provider=result.get("metadata", {}).get("provider", "unknown"),
            response_time=response_time,
            tokens_used=result.get("tokens"),
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

        file_path = os.path.join(upload_dir, file.filename or "uploaded_file")

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {
            "success": True,
            "message": f"文件上传成功: {file.filename}",
            "file_path": file_path,
            "file_size": len(content),
        }

    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@app.post("/api/v1/documents/process", response_model=DocumentProcessResponse)
async def process_documents(request: DocumentProcessRequest):
    """处理文档（添加到向量存储）"""
    try:
        import os
        from pathlib import Path

        processor = get_processor()
        vector_store = get_vector_store()
        
        # 初始化变量
        skipped_docs = []
        documents = []

        # 获取默认目录 - 使用绝对路径确保 API 和前端路径一致
        if request.process_directory and request.file_path:
            # 处理整个目录
            documents = processor.process_directory(request.file_path)
        elif request.file_path:
            # 处理单个文件
            documents = processor.process_file(request.file_path)
        else:
            # 处理默认目录 - 使用绝对路径
            raw_docs_dir = config.get("paths.raw_docs", "./data/raw_docs")
            # 转换为绝对路径
            if not os.path.isabs(raw_docs_dir):
                # 基于项目根目录
                project_root = Path(__file__).parent.parent.parent
                raw_docs_dir = str(project_root / raw_docs_dir)

            # 确保目录存在
            Path(raw_docs_dir).mkdir(parents=True, exist_ok=True)

            logger.info(f"处理文档目录: {raw_docs_dir}")

            # 获取向量存储中已存在的源文件
            indexed_sources = set()
            try:
                all_sources = vector_store.get_all_sources()
                indexed_sources = set(all_sources)
                logger.info(f"已索引的文档: {indexed_sources}")
            except Exception as e:
                logger.warning(f"获取已索引文档失败: {e}")

            # 加载所有文档
            all_docs = processor.load_documents_from_directory(raw_docs_dir)
            logger.info(f"加载了 {len(all_docs)} 个原始文档")

            # 过滤掉已存在的文档
            new_docs = []
            skipped_docs = []
            for doc in all_docs:
                source = doc.metadata.get("source", "")
                if source in indexed_sources:
                    skipped_docs.append(source)
                    logger.info(f"跳过已存在的文档: {source}")
                else:
                    new_docs.append(doc)

            logger.info(f"新文档: {len(new_docs)}, 跳过: {len(skipped_docs)}")

            # 如果有新文档，处理它们
            if new_docs:
                # 预处理
                for doc in new_docs:
                    doc.page_content = processor.preprocess_text(doc.page_content)
                
                # 分割
                documents = processor.split_documents(new_docs)
                logger.info(f"生成了 {len(documents)} 个 chunks")
            else:
                documents = []
                logger.info("没有新文档需要处理")

        # 添加到向量存储
        if documents:
            ids = vector_store.add_documents(documents)

            return DocumentProcessResponse(
                success=True,
                message=f"成功处理 {len(documents)} 个文档块",
                chunks_count=len(documents),
            )
        elif skipped_docs:
            # 全部已存在
            return DocumentProcessResponse(
                success=True,
                message=f"所有文档已存在，无需重复处理",
                chunks_count=0,
            )
        else:
            # 没有文档
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
            chunks_count=0,
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
            },
        }

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@app.get("/api/v1/documents/list", response_model=DocumentListResponse)
async def list_documents():
    """获取文档列表

    返回所有已上传文档的列表，包括文件名、路径、大小、修改时间、格式、
    chunks 数量和向量索引状态。

    Returns:
        DocumentListResponse: 包含文档列表和统计信息

    Raises:
        HTTPException: 获取文档列表失败时抛出 500 错误
    """
    try:
        import os
        from pathlib import Path

        # 获取原始文档目录 - 使用绝对路径
        raw_docs_dir = config.get("paths.raw_docs", "./data/raw_docs")
        # 转换为绝对路径
        if not os.path.isabs(raw_docs_dir):
            project_root = Path(__file__).parent.parent.parent
            raw_docs_dir = str(project_root / raw_docs_dir)

        raw_docs_path = Path(raw_docs_dir)

        # 如果目录不存在，返回空列表
        if not raw_docs_path.exists():
            return DocumentListResponse(
                documents=[],
                total=0,
                indexed_count=0,
                not_indexed_count=0
            )

        # 获取向量存储中所有已索引的源文件
        vector_store = get_vector_store()
        indexed_sources = set()
        source_chunks_count = {}

        try:
            all_sources = vector_store.get_all_sources()
            indexed_sources = set(all_sources)

            # 统计每个源文件的 chunks 数量
            for source in all_sources:
                docs = vector_store.get_documents_by_source(source)
                source_chunks_count[source] = len(docs)
        except Exception as e:
            logger.warning(f"获取向量存储信息失败: {e}")

        # 遍历目录获取文件列表
        documents = []
        indexed_count = 0
        not_indexed_count = 0

        for file_path in raw_docs_path.iterdir():
            if file_path.is_file():
                # 获取文件信息
                stat = file_path.stat()
                filename = file_path.name
                file_ext = file_path.suffix.lower()

                # 检查是否已索引
                source_path = str(file_path.resolve())
                is_indexed = source_path in indexed_sources
                chunks_count = source_chunks_count.get(source_path, 0)

                if is_indexed:
                    indexed_count += 1
                    vector_status = "indexed"
                else:
                    not_indexed_count += 1
                    vector_status = "not_indexed"

                doc_info = DocumentInfo(
                    filename=filename,
                    file_path=source_path,
                    file_size=stat.st_size,
                    modified_time=stat.st_mtime,
                    file_extension=file_ext,
                    chunks_count=chunks_count,
                    vector_status=vector_status
                )
                documents.append(doc_info)

        # 按修改时间排序（最新的在前）
        documents.sort(key=lambda x: x.modified_time or 0, reverse=True)

        return DocumentListResponse(
            documents=documents,
            total=len(documents),
            indexed_count=indexed_count,
            not_indexed_count=not_indexed_count
        )

    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@app.delete("/api/v1/documents/{filename}", response_model=DocumentDeleteResponse)
async def delete_document(filename: str):
    """删除文档及其向量（原子操作）

    删除操作遵循以下步骤：
    1. 首先删除向量存储中的向量
    2. 然后删除物理文件
    如果向量删除失败，操作将回滚（文件不会被删除）
    如果文件删除失败，向量也已被删除，不会再恢复
    """
    try:
        from pathlib import Path
        import shutil

        # 获取原始文档目录 - 使用绝对路径
        raw_docs_dir = config.get("paths.raw_docs", "./data/raw_docs")
        # 转换为绝对路径
        if not os.path.isabs(raw_docs_dir):
            project_root = Path(__file__).parent.parent.parent
            raw_docs_dir = str(project_root / raw_docs_dir)

        raw_docs_path = Path(raw_docs_dir)

        # 查找文件
        file_path = raw_docs_path / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

        # 获取文件的绝对路径（用于向量存储匹配）
        absolute_path = str(file_path.resolve())

        # 步骤1：先尝试删除向量
        vector_store = get_vector_store()
        vectors_deleted = False
        vector_delete_error = None

        try:
            vectors_deleted = vector_store.delete_by_source(absolute_path)
            logger.info(f"向量删除结果: {vectors_deleted}, 文件: {absolute_path}")
        except Exception as e:
            vector_delete_error = str(e)
            logger.error(f"删除向量失败: {e}")

        # 如果向量删除失败，尝试再次删除（处理并发情况）
        if not vectors_deleted and vector_delete_error:
            try:
                vectors_deleted = vector_store.delete_by_source(absolute_path)
            except Exception as e2:
                logger.warning(f"重试删除向量失败: {e2}")

        # 步骤2：删除物理文件
        file_deleted = False
        file_delete_error = None

        try:
            # 如果是目录，则删除整个目录；如果是文件，则删除文件
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()
            file_deleted = True
            logger.info(f"文件删除成功: {file_path}")
        except Exception as e:
            file_delete_error = str(e)
            logger.error(f"删除文件失败: {e}")

        # 返回结果
        if file_deleted:
            return DocumentDeleteResponse(
                success=True,
                message=f"文档 {filename} 已成功删除",
                file_deleted=True,
                vectors_deleted=vectors_deleted,
                error=None
            )
        else:
            # 文件删除失败
            return DocumentDeleteResponse(
                success=False,
                message=f"删除文档失败: {file_delete_error}",
                file_deleted=False,
                vectors_deleted=vectors_deleted,  # 向量可能已删除
                error=file_delete_error
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档时发生错误: {e}")
        return DocumentDeleteResponse(
            success=False,
            message=f"删除文档失败: {str(e)}",
            file_deleted=False,
            vectors_deleted=False,
            error=str(e)
        )


@app.get("/api/v1/documents/stats", response_model=DocumentStatsResponse)
async def get_document_stats():
    """获取文档统计信息

    返回文档统计信息，包括：
    - total_documents: 文档总数
    - indexed_documents: 已索引文档数
    - not_indexed_documents: 未索引文档数
    - total_size: 文档总大小（字节）
    - average_chunks: 平均每个文档的 chunks 数量

    Returns:
        DocumentStatsResponse: 包含文档统计信息

    Raises:
        HTTPException: 获取统计信息失败时抛出 500 错误
    """
    try:
        import os
        from pathlib import Path

        # 获取原始文档目录 - 使用绝对路径
        raw_docs_dir = config.get("paths.raw_docs", "./data/raw_docs")
        # 转换为绝对路径
        if not os.path.isabs(raw_docs_dir):
            project_root = Path(__file__).parent.parent.parent
            raw_docs_dir = str(project_root / raw_docs_dir)

        raw_docs_path = Path(raw_docs_dir)

        # 如果目录不存在，返回零值统计
        if not raw_docs_path.exists():
            return DocumentStatsResponse(
                total_documents=0,
                indexed_documents=0,
                not_indexed_documents=0,
                total_size=0,
                average_chunks=0.0
            )

        # 获取向量存储信息
        vector_store = get_vector_store()
        indexed_sources = set()
        source_chunks_count = {}

        try:
            all_sources = vector_store.get_all_sources()
            indexed_sources = set(all_sources)

            #文件的 chunks 数量 统计每个源
            for source in all_sources:
                docs = vector_store.get_documents_by_source(source)
                source_chunks_count[source] = len(docs)
        except Exception as e:
            logger.warning(f"获取向量存储信息失败: {e}")

        # 统计文件信息
        total_docs = 0
        indexed_count = 0
        not_indexed_count = 0
        total_size = 0
        total_chunks = 0

        for file_path in raw_docs_path.iterdir():
            if file_path.is_file():
                total_docs += 1
                stat = file_path.stat()
                total_size += stat.st_size

                # 检查是否已索引
                source_path = str(file_path.resolve())
                if source_path in indexed_sources:
                    indexed_count += 1
                    total_chunks += source_chunks_count.get(source_path, 0)
                else:
                    not_indexed_count += 1

        # 计算平均 chunks 数
        average_chunks = total_chunks / indexed_count if indexed_count > 0 else 0.0

        return DocumentStatsResponse(
            total_documents=total_docs,
            indexed_documents=indexed_count,
            not_indexed_documents=not_indexed_count,
            total_size=total_size,
            average_chunks=round(average_chunks, 2)
        )

    except Exception as e:
        logger.error(f"获取文档统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文档统计失败: {str(e)}")


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


@app.post("/api/v1/models/warmup")
async def warmup_model():
    """预热模型，让模型保持在内存中"""
    try:
        llm_manager = get_llm_manager()

        # 预热本地模型
        if llm_manager.is_local_available():
            logger.info("预热本地模型...")
            # 生成一个简单的回复来加载模型到内存
            result = llm_manager.generate("你好", provider="local")
            return {"success": True, "message": "模型预热完成"}
        else:
            return {"success": False, "message": "本地模型不可用"}
    except Exception as e:
        logger.error(f"模型预热失败: {e}")
        return {"success": False, "message": f"预热失败: {str(e)}"}


# 启动函数
def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """启动 API 服务器"""
    logger.info(f"启动 API 服务器: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_api_server()
