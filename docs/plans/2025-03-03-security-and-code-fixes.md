# 安全与代码修复实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复本地知识库系统中的安全漏洞和代码质量问题，提升项目安全性和代码质量

**Architecture:** 按优先级分阶段修复：P0安全漏洞 → P1重要问题 → P2代码质量 → P3配置问题 → 安装Ollama → 清理文件

**Tech Stack:** Python, FastAPI, Streamlit, LangChain, Ollama, Git

---

## 阶段1: P0紧急安全修复 (24小时内)

### 任务1: 清理泄露的API密钥

**Files:**
- Modify: `.env:21`
- Test: 验证环境变量安全

**Step 1: 移除硬编码的API密钥**

```bash
# 备份原始.env文件
cp .env .env.backup.$(date +%Y%m%d)
```

**Step 2: 编辑.env文件**

打开`.env`文件，将第21行修改为：
```bash
DEEPSEEK_API_KEY=""
```

**Step 3: 清理git历史中的敏感信息**

```bash
# 检查.gitignore是否包含.env
grep "^\.env$" .gitignore

# 如果.env已被提交，需要从历史中移除
# 注意：这会重写git历史，确保团队已同步
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all
```

**Step 4: 验证清理**

```bash
# 确保.env不在git跟踪中
git status --ignored
git log --all --full-history -- "**/.env"
```

**Step 5: 提交更改**

```bash
git add .gitignore
git add .env
git commit -m "security: remove hardcoded API key from .env and git history"
```

### 任务2: 修复eval()代码执行风险

**Files:**
- Modify: `src/agents/tools.py:227`
- Test: `tests/agents/test_tools.py` (需要创建)

**Step 1: 创建测试文件**

```python
# tests/agents/test_tools.py
import pytest
from src.agents.tools import safe_eval

def test_safe_eval_basic_operations():
    """测试安全表达式求值基本操作"""
    assert safe_eval("2 + 3", {}) == 5
    assert safe_eval("10 - 4", {}) == 6
    assert safe_eval("3 * 4", {}) == 12
    assert safe_eval("12 / 3", {}) == 4

def test_safe_eval_with_variables():
    """测试带变量的表达式求值"""
    names = {"x": 5, "y": 3}
    assert safe_eval("x + y", names) == 8
    assert safe_eval("x * y - 2", names) == 13

def test_safe_eval_security():
    """测试安全性 - 危险表达式应被阻止"""
    with pytest.raises(Exception):
        safe_eval("__import__('os').system('ls')", {})
    
    with pytest.raises(Exception):
        safe_eval("open('/etc/passwd').read()", {})
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/agents/test_tools.py -v
```
预期：失败，因为safe_eval函数不存在

**Step 3: 修改tools.py实现安全求值**

```python
# 在src/agents/tools.py顶部添加导入
import ast
import operator
from typing import Any, Dict

# 添加安全求值函数
def safe_eval(expression: str, allowed_names: Dict[str, Any]) -> Any:
    """
    安全地求值数学表达式
    
    Args:
        expression: 数学表达式字符串
        allowed_names: 允许使用的变量名和值
        
    Returns:
        表达式求值结果
        
    Raises:
        ValueError: 表达式不安全或求值失败
    """
    # 允许的操作符
    SAFE_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,  # 一元负号
        ast.UAdd: operator.pos,  # 一元正号
    }
    
    # 检查表达式长度（防止DoS）
    if len(expression) > 1000:
        raise ValueError("表达式过长")
    
    try:
        # 解析表达式为AST
        tree = ast.parse(expression, mode='eval')
        
        # 定义AST节点检查器
        def check_node(node):
            """递归检查AST节点安全性"""
            if isinstance(node, ast.Expression):
                return check_node(node.body)
            elif isinstance(node, ast.BinOp):
                if type(node.op) not in SAFE_OPERATORS:
                    raise ValueError(f"不允许的操作符: {type(node.op)}")
                check_node(node.left)
                check_node(node.right)
            elif isinstance(node, ast.UnaryOp):
                if type(node.op) not in SAFE_OPERATORS:
                    raise ValueError(f"不允许的一元操作符: {type(node.op)}")
                check_node(node.operand)
            elif isinstance(node, ast.Num):
                return  # 数字是安全的
            elif isinstance(node, ast.Name):
                if node.id not in allowed_names:
                    raise ValueError(f"未允许的变量名: {node.id}")
            elif isinstance(node, ast.Call):
                raise ValueError("函数调用不被允许")
            elif isinstance(node, ast.Attribute):
                raise ValueError("属性访问不被允许")
            elif isinstance(node, ast.Subscript):
                raise ValueError("下标访问不被允许")
            else:
                raise ValueError(f"不支持的AST节点: {type(node)}")
        
        # 检查AST安全性
        check_node(tree)
        
        # 安全地编译和执行
        code = compile(tree, '<string>', 'eval')
        return eval(code, {"__builtins__": {}}, allowed_names)
        
    except SyntaxError as e:
        raise ValueError(f"表达式语法错误: {e}")
    except Exception as e:
        raise ValueError(f"表达式求值失败: {e}")

# 修改原来的calculate函数
def calculate(expression: str) -> Dict[str, Any]:
    """计算数学表达式"""
    try:
        # 移除eval调用，改用safe_eval
        allowed_names = {
            'pi': 3.141592653589793,
            'e': 2.718281828459045,
        }
        result = safe_eval(expression, allowed_names)
        
        return {
            "success": True,
            "result": result,
            "expression": expression
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "expression": expression
        }
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/agents/test_tools.py -v
```
预期：所有测试通过

