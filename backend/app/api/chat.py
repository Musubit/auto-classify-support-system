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
    ---
    tags:
      - 对话
    summary: 发送聊天消息（SSE 流式）
    description: |
      接收用户消息，编排器依次执行意图分类、情感分析、知识库检索、
      并由 LLM 生成回答。通过 Server-Sent Events 流式推送结果。

      **SSE 事件序列：**
      - `event: intent` — 意图分类结果（intent + confidence）
      - `event: sentiment` — 情感分析结果（label + score）
      - `event: entity` — 实体抽取结果（如有）
      - `event: token` — 逐字回答（多次）
      - `event: done` — 回答完成，含完整文本和 message_id
      - `event: error` — 发生错误时
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - session_id
            - message
          properties:
            session_id:
              type: string
              description: 会话唯一标识
              example: "abc12345"
            message:
              type: string
              description: 用户输入的消息文本
              example: "我的快递什么时候到"
    responses:
      200:
        description: SSE 事件流（text/event-stream）
      400:
        description: 请求体校验失败
        schema:
          type: object
          properties:
            status:
              type: string
              example: error
            message:
              type: string
              example: 请求格式错误，请提供 session_id 和 message
            data:
              type: object
              example: null
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
