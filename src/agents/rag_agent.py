"""
RAG Agent
基于知识库的问答Agent
"""

import logging
from typing import Any, Dict, List, Optional

from .base_agent import AgentConfig, AgentState, BaseAgent

logger = logging.getLogger(__name__)


class RAGAgent(BaseAgent):
    """RAG问答Agent"""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm_manager=None,
        vector_store=None,
        system_prompt: str = "",
    ):
        # 设置默认配置
        if config is None:
            config = AgentConfig(
                name="rag_agent",
                description="基于知识库的问答Agent",
                max_iterations=5,
                system_prompt=system_prompt or self._get_default_system_prompt(),
            )

        super().__init__(config, llm_manager)

        self.vector_store = vector_store
        self.retrieval_top_k = 4

        # 初始化工具
        self._init_tools()

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示"""
        return """你是一个智能问答助手，专门基于提供的知识库内容回答用户问题。

工作流程：
1. 首先理解用户问题，判断是否是复杂多跳问题
2. 优先使用 hybrid_search 进行混合搜索获取更准确的结果
3. 若问题需要更多上下文，使用 parent_context_search
4. 基于找到的内容回答问题
5. 如果知识库中没有相关信息，明确告知用户

回答要求：
- 只基于知识库中的内容回答，不要编造信息
- 如果找到多个相关文档，综合这些文档的内容回答
- 引用来源时说明来自哪个文档
- 回答要简洁准确"""

    def _init_tools(self) -> None:
        """初始化工具"""
        from .tools import (
            create_hybrid_search_tool,
            create_list_documents_tool,
            create_parent_context_tool,
            create_retrieve_documents_tool,
            create_search_tool,
        )

        if self.vector_store:
            # 混合搜索工具（优先推荐）
            self.register_tool(
                "hybrid_search",
                create_hybrid_search_tool(self.vector_store),
                "混合搜索（向量+BM25），推荐优先使用",
            )

            # 父子上下文检索工具
            self.register_tool(
                "parent_context_search",
                create_parent_context_tool(self.vector_store),
                "父子上下文检索，返回更完整上下文",
            )

            # 基础搜索工具
            self.register_tool(
                "search_knowledge",
                create_search_tool(self.vector_store),
                "在知识库中搜索相关文档",
            )

            # 带分数的检索工具
            self.register_tool(
                "retrieve_documents",
                create_retrieve_documents_tool(self.vector_store),
                "检索相关文档并返回相似度分数",
            )

            # 列出文档工具
            self.register_tool(
                "list_documents",
                create_list_documents_tool(self.vector_store),
                "列出知识库中的所有文档",
            )

    def process(self, input_data: str) -> Dict[str, Any]:
        """处理用户查询"""
        self.set_state(AgentState.THINKING)
        self._iteration_count = 0

        try:
            # 添加用户消息
            self.add_message("user", input_data)

            # 1. 检索相关文档（优先使用混合搜索）
            self.set_state(AgentState.ACTING)
            context = self._retrieve_context(input_data)

            # 2. 构建prompt并调用LLM
            self.set_state(AgentState.THINKING)
            response = self._generate_response(input_data, context)

            # 3. 返回结果
            self.set_state(AgentState.RESPONDING)
            return {
                "success": True,
                "query": input_data,
                "response": response,
                "context_used": bool(context),
                "iterations": self._iteration_count,
            }

        except Exception as e:
            logger.error(f"RAG Agent处理失败: {e}")
            self.set_state(AgentState.ERROR)
            return {"success": False, "error": str(e), "query": input_data}

    def _retrieve_context(self, query: str) -> str:
        """检索上下文，优先使用混合搜索"""
        try:
            if not self.vector_store:
                return ""

            # 优先使用混合搜索（向量 + BM25）
            try:
                results = self.vector_store.hybrid_search(
                    query, k=self.retrieval_top_k
                )
            except (AttributeError, RuntimeError, ValueError):
                # 降级到普通相似度搜索
                results = self.vector_store.similarity_search(
                    query, k=self.retrieval_top_k
                )

            if not results:
                return ""

            # 格式化上下文
            context_parts = []
            for i, doc in enumerate(results, 1):
                source = doc.metadata.get("source", "未知来源")
                content = doc.page_content
                context_parts.append(f"【参考文档 {i}】来源: {source}\n\n{content}\n")

            context = "\n---\n".join(context_parts)
            logger.debug(f"检索到 {len(results)} 个相关文档")

            return context

        except Exception as e:
            logger.error(f"检索失败: {e}")
            return ""

    def _generate_response(self, query: str, context: str) -> str:
        """生成回答"""
        if not self.llm_manager:
            # 如果没有LLM管理器，返回简单响应
            if context:
                return f"根据检索到的内容：\n\n{context[:500]}..."
            return "抱歉，LLM管理器未初始化，无法生成回答。"

        # 构建prompt
        if context:
            prompt = f"""基于以下参考文档回答用户问题。