**Step 5: 提交更改**

```bash
git add src/agents/tools.py
git add tests/agents/test_tools.py
git commit -m "security: replace eval() with safe_eval() to prevent code injection"
```

### 任务3: 修复CORS配置

**Files:**
- Modify: `src/api/main.py:30-35`
- Test: 验证CORS头正确设置

**Step 1: 分析当前CORS需求**

检查前端应用可能的访问来源：
- Streamlit前端: http://localhost:8501
- 可能的其他前端: http://localhost:3000
- 生产环境域名: (根据实际配置)

**Step 2: 修改CORS配置**

```python
# src/api/main.py 第30-35行修改为：
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",    # Streamlit前端
        "http://localhost:3000",    # React/Vue前端
        "http://127.0.0.1:8501",
        "http://127.0.0.1:3000",
        # 生产环境域名在此添加，例如:
        # "https://your-domain.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```

**Step 3: 添加环境变量配置支持**

```python
# 在CORS配置前添加环境变量读取
import os

# 从环境变量读取允许的来源，支持多个来源用逗号分隔
cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
if cors_origins == [""]:
    cors_origins = [
        "http://localhost:8501",
        "http://localhost:3000", 
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
```

**Step 4: 更新.env.example文件**

```bash
# 在.env.example中添加CORS配置
echo "CORS_ALLOW_ORIGINS=http://localhost:8501,http://localhost:3000" >> .env.example
```

**Step 5: 测试CORS配置**

创建测试脚本：
```python
# scripts/test_cors.py
import requests
import json

def test_cors_headers():
    url = "http://localhost:8000/health"
    
    # 测试允许的来源
    headers = {"Origin": "http://localhost:8501"}
    response = requests.get(url, headers=headers)
    
    print(f"Status: {response.status_code}")
    print(f"Access-Control-Allow-Origin: {response.headers.get('Access-Control-Allow-Origin')}")
    print(f"Access-Control-Allow-Credentials: {response.headers.get('Access-Control-Allow-Credentials')}")
    
    # 测试不允许的来源
    headers = {"Origin": "http://evil.com"}
    response = requests.get(url, headers=headers)
    print(f"\nBlocked origin status: {response.status_code}")
    
if __name__ == "__main__":
    test_cors_headers()
```

**Step 6: 提交更改**

```bash
git add src/api/main.py
git add .env.example
git add scripts/test_cors.py
git commit -m "security: restrict CORS to specific origins with environment variable support"
```

---

## 阶段2: P1重要问题修复 (1周内)

### 任务4: 移除硬编码绝对路径

**Files:**
- Modify: `src/core/llm_manager.py:65-67`
- Modify: `src/core/vector_store.py:44-46`
- Modify: `.env.example`
- Create: `scripts/check_paths.py`

**Step 1: 创建路径检查脚本**

```python
# scripts/check_paths.py
import os
import sys
from pathlib import Path

def find_hardcoded_paths():
    """查找项目中的硬编码路径"""
    project_root = Path(__file__).parent.parent
    hardcoded_paths = []
    
    for root, dirs, files in os.walk(project_root):
        # 跳过虚拟环境和缓存目录
        if any(x in root for x in ['venv', '.venv', '__pycache__', '.git', '.ruff_cache']):
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = Path(root) / file
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # 查找Windows绝对路径
                    if 'D:/code/LLM' in content or 'D:\\code\\LLM' in content:
                        hardcoded_paths.append(str(filepath))
                        
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return hardcoded_paths

if __name__ == "__main__":
    paths = find_hardcoded_paths()
    if paths:
        print("发现硬编码路径:")
        for p in paths:
            print(f"  - {p}")
        sys.exit(1)
    else:
        print("未发现硬编码路径")
        sys.exit(0)
```

**Step 2: 修改llm_manager.py中的硬编码路径**

```python
# src/core/llm_manager.py 第65-67行修改为：
import os
from pathlib import Path

# 从环境变量获取模型缓存路径，默认为用户home目录下的.cache
model_cache_base = os.getenv("MODEL_CACHE_PATH", str(Path.home() / ".cache" / "models"))
modelscope_model_path = Path(model_cache_base) / "deepseek-ai" / "DeepSeek-V2-Lite"
use_modelscope = modelscope_model_path.exists()
```

