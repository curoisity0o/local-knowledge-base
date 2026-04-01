"""
Gradio 前端界面
本地知识库系统的统一前端，提供问答、文档管理和系统监控功能。

启动方式：
    python src/frontend/gradio_app.py
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

logger = logging.getLogger(__name__)

# API 基础 URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


# ─────────────────────────────────────────────────────────────
# API 辅助函数
# ─────────────────────────────────────────────────────────────


def _get(endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
    """GET 请求辅助"""
    try:
        resp = requests.get(f"{API_BASE_URL}{endpoint}", timeout=10, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("GET %s 失败: %s", endpoint, e)
        return None


def _post(endpoint: str, json: Optional[Dict] = None, files=None, data=None, timeout: int = 120) -> Optional[Dict[str, Any]]:
    """POST 请求辅助"""
    try:
        resp = requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=json,
            files=files,
            data=data,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("POST %s 失败: %s", endpoint, e)
        return None


# ─────────────────────────────────────────────────────────────
# 问答功能
# ─────────────────────────────────────────────────────────────


def query_knowledge_base(
    question: str,
    history: List[Dict],
    use_rag: bool = True,
    provider: str = "auto",
    top_k: int = 5,
    session_id: str = "",
) -> Tuple[List[Dict], str]:
    """向知识库提问，返回更新的历史和来源信息

    history 格式: [{"role": "user/assistant", "content": "..."}, ...]
    """
    if not question.strip():
        return history, "请输入问题"

    payload = {
        "question": question,
        "top_k": top_k,
        "provider": provider if provider != "auto" else None,
        "use_rag": use_rag,
    }

    # 优先使用 session_id（服务端管理历史）
    if session_id:
        payload["session_id"] = session_id
    else:
        # 向后兼容：前端传历史
        msg_history = []
        for msg in history[-10:]:  # 最近 10 条
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                msg_history.append({"role": role, "content": content})
        payload["history"] = msg_history

    data = _post("/api/v1/query", json=payload, timeout=180)

    if not data:
        answer = "❌ 请求失败，请检查 API 服务是否正常运行。"
        sources_text = ""
    else:
        answer = data.get("answer", "未获取到答案")
        sources = data.get("sources", [])
        images = data.get("images", [])

        # 构建来源文本（含图片）
        parts = []
        if images:
            img_lines = []
            for img in images:
                img_path = img.get("path", "")
                caption = img.get("caption", "")
                if img_path:
                    cap = f" {caption}" if caption else ""
                    img_lines.append(f"![{caption}]({img_path}){cap}")
            if img_lines:
                parts.append("### 📷 相关图片\n" + "\n\n".join(img_lines))

        if sources:
            source_lines = []
            for i, s in enumerate(sources, 1):
                src_name = Path(s.get("source", "未知")).name
                score = s.get("score")
                content_preview = s.get("content", "")
                score_text = f" (相关度: {score})" if score else ""
                content_text = f"\n> {content_preview[:120].replace(chr(10), ' ')}…" if content_preview else ""
                source_lines.append(f"**[{i}] {src_name}**{score_text}{content_text}")
            parts.append("### 📚 参考来源\n" + "\n\n".join(source_lines))
        else:
            parts.append("_未找到相关参考文档_")

        sources_text = "\n\n---\n\n".join(parts)

    history = history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    return history, sources_text


# ─────────────────────────────────────────────────────────────
# 文档管理功能
# ─────────────────────────────────────────────────────────────


def upload_and_process_file(file_obj) -> str:
    """上传并处理文件"""
    if file_obj is None:
        return "请选择文件"

    file_path = file_obj.name
    file_name = Path(file_path).name

    with open(file_path, "rb") as f:
        files = {"file": (file_name, f)}
        upload_data = _post("/api/v1/documents/upload", files=files)

    if not upload_data or not upload_data.get("success"):
        return f"❌ 上传失败: {upload_data}"

    process_data = _post("/api/v1/documents/process", json={"filenames": [file_name]})

    if not process_data:
        return f"❌ 处理失败，文件已上传但未入库"

    processed = process_data.get("processed_files", [])
    if processed:
        chunks = processed[0].get("chunks_count", 0)
        return f"✅ **{file_name}** 处理完成，生成 **{chunks}** 个检索片段"
    return f"✅ {file_name} 已上传并处理"


def list_documents() -> str:
    """列出知识库中的所有文档"""
    data = _get("/api/v1/documents/list")
    if not data:
        return "❌ 无法获取文档列表"

    docs = data.get("documents", [])
    if not docs:
        return "知识库为空，请先上传文档"

    lines = ["| 文件名 | 大小 | 片段数 |", "|--------|------|--------|"]
    for doc in docs:
        name = doc.get("filename", "未知")
        size_kb = doc.get("size", 0) // 1024
        chunks = doc.get("chunks_count", "?")
        lines.append(f"| {name} | {size_kb} KB | {chunks} |")

    return "\n".join(lines)


def delete_document(filename: str) -> str:
    """删除文档"""
    if not filename.strip():
        return "请输入要删除的文件名"

    data = _get(f"/api/v1/documents/list")
    if data:
        docs = [d.get("filename", "") for d in data.get("documents", [])]
        if filename not in docs:
            return f"❌ 文档 '{filename}' 不存在"

    result = requests.delete(f"{API_BASE_URL}/api/v1/documents/{filename}", timeout=30)
    if result.status_code == 200:
        return f"✅ '{filename}' 已删除"
    return f"❌ 删除失败: {result.text}"


# ─────────────────────────────────────────────────────────────
# 系统状态功能
# ─────────────────────────────────────────────────────────────


def get_system_stats() -> str:
    """获取完整系统状态（API + 文档统计 + 健康检查）"""
    lines = ["### 📊 系统状态"]

    # API 健康检查
    health = _get("/health")
    if health:
        status = health.get("status", "unknown")
        icon = "🟢" if status == "healthy" else "🔴"
        lines.append(f"{icon} **API 状态**: {status}")
    else:
        lines.append("🔴 **API 状态**: 不可达")

    # 文档统计
    stats = _get("/api/v1/documents/stats")
    if stats:
        total = stats.get("total_documents", 0)
        indexed = stats.get("indexed_documents", 0)
        total_size = stats.get("total_size", 0) / (1024 * 1024)
        lines.append(f"- **文档总数**: {total}")
        lines.append(f"- **已索引**: {indexed}")
        if total > 0:
            lines.append(f"- **索引率**: {indexed / total * 100:.0f}%")
        lines.append(f"- **存储大小**: {total_size:.1f} MB")

    # 向量存储
    vs_status = _get("/health/vectorstore")
    if vs_status:
        vs_ready = vs_status.get("ready", False)
        icon = "🟢" if vs_ready else "🔴"
        lines.append(f"{icon} **向量存储**: {'就绪' if vs_ready else '未就绪'}")

    # 本地模型
    local_status = _get("/health/local")
    if local_status:
        available = local_status.get("available", False)
        icon = "🟢" if available else "🔴"
        model = local_status.get("model", "未知")
        lines.append(f"{icon} **本地模型**: {model} ({'可用' if available else '不可用'})")

    return "\n".join(lines) if len(lines) > 1 else "❌ 无法获取状态信息"


def warmup_model() -> str:
    """预热模型"""
    data = _post("/api/v1/models/warmup", timeout=120)
    if data and data.get("success"):
        return "✅ 模型预热完成，后续问答会更快"
    return "❌ 预热失败，请检查 API 服务"


# ─────────────────────────────────────────────────────────────
# 会话管理功能
# ─────────────────────────────────────────────────────────────


def create_session_fn() -> str:
    """创建新会话，返回 session_id"""
    data = _post("/api/v1/sessions", json={"user_id": "default"})
    if data:
        return data.get("session_id", "")
    return ""


def clear_session_fn(session_id: str) -> Tuple[List[Dict], str, str]:
    """清空会话消息（保留会话）"""
    if session_id:
        _post(f"/api/v1/sessions/{session_id}/clear")
    return [], "_已清空_", session_id


def delete_session_fn(session_id: str) -> Tuple[List[Dict], str, str]:
    """删除会话"""
    if session_id:
        requests.delete(f"{API_BASE_URL}/api/v1/sessions/{session_id}", timeout=5)
    return [], "_会话已删除_", ""


# ─────────────────────────────────────────────────────────────
# Gradio 界面构建
# ─────────────────────────────────────────────────────────────


def build_interface():
    """构建 Gradio 界面"""
    try:
        import gradio as gr
    except ImportError:
        raise ImportError("Gradio 未安装，请运行: pip install gradio>=4.0.0")

    # ── 主题与样式 ──────────────────────────────────────────
    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "sans-serif"],
    )

    with gr.Blocks(
        theme=theme,
        title="本地知识库 · Local Knowledge Base",
        css="""
        .source-box { background: #f8f9fa; border-radius: 8px; padding: 12px; }
        footer { display: none !important; }
        """,
    ) as demo:

        # ── 页眉 ───────────────────────────────────────────
        gr.Markdown(
            """
            # 📚 本地知识库 · Local Knowledge Base
            基于 RAG + Agent 的智能文档问答系统 | [API 文档](http://localhost:8000/docs)
            """
        )

        # ── Tab: 问答（默认打开）────────────────────────────
        with gr.Tab("💬 智能问答"):
            session_state = gr.State("")

            with gr.Row():
                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(
                        label="对话",
                        height=500,
                        type="messages",
                        show_copy_button=True,
                    )
                    with gr.Row():
                        question_input = gr.Textbox(
                            placeholder="输入您的问题…（Shift+Enter 换行，Enter 发送）",
                            show_label=False,
                            scale=5,
                            lines=2,
                        )
                        submit_btn = gr.Button("发送 ▶", variant="primary", scale=1)
                    with gr.Row():
                        new_session_btn = gr.Button("➕ 新对话", size="sm")
                        clear_btn = gr.Button("🗑 清空对话", size="sm")
                        delete_session_btn = gr.Button("❌ 删除会话", size="sm")

                with gr.Column(scale=2):
                    gr.Markdown("### 🔍 参考来源")
                    sources_box = gr.Markdown(
                        value="_发送问题后，参考来源将显示在此处_",
                        elem_classes=["source-box"],
                    )
                    gr.Markdown("### ⚙️ 检索设置")
                    with gr.Row():
                        use_rag_toggle = gr.Checkbox(label="启用知识库检索", value=True)
                        provider_dropdown = gr.Dropdown(
                            choices=["auto", "local", "deepseek", "openai", "kimi"],
                            value="auto",
                            label="LLM 提供者",
                        )
                    top_k_slider = gr.Slider(
                        minimum=1, maximum=20, value=5, step=1,
                        label="检索文档数 (top_k)",
                    )

            # 事件绑定
            def _submit(question, history, use_rag, provider, top_k, session_id):
                if not question or not question.strip():
                    return history, sources_box.value
                return query_knowledge_base(question, history, use_rag, provider, int(top_k), session_id)

            question_input.submit(
                fn=_submit,
                inputs=[question_input, chatbot, use_rag_toggle, provider_dropdown, top_k_slider, session_state],
                outputs=[chatbot, sources_box],
            ).then(lambda: "", outputs=question_input)

            submit_btn.click(
                fn=_submit,
                inputs=[question_input, chatbot, use_rag_toggle, provider_dropdown, top_k_slider, session_state],
                outputs=[chatbot, sources_box],
            ).then(lambda: "", outputs=question_input)

            # 清空对话：重置 chatbot + session_state
            clear_btn.click(
                fn=clear_session_fn,
                inputs=[session_state],
                outputs=[chatbot, sources_box, session_state],
            )

            # 新建会话：创建新 session + 清空 chatbot
            new_session_btn.click(
                fn=create_session_fn,
                outputs=[session_state],
            ).then(fn=lambda: ([], "_新对话已创建_"), outputs=[chatbot, sources_box])

            # 删除会话：删除 + 清空 chatbot + 重置 session_state
            delete_session_btn.click(
                fn=delete_session_fn,
                inputs=[session_state],
                outputs=[chatbot, sources_box, session_state],
            )

        # ── Tab: 文档管理 ──────────────────────────────────
        with gr.Tab("📂 文档管理"):
            # 文档统计
            doc_stats = gr.Markdown("_加载中..._")

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 上传文档")
                    file_upload = gr.File(
                        label="选择文件",
                        file_types=[".pdf", ".docx", ".txt", ".md", ".html", ".csv"],
                        type="filepath",
                    )
                    upload_btn = gr.Button("上传并处理", variant="primary")
                    upload_status = gr.Markdown("_尚未上传文件_")

                with gr.Column():
                    gr.Markdown("### 知识库文档")
                    docs_display = gr.Markdown("_点击「刷新」查看文档列表_")
                    refresh_btn = gr.Button("🔄 刷新列表")

                    gr.Markdown("### 删除文档")
                    delete_input = gr.Textbox(
                        placeholder="输入文件名（含扩展名）", label="文件名"
                    )
                    delete_btn = gr.Button("🗑 删除", variant="stop")
                    delete_status = gr.Markdown("")

            upload_btn.click(
                fn=upload_and_process_file,
                inputs=file_upload,
                outputs=upload_status,
            ).then(fn=list_documents, outputs=docs_display).then(fn=get_doc_stats, outputs=doc_stats)

            refresh_btn.click(fn=list_documents, outputs=docs_display)

            delete_btn.click(
                fn=delete_document,
                inputs=delete_input,
                outputs=delete_status,
            ).then(fn=list_documents, outputs=docs_display).then(fn=get_doc_stats, outputs=doc_stats)

            # 页面加载时自动获取文档列表和统计
            demo.load(fn=get_doc_stats, outputs=doc_stats)

        # ── Tab: 系统状态 ──────────────────────────────────
        with gr.Tab("📊 系统状态"):
            status_display = gr.Markdown("_加载中..._")
            with gr.Row():
                refresh_status_btn = gr.Button("🔄 刷新状态")
                warmup_btn = gr.Button("🔥 预热模型", variant="secondary")

            refresh_status_btn.click(fn=get_system_stats, outputs=status_display)
            warmup_btn.click(fn=warmup_model, outputs=status_display)

            # 页面加载时自动刷新
            demo.load(fn=get_system_stats, outputs=status_display)

    return demo


def get_doc_stats() -> str:
    """获取文档统计摘要"""
    stats = _get("/api/v1/documents/stats")
    if not stats:
        return "❌ 无法获取文档统计"
    total = stats.get("total_documents", 0)
    indexed = stats.get("indexed_documents", 0)
    total_size = stats.get("total_size", 0) / (1024 * 1024)
    return f"📊 **{indexed}/{total}** 个文档已索引 · {total_size:.1f} MB"


# ─────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────


def launch(
    server_name: str = "0.0.0.0",
    server_port: int = 7860,
    share: bool = False,
    inbrowser: bool = False,
) -> None:
    """启动 Gradio 服务"""
    logging.basicConfig(level=logging.INFO)
    demo = build_interface()
    demo.launch(
        server_name=server_name,
        server_port=server_port,
        share=share,
        inbrowser=inbrowser,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="本地知识库 Gradio 前端")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=7860, help="端口号")
    parser.add_argument("--share", action="store_true", help="生成公网分享链接")
    parser.add_argument("--api-url", default="http://localhost:8000", help="后端 API 地址")
    args = parser.parse_args()

    API_BASE_URL = args.api_url
    launch(server_name=args.host, server_port=args.port, share=args.share)