参考文档：
{context}

用户问题：{query}

请根据参考文档内容回答问题。如果文档中没有相关信息，请明确说明。"""
        else:
            prompt = f"""用户问题：{query}

注意：知识库中没有找到相关信息，请如实告知用户。"""

        # 调用LLM
        try:
            result = self.llm_manager.generate(prompt)
            return result.get("text", "生成回答失败")
        except Exception as e:
            logger.error(f"LLM生成失败: {e}")
            return f"生成回答时出错: {str(e)}"

    def process_with_history(
        self, query: str, include_history: bool = True
    ) -> Dict[str, Any]:
        """带对话历史的处理"""
        if not include_history:
            return self.process(query)

        # 构建历史上下文
        history_context = ""
        if len(self.messages) > 1:
            recent_msgs = self.messages[-5:]  # 最近5条消息
            history_parts = []
            for msg in recent_msgs:
                if msg.role == "user":
                    history_parts.append(f"用户: {msg.content}")
                elif msg.role == "assistant":
                    history_parts.append(f"助手: {msg.content}")
            history_context = "\n".join(history_parts)

        self.set_state(AgentState.THINKING)
        self._iteration_count = 0

        try:
            # 检索相关文档
            self.set_state(AgentState.ACTING)
            context = self._retrieve_context(query)

            # 构建prompt
            if history_context:
                context_header = "参考文档：" + ("\n" + context) if context else ""
                prompt = f"""历史对话：
{history_context}

当前问题：{query}

{context_header}

请基于以上信息回答当前问题。"""
            else:
                context_header = (
                    "参考文档：" + ("\n" + context + "\n\n") if context else ""
                )
                prompt = f"""{context_header}
用户问题：{query}

