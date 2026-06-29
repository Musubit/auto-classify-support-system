"""统一 JSON 响应工具。

遵循 coding-standards.md §1.7：禁止在 API 层直接 jsonify，
所有响应必须通过此模块的 api_response / error_response 返回。
"""

from typing import Any

from flask import jsonify


def api_response(
    data: Any = None,
    message: str = "",
    code: int = 200,
    status: str = "success",
) -> tuple:
    """构建统一的 JSON 成功响应。

    Args:
        data: 响应数据体。
        message: 提示消息。
        code: HTTP 状态码。
        status: 业务状态标识。

    Returns:
        tuple: (jsonify 响应对象, HTTP 状态码)。
    """
    return jsonify({"status": status, "message": message, "data": data}), code


def error_response(message: str, code: int = 500, status: str = "error") -> tuple:
    """构建统一的 JSON 错误响应。

    Args:
        message: 错误提示消息（用户可见，使用中文）。
        code: HTTP 状态码。
        status: 业务状态标识。

    Returns:
        tuple: (jsonify 响应对象, HTTP 状态码)。
    """
    return jsonify({"status": status, "message": message, "data": None}), code
