"""会话管理 API — 历史会话列表、详情、删除。"""

from flask import jsonify, request

from app.api import api_bp
from app.services.db import delete_session, get_session, get_session_messages, get_sessions


@api_bp.route("/sessions", methods=["GET"])
def list_sessions():
    """获取会话列表。
    ---
    tags:
      - 对话
    summary: 获取会话列表
    description: 返回所有会话，按更新时间倒序排列。
    responses:
      200:
        description: 会话列表
    """
    sessions = get_sessions()
    return jsonify({"status": "success", "data": sessions})


@api_bp.route("/sessions/<session_id>", methods=["GET"])
def session_detail(session_id: str):
    """获取单个会话详情（含消息）。
    ---
    tags:
      - 对话
    summary: 获取会话详情
    description: 返回会话信息及所有历史消息。
    parameters:
      - in: path
        name: session_id
        required: true
        type: string
        description: 会话 ID
    responses:
      200:
        description: 会话详情
      404:
        description: 会话不存在
    """
    session = get_session(session_id)
    if not session:
        return jsonify({"status": "error", "message": "会话不存在"}), 404

    messages = get_session_messages(session_id)
    return jsonify({
        "status": "success",
        "data": {
            "session": session,
            "messages": messages,
        },
    })


@api_bp.route("/sessions/<session_id>", methods=["DELETE"])
def remove_session(session_id: str):
    """删除会话及其消息。
    ---
    tags:
      - 对话
    summary: 删除会话
    description: 删除会话及其所有关联消息。
    parameters:
      - in: path
        name: session_id
        required: true
        type: string
        description: 会话 ID
    responses:
      200:
        description: 删除成功
      404:
        description: 会话不存在
    """
    ok = delete_session(session_id)
    if not ok:
        return jsonify({"status": "error", "message": "会话不存在"}), 404

    return jsonify({"status": "success", "message": "已删除"})
