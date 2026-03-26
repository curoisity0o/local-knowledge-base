"""
Agent 基础模块
提供Agent系统的核心抽象
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """Agent状态"""

    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    RESPONDING = "responding"
    ERROR = "error"


@dataclass
class AgentConfig:
    """Agent配置"""

    name: str = "agent"
    description: str = ""
    max_iterations: int = 10
    timeout: int = 300  # 秒
    verbose: bool = True
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""


@dataclass
class AgentMessage:
    """Agent消息"""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


class BaseAgent(ABC):
    """Agent基类"""

    def __init__(self, config: Optional[AgentConfig] = None, llm_manager=None):
        self.config = config or AgentConfig()
        self.llm_manager = llm_manager
        self.state = AgentState.IDLE
        self.messages: List[AgentMessage] = []
        self.tools: Dict[str, Callable] = {}
        self._iteration_count = 0

    @abstractmethod
    def process(self, input_data: Any) -> Dict[str, Any]:
        """处理输入，返回结果"""
        raise NotImplementedError("子类必须实现 process() 方法")

    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        tool_call_id: Optional[str] = None,
    ) -> None:
        """添加消息到历史"""
        self.messages.append(
            AgentMessage(
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
            )
        )

    def clear_history(self) -> None:
        """清空消息历史"""
        self.messages = []
        self._iteration_count = 0

    def register_tool(self, name: str, func: Callable, description: str = "") -> None:
        """注册工具"""
        self.tools[name] = func
        if self.config.verbose:
            logger.info(f"注册工具: {name}")

    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """调用工具"""
        if tool_name not in self.tools:
            raise ValueError(f"未知工具: {tool_name}")

        try:
            if self.config.verbose:
                logger.info(f"调用工具: {tool_name}")
            result = self.tools[tool_name](**kwargs)
            return result
        except Exception as e:
            logger.error(f"工具调用失败: {tool_name}, 错误: {e}")
            return {"error": str(e)}

    def set_state(self, state: AgentState) -> None:
        """设置状态"""
        self.state = state
        if self.config.verbose:
            logger.debug(f"Agent状态: {state}")

    def check_iteration_limit(self) -> bool:
        """检查是否超过迭代限制"""
        self._iteration_count += 1
        if self._iteration_count > self.config.max_iterations:
            logger.warning(f"达到最大迭代次数: {self.config.max_iterations}")
            return True
        return False

    def reset(self) -> None:
        """重置Agent"""
        self.state = AgentState.IDLE
        self.messages = []
        self._iteration_count = 0
