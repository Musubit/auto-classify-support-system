# auto-classify-support-system 项目设计文档

> **版本**: v1.3（历史文档，2026-07-04 最终勘误）
> **日期**: 2026-06-30（原始），2026-07-04（最终勘误）
> **状态**: ⚠️ **此文档已冻结，是对项目设计阶段的历史记录。** 下划线标注的假设已被后续实现推翻。
> **当前架构请以 [`docs/architecture.md`](../architecture.md)、[`docs/api.md`](../api.md)、[`CONTEXT.md`](../../../CONTEXT.md) 为准。**
>
> **v1.3 主要出入点（与当前代码库的差异）：**
> - ~~Redis~~ → 已替换为 **SQLite**（`backend/app/services/db.py`，WAL 模式）
> - ~~classifier.py~~ → 已替换为 **NLPClient 适配器**（`backend/app/services/nlp_client.py`）
> - ~~God Function orchestrator~~ → 已重构为 **Pipeline + 5 Stage** 模式（`pipeline.py`）
> - ~~Ollama 未实现~~ → 已实现双后端（`LLM_BACKEND=ollama` / `deepseek`）
> - ~~实体抽取缺失~~ → 已实现（`nlp/src/extract.py`，jieba + 正则，7 类实体）
> - ~~SSE 空壳~~ → 已封装 **SSEEmitter** 类（`backend/app/utils/sse.py`）
> - 新增 `CONTEXT.md`（领域词汇表）、`docs/adr/`（架构决策记录）
> - ~~多轮对话历史未传递~~ → 已实现全链路历史传递（orchestrator → PipelineContext → GenerateStage → LLM）
> - ~~无上下文窗口管理~~ → 已实现 `estimate_tokens()` + `truncate_history()` + `MAX_CONTEXT_TOKENS` 截断管理
> - 所有标记为 🔴 的核心模块已全部实现并测试覆盖（144 backend + 42 nlp = 186 用例）
> - 新增 **数据分析看板**（`/plan` 路由，ECharts 可视化，`GET /api/analytics` SQLite 聚合查询，右上角图标入口）

> **v1.2 变更摘要**（相对于 v1.1）：
> - 架构方案：意图分类从 Rasa 切换为 **SetFit**（少样本微调，42 条数据即可），已实现 ✅
> - NLP 目录结构：从 Rasa 项目结构变更为 SetFit + Flask HTTP API 结构
> - 技术栈：移除 Rasa Open Source / rasa-sdk，新增 SetFit / sentence-transformers / jieba
> - 目录结构：更新为实际仓库结构，标注各模块实现状态
> - 开发顺序：更新当前实际进度

---

## 1. 项目概述

### 1.1 项目名称

**auto-classify-support-system** — 问题自动分类与回答生成客服系统

### 1.2 核心功能

| 编号 | 功能 | 说明 | 状态 |
|------|------|------|------|
| F1 | 问题分类 | 由 SetFit 少样本微调模型自动识别用户意图（退货、物流、商品咨询、投诉等 7 类） | ✅ 已实现 |
| F2 | 实体抽取 | 提取订单号、手机号、运单号、快递公司、金额、日期、商品名等 7 类实体 | ✅ 已实现 |
| F3 | 知识库检索 | 基于 BGE 向量 + ES kNN/BM25 混合检索（三级 fallback） | ✅ 已实现 |
| F4 | 情感分析 | 基于 BERT 京东评论微调模型分析用户消息情感（正/负/中三分类） | ✅ 已实现 |
| F5 | 多轮对话 | 基于 SQLite（WAL 模式）持久化会话上下文，历史消息全链路传递至 LLM，支持上下文窗口自动截断 | ✅ 已实现 |
| F6 | 回答生成 | 基于 RAG 架构，将检索结果喂给 DeepSeek / Ollama LLM 生成最终回答 | ✅ 已实现 |
| F7 | 用户界面 | 提供类 IM 的聊天界面，SSE 流式渲染，侧边栏会话历史管理 | ✅ 已实现 |

### 1.3 架构方案

采用 **混合方案：SetFit 意图分类 + BGE 向量检索 + RAG 回答生成**。

```
用户 → Vue 前端 → Flask API（Pipeline 编排）
                    ├── IntentStage     → NLPClient 适配器 → SetFit NLP（意图分类）
                    ├── SentimentStage  → BERT 模型（情感分析）
                    ├── EntityStage     → NLPClient 适配器 → jieba + 正则（实体抽取）
                    ├── RetrieveStage   → Retriever 类 → ES kNN/BM25 + BGE 内存向量（三级 fallback）
                    └── GenerateStage   → DeepSeek / Ollama（LLM 流式生成）
                    
会话持久化: SQLite（WAL 模式，零额外依赖）
SSE 推送: SSEEmitter → 前端逐字渲染
```

**关键设计决策（v1.3 更新）：**

- 意图分类由 **SetFit** 负责（基于 `paraphrase-multilingual-MiniLM-L12-v2`，42 条标注数据少样本微调）
- 实体抽取由 **NLP 微服务** 统一提供（jieba 词性标注 + 正则，`/extract` 端点）
- 检索语义能力由 **BGE 向量模型**（`BAAI/bge-base-zh-v1.5`）提供，ES 负责 kNN + BM25 混合检索
- 情感分析使用 BERT 京东评论微调模型 + 置信度阈值（低于阈值回退 neutral）
- 编排器已从 God Function 重构为 **Pipeline 模式**（5 个独立可测试 Stage）
- LLM 生成采用 **SSE 流式输出**，支持 **DeepSeek API / Ollama 本地** 双后端切换
- 会话持久化使用 **SQLite WAL 模式**（替代原设计的 Redis，零额外依赖）
- NLP HTTP 调用统一通过 **NLPClient 适配器**（单一 seam，统一超时/错误处理/fallback）

