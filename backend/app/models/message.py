"""聊天消息相关的 Pydantic 数据模型。"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST /api/chat 请求体模型。

    Attributes:
        session_id: 会话 ID，用于关联多轮对话。
        message: 用户消息文本。
    """

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="会话 ID",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户消息文本",
    )
