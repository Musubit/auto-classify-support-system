"""FAQ 检索服务 — BGE 向量 + Elasticsearch kNN/BM25 混合检索。

支持三种模式（自动降级）：
1. ES 混合模式（生产）：kNN 向量搜索 + BM25 文本搜索 → RRF 融合
2. 内存向量模式（无 ES）：BGE 余弦相似度
3. 关键词回退（无模型）：difflib 序列匹配

架构：Retriever 类封装全部状态（embedder / faq_store / faq_vectors / es_available），
消除了模块级全局变量，使测试可以创建独立实例而无顺序依赖。
"""

import logging
import os
from typing import Optional

import numpy as np
from flask import current_app

logger = logging.getLogger(__name__)

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


# ─── Retriever 类 ─────────────────────────────────────────


class Retriever:
    """FAQ 检索器，封装 embedder、faq_store、faq_vectors、ES 状态。

    所有状态均为实例属性——测试可创建独立实例，零全局污染。
    通过 Flask app.extensions 注入，避免模块级单例。

    Attributes:
        es_host: Elasticsearch 连接地址。
        es_index: ES 索引名称。
        embedding_model: sentence-transformers 模型名。
        vector_dims: 向量维度。
    """

    def __init__(
        self,
        es_host: str = "http://localhost:9200",
        es_index: str = "faq",
        embedding_model: str = "BAAI/bge-base-zh-v1.5",
        vector_dims: int = 768,
    ) -> None:
        self.es_host = es_host
        self.es_index = es_index
        self.embedding_model = embedding_model
        self.vector_dims = vector_dims

        # 实例状态（非全局）
        self._embedder = None
        self._faq_store: list[dict] = []
        self._faq_vectors: Optional[np.ndarray] = None
        self._es_available: bool = False

    # ─── 初始化 ──────────────────────────────────────

    def initialize(self) -> None:
        """初始化检索服务：ES 索引 + 内存索引 FAQ。

        幂等——重复调用安全。
        """
        # 1. 内存索引（始终启用）
        count = self._index_faq()
        if count > 0:
            logger.info("检索服务初始化完成（内存）: %d 条 FAQ", count)
        else:
            logger.warning("检索服务未加载向量模型，将使用关键词匹配")

        # 2. ES 索引（可选，失败不影响服务）
        try:
            es_count = self._es_index_faq(FAQ_SEED_DATA)
            if es_count > 0:
                self._es_available = True
                logger.info("检索服务 ES 模式已启用: %d 条 FAQ", es_count)
            else:
                logger.info("ES 不可用，使用内存检索模式")
        except Exception as e:
            logger.warning("ES 初始化跳过: %s", e)

    # ─── 向量模型（懒加载） ──────────────────────────

    def _load_embedder(self):
        """懒加载 BGE 向量模型。"""
        if self._embedder is not None:
            return self._embedder

        try:
            from sentence_transformers import SentenceTransformer

            logger.info("加载向量模型: %s", self.embedding_model)
            self._embedder = SentenceTransformer(self.embedding_model)
            return self._embedder
        except ImportError:
            logger.warning("sentence-transformers 未安装，将使用 fallback 模式")
            return None
        except Exception as e:
            logger.error("加载向量模型失败: %s", e)
            return None

    # ─── ES 辅助方法 ─────────────────────────────────

    def _get_es(self):
        """获取 ES 客户端，不可用时返回 None。"""
        try:
            from app.extensions import get_es_client
            return get_es_client()
        except Exception:
            return None

    def _ensure_es_index(self, es, index_name: str) -> bool:
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
                                    "dims": self.vector_dims,
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

    def _es_index_faq(self, faq_data: list[dict]) -> int:
        """将 FAQ 批量写入 ES（含向量）。"""
        es = self._get_es()
        if es is None:
            return 0

        if not self._ensure_es_index(es, self.es_index):
            return 0

        embedder = self._load_embedder()
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
                    "_index": self.es_index,
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
                index=self.es_index,
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
        self, query: str, top_k: int, score_threshold: float,
    ) -> list[dict]:
        """ES kNN 向量 + BM25 混合检索（RRF 融合）。"""
        es = self._get_es()
        if es is None:
            return []

        embedder = self._load_embedder()
        if embedder is None:
            return []

        try:
            query_vec = embedder.encode([query], normalize_embeddings=True)[0].tolist()

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

            resp = es.search(index=self.es_index, body=body)
            hits = resp["hits"]["hits"]

            results = []
            for hit in hits:
                score = float(hit["_score"])
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

    # ─── 内存索引 ────────────────────────────────────

    def _index_faq(self, faq_data: Optional[list[dict]] = None) -> int:
        """将 FAQ 数据编码为向量并存入内存索引。"""
        data = faq_data or FAQ_SEED_DATA
        self._faq_store = data

        embedder = self._load_embedder()
        if embedder is None:
            self._faq_vectors = None
            logger.warning("向量模型不可用，FAQ 仅支持关键词匹配")
            return 0

        questions = [item["question"] for item in data]
        vectors = embedder.encode(questions, normalize_embeddings=True)
        self._faq_vectors = np.array(vectors)
        logger.info("FAQ 内存索引完成: %d 条", len(data))
        return len(data)

    def _vector_search(
        self, query: str, top_k: int, score_threshold: float,
    ) -> list[dict]:
        """BGE 向量余弦相似度搜索。"""
        embedder = self._load_embedder()
        if embedder is None or self._faq_vectors is None:
            return []

        query_vec = embedder.encode([query], normalize_embeddings=True)[0]
        scores = np.dot(self._faq_vectors, query_vec)

        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for i in top_indices:
            score = float(scores[i])
            if score < score_threshold:
                continue
            item = self._faq_store[i]
            results.append({
                "id": item["id"],
                "question": item["question"],
                "answer": item["answer"],
                "category": item.get("category", ""),
                "score": round(score, 4),
            })

        logger.info("向量检索: query=%s hits=%d", query[:30], len(results))
        return results

    def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        """简单关键词匹配回退方案。"""
        from difflib import SequenceMatcher

        scored = []
        for item in self._faq_store:
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

    # ─── 公开接口 ────────────────────────────────────

    def search(
        self,
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
        if not self._faq_store:
            logger.warning("FAQ 索引为空，请先调用 initialize()")
            return []

        # 1. 优先 ES 混合检索
        if self._es_available:
            results = self._es_hybrid_search(query, top_k, score_threshold)
            if results:
                return results

        # 2. 内存向量检索
        embedder = self._load_embedder()
        if embedder is not None and self._faq_vectors is not None:
            return self._vector_search(query, top_k, score_threshold)

        # 3. 关键词回退
        return self._keyword_search(query, top_k)

    @staticmethod
    def format_context(results: list[dict]) -> str:
        """将检索结果格式化为 LLM 可用的上下文文本。"""
        if not results:
            return ""

        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] 问题: {r['question']}\n    答案: {r['answer']}")
        return "\n\n".join(parts)


