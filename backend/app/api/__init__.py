"""API 蓝图注册模块。

在此模块中集中注册所有 API 路由。
各子模块（chat, session, feedback）通过导入触发 @api_bp.route 装饰器。
"""

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


# 导入子模块以触发路由注册
import app.api.chat  # noqa: F401, E402 — 注册 /api/chat 路由
