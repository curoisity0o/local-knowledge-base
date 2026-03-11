# 文档处理策略分析报告

## 一、当前系统状态

### 1.1 支持的文档格式

| 格式 | 加载器 | 特点 |
|------|--------|------|
| PDF | PyPDFLoader | 只提取文本层，公式图片丢失 |
| DOCX | Docx2txtLoader | 基础文本提取 |
| TXT | TextLoader | 纯文本 |
| **MD** | **UnstructuredMarkdownLoader** | 保留Markdown结构 |
| HTML | UnstructuredHTMLLoader | 保留HTML结构 |
| CSV | CSVLoader | 表格数据 |

### 1.2 当前预处理配置（settings.yaml 第37-40行）

```yaml
preprocessing:
  remove_extra_whitespace: true   # \s+ → 空格，会破坏公式间距
  normalize_unicode: true          # NFKC规范化，会破坏特殊符号
  handle_mixed_language: true     # 中英文间加空格，会破坏LaTeX
```

### 1.3 当前分块策略

- 分割器：`ChineseTextSplitter`（继承 `RecursiveCharacterTextSplitter`）
- 分隔符：`["\n\n", "\n", "。", "？", "！", "；", "?", "!", ";", "…", "……"]`
- **问题**：没有考虑Markdown语法元素（标题、公式块、代码块）

---

## 二、问题分析

### 2.1 原始问题回顾

| 阶段 | 问题 | 严重程度 |
|------|------|----------|
| PDF加载 | PyPDFLoader只提取文本层，公式图片完全丢失 | 🔴 高 |
| Unicode标准化 | NFKC规范化破坏数学符号 (∫→f, x²→x2) | 🔴 高 |
| 空白符处理 | `\s+` → ` ` 破坏公式间距结构 | 🔴 高 |
| 分块 | 可能在公式中间截断 | 🟠 中 |

### 2.2 上传Markdown后的影响

| 问题 | 是否解决 | 说明 |
|------|----------|------|
| PDF加载 | ✅ 已解决 | 不再使用PyPDFLoader |
| Unicode标准化 | ❌ 仍影响 | 预处理仍会破坏LaTeX公式 |
| 空白符处理 | ❌ 仍影响 | 预处理仍会破坏公式结构 |
| 分块 | ❌ 仍影响 | 可能在 `$...$` 中间截断 |

---

## 三、方案对比

### 方案A：全部转Markdown

**做法**：所有文档都手动转为Markdown再上传

| 优点 | 缺点 |
|------|------|
| 格式统一，处理逻辑简单 | 需要手动转换，工作量大 |
| 保留完整结构（标题、列表、公式） | 简单文档转换浪费时间 |
| 不需要改代码 | 公式文档转换需要MinerU |

### 方案B：混合处理

**做法**：
- 简单文档（txt、docx、普通pdf）→ 继续使用现有预处理
- 复杂文档（含公式、技术文档）→ 手动转Markdown，关闭预处理

| 优点 | 缺点 |
|------|------|
| 简单文档处理不变 | 需要识别哪些是"复杂"文档 |
| 只需改配置/代码处理Markdown | 可能需要改代码判断文件类型 |
| 灵活适应不同场景 | - |

### 方案C：统一改进（推荐）

**做法**：
- 关闭全局预处理（或按文件类型配置）
- 改进分块策略，保护Markdown/LaTeX边界

| 优点 | 缺点 |
|------|------|
| 一劳永逸，所有文档都受益 | 需要改代码 |
| 更健壮的文档处理 | 需要测试验证 |
| 支持未来更多文档类型 | - |

---

## 四、分块策略对比

### 策略1：当前策略（RecursiveCharacterTextSplitter）

```python
separators = ["\n\n", "\n", "。", "？", "！", "；", "?", "!", ";", "…", "……"]
```

- **问题**：会破坏Markdown结构、截断LaTeX公式

### 策略2：添加LaTeX/Markdown边界（推荐）

```python
separators = [
    "\n\n", "\n",                    # 段落级别
    "$$",                            # 块公式
    "```",                           # 代码块
    "##", "#",                       # 标题
    "$",                             # 行内公式（可选）
    "。", "？", "！", "；", "?", "!", ";", "…", "……"  # 句子
]
```

- **优点**：公式、代码块、标题整体保留
- **问题**：`$` 可能与货币符号冲突

### 策略3：按Markdown标题分块（更智能）

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter

headers_to_split_on = [
    ("#", "header1"),
    ("##", "header2"),
    ("###", "header3"),
]
splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
```

- **优点**：每个标题下内容作为一个chunk，语义完整
- **适用**：结构化文档（书籍、论文、教程）

### 策略4：混合策略（最佳）

```python
# 第一步：按标题分块
# 第二步：每个标题块内再按大小分
```

- **优点**：兼顾结构完整性和块大小控制
- **复杂度**：实现较复杂

---

## 五、推荐方案

### 推荐：方案C + 策略2/3 组合

**核心思路**：统一改进，对Markdown和简单文档分别优化

### 5.1 具体实施

#### 第一步：修改配置（settings.yaml）