**与 v1.1 的差异：** 原设计使用 Rasa 做意图分类 + 对话管理 + 实体抽取。实际实现中切换为 SetFit（仅做意图分类），理由：
- SetFit 专为少样本场景设计，42 条数据即可获得可用效果
- 部署简单：一个 Flask HTTP API 容器，无需 Rasa Server 的复杂配置
- 原型阶段优先验证意图分类能力，实体抽取和多轮对话后续补充

### 1.4 业务领域与意图分类

面向 **电商客服** 场景，预设意图分类体系（全部 7 类已实现）：

| 意图 | 中文标签 | 示例问法 | 状态 |
|------|----------|----------|------|
| `refund_inquiry` | 退货咨询 | "我买的衣服不合适怎么退？" | ✅ |
| `logistics_inquiry` | 物流查询 | "我的快递到哪了？" | ✅ |
| `product_inquiry` | 商品咨询 | "这款手机支持5G吗？" | ✅ |
| `order_inquiry` | 订单查询 | "我的订单什么时候发货？" | ✅ |
| `complaint` | 投诉 | "收到的商品有质量问题！" | ✅ |
| `greeting` | 问候 | "你好" | ✅ |
| `other` | 其他 | 无法归类的问题 | ✅ |

知识检索与情感分析采用独立的 BERT/BGE 模型，不与意图标签体系耦合。

### 1.5 开发优先原则

为了降低实现和联调成本，项目在设计上优先满足"先跑通、再增强"的目标：

1. 先做最小闭环，再逐步增强能力。当前已优先完成"SetFit 意图分类 + 前端骨架"，下一步应接通 `/api/chat` → Orchestrator → SSE 这条完整链路。
2. 逻辑分层清晰，但本地开发尽量保持简单。服务边界保留，开发时优先通过本地函数调用、HTTP mock 或固定测试数据联调，避免一开始就强依赖完整分布式环境。
3. 默认接口可替换、可 mock。`retriever`、`sentiment`、`llm` 都应支持假实现，方便在某一模块未完成时继续开发其他模块。
4. 配置项保持最少且明确。只保留真正会变的参数（模型名、ES 地址、LLM 后端、NLP 地址），避免过多可选项导致启动复杂。
5. 返回结果尽量确定。开发阶段优先固定输出结构和错误码，减少前后端联调时的歧义。

### 1.6 MVP 范围

当前版本只做最小可用闭环，目标是先把系统稳定跑起来，再逐步增强能力。

MVP 必须包含：

1. 单轮问答和基础多轮上下文。
2. SetFit 意图分类（✅ 已实现）。
3. FAQ 检索与缓存。
4. SSE 流式返回。
5. 最基础的反馈记录。

MVP 暂不强求：

1. 用户登录、权限和多租户。
2. 管理后台。
3. 复杂知识图谱和任务编排。
4. 高可用集群和水平扩展。
5. 复杂报表和监控大盘。

### 1.7 非目标

为避免设计失焦，本项目当前不追求以下方向：

1. 不做"全自动通用客服大脑"，只聚焦电商客服高频问题。
2. 不把所有能力都交给 LLM，意图分类由 SetFit 独立完成。
3. 不把一开始的检索系统做成复杂向量平台，先保证能开发、能测试、能演示。
4. 不追求分布式架构最优解，优先单机可运行、容器可编排。

---

## 2. 项目目录结构

> 以下为实际仓库结构（v1.2 对齐），标注各模块实现状态。

