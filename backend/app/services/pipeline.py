"""Pipeline 模式 — 将 orchestrator 中的分析步骤拆分为独立可测试的 Stage。

每个 Stage 定义统一接口 execute(ctx) → Generator[str]，yield SSE 事件。
Pipeline 按序执行 Stage 列表，orchestrator 退化为薄 runner。

设计词汇（遵循 /codebase-design）：
- Stage  interface：execute(PipelineContext) → Generator[str]
- Pipeline：组合多个 Stage 的薄 runner，提供 leverage
- PipelineContext：贯穿所有 Stage 的共享状态（immutable input + mutable output）
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator

from app.services.llm import generate_stream
from app.services.nlp_client import get_nlp_client
from app.services.retriever import format_context, search_faq
from app.services.sentiment import analyze as analyze_sentiment
from app.utils.sse import SSEEmitter


# ─── PipelineContext — 贯穿管道的共享状态 ──────────────────


@dataclass
class PipelineContext:
    """Pipeline 执行过程的共享上下文。

    session_id 和 message 为不可变输入；其余字段由各 Stage 填充。
    """

    session_id: str
    message: str
    history: list[dict] | None = None

    # 各 Stage 产出
    intent: str = ""
    confidence: float = 0.0
    sentiment: dict = field(default_factory=dict)
    entities: dict | None = None
    faq_context: str | None = None
    full_answer: str = ""


# ─── Stage 抽象接口 ───────────────────────────────────────


class Stage(ABC):
    """Pipeline 中单个分析步骤的抽象接口。

    每个具体 Stage 实现 execute(ctx)，从 ctx 读取输入、写入产出，
    并通过 yield 发出 SSE 事件字符串。
    """

    @abstractmethod
    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        """执行该分析步骤。

        Args:
            ctx: 贯穿管道的共享上下文。

        Yields:
            str: SSE 事件字符串。
        """
        ...


# ─── 具体 Stage 实现 ──────────────────────────────────────


class IntentStage(Stage):
    """意图分类步骤：调用 NLP 微服务，yield intent SSE 事件。"""

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        emit = SSEEmitter()
        result = get_nlp_client().classify(ctx.message)
        ctx.intent = result["intent"]
        ctx.confidence = result["confidence"]
        yield emit.intent({"intent": ctx.intent, "confidence": ctx.confidence})


class SentimentStage(Stage):
    """情感分析步骤：调用 BERT 模型，yield sentiment SSE 事件。"""

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        emit = SSEEmitter()
        ctx.sentiment = analyze_sentiment(ctx.message)
        yield emit.sentiment(ctx.sentiment)


class EntityStage(Stage):
    """实体抽取步骤：调用 NLP 适配器，yield entity SSE 事件（可选）。"""

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        emit = SSEEmitter()
        data = get_nlp_client().extract(ctx.message)
        if data:
            ctx.entities = data
            yield emit.entity(data)


class RetrieveStage(Stage):
    """FAQ 检索步骤：混合搜索 + 格式化上下文，不 yield 事件。"""

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        results = search_faq(ctx.message, top_k=3, score_threshold=0.4)
        ctx.faq_context = format_context(results) or None
        # 此 Stage 无 SSE 事件产出，返回空迭代器以保持 Generator 类型
        return iter([])


class GenerateStage(Stage):
    """LLM 流式生成步骤：yield 逐 token SSE 事件。"""

    def execute(self, ctx: PipelineContext) -> Generator[str, None, None]:
        emit = SSEEmitter()
        for token in generate_stream(
            ctx.message, ctx.intent, context=ctx.faq_context, history=ctx.history
        ):
            ctx.full_answer += token
            yield emit.token(token)


# ─── Pipeline 薄 runner ───────────────────────────────────


class Pipeline:
    """按序执行 Stage 列表的薄 runner。

    不包含任何业务逻辑——仅迭代 stages 并串联 yield。
    这就是 leverage：一组 Stage 接口产生多种 Stage 组合，
    开发/测试/生产环境可装配不同 pipeline。
    """

    def __init__(self, *stages: Stage) -> None:
        self.stages = stages

    def run(self, ctx: PipelineContext) -> Generator[str, None, None]:
        """按序执行全部 Stage，串联所有 SSE 事件。

        Args:
            ctx: 共享上下文，各 Stage 读取并修改它。

        Yields:
            str: 所有 Stage 产出的 SSE 事件字符串，按执行顺序。
        """
        for stage in self.stages:
            yield from stage.execute(ctx)


# ─── 默认 Pipeline 工厂 ───────────────────────────────────


def create_default_pipeline() -> Pipeline:
    """创建标准五步 Pipeline：意图 → 情感 → 实体 → 检索 → 生成。

    Returns:
        Pipeline: 装配好默认 Stage 序列的管道。
    """
    return Pipeline(
        IntentStage(),
        SentimentStage(),
        EntityStage(),
        RetrieveStage(),
        GenerateStage(),
    )