# ─── 模块级兼容函数（通过 Flask app.extensions 获取实例） ──


def _get_retriever() -> Retriever:
    """从 Flask app.extensions 获取全局 Retriever 实例。"""
    return current_app.extensions["retriever"]


def search_faq(
    query: str,
    top_k: int = 3,
    score_threshold: float = 0.5,
) -> list[dict]:
    """检索 FAQ（模块级兼容函数，委托给 Retriever 实例）。"""
    return _get_retriever().search(query, top_k, score_threshold)


def format_context(results: list[dict]) -> str:
    """格式化 FAQ 结果为 LLM 上下文（模块级兼容函数）。"""
    return Retriever.format_context(results)


# ─── 应用工厂辅助 ─────────────────────────────────────────


def init_retriever(app) -> None:
    """在 Flask 应用中初始化 Retriever 实例并存入 app.extensions。

    Args:
        app: Flask 应用实例。
    """
    retriever = Retriever(
        es_host=app.config.get("ES_HOST", "http://localhost:9200"),
        es_index=app.config.get("ES_INDEX", "faq"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-zh-v1.5"),
        vector_dims=int(os.getenv("EMBEDDING_DIMS", "768")),
    )
    retriever.initialize()
    app.extensions["retriever"] = retriever
    logger.info("Retriever 已初始化并注册到 app.extensions")