请根据参考文档回答问题。"""

            # 生成回答
            self.set_state(AgentState.THINKING)
            if self.llm_manager:
                result = self.llm_manager.generate(prompt)
                response = result.get("text", "生成回答失败")
            else:
                response = "LLM管理器未初始化"

            # 添加到历史
            self.add_message("user", query)
            self.add_message("assistant", response)

            self.set_state(AgentState.RESPONDING)
            return {
                "success": True,
                "query": query,
                "response": response,
                "context_used": bool(context),
            }

        except Exception as e:
            logger.error(f"处理失败: {e}")
            self.set_state(AgentState.ERROR)
            return {"success": False, "error": str(e)}


class MultiStepRAGAgent(RAGAgent):
    """多步推理RAG Agent：通过 ReAct 模式自主选择工具、分解问题并综合答案。

    适合处理复杂的多跳问题，例如：
    - 需要比较多个文档的问题
    - 需要先检索摘要再深入搜索的问题
    - 需要拆解为子问题分别回答的问题
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm_manager=None,
        vector_store=None,
    ):
        if config is None:
            config = AgentConfig(
                name="multi_step_rag_agent",
                description="多步推理RAG Agent，适合复杂多跳问题",
                max_iterations=8,
                system_prompt=self._get_multi_step_system_prompt(),
            )

        super().__init__(config, llm_manager, vector_store)

        # 注册查询分解工具
        from .tools import create_knowledge_summary_tool, create_query_decompose_tool

        self.register_tool(
            "decompose_query",
            create_query_decompose_tool(llm_manager),
            "将复杂问题分解为子问题",
        )

        if vector_store:
            self.register_tool(
                "knowledge_summary",
                create_knowledge_summary_tool(vector_store, llm_manager),
                "对指定主题生成知识库综合摘要",
            )

        self.retrieval_top_k = 6

    def _get_multi_step_system_prompt(self) -> str:
        return """你是一个高级研究分析助手，擅长处理复杂的多步骤问题。

可用工具：
- hybrid_search(query, k): 混合搜索（推荐）
- parent_context_search(query, k): 父子上下文检索
- search_knowledge(query, k): 基础搜索
- decompose_query(query): 将复杂问题分解为子问题
- knowledge_summary(topic, max_docs): 对主题生成综合摘要
- list_documents(): 列出知识库中的文档

工作策略：
1. 分析问题复杂度，决定是否需要分解
2. 对复杂问题先用 decompose_query 拆分，再分别检索
3. 优先使用 hybrid_search 提升检索质量
4. 需要上下文时使用 parent_context_search
5. 综合所有检索结果给出完整答案

回答要求：
- 答案结构清晰，如有多个子问题应分点作答
- 明确引用来源文档
- 不编造信息"""

    def process(self, input_data: str) -> Dict[str, Any]:
        """通过多步骤 ReAct 循环处理复杂查询"""
        self.set_state(AgentState.THINKING)
        self._iteration_count = 0

        try:
            self.add_message("user", input_data)

            # 阶段1：判断是否需要分解
            is_complex = self._is_complex_query(input_data)

            collected_contexts: List[str] = []

            if is_complex and self.llm_manager:
                # 阶段2：分解问题
                self.set_state(AgentState.ACTING)
                sub_questions = self._decompose_query(input_data)

                # 阶段3：逐一检索子问题
                for sub_q in sub_questions:
                    if self.check_iteration_limit():
                        break
                    ctx = self._retrieve_context(sub_q)
                    if ctx:
                        collected_contexts.append(f"## 子问题: {sub_q}\n{ctx}")
            else:
                # 简单问题直接检索
                self.set_state(AgentState.ACTING)
                ctx = self._retrieve_context(input_data)
                if ctx:
                    collected_contexts.append(ctx)

            # 阶段4：综合生成答案
            self.set_state(AgentState.THINKING)
            combined_context = "\n\n".join(collected_contexts)
            response = self._generate_response(input_data, combined_context)

            self.set_state(AgentState.RESPONDING)
            self.add_message("assistant", response)

            return {
                "success": True,
                "query": input_data,
                "response": response,
                "context_used": bool(combined_context),
                "iterations": self._iteration_count,
                "sub_questions": sub_questions if is_complex and self.llm_manager else [],
            }

        except Exception as e:
            logger.error(f"MultiStepRAGAgent处理失败: {e}")
            self.set_state(AgentState.ERROR)
            return {"success": False, "error": str(e), "query": input_data}

    def _is_complex_query(self, query: str) -> bool:
        """启发式判断是否为复杂查询。

        触发条件（满足任一即视为复杂）：
        1. 查询字数超过 30 个字符（通常意味着包含多个约束条件）
        2. 包含比较/关系/分析类关键词（如"比较"、"区别"、"分析"等），
           这类词语通常意味着需要多个文档片段才能完整回答。
        """
        complex_indicators = [
            "比较", "对比", "区别", "联系", "关系",
            "分析", "总结", "综述", "哪些", "哪几",
            "compare", "difference", "relationship", "analyze",
            "和", "与", "及", "以及",
        ]
        return (
            len(query) > 30
            or any(ind in query for ind in complex_indicators)
        )

    def _decompose_query(self, query: str) -> List[str]:
        """将复杂查询分解为子问题"""
        if not self.llm_manager:
            return [query]

        try:
            prompt = (
                f"请将以下复杂问题分解为2-4个简单的子问题，每行一个，"
                f"直接输出子问题，不要编号或解释。\n\n复杂问题：{query}"
            )
            result = self.llm_manager.generate(prompt)
            text = result.get("text", "").strip()
            sub_questions = [
                line.strip() for line in text.splitlines() if line.strip()
            ]
            if sub_questions:
                logger.info(f"问题分解为 {len(sub_questions)} 个子问题")
                return sub_questions[:4]  # 最多4个子问题
        except Exception as e:
            logger.warning(f"问题分解失败: {e}")

        return [query]


