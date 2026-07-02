"""SSE（Server-Sent Events）流式推送工具。

提供 SSE 事件格式化与生成函数，遵循 SSE 协议规范。
用于 orchestrator 逐 token 推送回答至前端。
"""

import json
import logging
from typing import Union

logger = logging.getLogger(__name__)


def format_sse_event(event: str, data: Union[dict, str]) -> str:
    """将事件名称和数据体格式化为 SSE 协议字符串。

    遵循 SSE 规范：每行以 "field: value" 形式，
    事件之间用空行分隔。

    Args:
        event: SSE 事件类型（intent / token / done / error 等）。
        data: 事件数据，dict 会自动序列化为 JSON 字符串。

    Returns:
        str: 符合 SSE 协议的事件字符串，形如
            "event: intent\\ndata: {...}\\n\\n"。
    """
    if isinstance(data, dict):
        data_str = json.dumps(data, ensure_ascii=False)
    else:
        data_str = str(data)
    return f"event: {event}\ndata: {data_str}\n\n"


def generate_intent_event(intent: str, confidence: float) -> str:
    """生成意图分类结果的 SSE 事件。

    Args:
        intent: 意图标签，如 "logistics_inquiry"。
        confidence: 置信度，范围 [0, 1]。

    Returns:
        str: SSE 事件字符串。
    """
    return format_sse_event(
        "intent",
        {"intent": intent, "confidence": confidence},
    )


def generate_sentiment_event(label: str, score: float) -> str:
    """生成情感分析结果的 SSE 事件。

    Args:
        label: 情感标签，"positive" / "negative" / "neutral"。
        score: 置信度，范围 [0, 1]。

    Returns:
        str: SSE 事件字符串。
    """
    return format_sse_event(
        "sentiment",
        {"label": label, "score": score},
    )


def generate_token_event(token: str) -> str:
    """生成单个 token 的 SSE 事件。

    Args:
        token: 单个字符或词语。

    Returns:
        str: SSE 事件字符串。
    """
    return format_sse_event("token", {"token": token})


def generate_done_event(message_id: str, full_answer: str, source: str = "template") -> str:
    """生成流式结束的 SSE 事件。

    Args:
        message_id: 本条消息的唯一 ID。
        full_answer: 完整的回答文本。
        source: 回答来源（template / faq / llm）。

    Returns:
        str: SSE 事件字符串。
    """
    return format_sse_event(
        "done",
        {
            "message_id": message_id,
            "full_answer": full_answer,
            "source": source,
        },
    )


def generate_entity_event(entities: dict, summary: str) -> str:
    """生成实体抽取结果的 SSE 事件。

    Args:
        entities: 原始实体结果 dict。
        summary: 可读摘要字符串。

    Returns:
        str: SSE 事件字符串。
    """
    return format_sse_event("entity", {"entities": entities, "summary": summary})


def generate_error_event(message: str) -> str:
    """生成错误的 SSE 事件。

    Args:
        message: 用户可见的中文错误说明。

    Returns:
        str: SSE 事件字符串。
    """
    return format_sse_event("error", {"message": message})


# ─── SSEEmitter — 面向对象的 SSE 事件发射器 ──────────────────


class SSEEmitter:
    """SSE 事件发射器，封装全部事件名、数据结构与格式化知识。

    所有 SSE 格式决策集中于此单一 seam——变更事件协议（如新增字段、
    切换传输格式）只需修改此类的实现，orchestrator 等调用者不受影响。

    用法:
        emitter = SSEEmitter()
        yield emitter.intent({"intent": "logistics", "confidence": 0.95})
        yield emitter.token("你")
        yield emitter.done("msg_abc", "你好，请问...", source="llm")
    """

    # ─── 分析事件 ──────────────────────────────────────

    @staticmethod
    def intent(data: dict) -> str:
        """意图分类结果事件。data 需含 intent 和 confidence 字段。"""
        return format_sse_event("intent", data)

    @staticmethod
    def sentiment(data: dict) -> str:
        """情感分析结果事件。data 需含 label 和 score 字段。"""
        return format_sse_event("sentiment", data)

    @staticmethod
    def entity(data: dict) -> str:
        """实体抽取结果事件。data 需含 entities 和 summary 字段。"""
        return format_sse_event("entity", data)

    # ─── 流式事件 ──────────────────────────────────────

    @staticmethod
    def token(text: str) -> str:
        """单个 token 事件。"""
        return format_sse_event("token", {"token": text})

    @staticmethod
    def done(message_id: str, full_answer: str, source: str = "llm") -> str:
        """流式完成事件。"""
        return format_sse_event(
            "done",
            {
                "message_id": message_id,
                "full_answer": full_answer,
                "source": source,
            },
        )

    # ─── 错误事件 ──────────────────────────────────────

    @staticmethod
    def error(message: str) -> str:
        """错误事件。"""
        return format_sse_event("error", {"message": message})
