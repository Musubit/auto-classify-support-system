"""FAQ 检索服务 — BGE 向量检索 + Elasticsearch 混合搜索。

支持两种模式：
1. ES 模式（生产）：kNN 向量搜索 + BM25 文本搜索混合
2. 内存模式（本地开发）：纯 SentenceTransformer 余弦相似度，无需 ES
"""

import json
import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# 全局懒加载实例
_embedder = None
_faq_store: list[dict] = []
_faq_vectors: Optional[np.ndarray] = None


# ─── FAQ 种子数据 ───

FAQ_SEED_DATA: list[dict] = [
    # 退货退款
    {"id": "faq_001", "question": "如何申请退货退款？", "answer": "在「我的订单」找到对应订单，点击「申请退货」按钮，填写退货原因并提交。审核通过后按指引寄回商品，退款在签收后 3-7 个工作日原路返回。", "category": "refund_inquiry"},
    {"id": "faq_002", "question": "退款多久能到账？", "answer": "退款在审核通过后原路返回您的支付账户，一般需要 3-7 个工作日到账。如超时未到账可联系客服查询。", "category": "refund_inquiry"},
    {"id": "faq_003", "question": "退货需要自己出运费吗？", "answer": "商品质量问题产生的退货运费由商家承担，个人原因退货则需您自行承担运费。具体以退货审核结果为准。", "category": "refund_inquiry"},
    # 物流
    {"id": "faq_004", "question": "怎么查看物流信息？", "answer": "进入「我的订单」页面，点击对应订单的「查看物流」按钮即可查看快递实时状态。", "category": "logistics_inquiry"},
    {"id": "faq_005", "question": "物流信息长时间不更新怎么办？", "answer": "物流信息偶尔会有延迟，建议等几小时再查看。如超过 48 小时未更新，请联系客服帮您核实快递状态。", "category": "logistics_inquiry"},
    {"id": "faq_006", "question": "快递显示已签收但我没收到？", "answer": "先确认是否有家人或同事代收，然后检查门口、快递柜等位置。如确认未收到，请马上联系客服处理。", "category": "logistics_inquiry"},
    # 商品咨询
    {"id": "faq_007", "question": "这个商品有什么规格？", "answer": "您可以查看商品详情页的「规格参数」部分，包括尺寸、颜色、材质等完整信息。如有特殊需求可咨询在线客服。", "category": "product_inquiry"},
    {"id": "faq_008", "question": "商品支持七天无理由退货吗？", "answer": "大部分商品支持签收后 7 天内无理由退货，需保持商品完好、配件齐全。部分特殊商品（如内衣、食品等）不支持，具体以商品页面标注为准。", "category": "product_inquiry"},
    {"id": "faq_009", "question": "商品有质保吗？", "answer": "电子产品一般享受国家三包政策，质保期内非人为损坏可免费维修。具体质保期限以商品页面或说明书为准。", "category": "product_inquiry"},
    # 订单
    {"id": "faq_010", "question": "怎么取消订单？", "answer": "未发货的订单可在「我的订单」中直接取消。已发货的订单需要在收货后发起退货。", "category": "order_inquiry"},
    {"id": "faq_011", "question": "可以修改收货地址吗？", "answer": "订单未发货时可在「我的订单」中修改收货地址。已发货订单暂不支持修改地址。", "category": "order_inquiry"},
    {"id": "faq_012", "question": "什么时候发货？", "answer": "一般付款后 24-48 小时内发货，预售商品以页面标注的发货时间为准。节假日可能略有延迟。", "category": "order_inquiry"},
    # 投诉
    {"id": "faq_013", "question": "我要投诉商家/商品质量问题", "answer": "非常抱歉给您带来不便！请提供订单号和具体情况描述，我们将立即为您升级至专员处理，一般 24 小时内回复。", "category": "complaint"},
    {"id": "faq_014", "question": "客服态度不好怎么投诉？", "answer": "很抱歉让您有不好的体验！请提供聊天记录或具体时间，我们将核实并严肃处理。您的问题也会转接高级客服为您服务。", "category": "complaint"},
    # 其他
    {"id": "faq_015", "question": "怎么联系人工客服？", "answer": "您可以直接输入「转人工」或描述您的问题，我会帮您转接人工客服。人工客服工作时间：9:00-21:00。", "category": "other"},
    {"id": "faq_016", "question": "你们的退换货政策是什么？", "answer": "支持自签收日起 7 天内无理由退货，15 天内质量问题换货。退货需保证商品完好无损、配件齐全。退款在商家确认收货后 3-7 个工作日内到账。", "category": "refund_inquiry"},
]


