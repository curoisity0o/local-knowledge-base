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
st.markdown("""
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
""", unsafe_allow_html=True)

# 初始化会话状态
def init_session_state():
    """初始化会话状态"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}
    
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = "local"
    
    if 'vector_store_initialized' not in st.session_state:
        st.session_state.vector_store_initialized = False
    
    if 'llm_manager' not in st.session_state:
        st.session_state.llm_manager = None
    
    if 'vector_store' not in st.session_state:
        st.session_state.vector_store = None
    
    if 'document_processor' not in st.session_state:
        st.session_state.document_processor = None

# 初始化组件
def init_components():
    """初始化核心组件（延迟加载）"""
    try:
        from core.document_processor import DocumentProcessor
        from core.vector_store import SimpleVectorStore
        from core.llm_manager import LLMManager
        
        if st.session_state.document_processor is None:
            st.session_state.document_processor = DocumentProcessor()
            logger.info("文档处理器初始化完成")
        
        if st.session_state.vector_store is None:
            st.session_state.vector_store = SimpleVectorStore()
            logger.info("向量存储初始化完成")
        
        if st.session_state.llm_manager is None:
            st.session_state.llm_manager = LLMManager()
            logger.info("LLM管理器初始化完成")
            
        return True
    except Exception as e:
        logger.error(f"初始化组件失败: {e}")
        st.error(f"初始化组件失败: {e}")
        return False

# 页面标题
def render_header():
    """渲染页面标题"""
    st.markdown('<h1 class="main-header">📚 本地知识库系统</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">基于 LangChain + RAG + Agent 的智能知识管理平台</p>', unsafe_allow_html=True)
    
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
            ["auto", "local", "api"],
            index=0,
            help="auto: 自动选择, local: 本地模型, api: 云API"
        )
        st.session_state.selected_model = model_option
        
        # 系统状态
        st.markdown("### 📊 系统状态")
        
        if st.button("🔄 检查组件状态", use_container_width=True):
            components_ready = init_components()
            if components_ready:
                st.success("所有组件已就绪")
            else:
                st.error("组件初始化失败")
        
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
            help="支持 PDF, TXT, DOCX, MD, CSV, HTML 格式"
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
                    with st.spinner("处理文档中..."):
                        try:
                            # 保存上传的文件
                            raw_docs_dir = Path("./data/raw_docs")
                            raw_docs_dir.mkdir(parents=True, exist_ok=True)
                            
                            for uploaded_file in uploaded_files:
                                file_path = raw_docs_dir / uploaded_file.name
                                with open(file_path, "wb") as f:
                                    f.write(uploaded_file.getbuffer())
                            
                            # 初始化组件
                            if init_components():
                                processor = st.session_state.document_processor
                                documents = processor.process_directory(str(raw_docs_dir))
                                
                                # 添加到向量存储
                                vector_store = st.session_state.vector_store
                                ids = vector_store.add_documents(documents)
                                
                                st.session_state.vector_store_initialized = True
                                st.success(f"文档处理完成！生成 {len(documents)} 个 chunks，添加到向量存储")
                            else:
                                st.error("组件初始化失败，无法处理文档")
                        except Exception as e:
                            logger.error(f"文档处理失败: {e}")
                            st.error(f"文档处理失败: {e}")
        
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
                    
                    # 初始化组件
                    if not init_components():
                        st.error("组件初始化失败")
                        return
                    
                    # 检索相关文档
                    vector_store = st.session_state.vector_store
                    retrieved_docs = vector_store.similarity_search(user_input, k=4)
                    
                    # 构建上下文
                    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
                    
                    # 生成回答
                    llm_manager = st.session_state.llm_manager
                    result = llm_manager.generate(
                        prompt=user_input,
                        context=context,
                        provider=st.session_state.selected_model
                    )
                    
                    answer = result["text"]
                    
                    # 添加助手消息
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": answer,
                        "sources": [doc.metadata.get("source", "未知") for doc in retrieved_docs]
                    })
                    
                    # 显示回答
                    with chat_container:
                        with st.chat_message("assistant"):
                            st.markdown(answer)
                            with st.expander("查看参考来源"):
                                for i, doc in enumerate(retrieved_docs):
                                    source = doc.metadata.get("source", "未知")
                                    st.markdown(f"{i+1}. {source}")
                                    st.markdown(f"   {doc.page_content[:200]}...")
                    
                except Exception as e:
                    logger.error(f"生成回答失败: {e}")
                    error_msg = f"抱歉，生成回答时出现错误: {str(e)}"
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
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
    st.markdown("""
    <div style="text-align: center; color: #718096; font-size: 0.9rem;">
        <p>本地知识库系统 v1.0.0 | 基于 LangChain + RAG + Agent 架构 | 设计用于中英文混合文档处理</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()