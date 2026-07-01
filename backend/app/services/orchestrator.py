"""编排器服务 — 协调意图分类、LLM 生成与 SSE 流式输出。

核心流程：
1. 意图分类（NLP 微服务）
2. （待接入）ES FAQ 检索
3. DeepSeek LLM 流式生成
4. SSE 逐 token 推送
"""

import uuid
from typing import Generator

from flask import current_app

from app.services.classifier import classify_intent
from app.services.llm import generate_stream
from app.utils.sse import (
    generate_done_event,
    generate_error_event,
    generate_intent_event,
    generate_token_event,
)


def orchestrate(session_id: str, message: str) -> Generator[str, None, None]:
    """编排一次对话请求的处理流程，以 SSE 事件流方式返回。

    当前流程：
    1. 调用 NLP 服务进行意图分类
    2. 发送意图事件
    3. （待接入）ES FAQ 检索
    4. 调用 DeepSeek LLM 流式生成
    5. 逐 token 发送 + done 事件

    Args:
        session_id: 会话 ID。
        message: 用户消息文本。

    Yields:
        str: SSE 事件字符串，按顺序为 intent → token*N → done。
    """
    logger = current_app.logger
    message_id = f"msg_{uuid.uuid4().hex[:12]}"

    try:
        # 1. 意图分类
        result = classify_intent(message)
        intent = result["intent"]
        confidence = result["confidence"]
        logger.info(
            "会话 %s 意图分类: intent=%s confidence=%.4f",
            session_id,
            intent,
            confidence,
        )

        # 2. 发送意图事件
        yield generate_intent_event(intent, confidence)

        # 3. TODO: ES FAQ 检索（后续接入 retriever）

        # 4. 调用 DeepSeek LLM 流式生成
        full_answer = ""
        for token in generate_stream(message, intent):
            full_answer += token
            yield generate_token_event(token)

        # 5. 发送完成事件
        yield generate_done_event(message_id, full_answer, source="llm")
        logger.info("会话 %s 回复完成: message_id=%s len=%d", session_id, message_id, len(full_answer))

    except ValueError as e:
        # LLM API Key 未配置等明确的配置错误
        logger.warning("会话 %s LLM 配置错误: %s", session_id, e)
        yield generate_error_event(str(e))
        yield generate_done_event(message_id, "", source="error")

    except Exception:
        logger.exception("会话 %s 处理异常", session_id)
        yield generate_error_event("处理您的问题时出现错误，请稍后重试")
        yield generate_done_event(message_id, "", source="error")