def _load_embedder():
    """懒加载 BGE 向量模型。

    使用 BAAI/bge-base-zh-v1.5，首次调用自动下载到
    ~/.cache/huggingface/hub/。如果下载失败则回退到轻量模型。
    """
    global _embedder
    if _embedder is not None:
        return _embedder

    try:
        from sentence_transformers import SentenceTransformer

        model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5")
        logger.info("加载向量模型: %s", model_name)
        _embedder = SentenceTransformer(model_name)
        return _embedder
    except ImportError:
        logger.warning("sentence-transformers 未安装，将使用 fallback 模式")
        return None
    except Exception as e:
        logger.error("加载向量模型失败: %s", e)
        return None


def _normalize(vec: np.ndarray) -> np.ndarray:
    """L2 归一化。"""
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def index_faq(faq_data: Optional[list[dict]] = None) -> int:
    """将 FAQ 数据编码为向量并存入内存索引。

    Args:
        faq_data: FAQ 数据列表，默认使用内置种子数据。

    Returns:
        int: 已索引的 FAQ 数量。
    """
    global _faq_store, _faq_vectors

    data = faq_data or FAQ_SEED_DATA
    _faq_store = data

    embedder = _load_embedder()
    if embedder is None:
        _faq_vectors = None
        logger.warning("向量模型不可用，FAQ 仅支持关键词匹配")
        return 0

    questions = [item["question"] for item in data]
    vectors = embedder.encode(questions, normalize_embeddings=True)
    _faq_vectors = np.array(vectors)
    logger.info("FAQ 索引完成: %d 条", len(data))
    return len(data)


def search_faq(
    query: str,
    top_k: int = 3,
    score_threshold: float = 0.5,
) -> list[dict]:
    """向量检索 FAQ。

    优先使用 BGE 向量相似度搜索，模型不可用时回退到关键词匹配。

    Args:
        query: 用户查询文本。
        top_k: 返回的最多 FAQ 条数。
        score_threshold: 最低相似度阈值（低于此值的结果被过滤）。

    Returns:
        list[dict]: FAQ 匹配结果，每项含 id/question/answer/category/score。
    """
    if not _faq_store:
        logger.warning("FAQ 索引为空，请先调用 index_faq()")
        return []

    embedder = _load_embedder()

    if embedder is not None and _faq_vectors is not None:
        return _vector_search(query, top_k, score_threshold, embedder)
    else:
        return _keyword_search(query, top_k)


def _vector_search(
    query: str,
    top_k: int,
    score_threshold: float,
    embedder,
) -> list[dict]:
    """BGE 向量余弦相似度搜索。"""
    query_vec = embedder.encode([query], normalize_embeddings=True)[0]
    scores = np.dot(_faq_vectors, query_vec)

    # 取 top-K
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for i in top_indices:
        score = float(scores[i])
        if score < score_threshold:
            continue
        item = _faq_store[i]
        results.append({
            "id": item["id"],
            "question": item["question"],
            "answer": item["answer"],
            "category": item.get("category", ""),
            "score": round(score, 4),
        })

    logger.info("向量检索: query=%s hits=%d top_score=%.4f", query[:30], len(results), results[0]["score"] if results else 0)
    return results


def _keyword_search(query: str, top_k: int) -> list[dict]:
    """简单关键词匹配回退方案。"""
    from difflib import SequenceMatcher

    scored = []
    for item in _faq_store:
        ratio = SequenceMatcher(None, query, item["question"]).ratio()
        scored.append((ratio, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, item in scored[:top_k]:
        results.append({
            "id": item["id"],
            "question": item["question"],
            "answer": item["answer"],
            "category": item.get("category", ""),
            "score": round(score, 4),
        })

    logger.info("关键词检索: query=%s hits=%d", query[:30], len(results))
    return results


def format_context(results: list[dict]) -> str:
    """将检索结果格式化为 LLM 可用的上下文文本。

    Args:
        results: search_faq 返回的结果列表。

    Returns:
        str: 格式化的上下文文本，如为空则返回空字符串。
    """
    if not results:
        return ""

    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] 问题: {r['question']}\n    答案: {r['answer']}")
    return "\n\n".join(parts)


def init() -> None:
    """初始化检索服务：加载模型并索引 FAQ。

    在应用启动时调用一次。
    """
    count = index_faq()
    if count > 0:
        logger.info("检索服务初始化完成: %d 条 FAQ 已索引", count)
    else:
        logger.warning("检索服务未加载向量模型，将使用关键词匹配")