**Step 3: 修改vector_store.py中的硬编码路径**

```python
# src/core/vector_store.py 第44-46行修改为：
# 使用环境变量或默认路径
model_cache_base = os.getenv("MODEL_CACHE_PATH", str(Path.home() / ".cache" / "models"))
default_model_path = Path(model_cache_base) / "iic" / "nlp_corom_sentence-embedding_chinese-base"
```

**Step 4: 更新.env.example**

```bash
# 添加模型缓存路径配置
echo "MODEL_CACHE_PATH=~/.cache/models" >> .env.example
```

**Step 5: 测试路径配置**

```bash
# 运行路径检查脚本
python scripts/check_paths.py

# 测试环境变量读取
export MODEL_CACHE_PATH="/tmp/test_cache"
python -c "from src.core.llm_manager import LLMManager; print('路径配置测试通过')"
```

**Step 6: 提交更改**

```bash
git add src/core/llm_manager.py
git add src/core/vector_store.py
git add .env.example
git add scripts/check_paths.py
git commit -m "fix: remove hardcoded paths, use environment variables instead"
```

### 任务5: 修复路径遍历风险

**Files:**
- Modify: `src/agents/tools.py:183`
- Create: `tests/agents/test_path_security.py`

**Step 1: 创建路径安全测试**

```python
# tests/agents/test_path_security.py
import pytest
from pathlib import Path
import tempfile
import os

def test_path_traversal_prevention():
    """测试路径遍历攻击防护"""
    from src.agents.tools import safe_join
    
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        
        # 正常情况
        result = safe_join(str(base_path), "subdir/file.txt")
        assert str(result).startswith(str(base_path))
        
        # 路径遍历攻击应被阻止
        with pytest.raises(ValueError, match="路径遍历攻击检测"):
            safe_join(str(base_path), "../../etc/passwd")
            
        with pytest.raises(ValueError, match="路径遍历攻击检测"):
            safe_join(str(base_path), "subdir/../../../etc/shadow")
            
        # 绝对路径应被阻止
        with pytest.raises(ValueError, match="路径遍历攻击检测"):
            safe_join(str(base_path), "/etc/passwd")
```

**Step 2: 在tools.py中添加safe_join函数**

```python
# src/agents/tools.py 添加函数
from pathlib import Path

def safe_join(base_path: str, user_path: str) -> Path:
    """
    安全地拼接路径，防止路径遍历攻击
    
    Args:
        base_path: 基础路径
        user_path: 用户提供的相对路径
        
    Returns:
        安全的绝对路径
        
    Raises:
        ValueError: 如果检测到路径遍历攻击
    """
    # 解析路径
    base = Path(base_path).resolve()
    user = Path(user_path)
    
    # 防止绝对路径
    if user.is_absolute():
        raise ValueError("路径遍历攻击检测：不允许绝对路径")
    
    # 拼接并解析路径
    full_path = (base / user).resolve()
    
    # 验证结果路径在基础路径内
    if not str(full_path).startswith(str(base)):
        raise ValueError("路径遍历攻击检测：路径越界")
    
    return full_path
```

**Step 3: 修改使用路径的地方**

```python
# 在tools.py中找到使用路径的地方（约第183行）修改为：
full_path = safe_join(base_path, file_path)
```

**Step 4: 运行测试**

```bash
pytest tests/agents/test_path_security.py -v
```
预期：测试通过

**Step 5: 提交更改**

```bash
git add src/agents/tools.py
git add tests/agents/test_path_security.py
git commit -m "security: add path traversal protection with safe_join function"
```

### 任务6: 修复空except块

**Files:**
- Modify: `src/core/vector_store_backup.py:290`
- Test: 验证错误处理正确

**Step 1: 检查所有空except块**

```bash
# 查找所有空except块
grep -n "except:" src/core/vector_store_backup.py
grep -n "except Exception:" src/core/vector_store_backup.py
grep -n "except.*pass" src/ -r
```

**Step 2: 修复vector_store_backup.py中的空except**

```python
# src/core/vector_store_backup.py 第290行修改为：
except Exception as e:
    logger.error(f"获取文档失败: {e}")
    # 根据业务逻辑决定是返回空列表还是抛出异常
    return []  # 或 raise
```

**Step 3: 创建错误处理测试**

```python
# tests/core/test_error_handling.py
import pytest
import logging
from unittest.mock import patch

def test_no_empty_except_blocks():
    """确保没有空except块"""
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    empty_except_files = []
    
    for root, dirs, files in os.walk(os.path.join(project_root, 'src')):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines):
                        if 'except:' in line or 'except :' in line:
                            # 检查下一行是否有pass
                            if i + 1 < len(lines) and 'pass' in lines[i + 1]:
                                empty_except_files.append(f"{filepath}:{i+1}")
    
    assert len(empty_except_files) == 0, f"发现空except块: {empty_except_files}"
```

