"""
文档处理模块
负责加载、分割和预处理文档
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
    CSVLoader,
    UnstructuredHTMLLoader,
)
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)
from langchain_core.documents import Document

from .config import get_config

logger = logging.getLogger(__name__)

class ChineseTextSplitter(RecursiveCharacterTextSplitter):
    """中文优化的文本分割器，支持保护LaTeX公式"""
    
    def __init__(self, **kwargs):
        # 中文友好的分隔符 + LaTeX公式边界保护
        separators = [
            # 段落级别
            "\n\n", "\n",
            # LaTeX公式边界（优先保护）
            "$$",           # 块公式 $$...$$
            "```",           # 代码块
            # Markdown标题
            "##", "###", "#",
            # 句子级别
            "。", "？", "！", "；", "?", "!", ";", "…", "……",
        ]
        super().__init__(separators=separators, **kwargs)
    
    def split_text(self, text: str) -> List[str]:
        """重写分割方法，添加中文预处理"""
        # 预处理：合并连续空白
        text = re.sub(r'\s+', ' ', text)
        
        # 处理中英文混合：在中英文之间添加空格
        text = re.sub(r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2', text)
        text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2', text)
        
        return super().split_text(text)


class MarkdownAwareSplitter:
    """Markdown专用分块器：先按标题分，再按大小分（二级分块）"""
    
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 按Markdown标题分
        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "header1"),
                ("##", "header2"),
                ("###", "header3"),
                ("####", "header4"),
            ],
            return_each_line=False,
        )
        
        # 在每个标题块内再按大小分
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n", "\n",
                "$$",           # 块公式
                "```",           # 代码块
                "##", "###", "#",
                "。", "？", "！", "；", "?", "!", ";", "…", "……",
            ],
        )
    
    def split_text(self, text: str) -> List[Document]:
        """分割Markdown文本"""
        # 第一步：按标题分
        header_docs = self.header_splitter.split_text(text)
        
        # 第二步：每个标题块内再按大小分
        final_chunks = self.text_splitter.split_documents(header_docs)
        
        return final_chunks


class DocumentProcessor:
    """文档处理器"""
    
    def __init__(self, config=None):
        self.config = config or get_config("document_processing", {})
        
        # 初始化文本分割器 - 使用get_config获取配置值（支持环境变量替换）
        chunk_size = get_config("document_processing.chunking.chunk_size", 800)
        chunk_overlap = get_config("document_processing.chunking.chunk_overlap", 100)
        
        # 确保chunk_size和chunk_overlap是整数
        chunk_size = int(chunk_size) if chunk_size is not None else 800
        chunk_overlap = int(chunk_overlap) if chunk_overlap is not None else 100
        
        # 传统分块器（用于非Markdown文件）
        self.text_splitter = ChineseTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
        
        # Markdown专用分块器（二级分块）
        self.markdown_splitter = MarkdownAwareSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        
        # 获取配置
        self.simple_formats = self.config.get("simple_formats", ["pdf", "txt", "docx", "html", "csv"])
        self.markdown_config = self.config.get("preprocessing", {}).get("markdown", {})
        
        # 支持的格式和对应的加载器
        # self.config 是 get_config("document_processing", {}) 返回的字典
        self.supported_formats = self.config.get("supported_formats", [])
        self.loader_mapping = self._create_loader_mapping()
    
    def _create_loader_mapping(self) -> Dict[str, Any]:
        """创建文件格式到加载器的映射"""
        # 注意：对于Markdown文件，使用TextLoader而不是UnstructuredMarkdownLoader
        # 因为UnstructuredMarkdownLoader需要NLTK数据，可能会导致网络问题
        # 指定UTF-8编码避免解码错误
        mapping = {
            "pdf": PyPDFLoader,
            "txt": TextLoader,
            "docx": Docx2txtLoader,
            "md": lambda path: TextLoader(path, encoding="utf-8"),  # 使用TextLoader，避免NLTK依赖，指定UTF-8
            "csv": CSVLoader,
            "html": UnstructuredHTMLLoader,
        }
        
        # 只保留支持的格式
        return {fmt: mapping[fmt] for fmt in self.supported_formats if fmt in mapping}
    
    def get_file_format(self, file_path: str) -> Optional[str]:
        """获取文件格式"""
        ext = Path(file_path).suffix.lower()[1:]  # 去掉点号
        return ext if ext in self.supported_formats else None
    
    def load_document(self, file_path: str) -> List[Document]:
        """加载单个文档"""
        try:
            file_format = self.get_file_format(file_path)
            if not file_format:
                raise ValueError(f"不支持的文件格式: {file_path}")
            
            logger.info(f"加载文档: {file_path} (格式: {file_format})")
            
            # 使用对应的加载器
            loader_class = self.loader_mapping[file_format]
            loader = loader_class(file_path)
            documents = loader.load()
            
            # 添加元数据
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "format": file_format,
                    "file_name": Path(file_path).name,
                })
            
            logger.info(f"成功加载文档，共 {len(documents)} 页/部分")
            return documents
            
        except Exception as e:
            logger.error(f"加载文档失败: {file_path}, 错误: {e}")
            raise
    
    def load_documents_from_directory(self, directory: str) -> List[Document]:
        """从目录加载所有文档"""
        all_documents = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.warning(f"目录不存在: {directory}")
            return all_documents
        
        # 遍历目录下的所有文件
        for file_path in directory_path.rglob("*"):
            if file_path.is_file():
                try:
                    file_format = self.get_file_format(str(file_path))
                    if file_format:
                        documents = self.load_document(str(file_path))
                        all_documents.extend(documents)
                except Exception as e:
                    logger.error(f"处理文件失败: {file_path}, 错误: {e}")
                    continue
        
        logger.info(f"从目录加载完成，共 {len(all_documents)} 个文档部分")
        return all_documents
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割文档为 chunks"""
        if not documents:
            return []
        
        try:
            # 应用文本分割
            chunks = self.text_splitter.split_documents(documents)
            
            # 限制每个文档的最大 chunks 数
            max_chunks = get_config("document_processing.chunking.max_chunks_per_doc", 100)
            max_chunks = int(max_chunks) if max_chunks is not None else 100
            
            # 按来源分组并限制
            chunks_by_source = {}
            for chunk in chunks:
                source = chunk.metadata.get("source", "unknown")
                if source not in chunks_by_source:
                    chunks_by_source[source] = []
                chunks_by_source[source].append(chunk)
            
            # 应用限制
            final_chunks = []
            for source, source_chunks in chunks_by_source.items():
                if len(source_chunks) > max_chunks:
                    logger.warning(f"文档 {source} 的 chunks 数 ({len(source_chunks)}) 超过限制 ({max_chunks})，将截断")
                    # 选择前 max_chunks 个，可以根据需要更智能地选择
                    final_chunks.extend(source_chunks[:max_chunks])
                else:
                    final_chunks.extend(source_chunks)
            
            logger.info(f"文档分割完成，共 {len(documents)} 个文档部分 -> {len(final_chunks)} 个 chunks")
            return final_chunks
            
        except Exception as e:
            logger.error(f"文档分割失败: {e}")
            raise
    
    def preprocess_text(self, text: str, file_format: Optional[str] = None) -> str:
        """文本预处理
        
        Args:
            text: 待处理的文本
            file_format: 文件格式，用于判断是否跳过某些预处理
        """
        preprocessing_config = self.config.get("preprocessing", {})
        
        # 检查是否为Markdown文件
        is_markdown = file_format == "md"
        
        # Markdown文件检查专用配置
        if is_markdown:
            markdown_config = preprocessing_config.get("markdown", {})
            if markdown_config.get("skip_whitespace_normalize", True):
                return text  # 跳过所有预处理
            if markdown_config.get("skip_unicode_normalize", True) and markdown_config.get("skip_mixed_language", True):
                return text
        
        # 移除多余空白
        if preprocessing_config.get("remove_extra_whitespace", True):
            text = re.sub(r'\s+', ' ', text).strip()
        
        # Unicode 标准化（如果需要）
        if preprocessing_config.get("normalize_unicode", True):
            import unicodedata
            text = unicodedata.normalize('NFKC', text)
        
        # 处理混合语言
        if preprocessing_config.get("handle_mixed_language", True):
            text = self._handle_mixed_language(text)
        
        return text
    
    def _handle_mixed_language(self, text: str) -> str:
        """处理中英文混合文本"""
        # 在中英文之间添加空格，提高可读性和处理效果
        text = re.sub(r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2', text)
        text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2', text)
        return text
    
    def process_file(self, file_path: str) -> List[Document]:
        """处理单个文件：加载、预处理、分割
        
        根据文件类型选择不同的处理策略：
        - Markdown: 跳过预处理，使用二级分块（标题+大小）
        - 其他格式: 传统预处理+分块
        """
        # 1. 加载文档
        documents = self.load_document(file_path)
        
        # 获取文件格式
        file_format = self.get_file_format(file_path)
        is_markdown = file_format == "md"
        
        # 2. 预处理文本（Markdown跳过破坏性预处理）
        if is_markdown:
            logger.info(f"Markdown文件，跳过预处理: {file_path}")
        else:
            for doc in documents:
                doc.page_content = self.preprocess_text(doc.page_content, file_format)
        
        # 3. 分割文档（Markdown使用专用分块器）
        if is_markdown:
            logger.info(f"使用Markdown专用分块器: {file_path}")
            chunks = self._split_markdown(documents)
        else:
            chunks = self.split_documents(documents)
        
        return chunks
    
    def _split_markdown(self, documents: List[Document]) -> List[Document]:
        """Markdown专用分块：二级分块（标题+大小）"""
        all_chunks = []
        
        for doc in documents:
            # 使用MarkdownAwareSplitter分割
            chunks = self.markdown_splitter.split_text(doc.page_content)
            
            # 添加元数据
            for chunk in chunks:
                chunk.metadata.update(doc.metadata)
            
            all_chunks.extend(chunks)
        
        # 限制每个文档的最大chunks数
        max_chunks = get_config("document_processing.chunking.max_chunks_per_doc", 100)
        max_chunks = int(max_chunks) if max_chunks is not None else 100
        
        chunks_by_source = {}
        for chunk in all_chunks:
            source = chunk.metadata.get("source", "unknown")
            if source not in chunks_by_source:
                chunks_by_source[source] = []
            chunks_by_source[source].append(chunk)
        
        final_chunks = []
        for source, source_chunks in chunks_by_source.items():
            if len(source_chunks) > max_chunks:
                logger.warning(f"文档 {source} 的 chunks 数 ({len(source_chunks)}) 超过限制 ({max_chunks})，将截断")
                final_chunks.extend(source_chunks[:max_chunks])
            else:
                final_chunks.extend(source_chunks)
        
        logger.info(f"Markdown分块完成，共 {len(documents)} 个文档 -> {len(final_chunks)} 个 chunks")
        return final_chunks
    
    def process_directory(self, directory: str) -> List[Document]:
        """处理整个目录"""
        # 1. 加载所有文档
        documents = self.load_documents_from_directory(directory)
        
        # 按文件格式分组处理
        markdown_docs = []
        other_docs = []
        
        for doc in documents:
            file_format = doc.metadata.get("format", "")
            if file_format == "md":
                markdown_docs.append(doc)
            else:
                other_docs.append(doc)
        
        all_chunks = []
        
        # 2. 处理Markdown文档（跳过预处理）
        if markdown_docs:
            logger.info(f"处理 {len(markdown_docs)} 个Markdown文档")
            for doc in markdown_docs:
                chunks = self.markdown_splitter.split_text(doc.page_content)
                for chunk in chunks:
                    chunk.metadata.update(doc.metadata)
                all_chunks.extend(chunks)
        
        # 3. 处理其他文档（传统预处理）
        if other_docs:
            logger.info(f"处理 {len(other_docs)} 个其他格式文档")
            for doc in other_docs:
                doc.page_content = self.preprocess_text(doc.page_content, doc.metadata.get("format"))
            chunks = self.split_documents(other_docs)
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def batch_process(self, file_paths: List[str], output_dir: Optional[str] = None) -> Dict[str, Any]:
        """批量处理文件"""
        results = {
            "total_files": len(file_paths),
            "processed_files": 0,
            "failed_files": [],
            "total_chunks": 0,
            "file_results": [],
        }
        
        for file_path in file_paths:
            try:
                file_name = Path(file_path).name
                logger.info(f"开始处理文件: {file_name}")
                
                # 处理文件
                chunks = self.process_file(file_path)
                
                # 保存结果（如果需要）
                if output_dir:
                    self._save_chunks(chunks, output_dir, file_name)
                
                # 记录结果
                file_result = {
                    "file_name": file_name,
                    "file_path": file_path,
                    "chunks_count": len(chunks),
                    "status": "success",
                }
                results["file_results"].append(file_result)
                results["processed_files"] += 1
                results["total_chunks"] += len(chunks)
                
                logger.info(f"文件处理完成: {file_name}, 生成 {len(chunks)} 个 chunks")
                
            except Exception as e:
                logger.error(f"处理文件失败: {file_path}, 错误: {e}")
                results["failed_files"].append({
                    "file_path": file_path,
                    "error": str(e),
                })
        
        logger.info(f"批量处理完成: {results['processed_files']}/{results['total_files']} 个文件成功")
        return results
    
    def _save_chunks(self, chunks: List[Document], output_dir: str, base_name: str) -> None:
        """保存 chunks 到文件（用于调试）"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for i, chunk in enumerate(chunks):
            chunk_file = output_path / f"{base_name}_chunk_{i:03d}.txt"
            with open(chunk_file, 'w', encoding='utf-8') as f:
                f.write(f"=== 元数据 ===\n")
                for key, value in chunk.metadata.items():
                    f.write(f"{key}: {value}\n")
                f.write(f"\n=== 内容 ===\n")
                f.write(chunk.page_content)
                f.write(f"\n=== 结束 ===\n")


# 便捷函数
def create_document_processor(config=None) -> DocumentProcessor:
    """创建文档处理器实例"""
    return DocumentProcessor(config)

def process_single_file(file_path: str, config=None) -> List[Document]:
    """处理单个文件"""
    processor = create_document_processor(config)
    return processor.process_file(file_path)

def process_directory_files(directory: str, config=None) -> List[Document]:
    """处理目录中的所有文件"""
    processor = create_document_processor(config)
    return processor.process_directory(directory)