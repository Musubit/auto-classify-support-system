# 架构说明

> **版本**: v1.0
> **日期**: 2026-07-03
> **状态**: 与代码库（commit a738ab4）对齐
> **目标**: 电商客服智能问答系统——意图分类、情感分析、实体抽取、知识库检索、LLM 流式生成

## 1. 总体架构

```
用户 → Vue 3 前端 → Flask API → Orchestrator → Pipeline
                                                ├── IntentStage（NLPClient → SetFit）
                                                ├── SentimentStage（BERT）
                                                ├── EntityStage（NLPClient → jieba + 正则）
                                                ├── RetrieveStage（Retriever → ES / BGE / 关键词）
                                                └── GenerateStage（DeepSeek / Ollama 流式）
                                              → SSE Emitter → 前端 SSE 流
                                              → SQLite 持久化
```

**技术栈：**

| 层 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Vite + Pinia | SPA，SSE 流式渲染 |
| 后端 | Flask 3.x | 应用工厂模式，Blueprint 路由 |
| 意图分类 | SetFit + sentence-transformers | `paraphrase-multilingual-MiniLM-L12-v2`，7 类，42 样本 |
| 情感分析 | BERT（京东评论微调） | `uer/roberta-base-finetuned-jd-binary-chinese`，置信度阈值三分类 |
| 实体抽取 | jieba POS + 正则 | 7 类电商实体（订单号、手机号、金额、日期、运单号、快递公司、商品名） |
| 知识库检索 | BGE + Elasticsearch 8.x | kNN + BM25 混合检索，三级 fallback（ES → 内存向量 → 关键词） |
| 回答生成 | DeepSeek API / Ollama 本地 | 双后端，OpenAI 兼容接口，`LLM_BACKEND` 环境变量切换 |
| 会话持久化 | SQLite（WAL 模式） | 零额外依赖，Python stdlib sqlite3 |
| 容器编排 | Docker Compose | 5 容器：ES + Ollama + NLP + Backend + Frontend |

**不使用 Redis。** 会话、缓存全部通过 SQLite 实现。

## 2. 仓库结构

```
├── frontend/                    # Vue 3 SPA
│   └── src/
│       ├── App.vue              # 根组件：Sidebar + ChatArea
│       ├── api/index.js         # Axios + SSE 客户端（fetch ReadableStream）
│       ├── stores/chat.js       # Pinia store（messages, sessions, SSE 回调）
│       ├── utils/labels.js      # 意图/情感中文标签映射
│       └── components/
│           ├── Sidebar.vue      # 会话历史列表 + 新建对话
│           ├── ChatArea.vue     # 消息区 + 输入框 + 欢迎页
│           └── MessageBubble.vue # 消息气泡（意图/情感/实体标签）
│
├── backend/                     # Flask API 服务
│   ├── run.py                   # 入口
│   └── app/
│       ├── __init__.py          # create_app() 工厂：NLPClient → DB → Retriever → Sentiment
│       ├── config.py            # 环境变量配置
│       ├── extensions.py        # ES 客户端单例
│       ├── api/
│       │   ├── __init__.py      # Blueprint + /api/health
│       │   ├── chat.py          # POST /api/chat（SSE 流式）
│       │   └── session.py       # GET/DELETE /api/sessions
│       ├── services/
│       │   ├── orchestrator.py  # 薄 runner：会话管理 + Pipeline 调度
│       │   ├── pipeline.py      # Pipeline + 5 个 Stage（架构核心）
│       │   ├── nlp_client.py    # NLP 微服务适配器（classify + extract）
│       │   ├── retriever.py     # Retriever 类：ES/BGE/关键词三级检索
│       │   ├── sentiment.py     # BERT 情感分析（置信度阈值 → 三分类）
│       │   ├── llm.py           # 双后端 LLM 流式生成（DeepSeek/Ollama）
│       │   └── db.py            # SQLite 持久化（会话 + 消息 CRUD）
│       ├── models/
│       │   └── message.py       # Pydantic ChatRequest
│       └── utils/
│           ├── sse.py           # format_sse_event + SSEEmitter 类
│           └── response.py      # api_response / error_response
│
├── nlp/                         # NLP 微服务（Flask :5005）
│   ├── src/
│   │   ├── server.py            # /health, /intents, /parse, /parse/batch, /extract
│   │   ├── predict.py           # IntentClassifier（SetFit 包装）
│   │   ├── preprocess.py        # jieba 分词
│   │   ├── extract.py           # 实体抽取（jieba POS + 正则）
│   │   └── train.py             # SetFit 训练脚本
│   ├── config/intents.yml       # 7 类意图标签
│   └── data/training.jsonl      # 42 条训练样本
│
├── docker/
│   └── elasticsearch.yml        # ES 配置
│
└── docker-compose.yml           # 5 容器：ES + Ollama + NLP + Backend + Frontend
```

## 3. 核心架构决策

### 3.1 Pipeline 模式（2026-07 深化）

orchestrator 从 God Function（136 行直接调用 6 个依赖）重构为薄 runner + Pipeline：

```python
# orchestrator.py — 薄 runner
ctx = PipelineContext(session_id=session_id, message=message)
pipeline = create_default_pipeline()  # Intent → Sentiment → Entity → Retrieve → Generate
for event in pipeline.run(ctx):
    yield event

# pipeline.py — 每个 Stage 独立可测试
class IntentStage(Stage):
    def execute(self, ctx) -> Generator[str]:
        result = get_nlp_client().classify(ctx.message)
        ctx.intent = result["intent"]
        yield SSEEmitter().intent({"intent": ctx.intent, ...})
```