**Step 4: 运行测试**

```bash
pytest tests/core/test_error_handling.py -v
```
预期：测试通过

**Step 5: 提交更改**

```bash
git add src/core/vector_store_backup.py
git add tests/core/test_error_handling.py
git commit -m "fix: replace empty except blocks with proper error handling"
```

---

## 阶段3: P2代码质量问题修复

### 任务7: 添加文件上传限制

**Files:**
- Modify: `src/api/main.py:199-224`
- Create: `tests/api/test_file_upload.py`

**Step 1: 修改文件上传端点**

```python
# src/api/main.py 修改upload_document函数
from fastapi import UploadFile, File, HTTPException
import os

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.docx', '.md', '.csv', '.html'}

@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档，有大小和类型限制"""
    try:
        # 检查文件类型
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # 检查文件大小
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"文件太大: {len(content)}字节。最大允许: {MAX_FILE_SIZE}字节"
            )
        
        # 保存上传的文件
        upload_dir = config.get("paths.raw_docs", "./data/raw_docs")
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, file.filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        return {
            "success": True,
            "message": f"文件上传成功: {file.filename}",
            "file_path": file_path,
            "file_size": len(content),
            "file_type": file_ext
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")
```

**Step 2: 更新配置支持**

```python
# 在配置中添加文件上传限制
# config/settings.yaml 添加：
file_upload:
  max_size_mb: 10
  allowed_extensions: [".pdf", ".txt", ".docx", ".md", ".csv", ".html"]
  
# 在src/api/main.py中读取配置：
max_file_size = config.get("file_upload.max_size_mb", 10) * 1024 * 1024
allowed_extensions = set(config.get("file_upload.allowed_extensions", ALLOWED_EXTENSIONS))
```

**Step 3: 创建文件上传测试**

```python
# tests/api/test_file_upload.py
import pytest
from fastapi.testclient import TestClient
import os
import tempfile

def test_file_upload_success(client):
    """测试成功的文件上传"""
    test_content = b"This is a test file content."
    
    files = {'file': ('test.txt', test_content, 'text/plain')}
    response = client.post("/api/v1/documents/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["file_type"] == ".txt"

def test_file_upload_too_large(client):
    """测试文件过大"""
    # 创建11MB的文件内容
    large_content = b"x" * (11 * 1024 * 1024)
    
    files = {'file': ('large.txt', large_content, 'text/plain')}
    response = client.post("/api/v1/documents/upload", files=files)
    
    assert response.status_code == 400
    assert "文件太大" in response.json()["detail"]

def test_file_upload_invalid_type(client):
    """测试不支持的文件类型"""
    test_content = b"Malicious executable content"
    
    files = {'file': ('test.exe', test_content, 'application/x-msdownload')}
    response = client.post("/api/v1/documents/upload", files=files)
    
    assert response.status_code == 400
    assert "不支持的文件类型" in response.json()["detail"]
```

**Step 4: 运行测试**

```bash
pytest tests/api/test_file_upload.py -v
```
预期：测试通过

**Step 5: 提交更改**

```bash
git add src/api/main.py
git add config/settings.yaml
git add tests/api/test_file_upload.py
git commit -m "security: add file upload size and type restrictions"
```

### 任务8: 提取重复代码

**Files:**
- Modify: `src/core/llm_manager.py`
- Create: `src/core/utils.py`

**Step 1: 创建公共工具模块**

```python
# src/core/utils.py
"""
公共工具函数
"""

import re
from typing import Tuple

def estimate_tokens(text: str) -> int:
    """
    估算文本的token数量
    
    使用简单的启发式算法：英文字符约4个字符=1个token
    中文字符约1个字符=1-2个token
    
    Args:
        text: 输入文本
        
    Returns:
        估算的token数量
    """
    if not text:
        return 0
    
    # 统计中文字符
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    
    # 统计其他字符
    other_chars = len(text) - chinese_chars
    
    # 简单估算：中文1字符≈1.5token，英文4字符≈1token
    estimated = (chinese_chars * 1.5) + (other_chars / 4)
    
    return int(estimated)

def split_tokens(tokens: dict, input_text: str, output_text: str) -> Tuple[int, int]:
    """
    分割输入输出token计数
    
    Args:
        tokens: token字典（可能为空）
        input_text: 输入文本
        output_text: 输出文本
        
    Returns:
        (input_tokens, output_tokens)
    """
    if tokens and "input" in tokens and "output" in tokens:
        return tokens["input"], tokens["output"]
    else:
        return estimate_tokens(input_text), estimate_tokens(output_text)
```