```
auto-classify-support-system/
├── README.md                           # 项目完整文档 ✅
├── CONTEXT.md                          # 领域词汇表 ✅
├── .gitignore
├── .env.example                       # 环境变量模板 ✅
├── docker-compose.yml                 # 5 容器编排（ES + Ollama + NLP + Backend + Frontend） ✅
│
├── backend/                           # Flask 后端 :5000
│   ├── app/
│   │   ├── __init__.py                # Flask 工厂函数 create_app() ✅
│   │   ├── config.py                  # 配置类（从 .env 读取） ✅
│   │   ├── extensions.py              # ES 客户端单例 ✅
│   │   │
│   │   ├── api/                       # REST 接口层（薄层）
│   │   │   ├── __init__.py            # 蓝图注册 + GET /api/health ✅
│   │   │   ├── chat.py                # POST /api/chat — SSE 流式聊天 ✅
│   │   │   └── session.py             # GET/DELETE /api/sessions — 会话管理 ✅
│   │   │
│   │   ├── services/                  # 业务逻辑层（Pipeline 模式）
│   │   │   ├── pipeline.py            # Pipeline + 5 Stage（Intent/Sentiment/Entity/Retrieve/Generate） ✅
│   │   │   ├── nlp_client.py          # NLP 微服务 HTTP 适配器（/parse + /extract） ✅
│   │   │   ├── orchestrator.py        # 薄编排器（SSE 事件调度 + 会话持久化） ✅
│   │   │   ├── retriever.py           # Retriever 类 — ES/BGE/关键词三级检索 ✅
│   │   │   ├── sentiment.py           # BERT 情感分析（京东评论模型 + 阈值回退） ✅
│   │   │   ├── llm.py                 # DeepSeek / Ollama 双后端流式生成 ✅
│   │   │   └── db.py                  # SQLite 会话持久化（WAL 模式） ✅
│   │   │
│   │   ├── models/                    # 数据模型（Pydantic）
│   │   │   └── message.py             # ChatRequest 校验 ✅
│   │   │
│   │   └── utils/                     # 工具函数
│   │       ├── response.py            # 统一 JSON 响应格式 ✅
│   │       └── sse.py                 # SSEEmitter 类 + SSE 协议函数 ✅
│   │
│   ├── tests/                         # pytest 测试套件
│   │   ├── conftest.py                # 共享 fixtures ✅
│   │   ├── test_retriever.py          # 21 用例 ✅
│   │   ├── test_pipeline.py           # 21 用例 ✅
│   │   ├── test_db.py                 # 27 用例 ✅
│   │   ├── test_chat.py               # 24 用例 ✅
│   │   └── test_adapters.py           # NLPClient/Sentiment/LLM 测试 ✅
│   │
│   ├── pyproject.toml                  ✅
│   ├── uv.lock                         ✅
│   ├── Dockerfile                      ✅
│   └── run.py                          ✅
│
├── frontend/                          # Vue 3 前端 :80
│   ├── index.html                     ✅
│   ├── package.json                   ✅
│   ├── vite.config.js                 ✅
│   ├── Dockerfile                     ✅
│   └── src/
│       ├── main.js                    ✅
│       ├── App.vue                    # 左右两栏布局 + 侧边栏折叠 ✅
│       ├── api/
│       │   └── index.js               # axios + SSE fetch 封装 ✅
│       ├── components/
│       │   ├── ChatArea.vue           # Header + 欢迎态 + 消息区 + 输入区 ✅
│       │   ├── Sidebar.vue            # 导航 + 会话历史列表 + 折叠 ✅
│       │   └── MessageBubble.vue      # 消息气泡 + 意图/情感标签 + 流式光标 ✅
│       ├── stores/
│       │   └── chat.js                # Pinia 状态管理 + SSE 接收 ✅
│       ├── utils/
│       │   └── labels.js              # 意图/情感中文标签映射 ✅
│       └── assets/
│           └── style.css              # 全局样式 + CSS 变量 ✅
│
├── nlp/                               # SetFit NLP 微服务 :5005
│   ├── config/
│   │   └── intents.yml                # 意图定义（7 类） ✅
│   ├── data/
│   │   └── training.jsonl             # 训练数据（42 条） ✅
│   ├── src/
│   │   ├── preprocess.py              # jieba 分词 ✅
│   │   ├── train.py                   # SetFit 训练脚本 ✅
│   │   ├── predict.py                 # IntentClassifier 推理类 ✅
│   │   ├── extract.py                 # 实体抽取（jieba+正则，7 类实体） ✅
│   │   └── server.py                  # Flask HTTP API（/parse, /extract, /health, /intents） ✅
│   ├── models/                        # 训练好的模型（gitignore） ✅
│   ├── checkpoints/                   # 训练检查点（gitignore） ✅
│   ├── tests/
│   │   ├── test_classifier.py         # NLP 模块测试 ✅
│   │   └── test_extract.py            # 实体抽取测试（37 用例） ✅
│   ├── pyproject.toml                 ✅
│   └── Dockerfile                     ✅
│
├── docker/                            # 中间件配置
│   └── es/
│       └── elasticsearch.yml          ✅
│
├── docs/                              # 项目文档
│   ├── architecture.md                # 架构说明 ✅
│   ├── api.md                         # API 接口文档 ✅
│   ├── test_plan.md                   # 测试计划 ✅
│   ├── adr/                           # 架构决策记录 ✅
│   ├── vibecoding/                    # AI 开发规范
│   │   ├── ai-workflow.md             ✅
│   │   ├── coding-standards.md        ✅
│   │   └── git-convention.md          ✅
│   └── superpowers/
│       └── specs/
│           └── 2026-06-29-auto-classify-support-system-design.md  # 本文件（冻结）
└── ollama_data/                       # Ollama 模型挂载卷（gitignore）
```

### 2.1 核心模块职责

| 模块 | 职责 | 上游依赖 | 状态 |
|------|------|----------|------|
| `api/chat.py` | 请求体校验，触发 orchestrator，SSE 流式返回 | `orchestrator` | ✅ |
| `api/session.py` | 会话 CRUD（GET list, GET detail, DELETE） | `db.py`（SQLite） | ✅ |
| `services/orchestrator.py` | 薄编排器：会话持久化 + Pipeline 调度 + SSE 收尾 | `pipeline`, `db`, `SSEEmitter` | ✅ |
| `services/pipeline.py` | Pipeline + 5 Stage（Intent/Sentiment/Entity/Retrieve/Generate） | 各 Stage 依赖 | ✅ |
| `services/nlp_client.py` | NLPClient 适配器：统一 /parse + /extract HTTP 调用 | NLP Server (:5005) | ✅ |
| `services/retriever.py` | Retriever 类：ES kNN+BM25 / BGE 向量 / 关键词三级检索 | BGE, ES | ✅ |
| `services/sentiment.py` | BERT 情感分析 + 置信度阈值回退 neutral | BERT 模型 | ✅ |
| `services/llm.py` | DeepSeek / Ollama 双后端流式生成 | DeepSeek API / Ollama | ✅ |
| `services/db.py` | SQLite 会话持久化（WAL 模式） | — | ✅ |
| `utils/sse.py` | SSEEmitter 类 + format_sse_event 等 6 种事件格式化 | — | ✅ |
| `nlp/src/server.py` | NLP HTTP API（`/parse`, `/extract`, `/parse/batch`, `/intents`, `/health`） | SetFit, jieba | ✅ |
| `nlp/src/extract.py` | 实体抽取：7 类电商实体（订单号/手机号/运单号/快递公司/金额/日期/商品名） | jieba | ✅ |
| `nlp/src/train.py` | SetFit 少样本微调训练 | `training.jsonl` | ✅ |
| `nlp/src/predict.py` | IntentClassifier 推理类 | SetFit 模型 | ✅ |

---

## 3. 技术栈明细

### 3.1 技术栈总览

