"""
查询分类器
用 LLM 统一判断问题复杂度，决定走 RAGChain（简单）还是 Agent（复杂）。
"""

import logging
import re
from typing import Optional

from ..core.config import get_config

logger = logging.getLogger(__name__)

# 分类结果常量
SIMPLE = "simple"
COMPLEX = "complex"

# 分类 prompt 模板
_CLASSIFY_PROMPT = """判断以下问题的复杂度，只输出 simple 或 complex。

simple = 单一事实查询，一次检索即可回答（如"什么是RAG"、"怎么安装Ollama"）
complex = 需要对比、多步推理、综合多个文档、或一句话包含多个问题

问题：{query}

分类："""


class QueryClassifier:
    """查询复杂度分类器"""

    def __init__(self, llm_manager=None):
        self._llm_manager = llm_manager
        self._fallback = get_config("agent.classifier.fallback", SIMPLE)

    @property
    def llm_manager(self):
        return self._llm_manager

    @llm_manager.setter
    def llm_manager(self, value):
        self._llm_manager = value

    def classify(self, query: str) -> str:
        """判断查询复杂度，返回 SIMPLE 或 COMPLEX。

        LLM 调用失败时 fallback 到配置的默认值。
        """
        if not self._llm_manager:
            logger.debug("LLM 未初始化，使用 fallback: %s", self._fallback)
            return self._fallback

        if not query or not query.strip():
            return SIMPLE

        try:
            prompt = _CLASSIFY_PROMPT.format(query=query.strip())
            result = self._llm_manager.generate(prompt)
            text = result.get("text", "").strip().lower()

            # 提取标签
            if "complex" in text:
                label = COMPLEX
            elif "simple" in text:
                label = SIMPLE
            else:
                # LLM 输出无法解析，fallback
                label = self._fallback

            logger.info("查询分类: '%s...' → %s", query[:30], label)
            return label

        except Exception as e:
            logger.warning("查询分类失败，使用 fallback: %s (错误: %s)", self._fallback, e)
            return self._fallback