**Step 2: 修改llm_manager.py使用公共函数**

```python
# 在llm_manager.py顶部添加导入
from .utils import estimate_tokens, split_tokens

# 修改第501-503行的重复代码
# 原代码：
# input_tokens = len(prompt) // 4
# output_tokens = len(response) // 4

# 新代码：
input_tokens, output_tokens = split_tokens(
    result.get("tokens", {}) if "tokens" in locals() else {},
    prompt,
    response
)
```

**Step 3: 更新其他使用近似token计算的地方**

查找并替换所有 `len(text) // 4` 模式为 `estimate_tokens(text)`

**Step 4: 创建工具函数测试**

```python
# tests/core/test_utils.py
import pytest
from src.core.utils import estimate_tokens, split_tokens

def test_estimate_tokens():
    """测试token估算"""
    # 英文文本
    assert estimate_tokens("Hello world") == 3  # 11字符 / 4 ≈ 2.75 ≈ 3
    
    # 中文文本
    chinese_text = "你好世界"
    assert 4 <= estimate_tokens(chinese_text) <= 8  # 4字符 * 1.5 ≈ 6
    
    # 混合文本
    mixed_text = "Hello 世界"
    result = estimate_tokens(mixed_text)
    assert 4 <= result <= 7
    
    # 空文本
    assert estimate_tokens("") == 0

def test_split_tokens():
    """测试token分割"""
    # 有token信息的情况
    tokens = {"input": 100, "output": 200}
    assert split_tokens(tokens, "input", "output") == (100, 200)
    
    # 无token信息的情况
    assert split_tokens({}, "Hello", "World") == (estimate_tokens("Hello"), estimate_tokens("World"))
```

**Step 5: 运行测试**

```bash
pytest tests/core/test_utils.py -v
```
预期：测试通过

**Step 6: 提交更改**

```bash
git add src/core/utils.py
git add src/core/llm_manager.py
git add tests/core/test_utils.py
git commit -m "refactor: extract duplicate token calculation code into utils module"
```

---

## 阶段4: P3配置和组织问题修复

### 任务9: 锁定依赖版本

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`

**Step 1: 分析当前依赖**

```bash
# 检查依赖版本
pip list --format=freeze > current_versions.txt
```

**Step 2: 锁定生产依赖版本**

```python
# requirements.txt 修改为具体版本
langchain==0.1.0
langchain-community==0.0.10
langchain-core==0.1.0
chromadb==0.4.22
langchain-chroma==0.1.0
sentence-transformers==2.2.2
huggingface-hub==0.20.0
pypdf==3.17.0
pdfplumber==0.10.0
python-docx==0.8.11
markdown==3.5.0
unstructured==0.10.30
ollama==0.1.0
openai==1.12.0
anthropic==0.25.0
fastapi==0.104.0
uvicorn[standard]==0.24.0
pydantic==2.5.0
streamlit==1.29.0
gradio==4.0.0
langchain-experimental==0.0.50
langgraph==0.0.20
pandas==2.0.0
numpy==1.24.0
tiktoken==0.5.0
python-dotenv==1.0.0
pyyaml==6.0.0
loguru==0.7.0
```

**Step 3: 创建开发依赖文件**

```python
# requirements-dev.txt
# 开发工具
pytest==7.4.0
black==23.0.0
ruff==0.1.0
mypy==1.7.0
bandit==1.7.5
safety==2.3.5

# 测试工具
pytest-cov==4.1.0
pytest-asyncio==0.21.0

# 文档工具
mkdocs==1.5.0
mkdocs-material==9.5.0
```

**Step 4: 更新安装说明**

```bash
# 更新README.md中的安装说明
echo "## 安装依赖" > README_installation.md
echo "" >> README_installation.md
echo "### 生产环境" >> README_installation.md
echo '```bash' >> README_installation.md
echo 'pip install -r requirements.txt' >> README_installation.md
echo '```' >> README_installation.md
echo "" >> README_installation.md
echo "### 开发环境" >> README_installation.md
echo '```bash' >> README_installation.md
echo 'pip install -r requirements.txt -r requirements-dev.txt' >> README_installation.md
echo '```' >> README_installation.md
```

**Step 5: 测试依赖安装**

```bash
# 创建虚拟环境测试
python -m venv test_venv
source test_venv/bin/activate  # Linux/Mac
# 或 test_venv\Scripts\activate  # Windows

pip install -r requirements.txt
python -c "import langchain; print(f'LangChain version: {langchain.__version__}')"