class ResearchAgent(RAGAgent):
    """研究分析Agent - 更适合复杂分析任务"""

    def __init__(
        self, config: Optional[AgentConfig] = None, llm_manager=None, vector_store=None
    ):
        if config is None:
            config = AgentConfig(
                name="research_agent",
                description="研究分析Agent，适合复杂分析任务",
                max_iterations=8,
                system_prompt=self._get_research_system_prompt(),
            )

        super().__init__(config, llm_manager, vector_store)
        self.retrieval_top_k = 6

    def _get_research_system_prompt(self) -> str:
        """获取研究Agent的系统提示"""
        return """你是一个专业的研究分析助手。

你的工作：
1. 深入分析用户提出的问题
2. 在知识库中检索所有相关内容（优先使用 hybrid_search）
3. 综合分析多个文档的信息
4. 提供详细、结构化的回答
5. 如果需要，可以进行比较、总结、推理

分析要求：
- 充分利用所有相关文档
- 如果信息不完整，明确指出
- 提供深入的分析而不是简单的事实陈述
- 必要时可以引用多个来源进行对比

请开始分析。"""


class DocumentManagementAgent(BaseAgent):
    """文档管理Agent"""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        llm_manager=None,
        document_processor=None,
        vector_store=None,
    ):
        if config is None:
            config = AgentConfig(
                name="doc_manager",
                description="文档管理Agent，处理文档导入和处理",
                max_iterations=3,
            )

        super().__init__(config, llm_manager)
        self.document_processor = document_processor
        self.vector_store = vector_store

        # 注册文档管理工具
        self._init_tools()

    def _init_tools(self) -> None:
        """初始化文档管理工具"""
        if self.vector_store:
            self.register_tool(
                "list_documents", self._list_documents, "列出知识库中的文档"
            )

        if self.document_processor:
            self.register_tool(
                "process_document", self._process_document, "处理文档并添加到知识库"
            )

    def _list_documents(self) -> str:
        """列出文档"""
        try:
            if not self.vector_store:
                return "向量存储未初始化"
            info = self.vector_store.get_collection_info()
            return f"知识库状态: {info.get('document_count', 0)} 个文档"
        except Exception as e:
            return f"获取失败: {str(e)}"

    def _process_document(self, file_path: str) -> str:
        """处理文档"""
        if not self.document_processor:
            return "文档处理器未初始化"

        try:
            # 处理文档
            documents = self.document_processor.process_file(file_path)

            # 添加到向量存储
            if self.vector_store:
                ids = self.vector_store.add_documents(documents)
                return f"成功处理文档，添加了 {len(ids)} 个片段"

            return f"成功处理文档，生成了 {len(documents)} 个片段"
        except Exception as e:
            return f"处理失败: {str(e)}"

    def process(self, input_data: str) -> Dict[str, Any]:
        """处理文档管理命令"""
        # 简单的命令解析
        if input_data.startswith("list"):
            result = self._list_documents()
        elif input_data.startswith("add ") or input_data.startswith("process "):
            file_path = input_data.replace("add ", "").replace("process ", "").strip()
            result = self._process_document(file_path)
        else:
            result = "未知命令。支持: list, add <path>, process <path>"

        return {"success": True, "result": result}


# 便捷函数
def create_rag_agent(
    llm_manager=None, vector_store=None, system_prompt: str = ""
) -> RAGAgent:
    """创建RAG Agent"""
    return RAGAgent(
        llm_manager=llm_manager, vector_store=vector_store, system_prompt=system_prompt
    )


def create_research_agent(llm_manager=None, vector_store=None) -> ResearchAgent:
    """创建研究Agent"""
    return ResearchAgent(llm_manager=llm_manager, vector_store=vector_store)


def create_multi_step_agent(
    llm_manager=None, vector_store=None
) -> MultiStepRAGAgent:
    """创建多步推理Agent"""
    return MultiStepRAGAgent(llm_manager=llm_manager, vector_store=vector_store)


