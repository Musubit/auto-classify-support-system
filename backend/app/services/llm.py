"""LLM 回答生成服务 — 流式调用与 Prompt 构建。

支持双后端切换：
- DeepSeek API（云端）：默认，通过 DEEPSEEK_API_KEY 认证
- Ollama（本地）：通过 LLM_BACKEND=ollama 切换，OpenAI 兼容 API

统一使用 OpenAI 兼容接口，支持流式 token 输出。
"""

import logging
from typing import Generator, Optional

from flask import current_app
from openai import OpenAI

logger = logging.getLogger(__name__)

# ─── 意图对应的系统提示（精简版，不冗余模板） ───

INTENT_SYSTEM_PROMPTS: dict[str, str] = {
    "refund_inquiry": "你是电商客服专员，负责处理退货退款问题。请告知退货流程、退款时间、审核标准。语气友善、简洁。",
    "logistics_inquiry": "你是电商物流客服专员，负责处理快递查询和物流异常。请告知如何查物流、物流异常处理方式。语气友善、简洁。",
    "product_inquiry": "你是电商商品咨询客服专员，负责解答商品参数、规格、使用等问题。请根据商品常识回答，不确定时建议查看详情页。语气友善、简洁。",
    "order_inquiry": "你是电商订单客服专员，负责处理订单状态、修改地址、取消订单等问题。语气友善、简洁。",
    "complaint": "你是电商投诉处理专员，需要安抚客户情绪并承诺跟进处理。先道歉、再询问详情、最后承诺反馈。语气真诚、有同理心。",
    "greeting": "你是电商客服助手，负责欢迎用户并介绍服务范围。语气热情、简洁。",
    "other": "你是电商智能客服助手，当无法准确理解用户问题时，请礼貌引导用户描述得更清楚，或建议转人工。语气友善、有耐心。",
}


def build_messages(
    user_message: str,
    intent: str,
    context: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> list[dict]:
    """构建 LLM 调用的消息列表。

    Args:
        user_message: 用户当前输入文本。
        intent: 意图标签。
        context: 可选的检索上下文（FAQ 匹配结果，后续 RAG 阶段接入）。
        history: 可选的对话历史 [{role, content}, ...]。

    Returns:
        list[dict]: 符合 OpenAI Chat API 的消息列表。
    """
    system_prompt = INTENT_SYSTEM_PROMPTS.get(intent, INTENT_SYSTEM_PROMPTS["other"])

    # 如有检索上下文，追加到系统提示
    if context:
        system_prompt += (
            "\n\n以下是可供参考的知识库内容，请据此回答：\n" + context
        )

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": user_message})
    return messages


def generate_stream(
    user_message: str,
    intent: str,
    context: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> Generator[str, None, str]:
    """流式调用 LLM，逐 token 返回。支持 DeepSeek API 和 Ollama 本地模型。

    Args:
        user_message: 用户当前输入文本。
        intent: 意图标签。
        context: 可选的检索上下文。
        history: 可选的对话历史。

    Yields:
        str: 每个增量 token 的文本片段。

    Returns:
        str: 最终累积的完整回答文本（StopIteration value）。
    """
    backend = current_app.config.get("LLM_BACKEND", "deepseek")
    client, model = _get_client_and_model(backend)
    messages = build_messages(user_message, intent, context, history)

    logger.info("LLM 请求: backend=%s model=%s intent=%s len=%d",
                backend, model, intent, len(user_message))

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=1024,
        )

        full_answer = ""

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                token = delta.content
                full_answer += token
                yield token

        logger.info("LLM 完成: backend=%s len=%d", backend, len(full_answer))
        return full_answer

    except Exception as e:
        logger.error("LLM 调用失败: backend=%s error=%s", backend, e)
        raise


def _get_client_and_model(backend: str) -> tuple[OpenAI, str]:
    """根据后端类型返回 (OpenAI客户端, 模型名)。

    Args:
        backend: "deepseek" 或 "ollama"。

    Returns:
        tuple: (OpenAI 客户端实例, 模型名称字符串)。

    Raises:
        ValueError: 当 DeepSeek 模式未配置 API Key 时。
    """
    if backend == "ollama":
        base_url = current_app.config.get("OLLAMA_BASE_URL", "http://ollama:11434/v1")
        model = current_app.config.get("OLLAMA_MODEL", "qwen2.5:7b")
        # Ollama 本地不需要真实的 API Key，传占位值即可
        return OpenAI(api_key="ollama", base_url=base_url), model

    # 默认 DeepSeek
    api_key = current_app.config.get("DEEPSEEK_API_KEY", "")
    base_url = current_app.config.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = current_app.config.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY 未配置，请在 .env 中设置")

    return OpenAI(api_key=api_key, base_url=base_url), model
