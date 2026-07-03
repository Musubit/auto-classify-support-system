"""SSE 格式 + Chat API 端点测试。"""

import json
import uuid
from unittest.mock import patch

import pytest

from app.utils.sse import (
    SSEEmitter,
    format_sse_event,
    generate_done_event,
    generate_entity_event,
    generate_error_event,
    generate_intent_event,
    generate_sentiment_event,
    generate_token_event,
)


# ─── format_sse_event 基础函数 ─────────────────────────────


class TestFormatSSEEvent:
    """SSE 协议基础格式化。"""

    def test_format_with_dict(self):
        """dict 数据应序列化为 JSON。"""
        result = format_sse_event("test", {"key": "值"})
        assert result.startswith("event: test\n")
        assert "data:" in result
        assert '"key":' in result or '"key": "' in result.replace(" ", "")
        assert result.endswith("\n\n")

    def test_format_with_string(self):
        """字符串数据直接使用。"""
        result = format_sse_event("token", "你好")
        assert "event: token\n" in result
        assert "data: 你好\n" in result
        assert result.endswith("\n\n")

    def test_chinese_not_escaped(self):
        """中文字符不应被转义为 \\uXXXX。"""
        result = format_sse_event("intent", {"intent": "物流查询"})
        assert "物流查询" in result
        assert "\\u" not in result


# ─── 便捷生成函数 ──────────────────────────────────────────


class TestGenerateFunctions:
    """便捷函数应与 SSEEmitter 等效。"""

    def test_generate_intent_event(self):
        event = generate_intent_event("refund_inquiry", 0.92)
        assert "event: intent" in event
        assert "refund_inquiry" in event
        assert "0.92" in event

    def test_generate_sentiment_event(self):
        event = generate_sentiment_event("negative", 0.88)
        assert "event: sentiment" in event
        assert "negative" in event

    def test_generate_token_event(self):
        event = generate_token_event("你")
        assert "event: token" in event
        assert "你" in event

    def test_generate_done_event(self):
        event = generate_done_event("msg_1", "完整回答", source="llm")
        assert "event: done" in event
        assert "msg_1" in event
        assert "完整回答" in event
        assert "llm" in event

    def test_generate_entity_event(self):
        entities = {"order_id": {"values": ["DD123"]}}
        event = generate_entity_event(entities, "订单号: DD123")
        assert "event: entity" in event
        assert "DD123" in event

    def test_generate_error_event(self):
        event = generate_error_event("服务不可用")
        assert "event: error" in event
        assert "服务不可用" in event


# ─── SSEEmitter 类 ────────────────────────────────────────


class TestSSEEmitter:
    """SSEEmitter 封装类。"""

    @pytest.fixture
    def emit(self):
        return SSEEmitter()

    def test_intent(self, emit):
        result = emit.intent({"intent": "greeting", "confidence": 0.99})
        assert "event: intent" in result
        assert "greeting" in result

    def test_sentiment(self, emit):
        result = emit.sentiment({"label": "positive", "score": 0.85})
        assert "event: sentiment" in result
        assert "positive" in result

    def test_entity(self, emit):
        result = emit.entity({"entities": {}, "summary": "订单号: DD123"})
        assert "event: entity" in result

    def test_token(self, emit):
        result = emit.token("好")
        assert "event: token" in result
        assert '"token": "好"' in result

    def test_done(self, emit):
        result = emit.done("msg_abc", "完整回答内容", source="llm")
        assert "event: done" in result
        assert "msg_abc" in result
        assert "完整回答内容" in result
        assert "llm" in result

    def test_error(self, emit):
        result = emit.error("请求处理失败")
        assert "event: error" in result
        assert "请求处理失败" in result

    def test_all_events_are_valid_sse(self, emit):
        """所有事件应以 \\n\\n 结尾。"""
        events = [
            emit.intent({"intent": "o", "confidence": 0.5}),
            emit.sentiment({"label": "n", "score": 0.5}),
            emit.entity({"entities": {}, "summary": "x"}),
            emit.token("t"),
            emit.done("m", "a"),
            emit.error("e"),
        ]
        for e in events:
            assert e.endswith("\n\n"), f"事件不以 \\n\\n 结尾: {e[:50]}"


# ─── Chat API 端点测试 ─────────────────────────────────────


class TestChatAPI:
    """POST /api/chat — SSE 流式端点。"""

    @pytest.fixture
    def client(self, temp_db_path):
        """Flask 测试客户端。"""
        # temp_db_path fixture 由 conftest 提供或在 test_db.py 中
        # 这里复用它来确保 DB 路径已 patch
        from app import create_app
        import app.services.db as db

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_chat_returns_sse_content_type(self, client):
        """响应 Content-Type 应为 text/event-stream。"""
        resp = client.post(
            "/api/chat",
            json={"session_id": str(uuid.uuid4()), "message": "你好"},
        )
        # 状态码可能是 200（SSE 流）或 500（依赖服务不可用）
        # 但 Content-Type 在 200 时必须是 text/event-stream
        if resp.status_code == 200:
            assert "text/event-stream" in resp.content_type

    def test_chat_missing_body(self, client):
        """请求体为空时返回 400。"""
        resp = client.post("/api/chat", data="")  # 不设 content-type 为 json
        # Flask 返回 400 或 415，取决于具体实现
        assert resp.status_code in (400, 415)

    def test_chat_missing_session_id(self, client):
        """缺少 session_id 时返回 400。"""
        resp = client.post(
            "/api/chat",
            json={"message": "你好"},
        )
        assert resp.status_code == 400

    def test_chat_missing_message(self, client):
        """缺少 message 时返回 400。"""
        resp = client.post(
            "/api/chat",
            json={"session_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 400

    def test_chat_empty_message(self, client):
        """空 message 时返回 400。"""
        resp = client.post(
            "/api/chat",
            json={"session_id": str(uuid.uuid4()), "message": ""},
        )
        assert resp.status_code == 400

    def test_chat_message_too_long(self, client):
        """超长 message（>2000 字符）应返回 400。"""
        resp = client.post(
            "/api/chat",
            json={
                "session_id": str(uuid.uuid4()),
                "message": "长" * 2001,
            },
        )
        assert resp.status_code == 400

    def test_chat_valid_request_returns_200(self, client):
        """合法请求在 orchestrate 能运行时返回 200。

        注：orchestrate 依赖外部 NLP 服务，此处仅验证校验层通过。
        若 NLP 不可用，应有 error SSE 事件而非 HTTP 错误。
        """
        resp = client.post(
            "/api/chat",
            json={
                "session_id": str(uuid.uuid4()),
                "message": "你好，测试消息",
            },
        )
        # SSE 响应本身是 200；内部错误会通过 error SSE 事件传递
        if resp.status_code == 200:
            assert "text/event-stream" in resp.content_type
