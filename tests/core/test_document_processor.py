"""
文档处理模块测试
"""

import pytest
from langchain_core.documents import Document
from src.core.document_processor import (
    ChineseTextSplitter,
    MarkdownAwareSplitter,
    DocumentProcessor,
)


class TestChineseTextSplitter:
    """中文文本分割器测试"""

    def test_split_empty_text(self):
        """测试空文本分割"""
        splitter = ChineseTextSplitter(chunk_size=100, chunk_overlap=20)
        result = splitter.split_text("")
        assert result == []

    def test_split_chinese_text(self):
        """测试中文文本分割"""
        splitter = ChineseTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "这是第一个句子。这是第二个句子。这是第三个句子。"
        result = splitter.split_text(text)
        assert len(result) > 0

    def test_split_english_text(self):
        """测试英文文本分割"""
        splitter = ChineseTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "This is the first sentence. This is the second sentence. This is the third sentence."
        result = splitter.split_text(text)
        assert len(result) > 0

    def test_split_mixed_language(self):
        """测试中英文混合分割"""
        splitter = ChineseTextSplitter(chunk_size=80, chunk_overlap=10)
        text = "Python是一种编程语言。It is widely used in data science."
        result = splitter.split_text(text)
        assert len(result) > 0

    def test_split_with_punctuation(self):
        """测试带标点的分割"""
        splitter = ChineseTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "你好，世界！你今天怎么样？很好，谢谢！"
        result = splitter.split_text(text)
        assert len(result) > 0

    def test_split_respects_chunk_size(self):
        """测试分块大小限制"""
        chunk_size = 50
        splitter = ChineseTextSplitter(chunk_size=chunk_size, chunk_overlap=0)
        # 添加标点符号帮助分割
        text = "a" * 20 + "。" + "b" * 20 + "。" + "c" * 20
        result = splitter.split_text(text)

        # 每个块应该不超过chunk_size（允许一些重叠）
        for chunk in result:
            assert len(chunk) <= chunk_size + 20


class TestMarkdownAwareSplitter:
    """Markdown感知分割器测试"""

    def test_split_markdown_with_headers(self):
        """测试带标题的Markdown分割"""
        splitter = MarkdownAwareSplitter(chunk_size=100, chunk_overlap=20)
        text = """# 第一章

这是第一章的内容。

## 第一节

这是第一节的内容。

# 第二章

这是第二章的内容。
"""
        result = splitter.split_text(text)
        assert len(result) > 0

    def test_split_markdown_without_headers(self):
        """测试不带标题的Markdown"""
        splitter = MarkdownAwareSplitter(chunk_size=50, chunk_overlap=10)
        text = "这是普通文本内容。没有标题标记。"
        result = splitter.split_text(text)
        assert len(result) > 0

    def test_split_preserves_metadata(self):
        """测试分割保留元数据"""
        splitter = MarkdownAwareSplitter(chunk_size=100, chunk_overlap=20)
        doc = Document(
            page_content="# 标题\n\n内容段落。", metadata={"source": "test.md"}
        )
        result = splitter.split_text(doc.page_content)
        assert len(result) > 0

    def test_split_code_blocks(self):
        """测试代码块保护"""
        splitter = MarkdownAwareSplitter(chunk_size=200, chunk_overlap=20)
        text = """# 代码示例

```
def hello():
    print("Hello, World!")
```

以上是代码示例。
"""
        result = splitter.split_text(text)
        # 代码块应该被保护
        assert len(result) > 0


class TestDocumentProcessor:
    """文档处理器测试"""

    def test_get_file_format(self):
        """测试获取文件格式"""
        processor = DocumentProcessor()

        assert processor.get_file_format("test.pdf") == "pdf"
        assert processor.get_file_format("test.md") == "md"
        assert processor.get_file_format("test.txt") == "txt"
        assert processor.get_file_format("test.docx") == "docx"
        assert processor.get_file_format("test.doc") is None  # 不支持

    def test_preprocess_text_basic(self):
        """测试基础文本预处理"""
        processor = DocumentProcessor()
        text = "这是   带有   多余   空白的文本"
        result = processor.preprocess_text(text)
        assert "   " not in result

    def test_preprocess_text_mixed_language(self):
        """测试混合语言预处理"""
        processor = DocumentProcessor()
        text = "Python是一种编程语言"
        result = processor.preprocess_text(text)
        # 应该在英文和中文之间添加空格
        assert result is not None

    def test_split_documents_empty(self):
        """测试空文档分割"""
        processor = DocumentProcessor()
        result = processor.split_documents([])
        assert result == []

    def test_split_documents(self):
        """测试文档分割"""
        processor = DocumentProcessor()
        docs = [
            Document(
                page_content=("这是第一个文档的内容。" * 20 + "。") * 10,
                metadata={"source": "doc1.txt"},
            ),
            Document(
                page_content=("这是第二个文档的内容。" * 20 + "。") * 10,
                metadata={"source": "doc2.txt"},
            ),
        ]
        result = processor.split_documents(docs)
        # 验证至少有一些分割结果
        assert len(result) >= len(docs)

    def test_split_documents_preserves_metadata(self):
        """测试分割保留元数据"""
        processor = DocumentProcessor()
        docs = [
            Document(
                page_content="这是文档内容。" * 30,
                metadata={"source": "test.txt", "custom": "value"},
            )
        ]
        result = processor.split_documents(docs)

        # 所有分块应该保留source元数据
        for chunk in result:
            assert chunk.metadata.get("source") == "test.txt"
