"""
Agent 工具定义
定义Agent可用的各种工具
"""

import ast
import logging
import operator
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        func: Callable,
        description: str = "",
        parameters: Optional[Dict] = None,
    ) -> None:
        """注册工具"""
        self.tools[name] = {
            "function": func,
            "description": description,
            "parameters": parameters or {},
        }
        logger.debug(f"注册工具: {name}")

    def get_tool(self, name: str) -> Optional[Callable]:
        """获取工具函数"""
        tool = self.tools.get(name)
        return tool["function"] if tool else None

    def get_tools_schema(self) -> List[Dict]:
        """获取工具的JSON Schema格式"""
        schema = []
        for name, tool in self.tools.items():
            param_props = {}
            for param_name, param_info in (
                tool["parameters"].get("properties", {}).items()
            ):
                param_props[param_name] = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                }

            schema.append(
                {
                    "name": name,
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": param_props,
                        "required": tool["parameters"].get("required", []),
                    },
                }
            )
        return schema

    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self.tools.keys())


# ==================== 预定义工具 ====================


def create_search_tool(vector_store) -> Callable:
    """创建文档搜索工具"""

    def search(query: str, k: int = 4) -> str:
        """
        在知识库中搜索相关文档

        参数:
            query: 搜索查询
            k: 返回结果数量
        """
        try:
            results = vector_store.similarity_search(query, k=k)
            if not results:
                return "未找到相关文档"

            # 格式化结果
            formatted = []
            for i, doc in enumerate(results, 1):
                source = doc.metadata.get("source", "未知来源")
                content_preview = (
                    doc.page_content[:200] + "..."
                    if len(doc.page_content) > 200
                    else doc.page_content
                )
                formatted.append(f"【文档{i}】来源: {source}\n内容: {content_preview}")

            return "\n\n".join(formatted)
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return f"搜索失败: {str(e)}"

    return search


def create_retrieve_documents_tool(vector_store) -> Callable:
    """创建文档检索工具（带相似度分数）"""

    def retrieve(query: str, k: int = 4, threshold: float = 0.0) -> str:
        """
        检索相关文档并返回相似度分数

        参数:
            query: 搜索查询
            k: 返回结果数量
            threshold: 相似度阈值
        """
        try:
            results = vector_store.similarity_search_with_score(query, k=k)

            if not results:
                return "未找到相关文档"

            formatted = []
            for i, (doc, score) in enumerate(results, 1):
                # 分数越低越相似
                if threshold > 0 and score > threshold:
                    continue
                source = doc.metadata.get("source", "未知来源")
                content_preview = (
                    doc.page_content[:300] + "..."
                    if len(doc.page_content) > 300
                    else doc.page_content
                )
                formatted.append(
                    f"【文档{i}】相似度: {1 - score:.4f}\n来源: {source}\n内容: {content_preview}"
                )

            if not formatted:
                return f"没有找到高于阈值 {threshold} 的相关文档"

            return "\n\n".join(formatted)
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return f"检索失败: {str(e)}"

    return retrieve


def create_list_documents_tool(vector_store) -> Callable:
    """创建列出文档工具"""

    def list_docs() -> str:
        """列出知识库中的所有文档"""
        try:
            info = vector_store.get_collection_info()
            count = info.get("document_count", 0)
            model = info.get("embedding_model", "unknown")

            return f"知识库状态:\n- 文档数量: {count}\n- 嵌入模型: {model}"
        except Exception as e:
            logger.error(f"获取文档列表失败: {e}")
            return f"获取失败: {str(e)}"

    return list_docs