# 检查是否有依赖冲突
pip check
```

**Step 6: 提交更改**

```bash
git add requirements.txt
git add requirements-dev.txt
git add README_installation.md
git commit -m "chore: lock dependency versions and separate dev dependencies"
```

### 任务10: 修复文档与实现不符

**Files:**
- Modify: `README.md`
- Create: `src/api/routes.py`
- Create: `src/api/schemas.py`
- Create: `tests/` 目录结构

**Step 1: 创建缺失的API文件**

```python
# src/api/routes.py
"""
API路由模块
将main.py中的路由拆分到此文件
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
import logging

from .schemas import (
    QueryRequest, QueryResponse, 
    DocumentProcessRequest, DocumentProcessResponse,
    HealthResponse
)
from core.config import config
from core.document_processor import DocumentProcessor
from core.vector_store import SimpleVectorStore
from core.llm_manager import LLMManager

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1", tags=["api"])

# 依赖注入
def get_processor():
    return DocumentProcessor()

def get_vector_store():
    return SimpleVectorStore()

def get_llm_manager():
    return LLMManager()

@router.get("/health", response_model=HealthResponse)
async def health_check(
    llm_manager: LLMManager = Depends(get_llm_manager),
    vector_store: SimpleVectorStore = Depends(get_vector_store)
):
    """健康检查端点"""
    return HealthResponse(
        status="healthy",
        local_model_available=llm_manager.is_local_available(),
        api_available=llm_manager.is_api_available(),
        vector_store_ready=vector_store is not None,
        version="1.0.0"
    )

@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(
    request: QueryRequest,
    llm_manager: LLMManager = Depends(get_llm_manager),
    vector_store: SimpleVectorStore = Depends(get_vector_store)
):
    """查询知识库"""
    import time
    start_time = time.time()
    
    # ... 实现与main.py相同的逻辑
    
    return QueryResponse(
        answer=answer,
        sources=sources,
        provider=result.get("metadata", {}).get("provider", "unknown"),
        response_time=time.time() - start_time,
        tokens_used=result.get("tokens")
    )

# 其他路由...
```

**Step 2: 创建schemas模块**

```python
# src/api/schemas.py
"""
API数据模型（Pydantic schemas）
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any

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
    tokens_used: Optional[Dict[str, int]] = None

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

class SystemStats(BaseModel):
    llm_usage: Dict[str, Any]
    vector_store: Dict[str, Any]
    config: Dict[str, Any]

class AvailableModels(BaseModel):
    local_available: bool
    api_available: bool
    available_providers: List[str]
    local_model: str
