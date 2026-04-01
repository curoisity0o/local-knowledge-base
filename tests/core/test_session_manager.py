"""
SessionManager 会话管理器测试
"""

import os
import tempfile
import time
import pytest
from unittest.mock import patch

from src.core.session_manager import SessionManager, _init_db


@pytest.fixture
def tmp_session_manager(tmp_path):
    """使用临时数据库的 SessionManager"""
    db_path = tmp_path / "test_sessions.db"

    with patch("src.core.session_manager._DB_PATH", db_path):
        manager = SessionManager()
        yield manager


class TestSessionManager:
    """会话管理器测试"""

    def test_create_session(self, tmp_session_manager):
        """测试创建会话"""
        session = tmp_session_manager.create_session()
        assert "session_id" in session
        assert session["title"] == "新对话"
        assert session["messages"] == []
        assert "created_at" in session

    def test_create_session_with_title(self, tmp_session_manager):
        """测试创建带标题的会话"""
        session = tmp_session_manager.create_session(title="测试对话")
        assert session["title"] == "测试对话"

    def test_create_session_with_user(self, tmp_session_manager):
        """测试为不同用户创建会话"""
        s1 = tmp_session_manager.create_session(user_id="user1")
        s2 = tmp_session_manager.create_session(user_id="user2")
        assert s1["session_id"] != s2["session_id"]

    def test_get_session(self, tmp_session_manager):
        """测试获取会话"""
        created = tmp_session_manager.create_session()
        session = tmp_session_manager.get_session(created["session_id"])
        assert session is not None
        assert session["session_id"] == created["session_id"]

    def test_get_session_not_found(self, tmp_session_manager):
        """测试获取不存在的会话"""
        session = tmp_session_manager.get_session("non-existent-id")
        assert session is None

    def test_add_message(self, tmp_session_manager):
        """测试添加消息"""
        created = tmp_session_manager.create_session()
        sid = created["session_id"]

        msg = tmp_session_manager.add_message(sid, "user", "你好")
        assert msg["role"] == "user"
        assert msg["content"] == "你好"
        assert msg["session_id"] == sid

        # 验证会话消息数
        session = tmp_session_manager.get_session(sid)
        assert len(session["messages"]) == 1

    def test_add_message_auto_title(self, tmp_session_manager):
        """测试首条用户消息自动设置标题"""
        session = tmp_session_manager.create_session()
        sid = session["session_id"]

        tmp_session_manager.add_message(sid, "user", "介绍一下 DeepSeek-V2")
        updated = tmp_session_manager.get_session(sid)
        assert "DeepSeek-V2" in updated["title"]

    def test_add_message_with_sources(self, tmp_session_manager):
        """测试带引用来源的消息"""
        session = tmp_session_manager.create_session()
        sid = session["session_id"]

        sources = [{"source": "doc1.pdf", "score": 0.9}]
        msg = tmp_session_manager.add_message(
            sid, "assistant", "根据文档...", sources=sources
        )

        updated = tmp_session_manager.get_session(sid)
        assert updated["messages"][0]["sources"] == sources

    def test_get_history(self, tmp_session_manager):
        """测试获取对话历史"""
        session = tmp_session_manager.create_session()
        sid = session["session_id"]

        tmp_session_manager.add_message(sid, "user", "问题1")
        tmp_session_manager.add_message(sid, "assistant", "回答1")
        tmp_session_manager.add_message(sid, "user", "问题2")
        tmp_session_manager.add_message(sid, "assistant", "回答2")

        history = tmp_session_manager.get_history(sid)
        assert len(history) == 4
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "问题1"

    def test_get_history_with_limit(self, tmp_session_manager):
        """测试限制返回的历史轮数"""
        session = tmp_session_manager.create_session()
        sid = session["session_id"]

        for i in range(4):
            tmp_session_manager.add_message(sid, "user", f"Q{i}")
            tmp_session_manager.add_message(sid, "assistant", f"A{i}")

        # max_turns=1 应返回最近 2 条消息（1 轮 = 1 对）
        history = tmp_session_manager.get_history(sid, max_turns=1)
        assert len(history) == 2
        assert history[0]["content"] == "Q3"
        assert history[1]["content"] == "A3"

    def test_list_sessions(self, tmp_session_manager):
        """测试列出会话"""
        tmp_session_manager.create_session(user_id="test_user")
        tmp_session_manager.create_session(user_id="test_user")
        tmp_session_manager.create_session(user_id="other_user")

        sessions = tmp_session_manager.list_sessions(user_id="test_user")
        assert len(sessions) == 2

    def test_list_sessions_sorted(self, tmp_session_manager):
        """测试会话按更新时间倒序排列"""
        s1 = tmp_session_manager.create_session()
        time.sleep(0.05)  # 确保时间戳不同
        s2 = tmp_session_manager.create_session()
        time.sleep(0.05)
        tmp_session_manager.add_message(s2["session_id"], "user", "msg")

        sessions = tmp_session_manager.list_sessions()
        # s2 更新时间更晚（有消息），应排前面
        assert sessions[0]["session_id"] == s2["session_id"]

    def test_delete_session(self, tmp_session_manager):
        """测试删除会话"""
        session = tmp_session_manager.create_session()
        sid = session["session_id"]

        tmp_session_manager.add_message(sid, "user", "test")
        deleted = tmp_session_manager.delete_session(sid)
        assert deleted is True

        # 验证会话已删除
        assert tmp_session_manager.get_session(sid) is None

    def test_delete_session_not_found(self, tmp_session_manager):
        """测试删除不存在的会话"""
        deleted = tmp_session_manager.delete_session("non-existent")
        assert deleted is False

    def test_clear_history(self, tmp_session_manager):
        """测试清空会话历史"""
        session = tmp_session_manager.create_session()
        sid = session["session_id"]

        tmp_session_manager.add_message(sid, "user", "test")
        tmp_session_manager.add_message(sid, "assistant", "response")

        cleared = tmp_session_manager.clear_history(sid)
        assert cleared is True

        updated = tmp_session_manager.get_session(sid)
        assert len(updated["messages"]) == 0
        assert updated["title"] == "新对话"

    def test_clear_history_not_found(self, tmp_session_manager):
        """测试清空不存在的会话"""
        cleared = tmp_session_manager.clear_history("non-existent")
        assert cleared is False

    def test_update_title(self, tmp_session_manager):
        """测试更新会话标题"""
        session = tmp_session_manager.create_session()
        updated = tmp_session_manager.update_title(session["session_id"], "新标题")
        assert updated is True

        fetched = tmp_session_manager.get_session(session["session_id"])
        assert fetched["title"] == "新标题"

    def test_add_message_invalid_session(self, tmp_session_manager):
        """测试向不存在的会话添加消息"""
        with pytest.raises(ValueError, match="会话不存在"):
            tmp_session_manager.add_message("non-existent", "user", "test")

    def test_session_isolation(self, tmp_session_manager):
        """测试多会话隔离"""
        s1 = tmp_session_manager.create_session()
        s2 = tmp_session_manager.create_session()

        tmp_session_manager.add_message(s1["session_id"], "user", "session1的问题")
        tmp_session_manager.add_message(s2["session_id"], "user", "session2的问题")

        h1 = tmp_session_manager.get_history(s1["session_id"])
        h2 = tmp_session_manager.get_history(s2["session_id"])

        assert len(h1) == 1
        assert len(h2) == 1
        assert h1[0]["content"] != h2[0]["content"]
