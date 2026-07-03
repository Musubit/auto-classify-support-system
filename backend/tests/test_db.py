"""SQLite 会话持久化 + RESTful API 集成测试。

使用临时数据库文件，不影响真实数据。
"""

import time
import uuid

import pytest

import app.services.db as db


# ─── 数据库初始化 ──────────────────────────────────────────


class TestInitDB:
    """init_db() — 幂等建表。"""

    def test_db_file_created(self, temp_db_path):
        """数据库文件应被创建。"""
        assert temp_db_path.exists()

    def test_init_db_idempotent(self, temp_db_path):
        """重复调用 init_db() 不抛异常。"""
        db.init_db()  # 不应抛异常

    def test_wal_mode(self, temp_db_path):
        """WAL 模式应已启用。"""
        conn = db._get_conn()
        try:
            row = conn.execute("PRAGMA journal_mode").fetchone()
            assert row[0].upper() == "WAL"
        finally:
            conn.close()


# ─── 会话 CRUD ─────────────────────────────────────────────


class TestEnsureSession:
    """ensure_session() — 创建/更新会话。"""

    def test_create_new_session(self, temp_db_path):
        """首次 ensure_session 应创建新行。"""
        sid = str(uuid.uuid4())
        db.ensure_session(sid, title="测试会话")

        session = db.get_session(sid)
        assert session is not None
        assert session["title"] == "测试会话"

    def test_create_session_default_title(self, temp_db_path):
        """未提供标题时默认为「新对话」。"""
        sid = str(uuid.uuid4())
        db.ensure_session(sid)
        session = db.get_session(sid)
        assert session["title"] == "新对话"

    def test_idempotent(self, temp_db_path):
        """重复 ensure_session 不创建重复行。"""
        sid = str(uuid.uuid4())
        db.ensure_session(sid, title="初始标题")
        db.ensure_session(sid, title="新标题")

        sessions = db.get_sessions()
        # 应有且仅有一条
        session_ids = [s["id"] for s in sessions if s["id"] == sid]
        assert len(session_ids) == 1


class TestSaveMessage:
    """save_message() — 保存消息。"""

    @pytest.fixture
    def session_id(self, temp_db_path):
        sid = str(uuid.uuid4())
        db.ensure_session(sid, title="消息测试")
        return sid

    def test_save_user_message(self, session_id):
        """保存用户消息。"""
        msg_id = str(uuid.uuid4())
        db.save_message(msg_id, session_id, "user", "怎么退货？")
        messages = db.get_session_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["text"] == "怎么退货？"

    def test_save_assistant_with_metadata(self, session_id):
        """保存带 intent/sentiment 的助手消息。"""
        msg_id = str(uuid.uuid4())
        db.save_message(
            msg_id, session_id, "assistant", "好的，请提供订单号",
            intent_label="refund_inquiry",
            intent_confidence=0.92,
            sentiment_label="neutral",
            sentiment_score=0.65,
        )
        messages = db.get_session_messages(session_id)
        assert len(messages) == 1
        msg = messages[0]
        assert msg["intent_label"] == "refund_inquiry"
        assert msg["intent_confidence"] == 0.92
        assert msg["sentiment_label"] == "neutral"

    def test_multiple_messages_order(self, session_id):
        """消息应按创建时间正序。"""
        for i, role in enumerate(["user", "assistant", "user", "assistant"]):
            db.save_message(str(uuid.uuid4()), session_id, role, f"msg{i}")
            time.sleep(0.01)  # 确保时间戳不同

        messages = db.get_session_messages(session_id)
        assert len(messages) == 4
        assert [m["role"] for m in messages] == [
            "user", "assistant", "user", "assistant"
        ]

    def test_role_constraint(self, session_id):
        """非法 role 应抛异常。"""
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            db.save_message(str(uuid.uuid4()), session_id, "admin", "test")


class TestGetSessions:
    """get_sessions() — 会话列表。"""

    def test_empty(self, temp_db_path):
        """无会话时返回空列表。"""
        sessions = db.get_sessions()
        assert sessions == []

    def test_returns_all_sessions(self, temp_db_path):
        """返回所有创建的会话。"""
        s1 = str(uuid.uuid4())
        s2 = str(uuid.uuid4())
        db.ensure_session(s1, title="会话A")
        time.sleep(0.01)
        db.ensure_session(s2, title="会话B")

        sessions = db.get_sessions()
        ids = [s["id"] for s in sessions]
        assert s1 in ids
        assert s2 in ids

    def test_message_count(self, temp_db_path):
        """message_count 应准确。"""
        sid = str(uuid.uuid4())
        db.ensure_session(sid, title="计数测试")
        for _ in range(3):
            db.save_message(str(uuid.uuid4()), sid, "user", "test")

        sessions = db.get_sessions()
        assert sessions[0]["message_count"] == 3

    def test_message_count_zero(self, temp_db_path):
        """无消息的会话 message_count 为 0。"""
        sid = str(uuid.uuid4())
        db.ensure_session(sid)
        sessions = db.get_sessions()
        assert sessions[0]["message_count"] == 0


