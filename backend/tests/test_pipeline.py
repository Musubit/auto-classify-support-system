"""Pipeline 模式测试 — Stage 接口 + PipelineContext + Pipeline runner。

所有 Stage 依赖的外部服务均被 mock，确保测试只验证
Pipeline 的编排逻辑，不依赖网络/模型。
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.pipeline import (
    EntityStage,
    GenerateStage,
    IntentStage,
    Pipeline,
    PipelineContext,
    RetrieveStage,
    SentimentStage,
    Stage,
    create_default_pipeline,
)


# ─── PipelineContext 测试 ───────────────────────────────────


class TestPipelineContext:
    """共享上下文数据类。"""

    def test_default_values(self):
        """未填充的字段应有默认值。"""
        ctx = PipelineContext(session_id="s1", message="你好")
        assert ctx.session_id == "s1"
        assert ctx.message == "你好"
        assert ctx.history is None
        assert ctx.intent == ""
        assert ctx.confidence == 0.0
        assert ctx.sentiment == {}
        assert ctx.entities is None
        assert ctx.faq_context is None
        assert ctx.full_answer == ""

    def test_mutable_fields(self):
        """Stage 应可以修改 ctx 的字段。"""
        ctx = PipelineContext(session_id="s1", message="test")
        ctx.intent = "refund_inquiry"
        ctx.confidence = 0.95
        ctx.sentiment = {"label": "negative", "score": 0.9}
        ctx.entities = {"order_id": {"values": ["DD2024070212345"]}}
        ctx.faq_context = "[1] 问题: ...\n    答案: ..."
        ctx.full_answer = "您好！"

        assert ctx.intent == "refund_inquiry"
        assert ctx.full_answer == "您好！"


# ─── Stage 接口测试 ────────────────────────────────────────


class TestStageInterface:
    """验证 Stage 抽象类契约。"""

    def test_stage_is_abstract(self):
        """Stage 不可直接实例化。"""
        with pytest.raises(TypeError):
            Stage()  # type: ignore[abstract]

    def test_concrete_stage_implements_execute(self):
        """子类必须实现 execute(ctx)。"""

        class MockStage(Stage):
            def execute(self, ctx):
                yield "event"

        stage = MockStage()
        events = list(stage.execute(PipelineContext("s", "m")))
        assert events == ["event"]


# ─── IntentStage 测试 ───────────────────────────────────────


class TestIntentStage:
    """意图分类 Stage — mock NLPClient。"""

    @pytest.fixture
    def ctx(self):
        return PipelineContext(session_id="s1", message="我要退货")

    def test_execute_sets_intent_and_confidence(self, ctx):
        """执行后 ctx.intent 和 ctx.confidence 应被设置。"""
        mock_client = MagicMock()
        mock_client.classify.return_value = {
            "intent": "refund_inquiry",
            "confidence": 0.92,
        }

        with patch(
            "app.services.pipeline.get_nlp_client", return_value=mock_client
        ):
            stage = IntentStage()
            events = list(stage.execute(ctx))

        assert ctx.intent == "refund_inquiry"
        assert ctx.confidence == 0.92

    def test_execute_yields_sse_event(self, ctx):
        """应 yield 一条 SSE intent 事件。"""
        mock_client = MagicMock()
        mock_client.classify.return_value = {
            "intent": "complaint",
            "confidence": 0.88,
        }

        with patch(
            "app.services.pipeline.get_nlp_client", return_value=mock_client
        ):
            stage = IntentStage()
            events = list(stage.execute(ctx))

        assert len(events) == 1
        assert "event: intent" in events[0]
        assert "complaint" in events[0]

    def test_execute_calls_nlp_with_message(self, ctx):
        """应使用 ctx.message 调用 NLP classify。"""
        mock_client = MagicMock()
        mock_client.classify.return_value = {
            "intent": "other",
            "confidence": 0.1,
        }

        with patch(
            "app.services.pipeline.get_nlp_client", return_value=mock_client
        ):
            list(IntentStage().execute(ctx))

        mock_client.classify.assert_called_once_with("我要退货")


# ─── SentimentStage 测试 ────────────────────────────────────


class TestSentimentStage:
    """情感分析 Stage — mock sentiment.analyze。"""

    @pytest.fixture
    def ctx(self):
        return PipelineContext(session_id="s1", message="太差了")

    def test_execute_sets_sentiment(self, ctx):
        """执行后 ctx.sentiment 应被填充。"""
        sentiment_result = {"label": "negative", "score": 0.95}

        with patch(
            "app.services.pipeline.analyze_sentiment",
            return_value=sentiment_result,
        ):
            events = list(SentimentStage().execute(ctx))

        assert ctx.sentiment == sentiment_result

    def test_execute_yields_sse_event(self, ctx):
        """应 yield 一条 SSE sentiment 事件。"""
        sentiment_result = {"label": "positive", "score": 0.88}

        with patch(
            "app.services.pipeline.analyze_sentiment",
            return_value=sentiment_result,
        ):
            events = list(SentimentStage().execute(ctx))

        assert len(events) == 1
        assert "event: sentiment" in events[0]
        assert "positive" in events[0]


# ─── EntityStage 测试 ───────────────────────────────────────


class TestEntityStage:
    """实体抽取 Stage — mock NLPClient.extract。"""

    @pytest.fixture
    def ctx(self):
        return PipelineContext(session_id="s1", message="我的订单DD2024070212345")

    def test_execute_with_entities(self, ctx):
        """有实体时 ctx.entities 应被设置，并 yield SSE。"""
        entity_data = {
            "order_id": {"values": ["DD2024070212345"]},
        }
        mock_client = MagicMock()
        mock_client.extract.return_value = entity_data

        with patch(
            "app.services.pipeline.get_nlp_client", return_value=mock_client
        ):
            events = list(EntityStage().execute(ctx))

        assert ctx.entities == entity_data
        assert len(events) == 1
        assert "event: entity" in events[0]

    def test_execute_without_entities(self, ctx):
        """无实体时不 yield 事件，ctx.entities 保持 None。"""
        mock_client = MagicMock()
        mock_client.extract.return_value = {}

        with patch(
            "app.services.pipeline.get_nlp_client", return_value=mock_client
        ):
            events = list(EntityStage().execute(ctx))

        assert ctx.entities is None
        assert len(events) == 0


# ─── RetrieveStage 测试 ─────────────────────────────────────


class TestRetrieveStage:
    """FAQ 检索 Stage — mock retriever。"""

    @pytest.fixture
    def ctx(self):
        return PipelineContext(session_id="s1", message="退货流程")

    def test_execute_sets_faq_context(self, ctx):
        """命中 FAQ 时 ctx.faq_context 应被设置。"""
        fake_results = [
            {
                "id": "faq_001",
                "question": "如何申请退货退款？",
                "answer": "在「我的订单」中...",
                "category": "refund_inquiry",
                "score": 0.85,
            }
        ]
        formated = "[1] 问题: 如何申请退货退款？\n    答案: 在「我的订单」中..."

        with patch(
            "app.services.pipeline.search_faq", return_value=fake_results
        ), patch(
            "app.services.pipeline.format_context", return_value=formated
        ):
            events = list(RetrieveStage().execute(ctx))

        assert ctx.faq_context == formated
        # RetrieveStage 不 yield 事件
        assert len(events) == 0

    def test_execute_no_match(self, ctx):
        """无命中时 ctx.faq_context 保持 None。"""
        with patch(
            "app.services.pipeline.search_faq", return_value=[]
        ), patch(
            "app.services.pipeline.format_context", return_value=""
        ):
            events = list(RetrieveStage().execute(ctx))

        assert ctx.faq_context is None
        assert len(events) == 0


# ─── GenerateStage 测试 ─────────────────────────────────────


class TestGenerateStage:
    """LLM 生成 Stage — mock generate_stream。"""

    @pytest.fixture
    def ctx(self):
        ctx = PipelineContext(session_id="s1", message="怎么退货")
        ctx.intent = "refund_inquiry"
        ctx.faq_context = "[1] FAQ 内容..."
        return ctx

    def test_execute_streams_tokens(self, ctx):
        """应逐 token yield SSE 事件。"""
        tokens = ["请", "您", "在", "我", "的", "订单", "中", "申请", "退货"]

        with patch(
            "app.services.pipeline.generate_stream", return_value=iter(tokens)
        ):
            events = list(GenerateStage().execute(ctx))

        assert len(events) == len(tokens)
        for event in events:
            assert "event: token" in event

    def test_execute_accumulates_full_answer(self, ctx):
        """ctx.full_answer 应累积所有 token。"""
        tokens = ["您好", "，", "请提供订单号"]

        with patch(
            "app.services.pipeline.generate_stream", return_value=iter(tokens)
        ):
            list(GenerateStage().execute(ctx))

        assert ctx.full_answer == "您好，请提供订单号"

    def test_execute_passes_context_to_llm(self, ctx):
        """generate_stream 应收到 intent 和 faq_context。"""
        with patch(
            "app.services.pipeline.generate_stream", return_value=iter(["OK"])
        ) as mock_gen:
            list(GenerateStage().execute(ctx))

        mock_gen.assert_called_once()
        call_args = mock_gen.call_args
        assert call_args[0][0] == ctx.message
        assert call_args[1]["context"] == ctx.faq_context

    def test_execute_passes_history_to_llm(self, ctx):
        """generate_stream 应收到 history kwarg。"""
        ctx.history = [
            {"role": "user", "content": "之前的问题"},
            {"role": "assistant", "content": "之前的回答"},
        ]
        with patch(
            "app.services.pipeline.generate_stream", return_value=iter(["OK"])
        ) as mock_gen:
            list(GenerateStage().execute(ctx))

        mock_gen.assert_called_once()
        assert mock_gen.call_args[1]["history"] == ctx.history

    def test_execute_history_none_by_default(self, ctx):
        """无历史时 history 应为 None。"""
        with patch(
            "app.services.pipeline.generate_stream", return_value=iter(["OK"])
        ) as mock_gen:
            list(GenerateStage().execute(ctx))

        assert mock_gen.call_args[1]["history"] is None


# ─── Pipeline runner 测试 ──────────────────────────────────


class TestPipeline:
    """Pipeline 薄 runner — 串联 Stage 执行。"""

    @pytest.fixture
    def ctx(self):
        return PipelineContext(session_id="s1", message="test")

    def test_run_executes_stages_in_order(self, ctx):
        """Stage 应按构造顺序执行。"""
        order = []

        class StageA(Stage):
            def execute(self, ctx):
                order.append("A")
                yield "event-a"

        class StageB(Stage):
            def execute(self, ctx):
                order.append("B")
                yield "event-b"

        pipeline = Pipeline(StageA(), StageB())
        events = list(pipeline.run(ctx))

        assert order == ["A", "B"]
        assert events == ["event-a", "event-b"]

    def test_run_empty_pipeline(self, ctx):
        """空 Pipeline 不产生事件。"""
        pipeline = Pipeline()
        events = list(pipeline.run(ctx))
        assert events == []

    def test_run_stage_modifies_context(self, ctx):
        """前一个 Stage 修改的 ctx 应对后一个 Stage 可见。"""

        class StageSet(Stage):
            def execute(self, ctx):
                ctx.intent = "greeting"
                yield from ()

        class StageCheck(Stage):
            def execute(self, ctx):
                assert ctx.intent == "greeting"
                yield "done"

        pipeline = Pipeline(StageSet(), StageCheck())
        events = list(pipeline.run(ctx))
        assert events == ["done"]

    def test_run_generator_is_lazy(self, ctx):
        """Pipeline.run 应返回 generator，不立即执行。"""
        called = [False]

        class LazyStage(Stage):
            def execute(self, ctx):
                called[0] = True
                yield "event"

        pipeline = Pipeline(LazyStage())
        gen = pipeline.run(ctx)
        # 在 next() 调用前不应执行
        assert called[0] is False
        next(gen)
        assert called[0] is True


# ─── create_default_pipeline 测试 ───────────────────────────


class TestDefaultPipeline:
    """默认 Pipeline 工厂。"""

    def test_creates_five_stages(self):
        """应创建 5 个 Stage。"""
        pipeline = create_default_pipeline()
        assert len(pipeline.stages) == 5
        assert isinstance(pipeline.stages[0], IntentStage)
        assert isinstance(pipeline.stages[1], SentimentStage)
        assert isinstance(pipeline.stages[2], EntityStage)
        assert isinstance(pipeline.stages[3], RetrieveStage)
        assert isinstance(pipeline.stages[4], GenerateStage)