| 层级 | 技术 | 版本 | 用途 | 状态 |
|------|------|------|------|------|
| **语言** | Python | **3.10+**（后端）/ **3.12+**（NLP） | 后端 & NLP 服务 | ✅ |
| **包管理器** | uv | **最新** | Rust 实现的极速 Python 包管理器 | ✅ |
| **后端框架** | Flask | **3.1.x** | REST API 服务 | ✅ |
| **前端框架** | Vue 3 | **3.5.x** | 用户界面 | ✅ |
| **构建工具** | Vite | **7.x** | 前端打包与开发服务器 | ✅ |
| **状态管理** | Pinia | **3.0.x** | 前端会话状态 | ✅ |
| **HTTP 客户端** | Axios / fetch | **1.7.x** | 前端 API 调用 + SSE 流式读取 | ✅ |
| **意图分类** | SetFit | **1.1.x** | 意图分类（少样本微调） | ✅ |
| **语义模型** | sentence-transformers | **3.3.x** | BGE 向量检索 / SetFit 基础模型 | ✅ |
| **中文分词** | jieba | **0.42.x** | 中文分词 + 词性标注 | ✅ |
| **情感分析** | transformers | **4.47.x** | BERT pipeline 情感分类 | ✅ |
| **搜索引擎** | Elasticsearch | **8.15.x** | FAQ kNN + BM25 混合检索 | ✅ |
| **会话存储** | SQLite（标准库） | **WAL 模式** | 会话/消息持久化 | ✅ |
| **LLM（云端）** | DeepSeek | `deepseek-v4-flash` | 回答生成 | ✅ |
| **LLM（本地）** | Ollama | `qwen2.5:7b` Q4_K_M | 本地推理（GPU 直通） | ✅ |
| **LLM SDK** | openai (Python) | **1.55.x** | 调用 DeepSeek / Ollama（OpenAI 兼容） | ✅ |
| **容器运行时** | Docker | **最新稳定版** | 环境统一 | ✅ |
| **编排** | Docker Compose | **v2.x** | 5 容器编排（ES + Ollama + NLP + Backend + Frontend） | ✅ |
| **版本管理** | Git | — | 代码版本控制 | ✅ |

### 3.2 Python 版本选择说明

- **后端（Flask）选择 Python 3.10**：Flask 3.1.x + elasticsearch + redis + openai 等依赖均在 3.10 上稳定运行。
- **NLP 服务选择 Python 3.12+**：SetFit 和 sentence-transformers 需要较新的 Python 版本以获得最佳兼容性。NLP 服务通过 Docker 独立部署，与后端隔离，因此可以使用不同 Python 版本。

### 3.3 后端依赖（backend/pyproject.toml）

```toml
[project]
name = "auto-classify-support-system"
version = "0.1.0"
description = "电商客服智能问答系统"
requires-python = ">=3.10,<4.0"
dependencies = [
    "flask>=3.1.1,<4.0",
    "flask-cors>=5.0.0",
    "flasgger>=0.9.7",
    "openai>=1.55.0",            # DeepSeek + Ollama（OpenAI 兼容）
    "elasticsearch>=8.15.0,<9.0",
    "pydantic>=2.9.0",
    "python-dotenv>=1.0.0",
    "requests>=2.34.2",
    "numpy>=1.26.0",
    "sentence-transformers>=3.3.0",  # BGE 向量检索
    "transformers>=4.47.0,<5.0.0",   # BERT 情感分析
    "torch>=2.9.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
]
```

**常用 uv 命令：**

```bash
uv sync                    # 安装所有依赖（含 dev）
uv sync --no-dev           # 仅安装生产依赖
uv add flask               # 添加新依赖
uv add --dev pytest        # 添加开发依赖
uv lock                    # 更新锁文件
uv run python run.py       # 在项目环境中运行脚本
```

### 3.4 NLP 服务依赖（nlp/pyproject.toml）

```toml
[project]
name = "acss-nlp"
version = "0.1.0"
description = "ACSS NLP - 意图分类服务（jieba + SetFit）"
requires-python = ">=3.12"
dependencies = [
    "spacy>=3.8.0,<4.0",
    "setfit>=1.1.0,<2.0",           # 意图分类
    "jieba>=0.42.1,<0.43",          # 中文分词
    "sentence-transformers>=3.0.0",  # SetFit 底层依赖
    "transformers>=4.45.0",          # HuggingFace 模型加载
    "flask>=3.1.0,<4.0",
    "flask-cors>=5.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
]
```

### 3.5 前端依赖

```json
{
  "dependencies": {
    "vue": "^3.5.0",
    "pinia": "^3.0.0",
    "axios": "^1.7.0",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "vite": "^7.0.0",
    "@vitejs/plugin-vue": "^6.0.0"
  }
}
```

### 3.6 模型选型

> **核心原则：所有模型均从 HuggingFace/ModelScope 直接下载使用，无需从头训练。**
>
> 首次运行时模型自动下载并缓存到 `~/.cache/huggingface/hub/`，后续启动直接加载。
> 国内用户可通过 `export HF_ENDPOINT=https://hf-mirror.com` 加速下载。

#### 3.6.1 模型选型总览

| 用途 | 模型 | HuggingFace ID | 下载方式 | 状态 |
|------|------|---------------|----------|------|
| 意图分类 | SetFit + MiniLM | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | SetFit 自动下载 + 42条数据微调 | ✅ 已实现 |
| 知识检索 | BGE 中文向量 | `BAAI/bge-base-zh-v1.5` | `SentenceTransformer(...)` 自动下载 | ✅ 已实现 |
| 情感分析 | RoBERTa 电商情感 | `uer/roberta-base-finetuned-jd-binary-chinese` | `pipeline(...)` 自动下载 | ✅ 已实现 |
| 回答生成 | DeepSeek V4 Flash / Ollama | `deepseek-v4-flash` / `qwen2.5:7b` | 云端 API + 本地 GPU 推理 | ✅ 已实现 |

#### 3.6.2 意图分类 — SetFit 少样本微调

| 项目 | 内容 |
|------|------|
| **方案** | SetFit（Sentence Transformer Fine-tuning） |
| **基础模型** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| **训练数据** | 42 条（7 类意图，每类 ~6 条），见 `nlp/data/training.jsonl` |
| **训练参数** | 5 epoch, batch_size=16 |
| **推理服务** | `nlp/src/server.py`（Flask HTTP API，端口 5005） |
| **预处理** | jieba 中文分词（`nlp/src/preprocess.py`） |
| **状态** | ✅ 已实现 |

**选型理由：**
- SetFit 专为少样本场景设计，42 条数据即可获得可用效果
- 基础模型自动从 HuggingFace 下载，无需手动部署
- 训练 + 推理一体化，无需外部服务依赖

