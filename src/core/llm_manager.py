"""
双模式 LLM 管理器
负责管理本地模型和云 API 的智能切换
"""

import os
import time
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

from langchain_community.llms import Ollama
from langchain_openai import ChatOpenAI

# Anthropic 是可选的
try:
    from langchain_anthropic import ChatAnthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    ChatAnthropic = None

from .config import get_config

logger = logging.getLogger(__name__)


class LLMManager:
    """双模式 LLM 管理器"""

    def __init__(self, config=None):
        self.config = config or {}
        self.llm_config = get_config("llm", {})

        # 初始化本地模型
        self.local_llm = None
        self.local_provider = None

        # 初始化 API 客户端
        self.api_clients = {}
        self.api_enabled = False

        # 成本控制
        self.cost_controller = CostController()

        # 使用统计
        self.usage_stats = {
            "local": {"calls": 0, "tokens": 0, "errors": 0},
            "api": {"calls": 0, "tokens": 0, "errors": 0, "cost": 0.0},
        }

        # 初始化模型
        self._init_local_llm()
        self._init_api_clients()

    def _init_local_llm(self) -> None:
        """初始化本地模型"""
        try:
            # 使用get_config直接获取配置值（支持环境变量替换）
            provider = get_config("llm.local.provider", "ollama")
            self.local_provider = provider

            # 检查本地ModelScope模型路径
            modelscope_model_path = (
                "D:/code/LLM/model_cache/deepseek-ai/DeepSeek-V2-Lite"
            )
            use_modelscope = os.path.exists(modelscope_model_path)

            if provider == "ollama":
                # 尝试使用Ollama
                try:
                    # 移除streaming参数，因为它在新版本中不支持
                    self.local_llm = Ollama(
                        base_url=get_config(
                            "llm.local.ollama.base_url", "http://localhost:11434"
                        ),
                        model=get_config(
                            "llm.local.ollama.model", "deepseek-v2-lite:16b-q4_K_M"
                        ),
                        temperature=get_config("llm.local.ollama.temperature", 0.1),
                        num_predict=get_config("llm.local.ollama.num_predict", 1024),
                    )
                    logger.info(
                        f"初始化本地 Ollama 模型: {get_config('llm.local.ollama.model', 'deepseek-v2-lite:16b-q4_K_M')}"
                    )
                except Exception as e:
                    logger.warning(f"Ollama连接失败: {e}")
                    # 回退到transformers
                    provider = "transformers"

            if provider == "transformers":
                # 使用Transformers加载本地模型
                try:
                    from langchain_community.llms import HuggingFaceHub

                    if use_modelscope:
                        # 使用ModelScope下载的模型
                        self.local_llm = HuggingFaceHub(
                            repo_id="deepseek-ai/DeepSeek-V2-Lite",
                            model_kwargs={
                                "temperature": get_config("llm.local.temperature", 0.1),
                                "max_new_tokens": get_config(
                                    "llm.local.max_tokens", 1024
                                ),
                            },
                            huggingfacehub_cache_folder=modelscope_model_path,
                        )
                        logger.info(f"使用ModelScope本地模型: {modelscope_model_path}")
                    else:
                        # 使用HuggingFace Hub
                        self.local_llm = HuggingFaceHub(
                            repo_id="deepseek-ai/DeepSeek-V2-Lite",
                            model_kwargs={
                                "temperature": get_config("llm.local.temperature", 0.1),
                                "max_new_tokens": get_config(
                                    "llm.local.max_tokens", 1024
                                ),
                            },
                        )
                        logger.info(
                            "使用HuggingFace Hub模型: deepseek-ai/DeepSeek-V2-Lite"
                        )

                except ImportError:
                    logger.warning("HuggingFaceHub不可用，尝试使用Transformers直接加载")
                    try:
                        from langchain_community.llms import HuggingFacePipeline
                        from transformers import (
                            AutoModelForCausalLM,
                            AutoTokenizer,
                            pipeline,
                        )

                        tokenizer = AutoTokenizer.from_pretrained(
                            modelscope_model_path
                            if use_modelscope
                            else "deepseek-ai/DeepSeek-V2-Lite",
                            trust_remote_code=True,
                        )
                        model = AutoModelForCausalLM.from_pretrained(
                            modelscope_model_path
                            if use_modelscope
                            else "deepseek-ai/DeepSeek-V2-Lite",
                            trust_remote_code=True,
                            device_map="auto",
                        )
                        pipe = pipeline(
                            "text-generation",
                            model=model,
                            tokenizer=tokenizer,
                            max_new_tokens=1024,
                            temperature=0.1,
                        )
                        self.local_llm = HuggingFacePipeline(pipeline=pipe)
                        logger.info("使用Transformers本地模型加载成功")
                    except Exception as te:
                        logger.warning(f"Transformers加载失败: {te}")
                        self.local_llm = None

            elif provider == "vllm":
                # TODO: 实现 vLLM 集成
                logger.warning("vLLM 集成尚未实现")
                self.local_llm = None

            else:
                logger.error(f"不支持的本地模型提供商: {provider}")
                self.local_llm = None

        except Exception as e:
            logger.error(f"初始化本地模型失败: {e}")
            self.local_llm = None

    def _init_api_clients(self) -> None:
        """初始化 API 客户端"""
        try:
            api_config = self.llm_config.get("api", {})
            self.api_enabled = api_config.get("enabled", True)

            if not self.api_enabled:
                logger.info("API 模式已禁用")
                return

            # OpenAI
            openai_config = api_config.get("openai", {})
            openai_api_key = os.getenv("OPENAI_API_KEY") or openai_config.get("api_key")

            if openai_api_key:
                self.api_clients["openai"] = ChatOpenAI(
                    api_key=openai_api_key,
                    model=openai_config.get("model", "gpt-4o-mini"),
                    temperature=openai_config.get("temperature", 0.1),
                    max_tokens=openai_config.get("max_tokens", 2000),  # type: ignore
                    streaming=True,
                )
                logger.info(f"初始化 OpenAI 客户端: {openai_config.get('model')}")

            # Anthropic (可选)
            if ANTHROPIC_AVAILABLE and ChatAnthropic is not None:
                anthropic_config = api_config.get("anthropic", {})
                anthropic_api_key = os.getenv(
                    "ANTHROPIC_API_KEY"
                ) or anthropic_config.get("api_key")

                if anthropic_api_key:
                    try:
                        # 尝试不同的参数名
                        anthropic_kwargs = {
                            "api_key": anthropic_api_key,
                            "model": anthropic_config.get(
                                "model", "claude-3-haiku-20240307"
                            ),
                            "temperature": anthropic_config.get("temperature", 0.1),
                        }

                        # 尝试不同的token限制参数
                        max_tokens = anthropic_config.get("max_tokens", 2000)
                        if (
                            "max_tokens_to_sample"
                            in ChatAnthropic.__init__.__annotations__
                        ):
                            anthropic_kwargs["max_tokens_to_sample"] = max_tokens
                        else:
                            anthropic_kwargs["max_tokens"] = max_tokens

                        self.api_clients["anthropic"] = ChatAnthropic(
                            **anthropic_kwargs
                        )
                        logger.info(
                            f"初始化 Anthropic 客户端: {anthropic_config.get('model')}"
                        )
                    except Exception as e:
                        logger.warning(f"初始化 Anthropic 客户端失败: {e}")

            # DeepSeek API (使用 OpenAI 兼容接口)
            deepseek_config = api_config.get("deepseek", {})
            deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or deepseek_config.get(
                "api_key"
            )

            if deepseek_api_key:
                self.api_clients["deepseek"] = ChatOpenAI(
                    api_key=deepseek_api_key,
                    base_url=deepseek_config.get(
                        "base_url", "https://api.deepseek.com"
                    ),
                    model=deepseek_config.get("model", "deepseek-chat"),
                    temperature=deepseek_config.get("temperature", 0.1),
                    max_tokens=deepseek_config.get("max_tokens", 2000),  # type: ignore
                )
                logger.info(f"初始化 DeepSeek 客户端: {deepseek_config.get('model')}")

            # Kimi API (Moonshot AI, 使用 OpenAI 兼容接口)
            kimi_config = api_config.get("kimi", {})
            kimi_api_key = os.getenv("KIMI_API_KEY") or kimi_config.get("api_key")

            if kimi_api_key:
                self.api_clients["kimi"] = ChatOpenAI(
                    api_key=kimi_api_key,
                    base_url=kimi_config.get("base_url", "https://api.moonshot.cn/v1"),
                    model=kimi_config.get("model", "moonshot-v1-8k-vision-preview"),
                    temperature=kimi_config.get("temperature", 0.1),
                    max_tokens=kimi_config.get("max_tokens", 2000),
                )
                logger.info(f"初始化 Kimi 客户端: {kimi_config.get('model')}")

            if self.api_clients:
                logger.info(f"API 客户端初始化完成: {list(self.api_clients.keys())}")
            else:
                logger.warning("未找到可用的 API 密钥，API 模式将不可用")

        except Exception as e:
            logger.error(f"初始化 API 客户端失败: {e}")

    def analyze_query(
        self, query: str, context: Optional[str] = None
    ) -> Dict[str, Any]:
        """分析查询特征"""
        features = {
            "length": len(query),
            "requires_realtime_info": False,
            "complexity": 0.0,
            "sensitivity": "low",
            "context_length": len(context) if context else 0,
            "language": self._detect_language(query),
        }

        # 检查是否需要实时信息
        realtime_keywords = [
            "今天",
            "现在",
            "最新",
            "最近",
            "current",
            "latest",
            "recent",
        ]
        if any(keyword in query.lower() for keyword in realtime_keywords):
            features["requires_realtime_info"] = True

        # 评估复杂度（简单启发式）
        # 长查询、多个问题、技术术语等
        complexity = 0.0
        if len(query) > 100:
            complexity += 0.3
        if "?" in query and query.count("?") > 1:
            complexity += 0.2
        if any(
            term in query.lower()
            for term in ["如何", "怎样", "为什么", "how", "why", "what"]
        ):
            complexity += 0.2
        if any(
            term in query.lower()
            for term in ["解释", "分析", "比较", "explain", "analyze", "compare"]
        ):
            complexity += 0.3

        features["complexity"] = min(complexity, 1.0)

        # 检查隐私敏感性
        sensitive_keywords = [
            "密码",
            "密钥",
            "隐私",
            "机密",
            "password",
            "secret",
            "private",
        ]
        if any(keyword in query.lower() for keyword in sensitive_keywords):
            features["sensitivity"] = "high"

        logger.debug(f"查询分析结果: {features}")
        return features

    def _detect_language(self, text: str) -> str:
        """检测文本语言（简化版）"""
        # 简单启发式：检查中文字符
        chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
        if chinese_chars / max(len(text), 1) > 0.3:
            return "zh"
        return "en"

    def select_provider(
        self, query_features: Dict[str, Any], user_preference: Optional[str] = None
    ) -> str:
        """选择 LLM 提供商"""
        # 1. 用户偏好优先
        if user_preference:
            if user_preference == "local" and self.local_llm:
                return "local"
            elif user_preference == "api" and self.api_clients:
                return "api"

        # 2. 应用路由规则
        routing_rules = self.llm_config.get("routing", {}).get("rules", [])

        for rule in routing_rules:
            condition = rule.get("condition", "")
            action = rule.get("action", "")

            if self._evaluate_condition(condition, query_features):
                logger.debug(f"路由规则匹配: {condition} -> {action}")

                if action == "use_api" and self.api_clients:
                    return "api"
                elif action == "use_local" and self.local_llm:
                    return "local"

        # 3. 成本控制
        if self.cost_controller.should_use_local():
            logger.info("成本控制：使用本地模型")
            if self.local_llm:
                return "local"

        # 4. 默认策略
        default_mode = self.llm_config.get("default_mode", "auto")

        if default_mode == "local_only":
            return "local" if self.local_llm else "api"
        elif default_mode == "api_only":
            return "api" if self.api_clients else "local"
        elif default_mode == "local_first":
            return "local" if self.local_llm else "api"
        else:  # auto
            # 自动选择：根据查询特征
            if query_features["requires_realtime_info"]:
                return "api" if self.api_clients else "local"
            elif query_features["complexity"] > 0.8:
                return "api" if self.api_clients else "local"
            elif query_features["sensitivity"] == "high":
                return "local" if self.local_llm else "api"
            else:
                return "local" if self.local_llm else "api"

    def _evaluate_condition(self, condition: str, features: Dict[str, Any]) -> bool:
        """评估路由条件"""
        try:
            # 简单条件评估
            if "requires_realtime_info" in condition:
                return features["requires_realtime_info"]
            elif "complexity" in condition:
                threshold = float(condition.split(">")[1].strip())
                return features["complexity"] > threshold
            elif "context_length" in condition:
                threshold = int(condition.split(">")[1].strip())
                return features["context_length"] > threshold
            elif "sensitivity" in condition:
                target = condition.split("==")[1].strip().strip("'")
                return features["sensitivity"] == target
            return False
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        context: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """生成回答"""
        start_time = time.time()

        try:
            # 分析查询
            query_features = self.analyze_query(prompt, context)

            # 选择提供商
            if provider is None:
                provider = self.select_provider(query_features)

            # 生成回答
            if provider == "local" and self.local_llm:
                logger.info(f"使用本地模型生成: {prompt[:50]}...")
                result = self._generate_local(prompt, **kwargs)
                self.usage_stats["local"]["calls"] += 1

            elif provider in self.api_clients:
                logger.info(f"使用 API 模型生成 ({provider}): {prompt[:50]}...")
                result = self._generate_api(provider, prompt, **kwargs)
                self.usage_stats["api"]["calls"] += 1

                # 记录成本
                if "tokens" in result:
                    cost = self.cost_controller.estimate_cost(
                        provider, result["tokens"]["input"], result["tokens"]["output"]
                    )
                    self.usage_stats["api"]["cost"] += cost
                    self.cost_controller.record_usage(provider, result["tokens"], cost)

            else:
                # 后备：尝试其他提供商
                logger.warning(f"提供商 {provider} 不可用，尝试其他提供商")
                result = self._fallback_generate(prompt, **kwargs)

            # 添加元数据
            result["metadata"] = {
                "provider": provider,
                "query_features": query_features,
                "response_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
            }

            return result

        except Exception as e:
            logger.error(f"生成回答失败: {e}")
            # 确保provider不为None
            stats_provider = provider if provider else "unknown"
            if stats_provider in self.usage_stats:
                self.usage_stats[stats_provider]["errors"] += 1
            else:
                self.usage_stats["api"]["errors"] += 1  # 默认记录到api

            # 尝试后备生成
            try:
                result = self._fallback_generate(prompt, **kwargs)
                result["metadata"]["error"] = str(e)
                return result
            except Exception:
                return {
                    "text": f"抱歉，生成回答时发生错误: {str(e)}",
                    "tokens": {"input": 0, "output": 0},
                    "metadata": {
                        "provider": provider,
                        "error": str(e),
                        "response_time": time.time() - start_time,
                    },
                }

    def _generate_local(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """使用本地模型生成"""
        if self.local_llm is None:
            raise RuntimeError("本地模型未初始化")

        try:
            response = self.local_llm.invoke(prompt, **kwargs)

            # 简单 token 计数（近似）
            input_tokens = len(prompt) // 4  # 近似值
            output_tokens = len(response) // 4

            return {
                "text": response,
                "tokens": {"input": input_tokens, "output": output_tokens},
                "streaming": kwargs.get("streaming", False),
            }

        except Exception as e:
            logger.error(f"本地模型生成失败: {e}")
            raise

    def _generate_api(self, provider: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """使用 API 生成"""
        try:
            client = self.api_clients[provider]

            # 调用 API
            if kwargs.get("streaming", False):
                # 流式响应
                response = ""
                for chunk in client.stream(prompt, **kwargs):
                    if hasattr(chunk, "content"):
                        response += chunk.content
                    else:
                        response += str(chunk)

                # 流式模式下使用近似 token 计数
                input_tokens = len(prompt) // 4  # 近似值
                output_tokens = len(response) // 4
            else:
                response_obj = client.invoke(prompt, **kwargs)
                response = (
                    response_obj.content
                    if hasattr(response_obj, "content")
                    else str(response_obj)
                )

                # 获取 token 使用情况
                input_tokens = len(prompt) // 4  # 近似值
                output_tokens = len(response) // 4

                # 尝试从响应中获取实际 token 计数
                if hasattr(response_obj, "usage"):
                    input_tokens = response_obj.usage.prompt_tokens
                    output_tokens = response_obj.usage.completion_tokens

            return {
                "text": response,
                "tokens": {"input": input_tokens, "output": output_tokens},
                "streaming": kwargs.get("streaming", False),
            }

        except Exception as e:
            logger.error(f"API 生成失败 ({provider}): {e}")
            raise

    def _fallback_generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """后备生成：尝试所有可用提供商"""
        providers_to_try = []

        if self.local_llm:
            providers_to_try.append(("local", self._generate_local))

        for provider_name in self.api_clients:
            providers_to_try.append(
                (
                    provider_name,
                    lambda p, pr=provider_name: self._generate_api(pr, p, **kwargs),
                )
            )

        # 按优先级尝试
        for provider_name, generate_func in providers_to_try:
            try:
                logger.info(f"尝试后备提供商: {provider_name}")
                return generate_func(prompt)
            except Exception as e:
                logger.warning(f"后备提供商 {provider_name} 失败: {e}")
                continue

        # 所有都失败
        raise Exception("所有 LLM 提供商都失败")

    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return {
            "local": self.usage_stats["local"],
            "api": self.usage_stats["api"],
            "total_calls": self.usage_stats["local"]["calls"]
            + self.usage_stats["api"]["calls"],
            "total_cost": self.usage_stats["api"]["cost"],
            "local_model": self.llm_config.get("local", {})
            .get("ollama", {})
            .get("model"),
            "api_providers": list(self.api_clients.keys()),
        }

    def is_local_available(self) -> bool:
        """检查本地模型是否可用"""
        return self.local_llm is not None

    def is_api_available(self) -> bool:
        """检查 API 是否可用"""
        return len(self.api_clients) > 0

    def get_available_providers(self) -> List[str]:
        """获取可用的提供商列表"""
        providers = []
        if self.local_llm:
            providers.append("local")
        providers.extend(self.api_clients.keys())
        return providers


class CostController:
    """API 成本控制器"""

    def __init__(self, config=None):
        self.config = config or get_config("cost_control", {})

        self.budget_daily = self.config.get("budget_daily", 10.0)
        self.cost_today = 0.0
        self.usage_today = []

        # 价格配置
        self.prices = self.config.get("providers", {})

    def should_use_local(self) -> bool:
        """检查是否应该使用本地模型（基于成本）"""
        if not self.config.get("auto_switch_to_local", True):
            return False

        daily_limit = self.config.get("daily_api_limit", 50)
        if len(self.usage_today) >= daily_limit:
            logger.info(f"达到每日 API 限制 ({daily_limit})，切换到本地")
            return True

        budget_threshold = self.budget_daily * 0.8  # 80% 预算
        if self.cost_today >= budget_threshold:
            logger.info(
                f"达到预算阈值 ({budget_threshold:.2f}/{self.budget_daily:.2f})，切换到本地"
            )
            return True

        return False

    def estimate_cost(
        self, provider: str, input_tokens: int, output_tokens: int
    ) -> float:
        """估计 API 调用成本"""
        provider_prices = self.prices.get(provider, {})

        input_price = provider_prices.get("input_price_per_1k", 0.0) / 1000
        output_price = provider_prices.get("output_price_per_1k", 0.0) / 1000

        cost = (input_tokens * input_price) + (output_tokens * output_price)
        return cost

    def record_usage(self, provider: str, tokens: Dict[str, int], cost: float) -> None:
        """记录 API 使用情况"""
        self.cost_today += cost

        self.usage_today.append(
            {
                "timestamp": datetime.now().isoformat(),
                "provider": provider,
                "tokens": tokens,
                "cost": cost,
            }
        )

        # 限制记录数量
        if len(self.usage_today) > 1000:
            self.usage_today = self.usage_today[-1000:]

    def get_daily_summary(self) -> Dict[str, Any]:
        """获取每日使用摘要"""
        return {
            "budget_daily": self.budget_daily,
            "cost_today": self.cost_today,
            "usage_count": len(self.usage_today),
            "remaining_budget": self.budget_daily - self.cost_today,
            "budget_usage_percent": (self.cost_today / self.budget_daily * 100)
            if self.budget_daily > 0
            else 0,
        }


# 便捷函数
def create_llm_manager(config=None) -> LLMManager:
    """创建 LLM 管理器实例"""
    return LLMManager(config)


def generate_with_llm(
    prompt: str,
    context: Optional[str] = None,
    provider: Optional[str] = None,
    config=None,
) -> Dict[str, Any]:
    """使用 LLM 生成回答"""
    manager = create_llm_manager(config)
    return manager.generate(prompt, context, provider)
