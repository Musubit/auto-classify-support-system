"""数据分析 API 测试 — get_analytics() + GET /api/analytics。"""

import uuid

import pytest

import app.services.db as db


# ─── DB 层测试 ──────────────────────────────────────────────


class TestGetAnalyticsEmpty:
    """空数据库时 get_analytics() 返回全零。"""

    def test_empty_db_returns_zeros(self, temp_db_path):
        """无数据时所有计数为 0，列表为空。"""
        result = db.get_analytics()

        assert result["total_sessions"] == 0
        assert result["total_messages"] == 0
        assert result["average_session_depth"] == 0.0
        assert result["today_active_sessions"] == 0
        assert result["intent_distribution"] == []
        assert result["sentiment_distribution"] == []
        assert result["daily_trend"] == []
        assert result["hourly_activity"] == []

    def test_structure_is_correct(self, temp_db_path):
        """返回的 dict 包含所有 8 个字段。"""
        result = db.get_analytics()
        expected_keys = {
            "total_sessions", "total_messages", "average_session_depth",
            "today_active_sessions", "intent_distribution",
            "sentiment_distribution", "daily_trend", "hourly_activity",
        }
        assert set(result.keys()) == expected_keys


class TestGetAnalyticsWithData:
    """有数据时 get_analytics() 计数正确。"""

    @pytest.fixture
    def seed(self, temp_db_path):
        """创建 3 个会话 + 若干消息，覆盖多种意图和情感。"""
        sessions = [str(uuid.uuid4()) for _ in range(3)]
        for sid in sessions:
            db.ensure_session(sid)
            db.save_message(str(uuid.uuid4()), sid, "user", "我要退货")
            db.save_message(
                str(uuid.uuid4()), sid, "assistant", "您好，请提供订单号",
                intent_label="refund_inquiry", intent_confidence=0.92,
                sentiment_label="neutral", sentiment_score=0.50,
            )
        # 第二个会话额外加一条投诉消息
        db.save_message(str(uuid.uuid4()), sessions[1], "user", "太差了")
        db.save_message(
            str(uuid.uuid4()), sessions[1], "assistant", "抱歉给您带来不便",
            intent_label="complaint", intent_confidence=0.88,
            sentiment_label="negative", sentiment_score=0.95,
        )
        return sessions

    def test_total_counts(self, temp_db_path, seed):
        """3 个会话，8 条消息（4 user + 4 assistant）。"""
        result = db.get_analytics()
        assert result["total_sessions"] == 3
        assert result["total_messages"] == 8
        assert result["average_session_depth"] == round(8 / 3, 1)

    def test_intent_distribution(self, temp_db_path, seed):
        """4 条 assistant 消息：3 条 refund_inquiry，1 条 complaint。"""
        result = db.get_analytics()
        intents = {i["intent_label"]: i["count"] for i in result["intent_distribution"]}
        assert intents["refund_inquiry"] == 3
        assert intents["complaint"] == 1

    def test_sentiment_distribution(self, temp_db_path, seed):
        """4 条 assistant：3 条 neutral，1 条 negative。"""
        result = db.get_analytics()
        sentiments = {s["sentiment_label"]: s["count"] for s in result["sentiment_distribution"]}
        assert sentiments["neutral"] == 3
        assert sentiments["negative"] == 1

    def test_hourly_activity(self, temp_db_path, seed):
        """小时活跃列表不为空，hour 在 0-23 范围内。"""
        result = db.get_analytics()
        for item in result["hourly_activity"]:
            assert 0 <= item["hour"] <= 23
            assert item["count"] > 0

    def test_daily_trend(self, temp_db_path, seed):
        """daily_trend 至少有今天的记录。"""
        result = db.get_analytics()
        assert len(result["daily_trend"]) >= 1
        for item in result["daily_trend"]:
            assert "day" in item
            assert item["count"] > 0

    def test_today_active_sessions(self, temp_db_path, seed):
        """今天活跃会话数应为 3。"""
        result = db.get_analytics()
        assert result["today_active_sessions"] == 3


# ─── API 层测试 ──────────────────────────────────────────────


class TestAnalyticsAPI:
    """Flask 测试客户端 — GET /api/analytics。"""

    @pytest.fixture
    def client(self, temp_db_path):
        """提供 Flask 测试客户端。"""
        from app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_get_200(self, client):
        """返回 200 且 JSON 结构正确。"""
        resp = client.get("/api/analytics")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "total_sessions" in data["data"]
        assert "total_messages" in data["data"]

    def test_get_with_data(self, client):
        """有数据时返回正确计数。"""
        sid = str(uuid.uuid4())
        db.ensure_session(sid)
        db.save_message(str(uuid.uuid4()), sid, "user", "你好")
        db.save_message(
            str(uuid.uuid4()), sid, "assistant", "您好！",
            intent_label="greeting", intent_confidence=0.99,
            sentiment_label="positive", sentiment_score=0.90,
        )

        resp = client.get("/api/analytics")
        data = resp.get_json()
        assert data["data"]["total_sessions"] >= 1
        assert data["data"]["total_messages"] >= 2

    def test_response_json_structure(self, client):
        """验证 JSON 响应结构完整性。"""
        resp = client.get("/api/analytics")
        data = resp.get_json()

        assert data["status"] == "success"
        assert data["message"] == "ok"
        inner = data["data"]
        assert isinstance(inner["total_sessions"], int)
        assert isinstance(inner["total_messages"], int)
        assert isinstance(inner["average_session_depth"], (int, float))
        assert isinstance(inner["today_active_sessions"], int)
        assert isinstance(inner["intent_distribution"], list)
        assert isinstance(inner["sentiment_distribution"], list)
        assert isinstance(inner["daily_trend"], list)
        assert isinstance(inner["hourly_activity"], list)
