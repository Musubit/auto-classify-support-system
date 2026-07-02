"""FAQ 检索服务 — BGE 向量 + Elasticsearch kNN/BM25 混合检索。

支持三种模式（自动降级）：
1. ES 混合模式（生产）：kNN 向量搜索 + BM25 文本搜索 → RRF 融合
2. 内存向量模式（无 ES）：BGE 余弦相似度
3. 关键词回退（无模型）：difflib 序列匹配
"""

import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# 全局懒加载实例
_embedder = None
_faq_store: list[dict] = []
_faq_vectors: Optional[np.ndarray] = None
_es_available: bool = False

# BGE base 向量维度
VECTOR_DIMS = int(os.getenv("EMBEDDING_DIMS", "768"))


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


# ─── 向量模型 ───

def _load_embedder():
    """懒加载 BGE 向量模型。"""
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


# ─── ES 模式 ───

def _get_es():
    """获取 ES 客户端，不可用时返回 None。"""
    try:
        from app.extensions import get_es_client
        return get_es_client()
    except Exception:
        return None


def _ensure_es_index(es, index_name: str) -> bool:
    """确保 ES 索引存在并配置 mapping（幂等）。"""
    try:
        if not es.indices.exists(index=index_name):
            es.indices.create(
                index=index_name,
                body={
                    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                    "mappings": {
                        "properties": {
                            "question": {"type": "text", "analyzer": "standard"},
                            "answer": {"type": "text", "analyzer": "standard"},
                            "category": {"type": "keyword"},
                            "question_vector": {
                                "type": "dense_vector",
                                "dims": VECTOR_DIMS,
                                "index": True,
                                "similarity": "cosine",
                            },
                        }
                    },
                },
            )
            logger.info("ES 索引已创建: %s", index_name)
        return True
    except Exception as e:
        logger.warning("ES 索引创建失败: %s", e)
        return False


def _es_index_faq(faq_data: list[dict], index_name: str) -> int:
    """将 FAQ 批量写入 ES（含向量）。"""
    es = _get_es()
    if es is None:
        return 0

    if not _ensure_es_index(es, index_name):
        return 0

    embedder = _load_embedder()
    if embedder is None:
        logger.warning("向量模型不可用，ES 索引跳过")
        return 0

    try:
        from elasticsearch.helpers import bulk

        questions = [item["question"] for item in faq_data]
        vectors = embedder.encode(questions, normalize_embeddings=True)

        actions = []
        for i, item in enumerate(faq_data):
            actions.append({
                "_index": index_name,
                "_id": item["id"],
                "_source": {
                    "question": item["question"],
                    "answer": item["answer"],
                    "category": item.get("category", ""),
                    "question_vector": vectors[i].tolist(),
                },
            })

        # 先清空再写入（确保幂等）
        es.delete_by_query(
            index=index_name,
            body={"query": {"match_all": {}}},
            refresh=True,
        )

        success, _ = bulk(es, actions, refresh=True)
        logger.info("ES FAQ 索引完成: %d/%d 条", success, len(faq_data))
        return success
    except Exception as e:
        logger.error("ES FAQ 索引失败: %s", e)
        return 0


def _es_hybrid_search(
    query: str,
    index_name: str,
    top_k: int,
    score_threshold: float,
) -> list[dict]:
    """ES kNN 向量 + BM25 混合检索（RRF 融合）。"""
    es = _get_es()
    if es is None:
        return []

    embedder = _load_embedder()
    if embedder is None:
        return []

    try:
        query_vec = embedder.encode([query], normalize_embeddings=True)[0].tolist()

        # 单次查询同时做 kNN + BM25，ES 8.12+ 支持 knn 子句
        body = {
            "knn": {
                "field": "question_vector",
                "query_vector": query_vec,
                "k": top_k * 2,
                "num_candidates": 32,
            },
            "query": {
                "match": {"question": {"query": query, "boost": 0.3}}
            },
            "size": top_k,
        }

        resp = es.search(index=index_name, body=body)
        hits = resp["hits"]["hits"]

        results = []
        for hit in hits:
            score = float(hit["_score"])
            # ES 分数归一化到 [0, 1]
            norm_score = min(score / 2.0, 1.0)
            if norm_score < score_threshold:
                continue
            src = hit["_source"]
            results.append({
                "id": hit["_id"],
                "question": src["question"],
                "answer": src["answer"],
                "category": src.get("category", ""),
                "score": round(norm_score, 4),
            })

        logger.info("ES 混合检索: query=%s hits=%d", query[:30], len(results))
        return results
    except Exception as e:
        logger.error("ES 检索失败: %s，回退内存模式", e)
        return []


# ─── 内存向量模式 ───

def index_faq(faq_data: Optional[list[dict]] = None) -> int:
    """将 FAQ 数据编码为向量并存入内存索引。

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
    logger.info("FAQ 内存索引完成: %d 条", len(data))
    return len(data)


def _vector_search(
    query: str,
    top_k: int,
    score_threshold: float,
    embedder,
) -> list[dict]:
    """BGE 向量余弦相似度搜索。"""
    query_vec = embedder.encode([query], normalize_embeddings=True)[0]
    scores = np.dot(_faq_vectors, query_vec)

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

    logger.info("向量检索: query=%s hits=%d", query[:30], len(results))
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


# ─── 统一检索入口 ───

def search_faq(
    query: str,
    top_k: int = 3,
    score_threshold: float = 0.5,
) -> list[dict]:
    """检索 FAQ — 自动选择最优模式：ES 混合 > 内存向量 > 关键词。

    Args:
        query: 用户查询文本。
        top_k: 返回的最多 FAQ 条数。
        score_threshold: 最低相似度阈值。

    Returns:
        list[dict]: FAQ 匹配结果。
    """
    if not _faq_store:
        logger.warning("FAQ 索引为空，请先调用 index_faq()")
        return []

    # 1. 优先 ES 混合检索
    if _es_available:
        index_name = os.getenv("ES_INDEX", "faq")
        results = _es_hybrid_search(query, index_name, top_k, score_threshold)
        if results:
            return results

    # 2. 内存向量检索
    embedder = _load_embedder()
    if embedder is not None and _faq_vectors is not None:
        return _vector_search(query, top_k, score_threshold, embedder)

    # 3. 关键词回退
    return _keyword_search(query, top_k)


def format_context(results: list[dict]) -> str:
    """将检索结果格式化为 LLM 可用的上下文文本。"""
    if not results:
        return ""

    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] 问题: {r['question']}\n    答案: {r['answer']}")
    return "\n\n".join(parts)


# ─── 初始化 ───

def init() -> None:
    """初始化检索服务：ES 索引 + 内存索引 FAQ。"""
    global _es_available

    # 1. 内存索引（始终启用）
    count = index_faq()
    if count > 0:
        logger.info("检索服务初始化完成（内存）: %d 条 FAQ", count)
    else:
        logger.warning("检索服务未加载向量模型，将使用关键词匹配")

    # 2. ES 索引（可选，失败不影响服务）
    try:
        index_name = os.getenv("ES_INDEX", "faq")
        es_count = _es_index_faq(FAQ_SEED_DATA, index_name)
        if es_count > 0:
            _es_available = True
            logger.info("检索服务 ES 模式已启用: %d 条 FAQ", es_count)
        else:
            logger.info("ES 不可用，使用内存检索模式")
    except Exception as e:
        logger.warning("ES 初始化跳过: %s", e)
