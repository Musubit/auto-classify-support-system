"""GET /api/analytics — 数据分析聚合端点。"""

from app.api import api_bp
from app.services.db import get_analytics
from app.utils.response import api_response


@api_bp.route("/analytics", methods=["GET"])
def analytics():
    """返回会话、消息、意图、情感的聚合统计数据。"""
    return api_response(data=get_analytics(), message="ok")
