"""
会话管理器
基于 SQLite 的会话持久化，支持多会话管理、历史记录存储与检索
"""

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 数据库文件位置
_DB_DIR = Path(__file__).parent.parent.parent / "data"
_DB_PATH = _DB_DIR / "sessions.db"

_lock = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    """获取数据库连接（线程安全）"""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db():
    """初始化数据库表"""
    with _lock:
        conn = _get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL DEFAULT '新对话',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    sources TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_id
                    ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id
                    ON sessions(user_id, updated_at DESC);
            """)
            conn.commit()
        finally:
            conn.close()


class SessionManager:
    """会话管理器 — 管理多轮对话的持久化存储"""

    def __init__(self):
        _init_db()

    def create_session(
        self,
        user_id: str = "default",
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建新会话

        Args:
            user_id: 用户标识
            title: 会话标题，None 时自动生成

        Returns:
            {"session_id": str, "title": str, "created_at": str, "messages": []}
        """
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        title = title or "新对话"

        with _lock:
            conn = _get_connection()
            try:
                conn.execute(
                    "INSERT INTO sessions (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, user_id, title, now, now),
                )
                conn.commit()
            finally:
                conn.close()

        logger.info(f"创建会话: {session_id[:8]}... (用户: {user_id})")
        return {
            "session_id": session_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详情（含消息列表）"""
        conn = _get_connection()
        try:
            row = conn.execute(
                "SELECT id, user_id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()

            if not row:
                return None

            messages = conn.execute(
                "SELECT role, content, sources, created_at FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()

            return {
                "session_id": row["id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "messages": [
                    {
                        "role": m["role"],
                        "content": m["content"],
                        "sources": json.loads(m["sources"]) if m["sources"] else None,
                        "created_at": m["created_at"],
                    }
                    for m in messages
                ],
            }
        finally:
            conn.close()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """向会话添加消息

        Args:
            session_id: 会话 ID
            role: 角色 (user/assistant)
            content: 消息内容
            sources: 引用来源列表（仅 assistant 消息）

        Returns:
            新添加的消息记录
        """
        now = datetime.now().isoformat()
        sources_json = json.dumps(sources, ensure_ascii=False) if sources else None

        with _lock:
            conn = _get_connection()
            try:
                # 验证会话存在
                session = conn.execute(
                    "SELECT id FROM sessions WHERE id = ?", (session_id,)
                ).fetchone()
                if not session:
                    raise ValueError(f"会话不存在: {session_id}")

                # 自动更新会话标题（用第一条用户消息，在插入前检查计数）
                if role == "user":
                    existing_count = conn.execute(
                        "SELECT COUNT(*) FROM messages WHERE session_id = ? AND role = 'user'",
                        (session_id,),
                    ).fetchone()[0]
                    if existing_count == 0:
                        auto_title = content[:50] + ("..." if len(content) > 50 else "")
                        conn.execute(
                            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                            (auto_title, now, session_id),
                        )

                cursor = conn.execute(
                    "INSERT INTO messages (session_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, role, content, sources_json, now),
                )

                # 更新会话时间
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (now, session_id),
                )
                conn.commit()

                return {
                    "id": cursor.lastrowid,
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "sources": sources,
                    "created_at": now,
                }
            finally:
                conn.close()

    def get_history(
        self,
        session_id: str,
        max_turns: int = 0,
    ) -> List[Dict[str, str]]:
        """获取对话历史（用于 RAG 上下文）

        Args:
            session_id: 会话 ID
            max_turns: 最大轮数，0 表示全部

        Returns:
            [{"role": "user/assistant", "content": "..."}, ...]
        """
        conn = _get_connection()
        try:
            query = "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id"
            params: tuple = (session_id,)

            if max_turns > 0:
                query += " DESC LIMIT ?"
                params = (session_id, max_turns * 2)
                rows = conn.execute(query, params).fetchall()
                rows = list(reversed(rows))
            else:
                rows = conn.execute(query, params).fetchall()

            return [{"role": r["role"], "content": r["content"]} for r in rows]
        finally:
            conn.close()

    def list_sessions(
        self,
        user_id: str = "default",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """列出用户的所有会话（按更新时间倒序）"""
        conn = _get_connection()
        try:
            rows = conn.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) as message_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE s.user_id = ?
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()

            return [
                {
                    "session_id": r["id"],
                    "title": r["title"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "message_count": r["message_count"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其所有消息"""
        with _lock:
            conn = _get_connection()
            try:
                cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"删除会话: {session_id[:8]}...")
                return deleted
            finally:
                conn.close()

    def clear_history(self, session_id: str) -> bool:
        """清空会话消息（保留会话本身）"""
        with _lock:
            conn = _get_connection()
            try:
                # 验证会话存在
                session = conn.execute(
                    "SELECT id FROM sessions WHERE id = ?", (session_id,)
                ).fetchone()
                if not session:
                    return False

                conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                now = datetime.now().isoformat()
                conn.execute(
                    "UPDATE sessions SET title = '新对话', updated_at = ? WHERE id = ?",
                    (now, session_id),
                )
                conn.commit()
                logger.info(f"清空会话历史: {session_id[:8]}...")
                return True
            finally:
                conn.close()

    def update_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        with _lock:
            conn = _get_connection()
            try:
                cursor = conn.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                    (title, datetime.now().isoformat(), session_id),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()


# 单例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取会话管理器实例（延迟初始化）"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
