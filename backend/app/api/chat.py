"""POST /api/chat — SSE 流式聊天端点。"""

import logging

from flask import Response, request, stream_with_context
from pydantic import ValidationError

from app.api import api_bp
from app.models.message import ChatRequest
from app.services.orchestrator import orchestrate
from app.utils.response import error_response

logger = logging.getLogger(__name__)


@api_bp.route("/chat", methods=["POST"])
def chat():
    """发送聊天消息并以 SSE 流式返回回复。

    接收 JSON 格式的用户消息，调用编排器进行意图分类和
    回答生成，通过 Server-Sent Events 逐步推送结果。

    SSE 事件序列：
        event: intent  — 意图分类结果
        event: token   — 逐字回答（多次）
        event: done    — 回答完成

    Returns:
        Response: mimetype 为 text/event-stream 的流式响应。
        校验失败时返回 JSON 错误响应。
    """
    # 请求体校验
    body = request.get_json(silent=True)
    if body is None:
        return error_response("请求体不能为空", code=400)

    try:
        req = ChatRequest.model_validate(body)
    except ValidationError as e:
        logger.warning("Chat 请求校验失败: %s", e.errors())
        return error_response("请求格式错误，请提供 session_id 和 message", code=400)

    # 流式 SSE 响应
    return Response(
        stream_with_context(orchestrate(req.session_id, req.message)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