**实现要点（当前代码）：**

```python
# nlp/src/predict.py
from setfit import SetFitModel

class IntentClassifier:
    def __init__(self, model_path=None):
        self.model = SetFitModel.from_pretrained(model_path)

    def predict(self, text: str) -> dict:
        processed = tokenize(text)  # jieba 分词
        intent = self.model.predict([processed])[0]
        probs = self.model.predict_proba([processed])
        confidence = float(max(probs[0]))
        return {"intent": intent, "confidence": round(confidence, 4)}
```

**零样本替代方案（如需完全跳过训练）：**

```python
from transformers import pipeline
classifier = pipeline("zero-shot-classification",
    model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")
```

#### 3.6.3 知识检索 — BGE 中文向量模型

| 项目 | 内容 |
|------|------|
| **推荐模型** | `BAAI/bge-base-zh-v1.5` |
| **备选** | `moka-ai/m3e-base` / `shibing624/text2vec-base-chinese` |
| **向量维度** | 768 |
| **依赖** | `sentence-transformers>=3.0.0` |
| **状态** | ✅ 已实现 |

> 注：BGE 模型加载在 `Retriever` 类中（`backend/app/services/retriever.py`），不是独立的 `sentence-transformers` 安装。检索路径：ES kNN+BM25 → BGE 内存向量 → difflib 关键词。

**实现要点：**

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-base-zh-v1.5")
query_vec = model.encode("如何退货？")  # → numpy array (768,)
```

#### 3.6.4 情感分析 — 电商领域中文情感模型

| 项目 | 内容 |
|------|------|
| **推荐模型** | `uer/roberta-base-finetuned-jd-binary-chinese` |
| **备选** | `lxyuan/distilbert-base-multilingual-cased-sentiments-student`（三分类） |
| **分类数** | 2 类（正面/负面） |
| **依赖** | `transformers>=4.45.0` |
| **状态** | ✅ 已实现 |

> 注：情感分析实现在 `backend/app/services/sentiment.py`。二分类模型无中性概念，置信度低于 `SENTIMENT_THRESHOLD`（默认 0.85）时自动回退为 neutral。

#### 3.6.5 回答生成 — DeepSeek API

| 项目 | 内容 |
|------|------|
| **方案** | 云端 API 调用 |
| **模型** | `deepseek-v4-flash` |
| **SDK** | `openai`（DeepSeek 兼容 OpenAI 接口） |
| **费用** | $0.14 / 百万 input tokens |
| **配置** | `.env` 中 `DEEPSEEK_API_KEY` |
| **状态** | ✅ 已实现 |

> LLM 支持双后端：DeepSeek API（`LLM_BACKEND=deepseek`）和 Ollama 本地模型（`LLM_BACKEND=ollama`，qwen2.5:7b Q4_K_M，RTX 4060 8GB）。通过 OpenAI 兼容接口统一调用，`llm.py` 中根据环境变量切换。

#### 3.6.6 模型下载与缓存

```bash
# 国内用户推荐：使用 HuggingFace 镜像加速
export HF_ENDPOINT=https://hf-mirror.com

# 或使用 ModelScope（国内更稳定）
pip install modelscope
python -c "from modelscope import snapshot_download; snapshot_download('BAAI/bge-base-zh-v1.5')"
```

缓存路径：
- **Linux/macOS**: `~/.cache/huggingface/hub/`
- **Windows**: `%USERPROFILE%\.cache\huggingface\hub\`

### 3.7 中间件版本

| 中间件 | 镜像 | 端口 |
|--------|------|------|
| Elasticsearch | `docker.1ms.run/library/elasticsearch:8.19.17` | 9200 |
| Ollama | `docker.xuanyuan.run/ollama/ollama:latest` | 11434 |

> **注：** Redis 已从架构中移除。会话持久化改用 **SQLite**（Python 标准库 `sqlite3`，WAL 模式），零额外依赖，零额外容器。

### 3.8 关于存储方案的决策：ES + SQLite

| 存储需求 | 当前方案 | 说明 |
|----------|----------|------|
| FAQ 知识库（全文检索） | Elasticsearch | kNN 向量 + BM25 文本混合检索，RRF 融合 |
| FAQ 内存索引 | BGE 内存向量 + difflib | ES 不可用时自动降级 |
| 会话/消息持久化 | SQLite（WAL 模式） | 零额外依赖，单文件 `backend/data/acss.db` |
| 多轮对话上下文 | SQLite messages 表 | 按 session_id 查询历史消息 |

---

## 4. 基础环境搭建

### 4.1 前置要求

| 软件 | 最低版本 | 验证命令 |
|------|----------|----------|
| Docker | 24.x+ | `docker --version` |
| Docker Compose | v2.x+ | `docker compose version` |
| Python | 3.10.x（后端）/ 3.12+（NLP） | `python --version` |
| uv | 最新 | `uv --version` |
| Node.js | 20.x+ | `node --version` |
| Git | 2.40+ | `git --version` |

### 4.2 环境搭建步骤

#### 步骤 1：克隆项目并配置环境变量

```bash
git clone <repo-url> auto-classify-support-system
cd auto-classify-support-system
cp .env.example .env
```

编辑 `.env` 文件，填入必要配置：

```ini
# .env 示例
# ─── DeepSeek API ───
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash

# ─── Elasticsearch ───
ES_HOST=http://localhost:9200
ES_INDEX=faq

# ─── LLM 后端选择 ───
LLM_BACKEND=deepseek               # deepseek | ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:7b

# ─── NLP 服务 ───
NLP_SERVER_URL=http://localhost:5005

# ─── 情感分析 ───
SENTIMENT_THRESHOLD=0.85

# ─── Flask ───
SECRET_KEY=change-me-in-production
FLASK_ENV=development
CORS_ORIGINS=
```

#### 步骤 2：启动中间件

```bash
# 启动 ES + Ollama
docker compose up -d elasticsearch ollama

