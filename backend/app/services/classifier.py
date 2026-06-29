"""意图分类服务 — 调用 NLP 服务获取意图"""
import requests
from flask import current_app


def classify_intent(text: str) -> dict:
    """
    调用 NLP 服务进行意图分类

    Args:
        text: 用户消息文本

    Returns:
        {"intent": "logistics_inquiry", "confidence": 0.95}
        分类失败时返回 {"intent": "other", "confidence": 0.0}
    """
    nlp_url = current_app.config.get("NLP_SERVER_URL", "http://localhost:5005")
    try:
        resp = requests.post(
            f"{nlp_url}/parse",
            json={"text": text},
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "intent": data["intent"],
            "confidence": data["confidence"],
        }
    except Exception as e:
        current_app.logger.warning(f"NLP classify failed: {e}")
        return {"intent": "other", "confidence": 0.0}