def create_file_reader_tool(base_path: str = "./data") -> Callable:
    """创建文件读取工具"""

    def read_file(file_path: str, max_lines: int = 100) -> str:
        """
        读取文件内容

        参数:
            file_path: 相对于base_path的文件路径
            max_lines: 最大读取行数
        """
        try:
            # 使用safe_join防止路径遍历攻击
            full_path = safe_join(base_path, file_path)
            if not full_path.exists():
                return f"文件不存在: {file_path}"

            with open(full_path, "r", encoding="utf-8") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"... (共超过{max_lines}行)")
                        break
                    lines.append(line.rstrip())

            return "\n".join(lines)
        except ValueError as e:
            logger.warning(f"路径安全检查失败: {e}")
            return f"路径访问被拒绝: {str(e)}"
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            return f"读取失败: {str(e)}"

    return read_file


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
        tree = ast.parse(expression, mode="eval")

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
        code = compile(tree, "<string>", "eval")
        return eval(code, {"__builtins__": {}}, allowed_names)

    except SyntaxError as e:
        raise ValueError(f"表达式语法错误: {e}")
    except Exception as e:
        raise ValueError(f"表达式求值失败: {e}")


def create_calculator_tool() -> Callable:
    """创建计算器工具"""

    def calculate(expression: str) -> str:
        """
        执行数学计算

        参数:
            expression: 数学表达式 (如 "2+2", "sqrt(16)")
        """
        try:
            # 安全的数学表达式求值
            allowed_names = {
                "pi": 3.141592653589793,
                "e": 2.718281828459045,
            }

            # 替换常见数学函数
            expression = expression.replace("^", "**")
            expression = expression.replace("sqrt", "**0.5")

            result = safe_eval(expression, allowed_names)
            return f"结果: {result}"
        except Exception as e:
            return f"计算错误: {str(e)}"

    return calculate


def create_summary_tool() -> Callable:
    """创建文本摘要工具（简单版本）"""

    def summarize(text: str, max_length: int = 200) -> str:
        """
        生成文本摘要

        参数:
            text: 要摘要的文本
            max_length: 摘要最大长度
        """
        # 简单实现：取前N个字符
        if len(text) <= max_length:
            return text

        # 尝试在句号处截断
        truncated = text[:max_length]
        last_period = truncated.rfind("。")
        last_newline = truncated.rfind("\n")

        cut_point = max(last_period, last_newline)
        if cut_point > max_length * 0.7:  # 至少70%长度
            return text[: cut_point + 1]

        return truncated + "..."

    return summarize


def get_default_tools(vector_store=None, base_path: str = "./data") -> ToolRegistry:
    """获取默认工具注册表"""
    registry = ToolRegistry()

    # 文档搜索工具
    if vector_store:
        registry.register(
            "search_knowledge",
            create_search_tool(vector_store),
            description="在知识库中搜索相关文档",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "k": {"type": "integer", "description": "返回结果数量，默认4"},
                },
                "required": ["query"],
            },
        )

        registry.register(
            "retrieve_documents",
            create_retrieve_documents_tool(vector_store),
            description="检索相关文档并返回相似度分数",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "k": {"type": "integer", "description": "返回结果数量，默认4"},
                    "threshold": {"type": "number", "description": "相似度阈值"},
                },
                "required": ["query"],
            },
        )

        registry.register(
            "list_documents",
            create_list_documents_tool(vector_store),
            description="列出知识库中的所有文档和状态",
            parameters={"type": "object", "properties": {}},
        )

    # 文件工具
    registry.register(
        "read_file",
        create_file_reader_tool(base_path),
        description="读取指定路径的文件内容",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"},
                "max_lines": {"type": "integer", "description": "最大行数，默认100"},
            },
            "required": ["file_path"],
        },
    )

    # 计算工具
    registry.register(
        "calculate",
        create_calculator_tool(),
        description="执行数学计算",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式"}
            },
            "required": ["expression"],
        },
    )

    # 摘要工具
    registry.register(
        "summarize",
        create_summary_tool(),
        description="生成文本摘要",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要摘要的文本"},
                "max_length": {
                    "type": "integer",
                    "description": "摘要最大长度，默认200",
                },
            },
            "required": ["text"],
        },
    )

    return registry