# 如需本地 LLM，拉取模型
docker exec acss-ollama ollama pull qwen2.5:7b

# 验证 ES 是否就绪
curl http://localhost:9200/_cluster/health
```

#### 步骤 3：FAQ 知识库（启动时自动索引）

FAQ 种子数据（16 条）内置于 `backend/app/services/retriever.py` 的 `FAQ_SEED_DATA` 列表中。
后端启动时自动写入 ES 索引（如 ES 可用）并构建内存向量索引，无需手动执行导入脚本。

#### 步骤 4：训练并启动 NLP 意图分类服务（✅ SetFit）

```bash
cd nlp

# 安装依赖
uv sync

# 训练意图分类模型（42 条数据，7 类意图，约 1-2 分钟）
uv run python src/train.py
# 模型保存到: nlp/models/

# 启动 NLP HTTP API 服务
uv run python src/server.py
# 默认监听: http://localhost:5005

# 验证分类
curl -X POST http://localhost:5005/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "我的订单怎么还没到"}'
# 预期输出: {"intent": "logistics_inquiry", "confidence": 0.95}

# 查看支持的意图列表
curl http://localhost:5005/intents
cd ..
```

#### 步骤 5：启动 Flask 后端

```bash
cd backend

# 使用 uv 安装所有依赖
uv sync

# 开发模式启动
uv run python run.py
# 默认监听: http://localhost:5000

# 验证健康检查
curl http://localhost:5000/api/health
cd ..
```

#### 步骤 6：启动 Vue 前端

```bash
cd frontend

npm install
npm run dev
# Vite 开发服务器: http://localhost:5173

# 验证：浏览器打开 http://localhost:5173
cd ..
```

#### 步骤 7（可选）：一键启动所有服务

```bash
# 在完成上述各模块基础配置后
docker compose up -d
# 一键启动: ES + Ollama + NLP + Backend + Frontend
```

### 4.3 当前进度与推荐开发顺序

**当前进度总结：**

| 步骤 | 内容 | 状态 |
|------|------|------|
| 步骤 1 | 环境变量配置 | ✅ |
| 步骤 2 | ES + Ollama 中间件 | ✅ 可启动 |
| 步骤 3 | FAQ 知识库索引 | ✅ 启动时自动索引 |
| 步骤 4 | NLP 意图分类 + 实体抽取 | ✅ 已实现 |
| 步骤 5 | Flask 后端 | ✅ Pipeline + SSE + SQLite |
| 步骤 6 | Vue 前端 | ✅ 完整聊天界面 + SSE 流式渲染 |
| 步骤 7 | Docker Compose 全栈 | ✅ 5 容器编排就绪 |

**当前进度总结：**

所有核心模块已实现并通过测试覆盖。详见 [`docs/architecture.md`](../architecture.md)。

### 4.4 Docker Compose 服务编排

```yaml
# docker-compose.yml 核心服务定义
services:
  elasticsearch:
    image: docker.1ms.run/library/elasticsearch:8.19.17
    container_name: acss-es
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data
      - ./docker/es/elasticsearch.yml:/usr/share/elasticsearch/config/elasticsearch.yml

  ollama:
    image: docker.xuanyuan.run/ollama/ollama:latest
    container_name: acss-ollama
    ports:
      - "11434:11434"
    volumes:
      - ./ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - NVIDIA_VISIBLE_DEVICES=all

  nlp:
    build: ./nlp
    container_name: acss-nlp
    ports:
      - "5005:5005"

  backend:
    build: ./backend
    container_name: acss-backend
    ports:
      - "5000:5000"
    env_file:
      - .env
    depends_on:
      - elasticsearch
      - nlp

  frontend:
    build: ./frontend
    container_name: acss-frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  es_data:
```

> **注意：** Docker Compose 中 `nlp` 服务对应 SetFit NLP HTTP API（端口 5005），与 v1.1 设计中的 `rasa` 服务不同。

### 4.5 开发流程建议

```text
1. 拉代码 → git clone
2. 配环境 → cp .env.example .env → 填 API Key
3. 启中间件 → docker compose up -d elasticsearch
4. 训模型 → cd nlp && uv run python src/train.py               （✅）
5. 启动 NLP → cd nlp && uv run python src/server.py             （✅，:5005）
6. 启动后端 → cd backend && uv run python run.py                 （✅，:5000）
7. 启动前端 → cd frontend && npm run dev                        （✅，:5173）
8. 打开浏览器 → http://localhost:5173
```

> FAQ 数据已内置，后端启动时自动索引。如需本地 LLM：`docker compose up -d ollama` → `docker exec acss-ollama ollama pull qwen2.5:7b` → 在 `.env` 中设置 `LLM_BACKEND=ollama`。

---

## 5. 核心数据流设计

### 5.1 用户消息处理流程

```
┌──────────┐    POST /api/chat     ┌──────────┐
│  Vue 前端  │ ──────────────────→  │  Flask    │
│          │  {session_id, msg}    │  API     │
└──────────┘                       └────┬─────┘
                                        │
                              ┌─────────┼─────────┐
                              │  Orchestrator     │
                              │  (编排调度)        │
                              └─────────┼─────────┘
                                        │
                   ┌────────────────────┼────────────────────┐
                   ▼                    ▼                    ▼
            ┌──────────┐        ┌──────────┐        ┌──────────┐
            │ SetFit   │        │ ES 检索    │        │ 情感分析  │
            │ 意图分类  │        │ FAQ Top-K │        │ BERT     │
            └────┬─────┘        └────┬─────┘        └────┬─────┘
                 │                   │                    │
                 ▼                   ▼                    ▼
            intent:            faq_docs:            sentiment:
            "logistics"        [{score, answer}]    {label, score}
                 │                   │                    │
                 └───────────────────┼────────────────────┘
                                     │
                                     ▼
                            ┌────────────────┐
                            │ 命中缓存且      │
                            │ 置信度 > 阈值?  │
                            └───────┬────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     │ Yes                         │ No
                    ▼                             ▼
                     ┌──────────────┐            ┌──────────────┐
                     │ 直接返回 FAQ  │            │ DeepSeek 生成 │
                     │ 答案（不走LLM）│            │ (RAG Prompt)  │
                     └──────┬───────┘            └──────┬───────┘
                   │                            │
                   └────────────┬───────────────┘
                                │
                                ▼
                      SSE 流式推送到前端
