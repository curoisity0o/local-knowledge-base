"""
知识库系统前端 - Streamlit 应用
提供文档上传、问答交互和系统管理界面
"""

import re
import sys
from pathlib import Path

import streamlit as st

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import logging

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


def process_markdown_images(content: str, doc_filename: str = "") -> str:
    """处理Markdown中的图片链接，转换为可显示的HTML

    图片路径查找（data/images/ 目录下）：
    1. data/images/{doc_name}_images/images/{image_path}
    2. data/images/{doc_name}_images/{image_path}

    Args:
        content: 原始Markdown内容
        doc_filename: 当前文档的文件名（不含路径），用于构建图片路径

    Returns:
        处理后的Markdown内容，图片链接转换为可点击链接
    """
    # 获取项目根目录
    project_root = Path(__file__).parent.parent.parent
    image_base = project_root / "data" / "images"

    def replace_image_link(match):
        alt_text = match.group(1) if match.group(1) else "图片"
        image_path = match.group(2)

        # 清理文档名
        # 去除路径
        doc_name = Path(doc_filename).stem if doc_filename else ""
        # 去除.md后缀
        doc_name = doc_name.replace(".md", "") if ".md" in doc_name else doc_name

        # 判断图片路径类型
        if image_path.startswith("/") or image_path.startswith("http"):
            # 绝对路径或网络URL，保持原样
            full_path = image_path
        else:
            # 相对路径，查找 data/images/{doc_name}_images/ 目录
            doc_images_dir = f"{doc_name}_images"

            # 优先查找：data/images/{doc_name}_images/images/xxx.jpg
            path1 = image_base / doc_images_dir / "images" / image_path
            # 备选查找：data/images/{doc_name}_images/xxx.jpg（直接放根目录）
            path2 = image_base / doc_images_dir / image_path

            if path1.exists():
                full_path = str(path1)
            elif path2.exists():
                full_path = str(path2)
            else:
                # 路径都不存在，返回提示
                return f"📷 *图片不存在: {image_path}*"

        # 返回Markdown格式的图片
        return f"![{alt_text}]({full_path})"

    # 替换图片链接
    processed = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image_link, content)
    return processed


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

    if "processing" not in st.session_state:
        st.session_state.processing = False

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
    import time

    import requests

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
    import requests

    # 侧边栏API检查改为静默，不阻塞界面
    if "api_checked" not in st.session_state:
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            st.session_state.api_connected = response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.warning(f"API健康检查失败: {e}")
            st.session_state.api_connected = False
        st.session_state.api_checked = True

    # 右上角显示状态
    if not st.session_state.get("api_connected", False):
        st.markdown(
            """
        <div style="
            position: fixed;
            top: 10px;
            right: 10px;
            background: #ff6b6b;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            z-index: 9999;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        ">
            🔄 本地模型启动中...
        </div>
        <script>
            setTimeout(function(){
                window.location.reload();
            }, 3000);
        </script>
        """,
            unsafe_allow_html=True,
        )
        # 静默等待，不阻塞
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                st.session_state.api_connected = True
                st.rerun()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.debug(f"API连接重试失败: {e}")

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
        if st.button("🔄 检查状态", width="stretch"):
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

        if st.button("🔥 预热模型", width="stretch"):
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

        if st.button("🗑️ 清除历史记录", width="stretch"):
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


