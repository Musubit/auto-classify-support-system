"""编排器服务 — 薄 runner，负责会话生命周期管理并委托 Pipeline 执行分析流程。

职责分离：
- orchestrator：会话创建、消息持久化、错误处理、done 事件
- pipeline：意图 → 情感 → 实体 → 检索 → 生成（独立可测试的 Stage）
"""

import uuid
from typing import Generator

from flask import current_app

from app.services.db import ensure_session, get_session_messages, save_message
from app.services.pipeline import PipelineContext, create_default_pipeline
from app.utils.sse import SSEEmitter


def _db_rows_to_history(rows: list[dict]) -> list[dict]:
    """将数据库消息行转换为 LLM 对话历史格式 [{role, content}, ...]."""
    return [{"role": r["role"], "content": r["text"]} for r in rows]


def orchestrate(session_id: str, message: str) -> Generator[str, None, None]:
    """编排一次对话请求的处理流程，以 SSE 事件流方式返回。

    SSE 事件序列：
        event: intent     — 意图分类结果
        event: sentiment  — 情感分析结果
        event: entity     — 实体抽取结果（可选）
        event: token      — 逐字回答（多次）
        event: done       — 回答完成

    Args:
        session_id: 会话 ID。
        message: 用户消息文本。

    Yields:
        str: SSE 事件字符串，按顺序为 intent → sentiment → entity? → token*N → done。
    """
    logger = current_app.logger
    emit = SSEEmitter()
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"

    # ─── 会话准备（编排器职责，非 Pipeline 步骤） ───
    try:
        title = message[:20].replace("\n", " ").strip()
        ensure_session(session_id, title=title)

        # 加载历史对话（在保存当前消息之前，避免当前消息被包含）
        db_rows = get_session_messages(session_id)
        history = _db_rows_to_history(db_rows) if db_rows else None

        save_message(user_msg_id, session_id, "user", message)
    except Exception:
        logger.exception("会话 %s 初始化失败", session_id)
        yield emit.error("会话创建失败，请稍后重试")
        yield emit.done(message_id, "", source="error")
        return

    # ─── 执行分析 Pipeline ───
    ctx = PipelineContext(session_id=session_id, message=message, history=history)
    pipeline = create_default_pipeline()

    try:
        for event in pipeline.run(ctx):
            yield event
    except ValueError as e:
        # LLM API Key 未配置等明确的配置错误
        logger.warning("会话 %s LLM 配置错误: %s", session_id, e)
        yield emit.error(str(e))
        yield emit.done(message_id, "", source="error")
        return
    except Exception:
        logger.exception("会话 %s 处理异常", session_id)
        yield emit.error("处理您的问题时出现错误，请稍后重试")
        yield emit.done(message_id, "", source="error")
        return

    # ─── 日志 ───
    logger.info(
        "会话 %s 意图分类: intent=%s confidence=%.4f",
        session_id, ctx.intent, ctx.confidence,
    )
    if ctx.sentiment:
        logger.info(
            "会话 %s 情感分析: label=%s score=%.4f",
            session_id, ctx.sentiment.get("label"), ctx.sentiment.get("score"),
        )
    if ctx.entities:
        logger.info("会话 %s 实体抽取: %s", session_id, ctx.entities.get("summary"))
    if ctx.faq_context:
        logger.info("会话 %s FAQ 检索: 已命中", session_id)

    # ─── 持久化助手回复 ───
    try:
        save_message(
            message_id, session_id, "assistant", ctx.full_answer,
            intent_label=ctx.intent,
            intent_confidence=ctx.confidence,
            sentiment_label=ctx.sentiment.get("label", ""),
            sentiment_score=ctx.sentiment.get("score", 0.0),
        )
    except Exception:
        logger.exception("会话 %s 消息持久化失败", session_id)

    # ─── 完成事件 ───
    yield emit.done(message_id, ctx.full_answer, source="llm")
    logger.info(
        "会话 %s 回复完成: message_id=%s len=%d",
        session_id, message_id, len(ctx.full_answer),
    )