```

**降级策略（v1.2 更新）：**

- NLP 服务不可用时，`NLPClient.classify()` 返回 `{"intent": "other", "confidence": 0.0}`，不中断主流程。
- BGE 检索不可用时，退回到 ES 关键词检索或 difflib 匹配，保证 FAQ 仍可服务。
- LLM 不可用时，退回到 FAQ 直返或模板回复，不阻断完整请求链路。
- ES 不可用时，自动降级为 BGE 内存向量检索 → 关键词匹配（三级 fallback）。
- 检索和分类置信度过低时，优先澄清追问，而不是强行给出答案。

### 5.2 RAG Prompt 模板

LLM 生成回答时使用的 prompt 结构（实现在 `backend/app/services/llm.py`）：

```text
System: 你是电商客服专员，负责处理退货退款问题。请告知退货流程、退款时间、审核标准。语气友善、简洁。

以下是可供参考的知识库内容，请据此回答：
[1] 问题: 如何申请退货退款？
    答案: 在「我的订单」找到对应订单，点击「申请退货」按钮...

User: 我要退货
Assistant: (LLM 流式生成)
```

> 意图对应的 System Prompt 由 `INTENT_SYSTEM_PROMPTS` 字典按 intent key 选取（7 种意图各有专用 prompt）。FAQ 检索结果以 `[N] 问题: ... 答案: ...` 格式拼入 system prompt 末尾。

### 5.3 会话持久化策略

会话和消息存储在 **SQLite**（WAL 模式），`backend/data/acss.db`。启动时自动建表。

| 表 | 内容 | 说明 |
|------|------|------|
| `sessions` | id, title, created_at, updated_at | 会话元信息 |
| `messages` | id, session_id, role, text, intent_label, sentiment_label, ... | 消息（含元数据） |

### 5.4 失败与兜底规则

| 场景 | 处理方式 | 目的 |
|------|----------|------|
| 意图置信度低于阈值 | 触发澄清追问 | 降低误答 |
| NLP 服务不可用 | 返回 `intent: "other"`，继续主流程 | 不阻断核心能力 |
| 检索 Top-K 无命中 | 返回"未找到相关 FAQ"并交给 LLM 生成保守回答 | 避免硬编码错误答案 |
| LLM 超时 | 返回模板兜底文案 + 引导重试 | 保持接口可用 |
| SQLite 不可写 | 应用仍可启动，聊天请求返回 error SSE 事件 | 不阻断启动 |

### 5.5 响应规范

所有 HTTP JSON 响应遵循统一结构，便于前端和测试固定处理：

```json
{
  "status": "success",
  "message": "ok",
  "data": {}
}
```

错误响应同样保持同一结构，只是 `status="error"`：

```json
{
  "status": "error",
  "message": "错误说明",
  "data": null
}
```

---

## 6. API 接口设计概览

| 方法 | 路径 | 说明 | 请求体 | 响应类型 | 状态 |
|------|------|------|--------|----------|------|
| `GET` | `/api/health` | 健康检查 | — | JSON | ✅ |
| `GET` | `/api/sessions` | 会话列表 | — | JSON | ✅ |
| `GET` | `/api/sessions/<id>` | 会话详情 + 消息 | — | JSON | ✅ |
| `DELETE` | `/api/sessions/<id>` | 删除会话 | — | JSON | ✅ |
| `POST` | `/api/chat` | SSE 流式聊天 | `{session_id, message}` | **SSE 流** | ✅ |
| `GET` | `/docs` | Swagger 交互式文档 | — | HTML | ✅ |

### 6.1 SSE 事件格式

聊天接口以 SSE 流式返回，事件类型：

```text
event: intent
data: {"intent": "logistics_inquiry", "confidence": 0.95}

event: sentiment
data: {"label": "negative", "score": 0.72}

event: entity
data: {"entities": {...}, "summary": "运单号: SF1234567890"}

event: token
data: {"token": "您"}

event: token
data: {"token": "的"}

...（逐 token 推送）...

