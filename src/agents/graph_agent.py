"""
LangGraph Agent
基于 LangGraph StateGraph 构建的 Agentic RAG，LLM 自主选择工具、反思检索质量、多轮迭代。
"""

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from ..core.config import get_config
from .tools import ToolRegistry, get_default_tools

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """LangGraph 状态定义"""

    query: str  # 原始问题
    tool_calls_json: str  # LLM 输出的工具调用指令（JSON 字符串）
    tool_results: List[str]  # 工具执行结果列表
    documents: List[str]  # 检索到的文档内容
    answer: str  # 最终答案
    iteration: int  # 当前迭代次数
    max_iterations: int  # 最大迭代次数
    need_more: bool  # 是否需要继续检索


class GraphAgent:
    """基于 LangGraph 的 Agentic RAG Agent。

    流程: analyze_query → execute_tools → reflect → [loop or synthesize] → END
    """

    def __init__(self, llm_manager=None, vector_store=None):
        self._llm_manager = llm_manager
        self._vector_store = vector_store
        self._max_iterations = int(get_config("agent.graph.max_iterations", 3))
        self._tools = get_default_tools(vector_store, llm_manager)
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 状态图"""
        workflow = StateGraph(AgentState)

        workflow.add_node("analyze_query", self._node_analyze_query)
        workflow.add_node("execute_tools", self._node_execute_tools)
        workflow.add_node("reflect", self._node_reflect)
        workflow.add_node("synthesize", self._node_synthesize)

        workflow.set_entry_point("analyze_query")
        workflow.add_edge("analyze_query", "execute_tools")
        workflow.add_conditional_edges(
            "execute_tools",
            self._should_continue,
            {"continue": "reflect", "stop": "synthesize"},
        )
        workflow.add_conditional_edges(
            "reflect",
            self._need_more_data,
            {"more": "analyze_query", "enough": "synthesize"},
        )

        return workflow.compile()

    def _get_tools_description(self) -> str:
        """生成工具列表描述，注入到 LLM prompt"""
        schema = self._tools.get_tools_schema()
        lines = []
        for tool in schema:
            params = tool.get("parameters", {}).get("properties", {})
            param_str = ", ".join(
                f"{name}: {info.get('description', name)}"
                for name, info in params.items()
            )
            lines.append(f"- {tool['name']}({param_str}): {tool['description']}")
        return "\n".join(lines)

    def _node_analyze_query(self, state: AgentState) -> Dict[str, Any]:
        """分析查询意图，选择要调用的工具。"""
        query = state["query"]
        iteration = state.get("iteration", 0) + 1
        tool_results = state.get("tool_results", [])
        documents = state.get("documents", [])

        if not self._llm_manager:
            # 无 LLM 时默认调用 hybrid_search
            return {
                "tool_calls_json": json.dumps([{"tool": "hybrid_search", "args": {"query": query, "k": 5}}]),
                "iteration": iteration,
            }

        # 构建工具选择 prompt
        tools_desc = self._get_tools_description()
        history = ""
        if tool_results:
            history = "\n\n已收集的信息：\n" + "\n---\n".join(tool_results[-3:])

        prompt = (
            f"你是一个知识库检索助手。根据用户问题和已收集的信息，决定下一步操作。\n"
            f"\n可用工具：\n{tools_desc}\n"
            f"\n用户问题：{query}"
            f"{history}"
            f"\n\n请输出一个 JSON 数组，每个元素是 {{\"tool\": \"工具名\", \"args\": {{参数}}}}。"
            f"如果已有足够信息可以回答，输出空数组 []。只输出 JSON，不要其他文字。"
        )

        try:
            result = self._llm_manager.generate(prompt)
            text = result.get("text", "").strip()

            # 提取 JSON（LLM 可能包裹在 markdown 代码块中）
            json_match = _extract_json(text)
            if json_match:
                tool_calls = json_match
            else:
                # 解析失败，默认检索
                tool_calls = [{"tool": "hybrid_search", "args": {"query": query, "k": 5}}]

            logger.info("Agent 迭代 %d: 选择工具 %s", iteration, [t["tool"] for t in tool_calls])
            return {
                "tool_calls_json": json.dumps(tool_calls, ensure_ascii=False),
                "iteration": iteration,
            }
        except Exception as e:
            logger.warning("分析查询失败: %s，使用默认检索", e)
            return {
                "tool_calls_json": json.dumps([{"tool": "hybrid_search", "args": {"query": query, "k": 5}}]),
                "iteration": iteration,
            }

    def _node_execute_tools(self, state: AgentState) -> Dict[str, Any]:
        """执行 LLM 选择的工具，收集结果。"""
        tool_calls_json = state.get("tool_calls_json", "[]")
        tool_results = list(state.get("tool_results", []))
        documents = list(state.get("documents", []))

        try:
            tool_calls = json.loads(tool_calls_json)
        except (json.JSONDecodeError, TypeError):
            tool_calls = []

        if not tool_calls:
            return {"tool_results": tool_results, "documents": documents}

        for call in tool_calls:
            tool_name = call.get("tool", "")
            args = call.get("args", {})

            func = self._tools.get_tool(tool_name)
            if func is None:
                logger.warning("Agent 请求了未知工具: %s", tool_name)
                tool_results.append(f"工具 {tool_name} 不存在")
                continue

            try:
                # 将参数转为正确的类型
                typed_args = _cast_args(args)
                result = func(**typed_args)
                result_str = result if isinstance(result, str) else str(result)
                tool_results.append(result_str)

                # 收集文档内容（用于 trace_source）
                if tool_name in ("hybrid_search", "search_knowledge", "parent_context_search"):
                    documents.append(result_str)
            except Exception as e:
                logger.error("工具 %s 执行失败: %s", tool_name, e)
                tool_results.append(f"工具 {tool_name} 执行失败: {e}")

        return {"tool_results": tool_results, "documents": documents}

    def _node_reflect(self, state: AgentState) -> Dict[str, Any]:
        """反思：评估已有信息是否足够回答问题。"""
        query = state["query"]
        tool_results = state.get("tool_results", [])
        iteration = state.get("iteration", 1)
        max_iter = state.get("max_iterations", self._max_iterations)

        # 达到最大迭代次数，停止
        if iteration >= max_iter:
            logger.info("Agent 达到最大迭代次数 %d，停止检索", max_iter)
            return {"need_more": False}

        # 无 LLM 时不做反思，直接停止
        if not self._llm_manager:
            return {"need_more": False}

        combined = "\n".join(tool_results)

        prompt = (
            f"评估已有信息是否足够回答用户问题。\n"
            f"用户问题：{query}\n"
            f"已收集信息：\n{combined[:2000]}\n\n"
            f"信息足够回答问题吗？只输出 enough 或 more。"
        )

        try:
            result = self._llm_manager.generate(prompt)
            text = result.get("text", "").strip().lower()
            need_more = "more" in text and "enough" not in text

            if need_more:
                logger.info("Agent 反思: 信息不足，继续检索（迭代 %d/%d）", iteration, max_iter)
            else:
                logger.info("Agent 反思: 信息充分，开始生成答案")

            return {"need_more": need_more}
        except Exception as e:
            logger.warning("反思失败: %s，默认停止", e)
            return {"need_more": False}

    def _node_synthesize(self, state: AgentState) -> Dict[str, Any]:
        """综合所有检索结果，生成最终答案。"""
        query = state["query"]
        tool_results = state.get("tool_results", [])
        documents = state.get("documents", [])

        if not self._llm_manager:
            if tool_results:
                return {"answer": "\n\n".join(tool_results)}
            return {"answer": "LLM 未初始化，无法生成答案。"}

        combined = "\n\n".join(tool_results)

        prompt = (
            f"基于以下检索结果回答用户问题。只使用检索到的信息，不要编造。\n"
            f"如果信息不足，明确说明。\n\n"
            f"检索结果：\n{combined[:4000]}\n\n"
            f"用户问题：{query}\n\n请用中文回答："
        )

        try:
            result = self._llm_manager.generate(prompt)
            answer = result.get("text", "").strip()
            return {"answer": answer or "生成失败"}
        except Exception as e:
            logger.error("生成答案失败: %s", e)
            return {"answer": f"生成答案失败: {e}"}

    @staticmethod
    def _should_continue(state: AgentState) -> str:
        """判断是否还有工具要执行（非空数组则继续到 reflect）。"""
        try:
            calls = json.loads(state.get("tool_calls_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            calls = []
        return "continue" if calls else "stop"

    @staticmethod
    def _need_more_data(state: AgentState) -> str:
        """反思后决定是否继续检索。"""
        return "more" if state.get("need_more", False) else "enough"

    def process(self, query: str) -> Dict[str, Any]:
        """执行 Agent 查询。"""
        logger.info("GraphAgent 开始处理: '%s...'", query[:50])

        initial_state: AgentState = {
            "query": query,
            "tool_calls_json": "[]",
            "tool_results": [],
            "documents": [],
            "answer": "",
            "iteration": 0,
            "max_iterations": self._max_iterations,
            "need_more": False,
        }

        try:
            final_state = self._graph.invoke(initial_state)
            answer = final_state.get("answer", "")
            iterations = final_state.get("iteration", 0)

            logger.info(
                "GraphAgent 完成: 迭代 %d 次, 答案长度 %d 字符",
                iterations, len(answer),
            )

            return {
                "success": True,
                "query": query,
                "answer": answer,
                "iterations": iterations,
                "tool_results_count": len(final_state.get("tool_results", [])),
            }
        except Exception as e:
            logger.error("GraphAgent 处理失败: %s", e)
            return {
                "success": False,
                "query": query,
                "answer": f"Agent 处理失败: {e}",
                "error": str(e),
            }


def _extract_json(text: str) -> Optional[list]:
    """从 LLM 输出中提取 JSON 数组。"""
    # 尝试直接解析
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1).strip())
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # 尝试提取 [...] 部分
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def _cast_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """将工具参数转换为正确的类型。"""
    from .tools import ToolRegistry

    casted = {}
    for key, value in args.items():
        if isinstance(value, str):
            # 尝试转为 int
            try:
                casted[key] = int(value)
                continue
            except ValueError:
                pass
            # 尝试转为 float
            try:
                casted[key] = float(value)
                continue
            except ValueError:
                pass
        casted[key] = value
    return casted
