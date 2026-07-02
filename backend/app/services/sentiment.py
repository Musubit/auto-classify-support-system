"""BERT 情感分析服务 — 电商客服场景下的用户消息情感分析。

使用京东评论微调模型，对投诉、不满等负面表述更敏感。
支持懒加载与优雅降级，模型不可用时返回中性结果。
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# 全局懒加载实例
_sentiment_pipeline = None

# 默认模型：京东评论微调的二分类中文情感模型
DEFAULT_MODEL = "uer/roberta-base-finetuned-jd-binary-chinese"

# 模型标签映射到统一输出
LABEL_MAP: dict[str, str] = {
    # 京东评论微调模型实际返回的标签
    "negative (stars 1, 2 and 3)": "negative",
    "positive (stars 4 and 5)": "positive",
    # 常见变体（防御性覆盖）
    "positive": "positive",
    "negative": "negative",
    "POSITIVE": "positive",
    "NEGATIVE": "negative",
    "LABEL_0": "negative",
    "LABEL_1": "positive",
    "0 star": "negative",
    "1 star": "negative",
    "2 star": "negative",
    "3 star": "positive",
    "4 star": "positive",
    "5 star": "positive",
}


def _load_pipeline():
    """懒加载情感分析 pipeline。

    首次调用时自动从 HuggingFace 下载模型到
    ~/.cache/huggingface/hub/，后续调用直接复用。
    """
    global _sentiment_pipeline
    if _sentiment_pipeline is not None:
        return _sentiment_pipeline

    try:
        from transformers import pipeline

        model_name = os.getenv("SENTIMENT_MODEL", DEFAULT_MODEL)
        logger.info("加载情感分析模型: %s", model_name)
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model=model_name,
            tokenizer=model_name,
            top_k=None,
        )
        return _sentiment_pipeline
    except ImportError:
        logger.warning("transformers 未安装，情感分析不可用")
        return None
    except Exception as e:
        logger.error("加载情感分析模型失败: %s", e)
        return None


def analyze(text: str) -> dict:
    """分析文本的情感倾向。

    京东评论模型是二分类器，无中性概念。当模型置信度不足时说明
    文本不在其训练分布内（如提问、寒暄），此时回退为 neutral。

    Args:
        text: 用户消息文本。

    Returns:
        dict: {"label": "positive"|"negative"|"neutral", "score": 0.0~1.0}
        模型不可用时返回 {"label": "neutral", "score": 0.0}。
    """
    pipe = _load_pipeline()
    if pipe is None:
        return {"label": "neutral", "score": 0.0}

    # 置信度阈值：低于此值视为模型在"硬猜"，归为 neutral
    threshold = float(os.getenv("SENTIMENT_THRESHOLD", "0.85"))

    try:
        result = pipe(text)

        # pipeline 返回可能是 list[dict] 或 list[list[dict]]
        if isinstance(result, list) and len(result) > 0:
            first = result[0]
            # top_k=None 时返回 list[list[dict]]
            if isinstance(first, list):
                best = max(first, key=lambda x: x["score"])
            else:
                best = first
        else:
            best = {"label": "neutral", "score": 0.0}

        raw_label = best.get("label", "neutral")
        raw_score = float(best.get("score", 0.0))

        label = LABEL_MAP.get(raw_label)
        if label is None:
            logger.warning("未知情感标签: %s，回退为 neutral", raw_label)
            label = "neutral"

        # 置信度不足时，二分类模型可能在分布外硬猜 → 中性
        if raw_score < threshold:
            logger.info(
                "情感分析置信度不足: text=%s raw=%s score=%.4f < %.2f → neutral",
                text[:30], raw_label, raw_score, threshold,
            )
            label = "neutral"

        score = round(raw_score, 4)
        logger.info("情感分析: text=%s label=%s score=%.4f", text[:30], label, score)
        return {"label": label, "score": score}

    except Exception as e:
        logger.error("情感分析失败: %s", e)
        return {"label": "neutral", "score": 0.0}


def init() -> None:
    """初始化情感分析服务：预加载模型。

    在应用启动时调用一次，提前加载避免首次请求的延迟。
    """
    pipe = _load_pipeline()
    if pipe is not None:
        logger.info("情感分析服务初始化完成")
    else:
        logger.warning("情感分析服务不可用，将返回中性结果")