event: done
data: {"message_id": "msg_001", "full_answer": "您的订单...", "source": "llm"}
```

> SSE 事件序列：`intent` → `sentiment` → `entity`（可选）→ `token`×N → `done`。错误时发送 `event: error`。

---

## 7. 测试策略

### 7.1 测试分层

| 层级 | 工具 | 覆盖范围 | 状态 |
|------|------|----------|------|
| 单元测试 | pytest | `services/` 中每个模块的独立逻辑 | ✅ 115 用例 |
| 集成测试 | pytest | Flask API → DB 联动 | ✅ 27 用例 |
| NLP 测试 | pytest | 意图分类 + 实体抽取 + 训练数据 | ✅ 42 用例 |
| 前端测试 | 手动验证 | 页面渲染、组件交互 | ⚠️ 手动 |
| API 测试 | Swagger / curl | `/docs` 交互式文档 | ✅ |

### 7.2 关键测试场景

1. **分类准确** — SetFit 正确识别 7 种意图 ✅ 已测试
2. **检索命中** — ES/BGE 能匹配同义表达（"退款" ↔ "退钱"，"买了不想要了" → 退货FAQ） ✅ 已测试
3. **会话持久化** — 刷新页面后历史会话不丢失 ✅ 已测试
4. **流式输出** — SSE 逐 token 推送，前端逐字显示（含"模型思考中..."占位） ✅ 已实现
5. **降级处理** — NLP 不可用时优雅降级（intent→other, 实体→静默跳过） ✅ 已测试
6. **情感标注** — 正确识别投诉类消息为负面情感，置信度不足回退 neutral ✅ 已测试

### 7.3 验收标准

1. 前端能完整发起一次对话并收到 SSE 流式回复（含意图/情感/实体/逐字回答）。✅
2. SetFit 能返回意图和置信度。✅
3. FAQ 检索命中时能将匹配结果作为上下文注入 LLM Prompt（RAG）。✅
4. LLM 不可用时系统仍能返回可读兜底回复。✅
5. 关键配置通过 `.env` 即可完成本地启动，不需要改代码。✅
6. SQLite 数据库首次启动自动创建，零手动配置。✅

---

## 8. 后续扩展方向（非本阶段）

以下功能设计时预留接口，但不纳入当前学习/原型阶段的开发范围：

- [ ] 用户认证与多租户
- [ ] 管理员后台（FAQ 管理、对话日志查看）
- [ ] 对话统计仪表盘
- [ ] CI/CD 流水线
- [ ] 水平扩展（多实例负载均衡）
- [ ] WebSocket 替代 SSE（双向通信）

---

## 9. 参考链接

- DeepSeek API 文档: https://api-docs.deepseek.com
- SetFit: https://github.com/huggingface/setfit
- sentence-transformers: https://www.sbert.net
- Elasticsearch Python Client: https://elasticsearch-py.readthedocs.io
- Flask 3.1.x: https://flask.palletsprojects.com/en/3.1.x/
- Vue 3: https://vuejs.org
- Vite: https://vitejs.dev
- Ollama: https://ollama.com

---

## 10. 前端 UI 设计规范

> **参考方向**: 左侧导航 + 主内容区 + 空状态引导，风格偏简洁、克制、易开发。

### 10.1 整体布局

采用 **左右两栏布局**，适合客服对话场景，也方便后续扩展会话列表和产品导航。

```
+--------------+------------------------------------+
|              |  Header (模型选择 + 操作按钮)        |
|   Sidebar    +------------------------------------+
|  (220px)     |                                     |
|              |         Welcome / Empty State       |
|  - 导航项    |         (标题 + 推荐问题)            |
|  - 会话列表  |                                     |
|  - 用户区    +------------------------------------+
|              |  Input Area (输入框 + 发送按钮)       |
+--------------+------------------------------------+
```

> **当前实现状态：** Sidebar（✅）、Header 模型选择器（✅）、Welcome 空状态 + 推荐问题（✅）、Input Area（✅）、MessageBubble + 意图/情感/实体标签（✅）、SSE 逐字渲染 + "模型思考中..."占位（✅）。

### 10.2 侧边栏（Sidebar）

侧边栏建议兼顾"产品导航"和"会话入口"，不要做成纯列表堆叠。

| 区域 | 内容 | 说明 | 状态 |
|------|------|------|------|
| Header | 产品 Logo + 新建会话按钮 | 固定在顶部 | ✅ |
| Nav | 导航项列表（智能客服等） | 当前选中项高亮 | ✅ |
| Session | 会话历史列表 | 支持点击切换、删除，从 SQLite 加载 | ✅ |
| User | 头像 + 用户名 | 固定在底部 | ⚠️ 仅展示"未登录" |

### 10.3 主内容区（Chat View）

主内容区建议拆成三个部分：`ChatContainer`、`MessageBubble` 和 `InputBox`。

#### Header

| 元素 | 说明 | 状态 |
|------|------|------|
| 模型选择器 | 下拉选择 LLM 模型（DeepSeek-V4-Flash / Pro） | ✅ |
| API 按钮 | 跳转接口文档或测试页面 | ✅ |
| 运行状态 | 显示后端/NLP 服务在线状态 | 🔴 未实现 |

#### Welcome / Empty State

当没有对话时，页面中心显示欢迎态，降低首次使用成本：

- 大标题 + 一句短副标题 ✅
- 推荐问题卡片 ✅
- 说明当前系统支持的能力，例如"退货、物流、商品咨询" ✅

#### 消息区

- 用户消息和机器人消息使用不同气泡样式（深色/浅色） ✅
- 机器人回复支持 SSE 逐字渲染 + 闪烁光标 ✅
- 等待 LLM 响应时显示"模型思考中..." ✅
- 长消息自动滚动到底部，但保留手动回看能力 ✅

#### 输入区

- 输入框采用圆角卡片样式 ✅
- 发送按钮在无内容时禁用 ✅
- 发送后清空输入框，Enter 发送、Shift+Enter 换行 ✅

### 10.4 配色建议

可参考浅灰 + 近黑的极简风格，避免过重的紫色或高饱和渐变。

| 用途 | 色值 | 说明 |
|------|------|------|
| 主背景 | `#ffffff` | 纯白 |
| 侧边栏背景 | `#f5f5f7` | 浅灰 |
| 主文字 | `#1d1d1f` | 近黑 |
| 次要文字 | `#86868b` | 中灰 |
| 边框 | `#e5e5e7` | 极浅灰 |
| 按钮深色 | `#1d1d1f` | 主要操作按钮 |
| 强调蓝 | `#0071e3` | 徽章/链接/高亮 |

### 10.5 组件映射

| 组件 | 文件 | 说明 | 状态 |
|------|------|------|------|
| Sidebar | `frontend/src/components/Sidebar.vue` | 侧边导航 + 会话历史列表 + 删除 | ✅ |
| ChatArea | `frontend/src/components/ChatArea.vue` | Header + 欢迎态 + 消息区 + 输入区 | ✅ |
| MessageBubble | `frontend/src/components/MessageBubble.vue` | 消息气泡 + 意图/情感/实体标签 + SSE 流式渲染 | ✅ |

> **注：** 原设计中的 ChatContainer、InputBox、ChatView 在实际实现中合并入 ChatArea（减少组件拆分，简化数据流）。

### 10.6 设计原则

1. 首屏要能一眼看懂系统做什么。
2. 空状态必须提供推荐问题，避免用户不知道怎么开始。
3. 交互优先保持轻量，不把 UI 设计得比业务更复杂。
4. 风格统一，组件复用优先于每个页面单独设计。