# 删除文档功能
def render_delete_document():
    """渲染删除文档界面"""
    import requests

    with st.container():
        try:
            # 获取文档列表
            response = requests.get(
                "http://localhost:8000/api/v1/documents/list", timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                documents = data.get("documents", [])

                if not documents:
                    st.info("暂无文档")
                    return

                # 选择要删除的文档
                filenames = [doc.get("filename", "") for doc in documents]
                selected_file = st.selectbox(
                    "选择要删除的文档",
                    ["请选择..."] + filenames,
                    key="delete_doc_select",
                )

                if selected_file and selected_file != "请选择...":
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.warning(
                            f"⚠️ 确定要删除 **'{selected_file}'** 吗？此操作不可恢复！"
                        )
                    with col2:
                        if st.button(
                            "🗑️ 确认删除", key=f"confirm_delete_{selected_file}"
                        ):
                            try:
                                delete_response = requests.delete(
                                    f"http://localhost:8000/api/v1/documents/{selected_file}",
                                    timeout=10,
                                )

                                if delete_response.status_code == 200:
                                    result = delete_response.json()
                                    if result.get("success"):
                                        st.success(
                                            f"✅ {result.get('message', '删除成功')}"
                                        )
                                        st.rerun()
                                    else:
                                        st.error(
                                            f"❌ {result.get('message', '删除失败')}"
                                        )
                                else:
                                    st.error(
                                        f"❌ 删除失败: {delete_response.status_code}"
                                    )
                            except Exception as e:
                                st.error(f"❌ 删除失败: {e}")
        except Exception as e:
            st.error(f"加载文档列表失败: {e}")


# 文档上传和处理
def render_document_upload():
    """渲染文档上传区域"""
    import requests

    with st.container():
        st.markdown("### 📄 文档上传")

        # 文档来源选项
        source_option = st.radio(
            "选择文档来源",
            ["直接上传", "从 MinerU 导入"],
            horizontal=True,
            help="直接上传: 上传PDF/TXT等文件\n从MinerU导入: 导入MinerU处理后的Markdown文档",
        )

        uploaded_files = None

        if source_option == "直接上传":
            # 直接上传模式
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

        elif source_option == "从 MinerU 导入":
            # MinerU 导入模式
            st.markdown("""
            > **MinerU** 是PDF文档智能解析工具，可将PDF转换为Markdown。
            > 导入后自动完成：复制文档 + 复制图片 + 提取元数据 + 向量化
            """)

            # 文件夹选择器
            col_browse1, col_browse2 = st.columns([4, 1])
            with col_browse1:
                mineru_dir = st.text_input(
                    "MinerU输出目录路径",
                    placeholder="点击右侧按钮选择文件夹",
                    help="点击右侧按钮选择MinerU处理后的输出目录",
                    key="mineru_dir_input",
                    disabled=True,
                )
            with col_browse2:
                st.write("")
                if st.button("📂 选择文件夹", key="browse_mineru"):
                    # 使用tkinter弹出文件夹选择对话框
                    import tkinter as tk
                    from tkinter import filedialog

                    root = tk.Tk()
                    root.withdraw()  # 隐藏主窗口
                    root.attributes("-topmost", True)  # 置顶

                    selected_dir = filedialog.askdirectory(
                        initialdir="C:/Users/10234/MinerU", title="选择MinerU输出目录"
                    )
                    root.destroy()

                    if selected_dir:
                        # 更新session state来刷新页面显示选择的路径
                        st.session_state.mineru_selected_dir = selected_dir
                        st.rerun()

            # 显示已选择的路径
            if (
                "mineru_selected_dir" in st.session_state
                and st.session_state.mineru_selected_dir
            ):
                mineru_dir = st.session_state.mineru_selected_dir
                st.success(f"✅ 已选择: {mineru_dir}")

            if mineru_dir:
                if st.button("📥 导入并向量化", key="mineru_import", type="primary"):
                    with st.spinner("导入并向量化中，请稍候（可能需要1-2分钟）..."):
                        try:
                            # 调用MinerU导入API（后端自动向量化）
                            import_response = requests.post(
                                "http://localhost:8000/api/v1/documents/import/mineru",
                                json={"mineru_dir": mineru_dir},
                                timeout=180,  # 增加超时时间
                            )

                            if import_response.status_code != 200:
                                st.error(f"导入失败: {import_response.status_code}")
                            else:
                                result = import_response.json()
                                st.success(f"""✅ 导入并向量化成功！

- **文件名**: {result.get("filename", "")}
- **标题**: {result.get("title", "")}
- **作者**: {", ".join(result.get("authors", [])) or "未知"}
- **向量 chunks**: {result.get("message", "N/A")}
- **包含图片**: {"✅ 是" if result.get("has_images") else "❌ 否"}
""")
                                st.rerun()

                        except Exception as e:
                            st.error(f"导入失败: {e}")

        # 直接上传模式的处理按钮
        if source_option == "直接上传" and uploaded_files:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 处理文档", width="stretch"):
                    with st.spinner("处理文档中，请稍候..."):
                        try:
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
                                    st.success(
                                        f"✅ 文档处理完成！{result.get('message', '')}"
                                    )
                                else:
                                    st.error(f"处理失败: {result.get('message', '')}")
                            else:
                                st.error(f"API 错误: {response.status_code}")

                        except Exception as e:
                            st.error(f"处理失败: {e}")

            with col2:
                if st.button("📊 查看向量存储信息", width="stretch"):
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

        # 检查是否正在处理中，显示提示而不是输入框
        is_processing = st.session_state.get("processing", False)

        if is_processing:
            # 处理中，不显示输入框，显示提示
            st.info("🤖 正在处理您的问题，请稍候...")
            user_input = None
        else:
            # 处理完成，显示输入框
            user_input = st.chat_input("输入您的问题...", key="chat_input")

        if user_input and not is_processing:
            # 标记正在处理 - 先添加用户消息，再立即刷新
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.processing = True
            st.rerun()

        # 如果正在处理中，显示加载状态
        if st.session_state.get("processing", False):
            # 生成回答
            with st.spinner("思考中..."):
                try:
                    # 自动检测向量存储是否已初始化
                    if not st.session_state.vector_store_initialized:
                        # 尝试调用文档统计API检测是否有已索引的文档
                        try:
                            import requests

                            stats_response = requests.get(
                                "http://localhost:8000/api/v1/documents/stats",
                                timeout=5,
                            )
                            if stats_response.status_code == 200:
                                stats = stats_response.json()
                                if stats.get("indexed_documents", 0) > 0:
                                    # 已有索引的文档，自动标记为已初始化
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
                        except Exception as detect_e:
                            logger.warning(f"检测向量存储状态失败: {detect_e}")

                    if not st.session_state.vector_store_initialized:
                        error_msg = "向量存储未初始化，请先上传并处理文档"
                        st.warning(error_msg)
                        # 添加错误消息
                        st.session_state.messages.append(
                            {"role": "assistant", "content": error_msg}
                        )
                        with chat_container:
                            with st.chat_message("assistant"):
                                st.markdown(error_msg)
                        st.session_state.processing = False
                        st.rerun()

                    # 使用 API 进行查询，传递用户选择的模型模式
                    import requests

                    # 获取用户最后一个问题
                    user_input = st.session_state.messages[-1]["content"]

                    # 构建对话历史 (最近6条，不含当前)
                    history = []
                    for msg in st.session_state.messages[:-1][-6:]:
                        history.append(
                            {
                                "role": msg.get("role", "user"),
                                "content": msg.get("content", ""),
                            }
                        )

                    selected_provider = st.session_state.selected_model
                    response = requests.post(
                        "http://localhost:8000/api/v1/query",
                        json={
                            "question": user_input,
                            "top_k": 4,
                            "provider": selected_provider,
                            "history": history,  # 传递对话历史
                        },
                        timeout=120,
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
                                        # 去重显示
                                        seen = set()
                                        unique_sources = []
                                        for s in sources:
                                            # 提取文件名作为唯一标识
                                            filename = s.split("/")[-1].split("\\")[-1]
                                            if filename not in seen:
                                                seen.add(filename)
                                                unique_sources.append(s)
                                        for i, source in enumerate(unique_sources):
                                            # 只显示文件名
                                            filename = source.split("/")[-1].split(
                                                "\\"
                                            )[-1]
                                            st.markdown(f"{i + 1}. {filename}")
                    else:
                        error_msg = f"查询失败: {response.status_code}"
                        st.error(error_msg)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": error_msg}
                        )
                        with chat_container:
                            with st.chat_message("assistant"):
                                st.markdown(error_msg)

                except Exception as e:
                    logger.error(f"生成回答失败: {e}")
                    error_msg = f"生成回答失败: {e}"
                    st.error(error_msg)
                    # 显示错误消息
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
                    with chat_container:
                        with st.chat_message("assistant"):
                            st.markdown(error_msg)
                finally:
                    # 处理完成，启用输入
                    st.session_state.processing = False
                    # 刷新页面更新状态
                    st.rerun()


# 文档管理界面
def render_document_management():
    """渲染文档管理界面（包含列表、统计、查看功能）"""
    import pandas as pd
    import requests

    # 初始化变量
    response = None
    documents = []

    with st.container():
        st.markdown("### 📊 文档统计")

        # 获取统计信息
        try:
            response = requests.get(
                "http://localhost:8000/api/v1/documents/stats", timeout=5
            )
            if response.status_code == 200:
                stats = response.json()

                # 显示统计指标
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("文档总数", stats.get("total_documents", 0))
                with col2:
                    st.metric("已索引", stats.get("indexed_documents", 0))
                with col3:
                    st.metric("未索引", stats.get("not_indexed_documents", 0))
                with col4:
                    total_size_mb = stats.get("total_size", 0) / (1024 * 1024)
                    st.metric("总大小", f"{total_size_mb:.2f} MB")
            else:
                st.warning("无法获取文档统计")
        except Exception as e:
            st.warning(f"无法获取统计: {str(e)[:50]}")

        st.markdown("---")

        # 刷新按钮
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("🔄 刷新", key="refresh_docs"):
                st.rerun()

        # 获取文档列表
        try:
            response = requests.get(
                "http://localhost:8000/api/v1/documents/list", timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                documents = data.get("documents", [])

                if not documents:
                    st.info("暂无文档，请先上传文档")
                    return

                # 准备表格数据
                doc_data = []
                for doc in documents:
                    size_kb = doc.get("file_size", 0) / 1024
                    size_str = (
                        f"{size_kb:.2f} KB"
                        if size_kb < 1024
                        else f"{size_kb / 1024:.2f} MB"
                    )

                    # 处理修改时间
                    modified_time = doc.get("modified_time")
                    if modified_time:
                        from datetime import datetime

                        mod_time = datetime.fromtimestamp(modified_time)
                        mod_time_str = mod_time.strftime("%Y-%m-%d %H:%M")
                    else:
                        mod_time_str = "未知"

                    doc_data.append(
                        {
                            "文件名": doc.get("filename", ""),
                            "大小": size_str,
                            "格式": doc.get("file_extension", ""),
                            "修改时间": mod_time_str,
                            "向量状态": doc.get("vector_status", "not_indexed"),
                            "Chunks": doc.get("chunks_count", 0),
                            "文件路径": doc.get("file_path", ""),
                        }
                    )

                # 创建 DataFrame
                df = pd.DataFrame(doc_data)

                # 显示表格
                st.markdown("### 📁 文档列表")

                # 格式化向量状态显示
                def format_vector_status(status):
                    if status == "indexed":
                        return "✅ 已索引"
                    return "❌ 未索引"

                df["向量状态"] = df["向量状态"].apply(format_vector_status)

                # 使用 Streamlit 的 data_editor 实现可交互表格
                st.dataframe(
                    df[["文件名", "大小", "格式", "修改时间", "向量状态", "Chunks"]],
                    width="stretch",
                    hide_index=True,
                )

            else:
                st.error(f"获取文档列表失败: {response.status_code}")
        except Exception as e:
            st.error(f"加载文档列表失败: {e}")

        # 查看文档内容功能
        st.markdown("---")
        st.markdown("### 📖 查看文档内容")

        col1, col2 = st.columns([3, 1])
        with col1:
            # 获取已索引的文档列表
            indexed_docs = []  # type: ignore
            if response and response.status_code == 200:
                for doc in documents:  # type: ignore
                    if doc.get("vector_status") == "indexed":
                        indexed_docs.append(doc.get("filename", ""))

            view_options = ["请选择要查看的文档..."] + indexed_docs
            selected_view_doc = st.selectbox(
                "选择已索引的文档查看其chunks内容",
                view_options,
                key="view_doc_select",
            )

        with col2:
            st.write("")  # 间距
            st.write("")  # 间距
            view_clicked = st.button("🔍 查看内容", key="view_chunks_btn")

        # 初始化分页状态
        if "current_chunk_page" not in st.session_state:
            st.session_state.current_chunk_page = 1

        # 如果点击了查看按钮，重置页码
        if view_clicked:
            st.session_state.current_chunk_page = 1

        # 加载chunks（如果有选择文档）
        chunks = []
        chunks_loaded = False
        if selected_view_doc and selected_view_doc != "请选择要查看的文档...":
            try:
                if view_clicked:
                    with st.spinner("加载文档chunks中..."):
                        chunks_response = requests.get(
                            f"http://localhost:8000/api/v1/documents/{selected_view_doc}/chunks",
                            timeout=30,
                        )
                        if chunks_response.status_code == 200:
                            chunks_data = chunks_response.json()
                            chunks = chunks_data.get("chunks", [])
                            st.session_state.loaded_chunks = chunks
                            chunks_loaded = True
                        else:
                            st.error(f"获取失败: {chunks_response.status_code}")
                elif "loaded_chunks" in st.session_state:
                    # 使用已加载的chunks
                    chunks = st.session_state.loaded_chunks
                    chunks_loaded = True
            except Exception as e:
                st.error(f"加载失败: {e}")

        # 显示chunks和分页
        if chunks_loaded and len(chunks) > 0:
            total_chunks = len(chunks)
            st.success(f"📄 {selected_view_doc} - 共 {total_chunks} 个chunks")

            # 分页设置
            chunks_per_page = 10
            total_pages = max(
                1, (total_chunks + chunks_per_page - 1) // chunks_per_page
            )
            current_page = st.session_state.current_chunk_page

            # 分页按钮
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("◀ 上一页"):
                    if current_page > 1:
                        st.session_state.current_chunk_page -= 1
                        st.rerun()
            with col2:
                st.markdown(f"### 第 {current_page} / {total_pages} 页")
            with col3:
                if st.button("下一页 ▶"):
                    if current_page < total_pages:
                        st.session_state.current_chunk_page += 1
                        st.rerun()

            # 计算当前页chunks
            start_idx = (current_page - 1) * chunks_per_page
            end_idx = start_idx + chunks_per_page
            current_chunks = chunks[start_idx:end_idx]

            # 显示每个chunk（展开盒）
            for chunk in current_chunks:
                chunk_idx = chunk.get("chunk_index", start_idx + 1)
                content = chunk.get("content", "")

                # 处理图片链接
                content = process_markdown_images(content, selected_view_doc)

                with st.expander(f"📝 Chunk {chunk_idx}", expanded=False):
                    st.markdown(content)


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
        # 新增：文档管理界面
        render_document_management()
        # 保留原有上传功能
        st.markdown("---")
        render_document_upload()
        # 删除功能（放在最下面）
        st.markdown("---")
        st.markdown("### 🗑️ 删除文档")
        render_delete_document()

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
