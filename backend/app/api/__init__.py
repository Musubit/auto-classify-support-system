"""API 蓝图注册模块。"""

from flask import Blueprint

from app.utils.response import api_response

api_bp = Blueprint("api", __name__)


@api_bp.route("/health", methods=["GET"])
def health():
    """健康检查端点。

    Returns:
        tuple: 包含服务状态信息的统一响应。
    """
    return api_response(
        data={"service": "auto-classify-support-system", "version": "0.1.0"},
        message="服务运行中",
    )
