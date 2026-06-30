"""编排器服务 — 协调意图分类与回答生成的 SSE 流式输出。

当前阶段（最小闭环）使用固定模板回复，后续将接入
ES 检索和 DeepSeek LLM 生成。
"""

import time
import uuid
from typing import Generator

from flask import current_app

from app.services.classifier import classify_intent
from app.utils.sse import (
    generate_done_event,
    generate_error_event,
    generate_intent_event,
    generate_token_event,
)

# ─── 固定模板回复（7 类意图） ───

TEMPLATES: dict[str, str] = {
    "refund_inquiry": (
        "您好！关于退货退款，您可以在「我的订单」页面找到对应订单，"
        "点击「申请退货」按钮，按照指引填写退货原因并提交即可。"
        "提交后我们会在 1-3 个工作日内审核。"
        "退款将在审核通过后原路返回您的支付账户，一般需要 3-7 个工作日到账。"
        "如有其他疑问，随时告诉我！"
    ),
    "logistics_inquiry": (
        "您好！查询物流信息，您可以进入「我的订单」页面，"
        "点击对应订单的「查看物流」按钮，即可看到最新的快递状态。"
        "如果物流信息长时间未更新，可能是快递公司系统延迟，"
        "建议您稍等几小时再查看。如超过 48 小时仍未更新，"
        "请联系我们为您进一步处理！"
    ),
    "product_inquiry": (
        "您好！关于商品信息，您可以在商品详情页查看完整的参数、"
        "规格、尺寸说明和用户评价。建议您在购买前仔细阅读商品描述，"
        "如有尺寸或颜色选择的疑问，可以参考详情页的尺码表或联系在线客服。"
        "特定商品的库存和价格以页面实时显示为准。还有什么可以帮您的吗？"
    ),
    "order_inquiry": (
        "您好！查询订单状态，您可以进入「我的订单」页面，"
        "查看所有订单的实时状态，包括待付款、待发货、运输中、已签收等。"
        "如需修改收货地址或取消订单，请在订单未发货前操作。"
        "如果订单显示已签收但您未收到，请先确认是否由家人或同事代收，"
        "若确认未收到请联系我们处理！"
    ),
    "complaint": (
        "非常抱歉给您带来了不好的体验！我们非常重视您的反馈。"
        "请您详细描述遇到的问题（如订单号、商品名称、具体情况），"
        "我会立即将您的问题升级给专员处理。"
        "一般情况下，专员会在 24 小时内与您联系。"
        "再次为给您带来的不便深表歉意！"
    ),
    "greeting": (
        "您好！我是智能客服助手，很高兴为您服务。"
        "我可以帮您查询订单、了解物流状态、解答商品疑问、"
        "处理退货退款等问题。请问有什么可以帮助您的呢？"
    ),
    "other": (
        "您好！我目前还在学习中，暂时无法准确理解您的问题。"
        "您可以尝试换一种方式描述，或者告诉我您想了解的具体内容，"
        "比如订单查询、物流信息、退货流程等。我也可以帮您转接人工客服！"
    ),
}


def orchestrate(session_id: str, message: str) -> Generator[str, None, None]:
    """编排一次对话请求的处理流程，以 SSE 事件流方式返回。

    当前流程（最小闭环）：
    1. 调用 NLP 服务进行意图分类
    2. 根据意图查找固定模板回复
    3. 逐字推送模板文本

    Args:
        session_id: 会话 ID。
        message: 用户消息文本。

    Yields:
        str: SSE 事件字符串，按顺序为 intent → token*N → done。
    """
    logger = current_app.logger
    message_id = f"msg_{uuid.uuid4().hex[:12]}"

    try:
        # 1. 意图分类
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

        # 3. 查找模板回复
        template = TEMPLATES.get(intent, TEMPLATES["other"])

        # 4. 逐字推送（模拟流式效果）
        delay = 0.015  # 每字间隔，模拟 LLM 流式输出速度
        for char in template:
            yield generate_token_event(char)
            time.sleep(delay)

        # 5. 发送完成事件
        yield generate_done_event(message_id, template, source="template")
        logger.info("会话 %s 回复完成: message_id=%s", session_id, message_id)

    except Exception:
        logger.exception("会话 %s 处理异常", session_id)
        yield generate_error_event("处理您的问题时出现错误，请稍后重试")
        yield generate_done_event(message_id, "", source="error")
