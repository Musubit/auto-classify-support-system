"""编排器服务 — 协调意图分类、情感分析、实体抽取、FAQ 检索与 LLM 生成的 RAG 流程。

核心流程：
1. 意图分类（NLP 微服务）
2. 情感分析（BERT 模型）
3. 实体抽取（jieba + 正则，NLP 微服务）
4. FAQ 检索（ES 混合 / BGE 向量 / 关键词）
5. LLM 流式生成（DeepSeek / Ollama，RAG 增强）
6. SSE 逐 token 推送 + SQLite 持久化
"""

import uuid
from typing import Generator

import requests
from flask import current_app

from app.services.classifier import classify_intent
from app.services.db import ensure_session, save_message
from app.services.llm import generate_stream
from app.services.retriever import format_context, search_faq
from app.services.sentiment import analyze as analyze_sentiment
from app.utils.sse import (
    generate_done_event,
    generate_entity_event,
    generate_error_event,
    generate_intent_event,
    generate_sentiment_event,
    generate_token_event,
)


def orchestrate(session_id: str, message: str) -> Generator[str, None, None]:
    """编排一次对话请求的处理流程，以 SSE 事件流方式返回。

    SSE 事件序列：
        event: intent     — 意图分类结果
        event: sentiment  — 情感分析结果
        event: token      — 逐字回答（多次）
        event: done       — 回答完成

    Args:
        session_id: 会话 ID。
        message: 用户消息文本。

    Yields:
        str: SSE 事件字符串，按顺序为 intent → token*N → done。
    """
    logger = current_app.logger
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"

    try:
        # 0. 确保会话存在 + 自动标题（首条消息前20字）
        title = message[:20].replace("\n", " ").strip()
        ensure_session(session_id, title=title)

        # 0.1 保存用户消息
        save_message(user_msg_id, session_id, "user", message)
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

        # 3. 情感分析
        sentiment = analyze_sentiment(message)
        yield generate_sentiment_event(sentiment["label"], sentiment["score"])
        logger.info(
            "会话 %s 情感分析: label=%s score=%.4f",
            session_id,
            sentiment["label"],
            sentiment["score"],
        )

        # 3.5 实体抽取（NLP 微服务）
        try:
            nlp_url = current_app.config.get("NLP_SERVER_URL", "http://localhost:5005")
            extract_resp = requests.post(
                f"{nlp_url}/extract",
                json={"text": message},
                timeout=3.0,
            )
            if extract_resp.ok:
                extract_data = extract_resp.json()
                entities = extract_data.get("entities", {})
                summary = extract_data.get("summary", "")
                if entities:
                    yield generate_entity_event(entities, summary)
                    logger.info("会话 %s 实体抽取: %s", session_id, summary)
        except Exception:
            pass  # 实体抽取失败不影响主流程

        # 4. FAQ 检索
        faq_results = search_faq(message, top_k=3, score_threshold=0.4)
        context = format_context(faq_results)
        if context:
            logger.info("会话 %s FAQ 检索: hits=%d", session_id, len(faq_results))

        # 5. 调用 DeepSeek LLM 流式生成（带 RAG 上下文）
        full_answer = ""
        for token in generate_stream(message, intent, context=context or None):
            full_answer += token
            yield generate_token_event(token)

        # 5.1 保存助手回复到 SQLite
        save_message(
            message_id, session_id, "assistant", full_answer,
            intent_label=intent,
            intent_confidence=confidence,
            sentiment_label=sentiment["label"],
            sentiment_score=sentiment["score"],
        )

        # 6. 发送完成事件
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