```yaml
document_processing:
  preprocessing:
    # 改为按文件类型处理
    remove_extra_whitespace: false   # 全局关闭
    normalize_unicode: false          # 全局关闭
    handle_mixed_language: false      # 全局关闭
    
  # 新增：Markdown专用配置
  markdown:
    enable_semantic_chunking: true   # 启用语义分块
    preserve_formula: true            # 保留公式边界
    
  # 保留简单文档的处理配置
  simple_formats:
    - "txt"
    - "docx"
    preprocess_these: false           # 是否预处理
```

#### 第二步：改进代码（document_processor.py）

```python
class DocumentProcessor:
    def process_file(self, file_path: str) -> List[Document]:
        # 1. 加载文档
        documents = self.load_document(file_path)
        
        # 2. 根据文件类型决定是否预处理
        file_format = self.get_file_format(file_path)
        
        if file_format == "md":
            # Markdown：跳过破坏性预处理，使用语义分块
            pass  # 不预处理
        else:
            # 其他格式：使用原有预处理
            for doc in documents:
                doc.page_content = self.preprocess_text(doc.page_content)
        
        # 3. 分块
        if file_format == "md":
            chunks = self._split_markdown(documents)
        else:
            chunks = self.split_documents(documents)
        
        return chunks
    
    def _split_markdown(self, documents: List[Document]) -> List[Document]:
        """Markdown专用分块：保护公式和结构"""
        # 使用 MarkdownHeaderTextSplitter 或添加公式边界
        pass
```

#### 第三步：分块策略改进

```python
class MarkdownAwareSplitter(RecursiveCharacterTextSplitter):
    """保护Markdown和LaTeX公式的分块器"""
    
    def __init__(self, **kwargs):
        # 公式和代码块优先作为分隔符
        separators = [
            "\n\n", "\n",
            "$$",           # 块公式
            "```",          # 代码块
            "##", "###", "#",  # 标题
            "。", "？", "！", "；", "?", "!", ";",
        ]
        super().__init__(separators=separators, **kwargs)
```

---

## 六、用户操作建议

### 6.1 当前最优操作

1. **简单文档**（txt、普通docx、普通pdf）：
   - 直接上传，不需手动转换
   - 使用现有预处理逻辑

2. **复杂文档**（含公式的技术文档、论文、教程）：
   - 用MinerU在线版转Markdown
   - 上传.md文件

### 6.2 未来改进后

统一处理流程：
- 所有文档 → Markdown（可选）
- 系统自动识别并应用最佳处理策略

---

## 七、总结

| 决策点 | 推荐 | 理由 |
|--------|------|------|
| 是否都转Markdown | **否，按需转换** | 简单文档没必要 |
| 是否改预处理 | **是，按文件类型** | 保护Markdown公式 |
| 分块策略 | **添加公式边界** | 改动小，效果好 |

**最终目标**：系统能自动识别文档类型，对Markdown使用语义分块，对简单文档保留现有逻辑。

---

## 八、MinerU PDF转换工具使用指南

### 8.1 什么时候需要MinerU？

| 文档类型 | 是否需要MinerU | 说明 |
|----------|---------------|------|
| 纯文本PDF（无公式） | ❌ 不需要 | 直接上传即可 |
| 扫描版PDF | ✅ 需要 | 需要OCR识别文字 |
| **含公式的PDF**（技术文档、论文） | ✅ **强烈推荐** | 公式会转为LaTeX |
| 含表格的PDF | ✅ 推荐 | 表格会转为HTML |

### 8.2 使用流程（推荐）

**步骤1**：访问 MinerU 在线版
```
https://mineru.net/
```

**步骤2**：上传PDF文件
- 点击 "上传文件" 按钮
- 选择要转换的PDF
- 等待转换完成

**步骤3**：下载Markdown
- 转换完成后，点击 "下载"
- 选择 "Markdown" 格式

**步骤4**：上传到知识库
- 将下载的 `.md` 文件放到 `data/raw_docs/` 目录
- 在系统中上传该Markdown文件

### 8.3 MinerU的优势

| 特性 | 说明 |
|------|------|
| ✅ 公式识别 | 自动将公式转为 `$...$` 或 `$$...$$` LaTeX格式 |
| ✅ 表格识别 | 自动将表格转为HTML格式 |
| ✅ 图像提取 | 可以提取图片（可选） |
| ✅ 多语言 | 支持109种语言OCR |
| ✅ 免费使用 | 每天2000页免费额度 |

### 8.4 API配置（可选）

如果你有大量文档需要处理，可以配置MinerU API：

**配置Token**：
```bash
# 在 .env 文件中添加
MINERU_API_TOKEN=你的token
```

**Token验证**：
```python
from src.core.mineru_api import validate_mineru_token

result = validate_mineru_token("你的token")
print(result)
# {'valid': True, 'message': 'Token有效，可以正常调用API'}
```

⚠️ **注意**：API需要PDF文件的公网URL，操作较复杂。**建议继续使用在线版**。

### 8.5 注意事项

1. **图片处理**：MinerU会提取图片，但对于纯文本RAG系统，图片不是必需的
2. **文件大小**：单文件不超过200MB，页数不超过600页
3. **每日限额**：每天2000页免费额度

---

## 九、常见问题

**Q: 上传PDF还是Markdown？**
A: 优先上传Markdown，特别是含公式的文档。

**Q: 公式显示不正常？**
A: 确保使用Markdown格式上传，LaTeX公式会被保留。

**Q: MinerU转换失败？**
A: 检查PDF是否加密、损坏，或尝试在线版处理。