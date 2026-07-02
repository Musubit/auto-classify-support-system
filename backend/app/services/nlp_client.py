"""NLP 微服务适配器 — 统一封装所有对 NLP 服务的 HTTP 调用。

将原本分散在 classifier.py 和 orchestrator 中的两处 HTTP 调用
合并为单一 seam，提供一致的错误处理、超时和 fallback 策略。
"""

import logging
from typing import Any

import requests
from flask import current_app

logger = logging.getLogger(__name__)


class NLPClient:
    """与 NLP 微服务通信的单一适配器。

    封装意图分类（/parse）和实体抽取（/extract）两个端点，
    提供统一的超时、错误处理和 fallback。

    Attributes:
        base_url: NLP 服务基地址，如 "http://localhost:5005"。
        timeout: 默认请求超时秒数。
    """

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ─── 意图分类 ────────────────────────────────────────

    def classify(self, text: str) -> dict[str, Any]:
        """调用 NLP 服务进行意图分类。

        Args:
            text: 用户消息文本。

        Returns:
            {"intent": str, "confidence": float}。
            分类失败时返回 {"intent": "other", "confidence": 0.0}。
        """
        try:
            resp = requests.post(
                f"{self.base_url}/parse",
                json={"text": text},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "intent": data["intent"],
                "confidence": data["confidence"],
            }
        except Exception as e:
            logger.warning("NLP 意图分类失败: %s", e)
            return {"intent": "other", "confidence": 0.0}

    # ─── 实体抽取 ────────────────────────────────────────

    def extract(self, text: str) -> dict[str, Any]:
        """调用 NLP 服务进行实体抽取。

        实体抽取失败不影响主流程，静默返回空 dict。

        Args:
            text: 用户消息文本。

        Returns:
            {"entities": dict, "summary": str}，无实体或失败时返回 {}。
        """
        try:
            resp = requests.post(
                f"{self.base_url}/extract",
                json={"text": text},
                timeout=self.timeout,
            )
            if resp.ok:
                data = resp.json()
                entities = data.get("entities", {})
                summary = data.get("summary", "")
                if entities:
                    return {"entities": entities, "summary": summary}
        except Exception as e:
            logger.debug("NLP 实体抽取失败（非致命）: %s", e)
        return {}


def get_nlp_client() -> NLPClient:
    """从 Flask app.extensions 获取全局 NLPClient 实例。

    要求 create_app() 中已完成 NLPClient 的初始化并存入
    `app.extensions['nlp']`。

    Returns:
        NLPClient: 已配置的实例。
    """
    return current_app.extensions["nlp"]
