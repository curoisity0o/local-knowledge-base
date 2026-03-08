"""
知识库系统前端 - Streamlit 应用
提供文档上传、问答交互和系统管理界面
"""

import streamlit as st
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 页面配置
st.set_page_config(
    page_title="本地知识库系统",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义CSS样式
st.markdown(
    """
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #4a5568;
        margin-bottom: 2rem;
    }
    .card {
        padding: 1.5rem;
        border-radius: 10px;
        background: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
        border: 1px solid #e2e8f0;
    }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }
    .success-message {
        padding: 1rem;
        background-color: #c6f6d5;
        border: 1px solid #9ae6b4;
        border-radius: 8px;
        color: #22543d;
    }
    .warning-message {
        padding: 1rem;
        background-color: #feebc8;
        border: 1px solid #fbd38d;
        border-radius: 8px;
        color: #744210;
    }
    .info-message {
        padding: 1rem;
        background-color: #bee3f8;
        border: 1px solid #90cdf4;
        border-radius: 8px;
        color: #2c5282;
    }
</style>
""",
    unsafe_allow_html=True,
)


# 初始化会话状态
def init_session_state():
    """初始化会话状态"""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []

    if "processing_status" not in st.session_state:
        st.session_state.processing_status = {}

    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "local"

    if "vector_store_initialized" not in st.session_state:
        st.session_state.vector_store_initialized = False

    if "llm_manager" not in st.session_state:
        st.session_state.llm_manager = None

    if "vector_store" not in st.session_state:
        st.session_state.vector_store = None

    if "document_processor" not in st.session_state:
        st.session_state.document_processor = None


# 初始化组件 - 使用API健康检查，避免重复初始化导致卡死
def get_vector_store():
    """获取向量存储"""
    from src.core.vector_store import SimpleVectorStore

    return SimpleVectorStore()


def get_document_processor():
    """获取文档处理器"""
    from src.core.document_processor import DocumentProcessor

    return DocumentProcessor()


def check_components_status(mode: str = "local", retries: int = 3, delay: float = 1.0):
    """根据模式检查组件状态，带重试机制"""
    import requests
    import time

    last_error = None

    for attempt in range(retries):
        try:
            if mode == "local":
                # 只检查本地模型
                response = requests.get(
                    "http://localhost:8000/health/local",
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "mode": "local",
                        "available": data.get("available", False),
                        "message": data.get("provider", "未知"),
                    }
            elif mode == "api":
                # 只检查 API
                response = requests.get(
                    "http://localhost:8000/health/api",
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "mode": "api",
                        "available": data.get("available", False),
                        "providers": data.get("providers", []),
                    }
            else:
                # 详细检查
                response = requests.get(
                    "http://localhost:8000/health/detailed",
                    timeout=60,
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "mode": "detailed",
                        "local_model_available": data.get(
                            "local_model_available", False
                        ),
                        "api_available": data.get("api_available", False),
                        "vector_store_ready": data.get("vector_store_ready", False),
                    }

            last_error = f"请求失败: {response.status_code}"

        except requests.exceptions.ConnectionError:
            last_error = "无法连接到API服务"
            # 连接错误时重试
            if attempt < retries - 1:
                time.sleep(delay)
                continue
        except requests.exceptions.Timeout:
            last_error = "请求超时"
            if attempt < retries - 1:
                time.sleep(delay)
                continue
        except Exception as e:
            last_error = f"检查失败: {str(e)}"
            break

    return {"success": False, "message": last_error}


def init_components():
    """初始化核心组件（仅在首次调用时初始化）"""
    try:
        # 文档处理器 - 已初始化则跳过
        if st.session_state.document_processor is None:
            st.session_state.document_processor = get_document_processor()

        # 向量存储 - 已初始化则跳过
        if st.session_state.vector_store is None:
            try:
                vs = get_vector_store()
                vs._ensure_initialized()
                if vs.vector_store is None:
                    st.error("向量存储内部未正确创建")
                    return False
                st.session_state.vector_store = vs
            except Exception as e:
                st.error(f"向量存储初始化失败: {e}")
                import traceback

                st.code(traceback.format_exc())
                return False

        # LLM管理器 - 已初始化则跳过
        if st.session_state.llm_manager is None:
            from src.core.llm_manager import LLMManager

            st.session_state.llm_manager = LLMManager()

        return True
    except Exception as e:
        logger.error(f"初始化组件失败: {e}")
        st.error(f"初始化组件失败: {e}")
        return False


# 页面标题
def render_header():
    """渲染页面标题"""
    st.markdown(
        '<h1 class="main-header">📚 本地知识库系统</h1>', unsafe_allow_html=True
    )
    st.markdown(
        '<p class="sub-header">基于 LangChain + RAG + Agent 的智能知识管理平台</p>',
        unsafe_allow_html=True,
    )

    # 系统状态概览
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("文档数量", len(st.session_state.uploaded_files))
    with col2:
        status = "就绪" if st.session_state.vector_store_initialized else "未初始化"
        st.metric("向量存储", status)
    with col3:
        model_status = "本地" if st.session_state.selected_model == "local" else "API"
        st.metric("当前模型", model_status)
    with col4:
        st.metric("对话历史", len(st.session_state.messages))


# 侧边栏
def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.markdown("### 🛠️ 系统设置")

        # 模型选择
        model_option = st.selectbox(
            "选择模型模式",
            ["local", "api"],
            index=0,
            help="local: 本地 Ollama 模型, api: 云 API (DeepSeek/OpenAI/Kimi)",
        )
        st.session_state.selected_model = model_option

        # 系统状态 - 根据选择的模式独立显示
        st.markdown("### 📊 系统状态")

        # 显示当前选择的模式状态
        current_mode = st.session_state.selected_model
        if st.button("🔄 检查状态", use_container_width=True):
            # 根据选择的模式检查对应状态
            with st.spinner("检查中..."):
                status = check_components_status(current_mode)
                if status.get("success"):
                    # 根据当前选择的模式显示对应状态
                    if current_mode == "local":
                        if status.get("available"):
                            st.success("✅ 本地模型可用")
                        else:
                            st.error("❌ 本地模型不可用 (请检查 Ollama 服务)")
                    else:  # api
                        if status.get("available"):
                            st.success("✅ API 可用")
                        else:
                            st.error("❌ API 不可用 (请检查 API Key 配置)")
                else:
                    st.error(f"❌ {status.get('message', '检查失败')}")

        if st.button("🔥 预热模型", use_container_width=True):
            with st.spinner("预热模型中（首次约需15秒）..."):
                try:
                    import requests

                    response = requests.post(
                        "http://localhost:8000/api/v1/models/warmup", timeout=120
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            st.success("✅ 模型预热完成！现在问答会更快")
                        else:
                            st.warning(result.get("message", "预热失败"))
                    else:
                        st.error(f"预热失败: {response.status_code}")
                except Exception as e:
                    st.error(f"预热出错: {e}")

        if st.button("🗑️ 清除历史记录", use_container_width=True):
            st.session_state.messages = []
            st.success("历史记录已清除")

        # 关于信息
        st.markdown("---")
        st.markdown("### ℹ️ 关于")
        st.markdown("""
        本地知识库系统基于以下技术构建：
        - **LangChain**: 框架集成
        - **RAG**: 检索增强生成
        - **DeepSeek-V2-Lite**: 本地模型
        - **ChromaDB**: 向量数据库
        - **Streamlit**: 前端界面
        """)


# 文档上传和处理
def render_document_upload():
    """渲染文档上传区域"""
    with st.container():
        st.markdown("### 📄 文档上传")

        uploaded_files = st.file_uploader(
            "选择文档文件",
            type=["pdf", "txt", "docx", "md", "csv", "html"],
            accept_multiple_files=True,
            help="支持 PDF, TXT, DOCX, MD, CSV, HTML 格式",
        )

        if uploaded_files:
            for uploaded_file in uploaded_files:
                if uploaded_file.name not in st.session_state.uploaded_files:
                    st.session_state.uploaded_files.append(uploaded_file.name)

            st.info(f"已选择 {len(uploaded_files)} 个文件")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 处理文档", use_container_width=True):
                if not uploaded_files:
                    st.warning("请先选择文档文件")
                else:
                    with st.spinner("处理文档中，请稍候..."):
                        try:
                            # 直接调用 API 处理文档
                            import requests

                            # 先上传文件
                            raw_docs_dir = Path("./data/raw_docs")
                            raw_docs_dir.mkdir(parents=True, exist_ok=True)

                            for uploaded_file in uploaded_files:
                                file_path = raw_docs_dir / uploaded_file.name
                                with open(file_path, "wb") as f:
                                    f.write(uploaded_file.getbuffer())

                            # 调用 API 处理
                            response = requests.post(
                                "http://localhost:8000/api/v1/documents/process",
                                json={},
                                timeout=60,
                            )

                            if response.status_code == 200:
                                result = response.json()
                                if result.get("success"):
                                    st.session_state.vector_store_initialized = True

                                    # 创建一个假的 vector_store 对象用于查询
                                    class FakeVectorStore:
                                        def __init__(self):
                                            self.vector_store = "initialized"

                                        def get_collection_info(self):
                                            return {
                                                "status": "ok",
                                                "message": "通过 API 初始化",
                                            }

                                    st.session_state.vector_store = FakeVectorStore()
                                    st.success(
                                        f"✅ 文档处理完成！{result.get('message', '')}"
                                    )
                                else:
                                    st.error(f"处理失败: {result.get('message', '')}")
                            else:
                                st.error(f"API 错误: {response.status_code}")

                        except Exception as e:
                            # 如果 API 失败，回退到本地处理
                            st.warning(f"API 调用失败，尝试本地处理: {e}")

                            # 本地处理（简化版）
                            raw_docs_dir = Path("./data/raw_docs")
                            raw_docs_dir.mkdir(parents=True, exist_ok=True)

                            for uploaded_file in uploaded_files:
                                file_path = raw_docs_dir / uploaded_file.name
                                with open(file_path, "wb") as f:
                                    f.write(uploaded_file.getbuffer())

                            try:
                                from src.core.document_processor import (
                                    DocumentProcessor,
                                )
                                from src.core.vector_store import SimpleVectorStore

                                processor = DocumentProcessor()
                                documents = processor.process_directory(
                                    str(raw_docs_dir)
                                )

                                vector_store = SimpleVectorStore()
                                vector_store._ensure_initialized()
                                vector_store.add_documents(documents)

                                st.session_state.vector_store_initialized = True
                                st.success(
                                    f"✅ 文档处理完成！生成 {len(documents)} 个 chunks"
                                )
                            except Exception as e2:
                                st.error(f"本地处理也失败: {e2}")

        with col2:
            if st.button("📊 查看向量存储信息", use_container_width=True):
                if st.session_state.vector_store_initialized:
                    try:
                        vector_store = st.session_state.vector_store
                        info = vector_store.get_collection_info()
                        st.json(info)
                    except Exception as e:
                        st.error(f"获取向量存储信息失败: {e}")
                else:
                    st.warning("向量存储未初始化，请先处理文档")


# 问答界面
def render_chat_interface():
    """渲染问答界面"""
    with st.container():
        st.markdown("### 💬 智能问答")

        # 聊天历史
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    if "sources" in message:
                        with st.expander("查看来源"):
                            for source in message["sources"]:
                                st.markdown(f"- {source}")

        # 用户输入
        user_input = st.chat_input("输入您的问题...")

        if user_input:
            # 添加用户消息
            st.session_state.messages.append({"role": "user", "content": user_input})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(user_input)

            # 生成回答
            with st.spinner("思考中..."):
                try:
                    if not st.session_state.vector_store_initialized:
                        st.warning("向量存储未初始化，请先上传文档")
                        return

                    # 使用 API 进行查询，传递用户选择的模型模式
                    import requests

                    selected_provider = st.session_state.selected_model
                    response = requests.post(
                        "http://localhost:8000/api/v1/query",
                        json={
                            "question": user_input,
                            "top_k": 4,
                            "provider": selected_provider,
                        },
                        timeout=60,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        answer = result.get("answer", "无法获取回答")
                        sources = result.get("sources", [])

                        # 添加助手消息
                        st.session_state.messages.append(
                            {"role": "assistant", "content": answer, "sources": sources}
                        )

                        # 显示回答
                        with chat_container:
                            with st.chat_message("assistant"):
                                st.markdown(answer)
                                if sources:
                                    with st.expander("查看参考来源"):
                                        for i, source in enumerate(sources):
                                            st.markdown(f"{i + 1}. {source}")
                    else:
                        st.error(f"查询失败: {response.status_code}")

                except Exception as e:
                    logger.error(f"生成回答失败: {e}")
                    error_msg = f"抱歉，生成回答时出现错误: {str(e)}"
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
                    with chat_container:
                        with st.chat_message("assistant"):
                            st.markdown(error_msg)


# 系统信息
def render_system_info():
    """渲染系统信息"""
    with st.expander("🔧 系统信息", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 硬件配置")
            st.markdown("""
            - **CPU**: i5-13600KF
            - **内存**: 32GB
            - **GPU**: RTX 4070 SUPER (12GB)
            - **存储**: 3.7TB
            """)

        with col2:
            st.markdown("#### 软件配置")
            st.markdown("""
            - **核心模型**: DeepSeek-V2-Lite (16B MoE)
            - **嵌入模型**: BGE-M3 (中文优化)
            - **向量数据库**: ChromaDB
            - **前端框架**: Streamlit
            """)

        if st.button("📋 生成诊断报告"):
            try:
                import platform
                import psutil

                info = {
                    "系统": platform.system(),
                    "Python版本": platform.python_version(),
                    "CPU使用率": f"{psutil.cpu_percent()}%",
                    "内存使用率": f"{psutil.virtual_memory().percent}%",
                    "磁盘使用率": f"{psutil.disk_usage('/').percent}%",
                }

                st.json(info)
            except ImportError:
                st.warning("无法获取完整系统信息")


# 主函数
def main():
    """主函数"""
    init_session_state()
    render_header()
    render_sidebar()

    # 创建标签页
    tab1, tab2, tab3 = st.tabs(["📄 文档管理", "💬 智能问答", "🔧 系统设置"])

    with tab1:
        render_document_upload()

    with tab2:
        render_chat_interface()

    with tab3:
        render_system_info()

    # 页脚
    st.markdown("---")
    st.markdown(
        """
    <div style="text-align: center; color: #718096; font-size: 0.9rem;">
        <p>本地知识库系统 v1.0.0 | 基于 LangChain + RAG + Agent 架构 | 设计用于中英文混合文档处理</p>
    </div>
    """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