```

**Step 3: 更新main.py使用新模块**

```python
# src/api/main.py 简化版本
"""
FastAPI 主应用 - 简化版
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os

from .routes import router as api_router

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="本地知识库系统 API",
    description="基于 LangChain + RAG + Agent 的本地知识库系统",
    version="1.0.0"
)

# CORS配置
cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
if cors_origins == [""]:
    cors_origins = [
        "http://localhost:8501",
        "http://localhost:3000", 
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

# 注册路由
app.include_router(api_router)

@app.get("/")
async def root():
    """根端点，返回 API 信息"""
    return {
        "name": "本地知识库系统 API",
        "version": "1.0.0",
        "description": "基于 LangChain + RAG + Agent 的本地知识库系统",
        "endpoints": {
            "health": "/api/v1/health",
            "query": "/api/v1/query (POST)",
            "upload": "/api/v1/documents/upload (POST)",
            "process": "/api/v1/documents/process (POST)",
            "stats": "/api/v1/stats (GET)",
            "models": "/api/v1/models/available (GET)",
        }
    }

# 启动函数
def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """启动 API 服务器"""
    logger.info(f"启动 API 服务器: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_api_server()
```

**Step 4: 创建tests目录结构**

```bash
mkdir -p tests/{core,api,agents,frontend}
touch tests/__init__.py
touch tests/core/__init__.py
touch tests/api/__init__.py
touch tests/agents/__init__.py
touch tests/frontend/__init__.py

# 创建conftest.py
cat > tests/conftest.py << 'EOF'
"""
测试配置和夹具
"""
import pytest
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

@pytest.fixture
def test_client():
    """测试客户端夹具"""
    from fastapi.testclient import TestClient
    from src.api.main import app
    
    with TestClient(app) as client:
        yield client
EOF
```

**Step 5: 更新README.md**

更新README.md中关于项目结构的部分，使其与实际一致。

**Step 6: 测试新结构**

```bash
# 测试API导入
python -c "from src.api.main import app; print('API导入成功')"

# 测试路由导入
python -c "from src.api.routes import router; print('路由导入成功')"

# 测试schemas导入
python -c "from src.api.schemas import QueryRequest; print('schemas导入成功')"
```

**Step 7: 提交更改**

```bash
git add src/api/routes.py
git add src/api/schemas.py
git add src/api/main.py
git add tests/
git add README.md
git commit -m "refactor: split API into modules and create tests directory as documented"
```

---

## 阶段5: Ollama安装与配置

### 任务11: 安装Ollama

**Files:**
- Check: `d:\code\LLM\OllamaSetup-v0.7.0.exe`
- Create: `scripts/install_ollama.ps1`

**Step 1: 检查安装文件**

```bash
# 检查安装文件
ls -la "d:/code/LLM/OllamaSetup-v0.7.0.exe"
```

**Step 2: 创建自动安装脚本**

```powershell
# scripts/install_ollama.ps1
Write-Host "Ollama 安装脚本" -ForegroundColor Green
Write-Host "=============================="

# 检查是否已安装
$ollamaInstalled = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaInstalled) {
    Write-Host "Ollama 已安装，版本信息:" -ForegroundColor Yellow
    ollama --version
    exit 0
}

# 检查安装文件
$installerPath = "D:\code\LLM\OllamaSetup-v0.7.0.exe"
if (-not (Test-Path $installerPath)) {
    Write-Host "错误: 安装文件不存在: $installerPath" -ForegroundColor Red
    Write-Host "请从 https://ollama.ai/download/windows 下载安装程序" -ForegroundColor Yellow
    exit 1
}

Write-Host "找到安装文件: $installerPath" -ForegroundColor Green
Write-Host "文件大小: $((Get-Item $installerPath).Length / 1MB) MB" -ForegroundColor Green

# 显示安装选项
Write-Host "`n安装选项:" -ForegroundColor Cyan
Write-Host "1. 静默安装（推荐）" -ForegroundColor White
Write-Host "2. 交互式安装" -ForegroundColor White
Write-Host "3. 仅下载不安装" -ForegroundColor White

$choice = Read-Host "`n请选择安装方式 (1-3, 默认: 1)"
if (-not $choice) { $choice = 1 }

switch ($choice) {
    1 {
        Write-Host "执行静默安装..." -ForegroundColor Green
        # 静默安装参数
        $installArgs = "/S"
        
        Write-Host "正在安装 Ollama..." -ForegroundColor Yellow
        Start-Process -Wait -FilePath $installerPath -ArgumentList $installArgs
        
        # 等待服务启动
        Write-Host "等待 Ollama 服务启动..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
        
        # 验证安装
        $ollamaCheck = Get-Command ollama -ErrorAction SilentlyContinue
        if ($ollamaCheck) {
            Write-Host "Ollama 安装成功!" -ForegroundColor Green
            ollama --version
        } else {
            Write-Host "Ollama 安装可能失败，请检查" -ForegroundColor Red
        }
    }
    2 {
        Write-Host "启动交互式安装界面..." -ForegroundColor Green
        Start-Process -Wait -FilePath $installerPath
    }
    3 {
        Write-Host "跳过安装，仅显示下载信息" -ForegroundColor Yellow
        Write-Host "安装文件已准备就绪: $installerPath" -ForegroundColor White
        Write-Host "请手动运行安装程序" -ForegroundColor White
    }
}

# 安装后配置
Write-Host "`n安装后配置建议:" -ForegroundColor Cyan
Write-Host "1. 设置环境变量（如果需要）" -ForegroundColor White
Write-Host "2. 配置模型存储路径" -ForegroundColor White
Write-Host "3. 拉取所需模型" -ForegroundColor White

$configure = Read-Host "`n是否立即配置模型? (y/n, 默认: n)"
if ($configure -eq 'y') {
    Write-Host "拉取 DeepSeek-V2-Lite 模型..." -ForegroundColor Yellow
    ollama pull deepseek-v2-lite:16b-q4_K_M
    
    Write-Host "拉取 BGE-M3 嵌入模型..." -ForegroundColor Yellow
    ollama pull bge-m3
    
    Write-Host "可用模型列表:" -ForegroundColor Green
    ollama list
}

Write-Host "`n安装完成!" -ForegroundColor Green
```

**Step 3: 创建安装文档**

```markdown
# docs/installation/ollama-setup.md
# Ollama 安装指南

## 系统要求
- **操作系统**: Windows 10/11 64位
- **内存**: 至少 8GB RAM（推荐 16GB+）
- **存储**: 至少 10GB 可用空间（用于模型存储）
- **网络**: 稳定的互联网连接（下载模型需要）

## 安装步骤

### 方法1: 自动安装（推荐）
```powershell
# 在项目根目录运行
.\scripts\install_ollama.ps1
```

### 方法2: 手动安装
1. 下载安装程序: [Ollama Windows Installer](https://ollama.ai/download/windows)
2. 运行 `OllamaSetup-v0.7.0.exe`
3. 按照安装向导完成安装
4. 验证安装: `ollama --version`

### 方法3: 静默安装（适用于批量部署）
```powershell
# 以管理员身份运行
D:\code\LLM\OllamaSetup-v0.7.0.exe /S
```

## 配置模型

### 拉取所需模型
```bash
# 核心LLM模型（约3-4GB）
ollama pull deepseek-v2-lite:16b-q4_K_M

# 嵌入模型（约1-2GB）
ollama pull bge-m3

# 备选模型（可选）
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull nomic-embed-text
```

### 模型存储位置
- 默认位置: `C:\Users\<用户名>\.ollama`
- 修改位置: 设置环境变量 `OLLAMA_MODELS`

## 验证安装

运行以下命令验证安装：
```bash
# 检查版本
ollama --version

# 检查服务状态
ollama serve

# 列出已安装模型
ollama list

# 运行测试
ollama run deepseek-v2-lite:16b-q4_K_M "Hello, world!"
```

## 故障排除

### 常见问题
1. **安装失败**: 确保有管理员权限，关闭杀毒软件
2. **模型下载慢**: 使用镜像源或代理
3. **内存不足**: 选择更小的模型或增加虚拟内存
4. **服务无法启动**: 检查端口11434是否被占用

### 日志文件
- 安装日志: `%TEMP%\OllamaInstall.log`
- 服务日志: `%USERPROFILE%\.ollama\logs\server.log`

## 下一步
安装完成后，继续配置本地知识库系统：
1. 配置环境变量 (`.env` 文件)
2. 安装Python依赖 (`pip install -r requirements.txt`)
3. 启动API服务 (`python src/api/main.py`)
4. 启动前端 (`streamlit run src/frontend/app.py`)
```

**Step 4: 运行安装脚本（可选）**

```powershell
# 如果需要自动安装
powershell -ExecutionPolicy Bypass -File scripts/install_ollama.ps1
```

**Step 5: 更新项目文档**

在README.md中添加Ollama安装章节。

**Step 6: 提交更改**

```bash
git add scripts/install_ollama.ps1
git add docs/installation/ollama-setup.md
git add README.md
git commit -m "docs: add Ollama installation guide and automation script"
```

---

## 阶段6: 清理无用文件

### 任务12: 清理备份和无用文件

**Files:**
- Review: `src/core/vector_store_backup.py`
- Review: 其他备份文件
- Clean: 临时文件和缓存

**Step 1: 评估备份文件**

```python
# 检查vector_store_backup.py的内容
# 如果功能已合并到vector_store.py中，可以删除
# 如果有独特功能，考虑重命名或移动到utils
```

**Step 2: 清理决策**

根据检查结果决定：
1. **删除**: 如果功能已完全迁移
2. **重命名**: 如果是有用的备份（如 `vector_store_legacy.py`）
3. **移动**: 如果有用但位置不对

**Step 3: 执行清理**

```bash
# 备份重要文件（如果需要）
cp src/core/vector_store_backup.py src/core/vector_store_backup.py.backup

# 检查文件差异
diff -u src/core/vector_store.py src/core/vector_store_backup.py | head -50

# 如果确定删除
rm src/core/vector_store_backup.py

# 清理其他无用文件
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name ".ruff_cache" -type d -exec rm -rf {} +
```

**Step 4: 更新.gitignore**

确保.gitignore包含常见临时文件：

```bash
# 在.gitignore中添加
*.pyc
__pycache__/
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/
*.log
*.tmp
*.temp
```

**Step 5: 验证清理后功能**

```bash
# 运行基本测试
python scripts/test_rag.py

# 检查导入
python -c "from src.core.vector_store import SimpleVectorStore; print('导入成功')"
```

**Step 6: 提交更改**

```bash
git add .gitignore
git rm src/core/vector_store_backup.py  # 如果删除
git commit -m "chore: clean up backup files and temporary files"
```

---

## 执行计划总结

### 已完成任务
- [ ] 任务1: 清理泄露的API密钥
- [ ] 任务2: 修复eval()代码执行风险  
- [ ] 任务3: 修复CORS配置
- [ ] 任务4: 移除硬编码绝对路径
- [ ] 任务5: 修复路径遍历风险
- [ ] 任务6: 修复空except块
- [ ] 任务7: 添加文件上传限制
- [ ] 任务8: 提取重复代码
- [ ] 任务9: 锁定依赖版本
- [ ] 任务10: 修复文档与实现不符
- [ ] 任务11: 安装Ollama
- [ ] 任务12: 清理无用文件

### 执行选项

**计划完成并保存到 `docs/plans/2025-03-03-security-and-code-fixes.md`。两个执行选项：**

**1. 子代理驱动（本会话）** - 我分派新子代理执行每个任务，任务间进行代码审查，快速迭代

**2. 并行会话（单独）** - 在新会话中使用executing-plans打开，批量执行检查点

**哪种方法？**

**如果选择子代理驱动：**
- **必需子技能**: 使用 superpowers:subagent-driven-development
- 保持在本会话中
- 每个任务使用新子代理 + 代码审查

**如果选择并行会话：**
- 指导在工作树中打开新会话
- **必需子技能**: 新会话使用 superpowers:executing-plans