class TestGetSession:
    """get_session() — 单会话查询。"""

    def test_get_existing(self, temp_db_path):
        sid = str(uuid.uuid4())
        db.ensure_session(sid, title="查询测试")
        s = db.get_session(sid)
        assert s is not None
        assert s["id"] == sid
        assert "created_at" in s
        assert "updated_at" in s

    def test_get_nonexistent(self, temp_db_path):
        """不存在的会话返回 None。"""
        s = db.get_session("nonexistent-id")
        assert s is None


class TestGetSessionMessages:
    """get_session_messages() — 会话消息列表。"""

    def test_empty_session(self, temp_db_path):
        sid = str(uuid.uuid4())
        db.ensure_session(sid)
        messages = db.get_session_messages(sid)
        assert messages == []

    def test_nonexistent_session(self, temp_db_path):
        messages = db.get_session_messages("nonexistent")
        assert messages == []


class TestDeleteSession:
    """delete_session() — 级联删除。"""

    def test_delete_existing(self, temp_db_path):
        sid = str(uuid.uuid4())
        db.ensure_session(sid, title="待删除")
        db.save_message(str(uuid.uuid4()), sid, "user", "hello")

        ok = db.delete_session(sid)
        assert ok is True
        assert db.get_session(sid) is None

    def test_delete_cascades_messages(self, temp_db_path):
        """删除会话应级联删除消息。"""
        sid = str(uuid.uuid4())
        db.ensure_session(sid)
        db.save_message(str(uuid.uuid4()), sid, "user", "hello")

        db.delete_session(sid)
        messages = db.get_session_messages(sid)
        assert messages == []

    def test_delete_nonexistent(self, temp_db_path):
        """不存在返回 False。"""
        ok = db.delete_session("nonexistent")
        assert ok is False


# ─── Session API 端点测试 ──────────────────────────────────


class TestSessionAPI:
    """Flask 测试客户端 — 会话 RESTful API。"""

    @pytest.fixture
    def client(self, temp_db_path):
        """提供 Flask 测试客户端，同时 patch 数据库路径。"""
        from app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_list_empty(self, client):
        """空列表返回。"""
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert isinstance(data["data"], list)

    def test_create_and_list(self, client):
        """通过会话发送流程创建会话后，列表应包含该会话。"""
        sid = str(uuid.uuid4())
        # 直接写入 DB，模拟 orchestrator 行为
        db.ensure_session(sid, title="API 测试")
        db.save_message(str(uuid.uuid4()), sid, "user", "你好")
        db.save_message(str(uuid.uuid4()), sid, "assistant", "您好！")

        resp = client.get("/api/sessions")
        data = resp.get_json()
        assert len(data["data"]) >= 1

        session_ids = [s["id"] for s in data["data"]]
        assert sid in session_ids

    def test_get_session_detail(self, client):
        """单会话详情含消息数组。"""
        sid = str(uuid.uuid4())
        db.ensure_session(sid, title="详情测试")
        db.save_message(str(uuid.uuid4()), sid, "user", "test message")

        resp = client.get(f"/api/sessions/{sid}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "session" in data["data"]
        assert "messages" in data["data"]
        assert len(data["data"]["messages"]) == 1

    def test_get_nonexistent_session(self, client):
        """404。"""
        resp = client.get("/api/sessions/nonexistent-id")
        assert resp.status_code == 404

    def test_delete_session(self, client):
        """删除后再次查询应 404。"""
        sid = str(uuid.uuid4())
        db.ensure_session(sid, title="删除测试")

        resp = client.delete(f"/api/sessions/{sid}")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "success"

        # 确认已删
        resp2 = client.get(f"/api/sessions/{sid}")
        assert resp2.status_code == 404

    def test_delete_nonexistent(self, client):
        """删除不存在会话返回 404。"""
        resp = client.delete("/api/sessions/nonexistent")
        assert resp.status_code == 404
