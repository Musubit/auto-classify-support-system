"""适配器层测试 — NLPClient / Sentiment / LLM。

所有外部依赖被 mock，验证适配器逻辑而非模型本身。
依赖 current_app 的测试通过 app_context fixture 提供上下文。
"""

from unittest.mock import MagicMock, patch

import pytest


# ─── NLPClient 适配器测试 ───────────────────────────────────


class TestNLPClient:
    """NLP 微服务 HTTP 适配器。"""

    @pytest.fixture
    def client(self):
        from app.services.nlp_client import NLPClient
        return NLPClient(base_url="http://test:5005", timeout=2.0)

    def test_initialization(self, client):
        """初始化后 base_url 应已去除尾部斜杠。"""
        assert client.base_url == "http://test:5005"
        assert client.timeout == 2.0

    def test_base_url_strips_trailing_slash(self):
        """base_url 尾部斜杠应被去除。"""
        from app.services.nlp_client import NLPClient
        c = NLPClient(base_url="http://test:5005/")
        assert c.base_url == "http://test:5005"

    def test_classify_success(self, client):
        """正常分类返回 intent 和 confidence。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "intent": "refund_inquiry",
            "confidence": 0.92,
        }

        with patch("app.services.nlp_client.requests.post", return_value=mock_resp):
            result = client.classify("我要退货")

        assert result["intent"] == "refund_inquiry"
        assert result["confidence"] == 0.92

    def test_classify_failure_returns_fallback(self, client):
        """NLP 服务不可用时返回 other。"""
        with patch("app.services.nlp_client.requests.post", side_effect=ConnectionError):
            result = client.classify("随便什么")

        assert result["intent"] == "other"
        assert result["confidence"] == 0.0

    def test_classify_http_error_returns_fallback(self, client):
        """HTTP 4xx/5xx 返回 fallback。"""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("app.services.nlp_client.requests.post", return_value=mock_resp):
            result = client.classify("随便什么")

        assert result["intent"] == "other"

    def test_extract_with_entities(self, client):
        """有实体时返回 entities 和 summary。"""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "entities": {"order_id": {"values": ["DD123"]}},
            "summary": "订单号: DD123",
        }

        with patch("app.services.nlp_client.requests.post", return_value=mock_resp):
            result = client.extract("订单DD123")

        assert "entities" in result
        assert "summary" in result

    def test_extract_empty_entities_returns_empty_dict(self, client):
        """无实体时返回 {}。"""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"entities": {}, "summary": ""}

        with patch("app.services.nlp_client.requests.post", return_value=mock_resp):
            result = client.extract("你好")

        assert result == {}

    def test_extract_connection_error_returns_empty_dict(self, client):
        """连接错误静默返回 {}。"""
        with patch("app.services.nlp_client.requests.post", side_effect=ConnectionError):
            result = client.extract("随便")

        assert result == {}

    def test_extract_calls_correct_endpoint(self, client):
        """应调用 /extract 端点。"""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"entities": {}, "summary": ""}

        with patch("app.services.nlp_client.requests.post", return_value=mock_resp) as mock_post:
            client.extract("测试")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "/extract" in args[0]


# ─── Sentiment 情感分析测试 ─────────────────────────────────


class TestSentiment:
    """BERT 情感分析服务（mock pipeline，通过 app_context 提供配置）。"""

    def test_analyze_positive(self, app_context):
        """正向情感应识别为 positive。"""
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"label": "positive", "score": 0.95}]

        with patch("app.services.sentiment._sentiment_pipeline", mock_pipe), \
             patch("app.services.sentiment._load_pipeline", return_value=mock_pipe):
            from app.services.sentiment import analyze
            result = analyze("这个商品很好用")

            assert result["label"] == "positive"
            assert result["score"] > 0.8

    def test_analyze_negative(self, app_context):
        """负向情感应识别为 negative。"""
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"label": "negative", "score": 0.92}]

        with patch("app.services.sentiment._sentiment_pipeline", mock_pipe), \
             patch("app.services.sentiment._load_pipeline", return_value=mock_pipe):
            from app.services.sentiment import analyze
            result = analyze("质量太差了")

            assert result["label"] == "negative"

    def test_analyze_below_threshold_returns_neutral(self, app_context):
        """置信度低于阈值应回退为 neutral。"""
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"label": "negative", "score": 0.60}]

        with patch("app.services.sentiment._sentiment_pipeline", mock_pipe), \
             patch("app.services.sentiment._load_pipeline", return_value=mock_pipe):
            from app.services.sentiment import analyze
            result = analyze("今天天气不错")

            assert result["label"] == "neutral"

    def test_analyze_model_unavailable_returns_neutral(self, app_context):
        """模型不可用时返回 neutral。"""
        with patch("app.services.sentiment._load_pipeline", return_value=None):
            from app.services.sentiment import analyze
            result = analyze("随便")

            assert result["label"] == "neutral"
            assert result["score"] == 0.0

    def test_label_map_covers_jd_model_labels(self):
        """京东评论模型标签应映射为统一格式。"""
        from app.services.sentiment import LABEL_MAP

        assert LABEL_MAP["negative (stars 1, 2 and 3)"] == "negative"
        assert LABEL_MAP["positive (stars 4 and 5)"] == "positive"
        assert LABEL_MAP["positive"] == "positive"
        assert LABEL_MAP["negative"] == "negative"


# ─── LLM 生成测试 ──────────────────────────────────────────


class TestLLM:
    """LLM 回答生成（通过 app_context 提供配置，mock OpenAI client）。"""

    def test_build_messages_without_context(self):
        """无检索上下文时仅含 system + user。"""
        from app.services.llm import build_messages

        messages = build_messages("我想退货", "refund_inquiry")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "我想退货"

    def test_build_messages_with_context(self):
        """有检索上下文时拼入 system prompt。"""
        from app.services.llm import build_messages

        context = "[1] 问题: 如何退货\n    答案: 在订单中申请"
        messages = build_messages("我想退货", "refund_inquiry", context=context)
        assert len(messages) == 2
        assert context in messages[0]["content"]

    def test_build_messages_with_history(self):
        """历史消息应插入 system 和 current user 之间。"""
        from app.services.llm import build_messages

        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好！"},
        ]
        messages = build_messages("退货", "refund_inquiry", history=history)
        assert len(messages) == 4  # system + 2 history + 1 current
        assert messages[1] == history[0]
        assert messages[2] == history[1]
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "退货"

    def test_intent_system_prompts_all_present(self):
        """所有 7 种意图均有 system prompt。"""
        from app.services.llm import INTENT_SYSTEM_PROMPTS

        expected_intents = {
            "refund_inquiry", "logistics_inquiry", "product_inquiry",
            "order_inquiry", "complaint", "greeting", "other",
        }
        assert set(INTENT_SYSTEM_PROMPTS.keys()) == expected_intents

    def test_get_client_deepseek(self, app_context):
        """DeepSeek 后端配置正确（app_context 提供 config）。"""
        from app.services.llm import _get_client_and_model

        client, model = _get_client_and_model("deepseek")

        assert model == "deepseek-v4-flash"
        assert client.api_key == "sk-test-key"

    def test_get_client_deepseek_missing_key(self, app_context):
        """DeepSeek 无 API Key 抛 ValueError。"""
        # 临时覆盖配置中的 API Key
        app_context.config["DEEPSEEK_API_KEY"] = ""

        from app.services.llm import _get_client_and_model
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            _get_client_and_model("deepseek")

    def test_get_client_ollama(self, app_context):
        """Ollama 后端配置正确。"""
        from app.services.llm import _get_client_and_model

        client, model = _get_client_and_model("ollama")

        assert model == "qwen2.5:7b"
        assert client.api_key == "ollama"

    def test_generate_stream_yields_tokens(self, app_context):
        """流式生成应逐 token yield。"""
        from app.services.llm import generate_stream

        mock_client = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock(delta=MagicMock(content="测试"))]
        mock_client.chat.completions.create.return_value = iter([mock_chunk])

        with patch("app.services.llm._get_client_and_model", return_value=(mock_client, "test-model")):
            tokens = list(generate_stream("你好", "greeting"))
            assert "测试" in tokens

    def test_generate_stream_returns_full_answer(self, app_context):
        """generator return value 应为完整回答。"""
        from app.services.llm import generate_stream

        mock_client = MagicMock()
        chunks = []
        for token in ["你", "好", "！"]:
            c = MagicMock()
            c.choices = [MagicMock(delta=MagicMock(content=token))]
            chunks.append(c)
        mock_client.chat.completions.create.return_value = iter(chunks)

        with patch("app.services.llm._get_client_and_model", return_value=(mock_client, "test-model")):
            gen = generate_stream("你好", "greeting")
            tokens = list(gen)
            assert tokens == ["你", "好", "！"]
            # StopIteration value
            try:
                next(gen)
            except StopIteration as e:
                assert e.value == "你好！"
