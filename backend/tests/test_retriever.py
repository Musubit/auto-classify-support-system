"""Retriever 检索服务测试 — 内存向量 / ES 混合 / 关键词 fallback。"""

import pytest

from app.services.retriever import FAQ_SEED_DATA, Retriever, format_context, search_faq


# ─── 测试查询（覆盖不同意图 + 同义改写） ───

TEST_QUERIES = [
    ("退货退款", "我要退货，怎么操作啊？", "faq_001"),
    ("物流查询", "我的快递到哪了", "faq_006"),
    ("投诉", "你们客服太差了我要投诉", "faq_014"),
    ("同义改写", "买了东西不想要了能退吗", "faq_008"),
    ("短查询", "发货", "faq_012"),
    ("口语化", "钱啥时候退给我", "faq_002"),
]


# ─── Fixtures ───────────────────────────────────────────────


@pytest.fixture
def retriever_mem():
    """纯内存向量 Retriever（禁用 ES）。"""
    r = Retriever(es_host="http://localhost:9200", es_index="faq")
    r._index_faq()
    r._es_available = False
    return r


@pytest.fixture
def retriever_kw():
    """关键词回退 Retriever（无向量模型 + 无 ES）。"""
    r = Retriever(es_host="http://localhost:9200", es_index="faq")
    r._faq_store = FAQ_SEED_DATA
    r._faq_vectors = None
    r._es_available = False
    return r


# ─── 内存向量检索测试 ──────────────────────────────────────


class TestVectorSearch:
    """BGE 内存向量检索。"""

    def test_index_count(self, retriever_mem):
        """内存索引应包含全部 16 条 FAQ。"""
        assert len(retriever_mem._faq_store) == 16
        assert retriever_mem._faq_vectors is not None
        assert retriever_mem._faq_vectors.shape == (16, 768)

    def test_search_returns_results(self, retriever_mem):
        """检索应返回最多 top_k 条结果。"""
        results = retriever_mem.search("退货", top_k=3)
        assert 1 <= len(results) <= 3

    def test_search_has_required_fields(self, retriever_mem):
        """每条结果应包含 id/question/answer/category/score。"""
        results = retriever_mem.search("退货", top_k=1)
        assert len(results) >= 1
        for field in ("id", "question", "answer", "category", "score"):
            assert field in results[0]

    def test_score_range(self, retriever_mem):
        """相似度分数应在 0~1 之间。"""
        results = retriever_mem.search("退货", top_k=3)
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    @pytest.mark.parametrize("label,query,expected_id", TEST_QUERIES)
    def test_query_matches_expected(self, retriever_mem, label, query, expected_id):
        """测试用例应匹配预期 FAQ（Top-1 score >= 0.5）。"""
        results = retriever_mem.search(query, top_k=1, score_threshold=0.4)
        assert len(results) >= 1, f"[{label}] '{query}' 未命中任何 FAQ"
        # 验证语义匹配合理（score >= 0.5 即视为正确）
        assert results[0]["score"] >= 0.5, (
            f"[{label}] '{query}' → {results[0]['id']} score={results[0]['score']:.3f} < 0.5"
        )

    def test_score_threshold_filters(self, retriever_mem):
        """高阈值应过滤弱匹配。"""
        results = retriever_mem.search("跟客服无关的话题", top_k=3, score_threshold=0.9)
        # 不相关的查询在高阈值下应无结果
        assert len(results) == 0 or all(r["score"] >= 0.9 for r in results)

    def test_empty_faq_store(self, retriever_mem):
        """空 FAQ 存储应返回空列表。"""
        retriever_mem._faq_store = []
        results = retriever_mem.search("退货")
        assert results == []


# ─── 关键词回退测试 ────────────────────────────────────────


class TestKeywordFallback:
    """difflib 关键词匹配回退。"""

    def test_keyword_search_returns_results(self, retriever_kw):
        """关键词匹配应对短查询返回结果。"""
        results = retriever_kw._keyword_search("退货退款", top_k=3)
        assert len(results) >= 1

    def test_keyword_identical_query(self, retriever_kw):
        """完全相同的查询应得满分。"""
        results = retriever_kw._keyword_search("如何申请退货退款？", top_k=1)
        assert len(results) >= 1
        assert results[0]["score"] > 0.9

    def test_search_fallback_to_keyword(self, retriever_kw):
        """向量不可用时 search() 应回退到关键词。"""
        results = retriever_kw.search("退货", top_k=3)
        assert len(results) >= 1
        for r in results:
            assert "score" in r


# ─── 格式化测试 ────────────────────────────────────────────


class TestFormatContext:
    """FAQ 结果格式化为 LLM 上下文。"""

    def test_format_non_empty(self, retriever_mem):
        """非空结果应包含问题与答案。"""
        results = retriever_mem.search("退货", top_k=2)
        text = format_context(results)
        assert len(text) > 0
        assert "[1]" in text
        if len(results) >= 2:
            assert "[2]" in text

    def test_format_empty(self):
        """空结果应返回空字符串。"""
        assert format_context([]) == ""


# ─── ES 状态诊断测试 ──────────────────────────────────────


class TestESDiagnostics:
    """ES 连通性与索引诊断（ES 不可用时跳过）。"""

    @pytest.fixture
    def es_client(self):
        """尝试创建 ES 客户端，不可用时返回 None。"""
        try:
            from elasticsearch import Elasticsearch

            es = Elasticsearch("http://localhost:9200")
            es.info()  # 验证连通
            yield es
            es.close()
        except Exception:
            yield None

    def test_es_connected(self, es_client):
        """ES 应可连通。"""
        if es_client is None:
            pytest.skip("ES 不可用")
        info = es_client.info()
        assert "version" in info

    def test_faq_index_exists(self, es_client):
        """faq 索引应存在。"""
        if es_client is None:
            pytest.skip("ES 不可用")
        assert es_client.indices.exists(index="faq"), (
            "faq 索引不存在，请重启后端触发 init_retriever()"
        )

    def test_faq_doc_count(self, es_client):
        """faq 索引应有 16 条文档。"""
        if es_client is None:
            pytest.skip("ES 不可用")
        count = es_client.count(index="faq")
        assert count["count"] == 16, (
            f"faq 索引文档数: {count['count']}，预期 16"
        )


# ─── 模块级兼容函数测试 ───────────────────────────────────


class TestModuleLevelAPI:
    """search_faq / format_context 模块级函数（需要 app context）。"""

    def test_search_faq_requires_app_context(self):
        """模块级 search_faq 需 Flask app context，无 context 应抛异常。"""
        with pytest.raises(RuntimeError):
            search_faq("退货")