**设计词汇（遵循 /codebase-design）：**
- **Stage interface**：`execute(PipelineContext) → Generator[str]`
- **Pipeline**：组合 Stage 的薄 runner，提供 leverage
- **PipelineContext**：贯穿所有 Stage 的共享状态（dataclass）

### 3.2 NLPClient 适配器

统一对 NLP 微服务的所有 HTTP 调用，替代分散的 `classifier.py`（已删除）和 orchestrator 中的 raw `requests.post`：

```python
class NLPClient:
    def classify(self, text: str) -> dict:   # → /parse
    def extract(self, text: str) -> dict:    # → /extract
```

**原则：一个外部服务 = 一个 adapter seam。**

### 3.3 SSEEmitter

封装全部 SSE 事件名和数据结构，与业务逻辑分离：

```python
class SSEEmitter:
    def intent(self, data: dict) -> str:      # event: intent
    def sentiment(self, data: dict) -> str:   # event: sentiment
    def entity(self, data: dict) -> str:      # event: entity
    def token(self, text: str) -> str:        # event: token
    def done(self, message_id, full_answer, source) -> str:  # event: done
    def error(self, message: str) -> str:     # event: error
```

### 3.4 Retriever 类

消除 4 个模块级全局变量（`_embedder`、`_faq_store`、`_faq_vectors`、`_es_available`），转为类实例属性：

```python
class Retriever:
    def __init__(self, es_host, es_index, embedding_model, vector_dims): ...
    def initialize(self) -> None:  # ES 索引 + 内存索引
    def search(self, query, top_k, score_threshold) -> list[dict]:  # 三级 fallback
```

通过 `app.extensions["retriever"]` 注入，测试可创建独立实例。

### 3.5 SQLite 替代 Redis

Redis 已从系统中完全移除（无服务、无依赖、无代码引用）。会话和消息持久化使用 Python stdlib `sqlite3`（WAL 模式），零额外依赖。

## 4. SSE 事件流

```
POST /api/chat { session_id, message }
  → event: intent     { intent, confidence }
  → event: sentiment  { label, score }
  → event: entity     { entities, summary }        （可选，仅当抽取到实体时）
  → event: token      { token }                    （×N，流式逐字）
  → event: done       { message_id, full_answer, source }
  或
  → event: error      { message }
  → event: done       { message_id, "", source: "error" }
```

## 5. API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat` | SSE 流式聊天 |
| GET | `/api/sessions` | 会话列表（按时间倒序） |
| GET | `/api/sessions/<id>` | 会话详情 + 消息 |
| DELETE | `/api/sessions/<id>` | 删除会话 |
| GET | `/docs` | Swagger/OpenAPI 文档 |

## 6. 模型选型

### 6.1 意图分类

| 项目 | 内容 |
|------|------|
| **方案** | SetFit 少样本微调 |
| **基础模型** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| **训练数据** | 42 条（7 类 × 6 样本） |
| **推理服务** | NLP 微服务 `/parse`、`/parse/batch` |
| **状态** | ✅ 已实现 |

### 6.2 向量检索

| 项目 | 内容 |
|------|------|
| **模型** | `BAAI/bge-base-zh-v1.5`（768 维） |
| **检索方式** | ES kNN + BM25 → 内存 BGE 余弦相似度 → difflib 关键词（三级 fallback） |
| **对应服务** | `backend/app/services/retriever.py`（Retriever 类） |
| **状态** | ✅ 已实现 |

### 6.3 情感分析

| 项目 | 内容 |
|------|------|
| **模型** | `uer/roberta-base-finetuned-jd-binary-chinese` |
| **策略** | 二分类模型 + 置信度阈值（默认 0.85）→ 三分类（正/负/中） |
| **对应服务** | `backend/app/services/sentiment.py` |
| **状态** | ✅ 已实现 |

### 6.4 实体抽取

| 项目 | 内容 |
|------|------|
| **方案** | jieba 词性标注 + 正则表达式 |
| **实体类型** | 订单号、手机号、金额、日期、运单号、快递公司、商品名（7 类） |
| **推理服务** | NLP 微服务 `/extract` |
| **状态** | ✅ 已实现 |

### 6.5 回答生成

| 项目 | 内容 |
|------|------|
| **方案** | 双后端：DeepSeek API（云端）/ Ollama 本地 |
| **本地模型** | `qwen2.5:7b`（Q4_K_M 量化，~4.5GB 显存） |
| **切换方式** | `LLM_BACKEND=deepseek|ollama` 环境变量 |
| **SDK** | `openai`（均兼容 OpenAI 接口） |
| **对应服务** | `backend/app/services/llm.py` |
| **状态** | ✅ 已实现 |

## 7. 设计原则

1. 服务边界清晰，避免循环依赖（当前依赖图为纯树状）。
2. 不在 API 层写业务逻辑。
3. 失败路径显式处理（三级 fallback、置信度阈值、静默降级）。
4. **Seam 原则**：外部服务 → adapter；序列化格式 → emitter；业务流程 → pipeline stage。
5. **Locality 原则**：每个模块的代码、测试、错误处理在同一位置。
6. 文档和实现保持同一套口径。
