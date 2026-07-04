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


# ─── Token 估算与上下文截断 ───────────────────────────────


def estimate_tokens(text: str) -> int:
    """保守估算混合中英文文本的 token 数。

    中文约 1.5 字/token，英文约 4 字/token，取 len//2 作为安全上界。
    非空字符串至少返回 1。

    Args:
        text: 待估算文本。

    Returns:
        int: 估算 token 数。
    """
    return max(1, len(text) // 2)


def truncate_history(
    history: list[dict],
    max_tokens: int,
    min_turns: int = 3,
) -> list[dict]:
    """截断对话历史以适应上下文窗口。

    将历史按 (user, assistant) 成对分组，从最新轮次往前累加 token 数。
    超出 max_tokens 时丢弃最旧的轮次，至少保留 min_turns 轮。

    Args:
        history: 对话历史 [{role, content}, ...]，按时间正序。
        max_tokens: 历史部分允许的最大估算 token 数。
        min_turns: 最少保留的对话轮次数。

    Returns:
        list[dict]: 截断后的历史消息列表。
    """
    if not history:
        return []

    # 按 (user, assistant) 成对分组
    pairs: list[list[dict]] = []
    i = 0
    while i < len(history):
        if i + 1 < len(history) and history[i]["role"] == "user":
            pairs.append([history[i], history[i + 1]])
            i += 2
        else:
            pairs.append([history[i]])
            i += 1

    # 从最新轮次往前累加
    kept_pairs = []
    tokens_used = 0
    for pair in reversed(pairs):
        pair_tokens = sum(estimate_tokens(m["content"]) for m in pair)
        if tokens_used + pair_tokens > max_tokens and len(kept_pairs) >= min_turns:
            break
        kept_pairs.insert(0, pair)
        tokens_used += pair_tokens

    # 展开回消息列表
    result = []
    for pair in kept_pairs:
        result.extend(pair)

    original_count = len(history)
    if len(result) < original_count:
        logger.warning(
            "历史消息截断: %d条 → %d条 (保留%d轮对话, 估算token=%d/%d)",
            original_count, len(result), len(kept_pairs),
            tokens_used, max_tokens,
        )

    return result


# ─── Prompt 构建 ───────────────────────────────────────────


def build_messages(
    user_message: str,
    intent: str,
    context: Optional[str] = None,
    history: Optional[list[dict]] = None,
    max_context_tokens: int = 28000,
) -> list[dict]:
    """构建 LLM 调用的消息列表，含上下文窗口截断。

    Args:
        user_message: 用户当前输入文本。
        intent: 意图标签。
        context: 可选的检索上下文（FAQ 匹配结果）。
        history: 可选的对话历史 [{role, content}, ...]。
        max_context_tokens: 上下文窗口 token 预算上限。

    Returns:
        list[dict]: 符合 OpenAI Chat API 的消息列表。
    """
    system_prompt = INTENT_SYSTEM_PROMPTS.get(intent, INTENT_SYSTEM_PROMPTS["other"])

    # 如有检索上下文，追加到系统提示
    if context:
        system_prompt += (
            "\n\n以下是可供参考的知识库内容，请据此回答：\n" + context
        )

    # 固定 token 消耗：system prompt + 当前用户消息
    fixed_tokens = estimate_tokens(system_prompt) + estimate_tokens(user_message)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    if history:
        # 用剩余 budget 容纳历史，超出部分截断
        history_budget = max_context_tokens - fixed_tokens
        if history_budget > 0:
            truncated = truncate_history(history, history_budget)
            messages.extend(truncated)

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
    max_ctx = int(current_app.config.get("MAX_CONTEXT_TOKENS", "28000"))
    messages = build_messages(
        user_message, intent, context, history,
        max_context_tokens=max_ctx,
    )

    logger.info("LLM 请求: backend=%s model=%s intent=%s msgs=%d",
                backend, model, intent, len(messages))

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
