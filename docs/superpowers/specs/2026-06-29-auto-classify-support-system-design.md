# auto-classify-support-system 项目设计文档

> **版本**: v1.2（历史文档）
> **日期**: 2026-06-30（原始），2026-07-03（勘误标注）
> **状态**: ⚠️ **此文档已冻结，与当前代码库存在多处出入。** 以下划线标注的假设已被后续实现推翻。
> 当前架构请以 [`docs/architecture.md`](../architecture.md) 和 [`docs/api.md`](../api.md) 为准。
>
> **主要出入点：**
> - ~~Redis~~ → 已替换为 SQLite（`backend/app/services/db.py`）
> - ~~classifier.py~~ → 已替换为 `nlp_client.py`（NLPClient 适配器）
> - ~~God Function orchestrator~~ → 已重构为 Pipeline + 5 Stage 模式
> - ~~Ollama~~ → 已实现（`LLM_BACKEND=ollama`）
> - 所有标记为 🔴 的核心模块已全部实现

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
| F2 | 实体抽取 | 提取订单号、商品名、地址等关键信息 | 🔴 待实现 |
| F3 | 知识库检索 | 基于 BGE 向量模型 + Elasticsearch 检索最匹配的 FAQ 条目 | 🔴 待实现 |
| F4 | 情感分析 | 基于 BERT 分类模型分析用户消息情感倾向（正面/负面） | 🔴 待实现 |
| F5 | 多轮对话 | 基于 Redis 缓存会话上下文，维持对话连贯性 | 🔴 待实现 |
| F6 | 回答生成 | 基于 RAG 架构，将检索结果喂给 DeepSeek LLM 生成最终回答 | 🔴 待实现 |
| F7 | 用户界面 | 提供类 IM 的聊天界面，前端骨架已完成 | ⚠️ 骨架完成 |

### 1.3 架构方案

采用 **混合方案：SetFit 意图分类 + BGE 向量检索 + RAG 回答生成**。

```
用户 → Vue 前端 → Flask API → Redis（会话状态 & FAQ 缓存）
                              ├── SetFit NLP（意图分类） ──┐
                              ├── BGE 向量检索 + ES         ──┼──→ 聚合 → DeepSeek LLM 生成 → SSE 流式返回
                              └── BERT 情感分析             ──┘
```

**关键设计决策（v1.2 更新）：**

- 意图分类由 **SetFit** 负责（基于 `paraphrase-multilingual-MiniLM-L12-v2`，42 条标注数据少样本微调），轻量且适合原型阶段快速验证
- 检索语义能力由 **BGE 向量模型**（`BAAI/bge-base-zh-v1.5`）提供，ES 负责倒排检索和存储
- 情感分析单独使用 BERT 分类模型（`uer/roberta-base-finetuned-jd-binary-chinese`），避免把简单分类任务交给大模型
- ES 检索命中 FAQ 后，先查 Redis 缓存；命中则直接返回，跳过 LLM 调用
- LLM 生成采用 **SSE 流式输出**，逐 token 推送至前端
- SetFit 负责意图分类，LLM 只负责回答生成，各司其职

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
4. 配置项保持最少且明确。只保留真正会变的参数（模型名、ES 地址、Redis 地址、NLP 地址），避免过多可选项导致启动复杂。
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
├── README.md
├── .gitignore
├── .env.example                       # 环境变量模板（API Key等） ✅
├── docker-compose.yml                 # 一键启动所有服务 ✅
│
├── backend/                           # Flask 后端
│   ├── app/
│   │   ├── __init__.py                # Flask 工厂函数 create_app() ✅
│   │   ├── config.py                  # 配置类（从 .env 读取） ✅
│   │   ├── extensions.py              # Redis, ES 客户端单例 ✅
│   │   │
│   │   ├── api/                       # REST 接口层（薄层，只做参数校验和响应）
│   │   │   ├── __init__.py            # 蓝图注册 + GET /api/health ✅
│   │   │   ├── chat.py                # POST /api/chat — 发送消息（SSE流式） 🔴
│   │   │   ├── session.py             # POST/DELETE /api/sessions — 会话管理 🔴
│   │   │   └── feedback.py            # POST /api/feedback — 满意度反馈 🔴
│   │   │
│   │   ├── services/                  # 业务逻辑层（核心，可独立测试）
│   │   │   ├── __init__.py            ✅
│   │   │   ├── classifier.py          # 调用 NLP 服务获取意图 ✅
│   │   │   ├── entity_extractor.py    # 实体抽取 🔴
│   │   │   ├── retriever.py           # BGE 向量检索 + ES FAQ 检索 🔴
│   │   │   ├── llm.py                 # 调用 DeepSeek LLM 生成回答 🔴
│   │   │   ├── sentiment.py           # BERT 情感分析 🔴
│   │   │   └── orchestrator.py        # 编排器：协调意图→检索→生成→情感流程 🔴
│   │   │
│   │   ├── models/                    # 数据模型（Pydantic） 🔴
│   │   │   ├── __init__.py            ✅
│   │   │   ├── session.py             # Session 模型 🔴
│   │   │   └── message.py             # Message 模型 🔴
│   │   │
│   │   └── utils/                     # 工具函数
│   │       ├── __init__.py            ✅
│   │       ├── response.py            # 统一 JSON 响应格式 ✅
│   │       └── sse.py                 # SSE 流式推送工具（空壳，Phase 2） ⚠️
│   │
│   ├── tests/                         # 后端测试
│   │   ├── __init__.py                ✅
│   │   ├── conftest.py                # pytest fixtures ✅
│   │   ├── test_classifier.py         🔴
│   │   ├── test_retriever.py          🔴
│   │   ├── test_llm.py                🔴
│   │   └── test_orchestrator.py       🔴
│   │
│   ├── pyproject.toml                  # 项目依赖（uv 管理） ✅
│   ├── uv.lock                         # 依赖锁文件 ✅
│   ├── Dockerfile                      ✅
│   └── run.py                          # 启动入口 ✅
│
├── frontend/                          # Vue 3 前端
│   ├── index.html                     ✅
│   ├── package.json                   ✅
│   ├── vite.config.js                 ✅
│   ├── Dockerfile                     ✅
│   └── src/
│       ├── main.js                    ✅
│       ├── App.vue                    # 左右两栏布局 + 侧边栏折叠 ✅
│       ├── api/
│       │   └── index.js               # 封装 axios + SSE 调用 🔴
│       ├── components/
│       │   ├── ChatArea.vue           # 欢迎态 + 模型选择器 + 推荐问题 + 输入区 ✅
│       │   ├── Sidebar.vue            # 侧边栏导航 + 折叠 ✅
│       │   ├── ChatContainer.vue      # 聊天容器（管理滚动和布局） 🔴
│       │   ├── MessageBubble.vue      # 消息气泡 🔴
│       │   └── InputBox.vue           # 输入框 🔴
│       ├── stores/
│       │   └── chat.js                # Pinia 状态管理 🔴
│       ├── views/
│       │   └── ChatView.vue           # 聊天页面 🔴
│       └── assets/
│           └── style.css              # 全局样式 + CSS 变量 ✅
│
├── nlp/                               # SetFit NLP 意图分类服务
│   ├── config/
│   │   └── intents.yml                # 意图定义（7 类） ✅
│   ├── data/
│   │   └── training.jsonl             # 训练数据（42 条） ✅
│   ├── src/
│   │   ├── __init__.py                ✅
│   │   ├── preprocess.py              # jieba 中文分词 ✅
│   │   ├── train.py                   # SetFit 训练脚本 ✅
│   │   ├── predict.py                 # IntentClassifier 推理类 ✅
│   │   └── server.py                  # Flask HTTP API（端口 5005） ✅
│   ├── models/                        # 训练好的模型（gitignore） ✅
│   ├── tests/
│   │   ├── __init__.py                ✅
│   │   └── test_classifier.py         ✅
│   ├── pyproject.toml                 # 依赖：setfit, spacy, jieba, flask ✅
│   └── Dockerfile                     ✅
│
├── knowledge/                         # ES 知识库
│   ├── data/
│   │   └── faq.jsonl                  # 电商 FAQ 数据 🔴
│   ├── scripts/
│   │   ├── seed_es.py                 # 导入 FAQ 到 ES 并建索引 🔴
│   │   └── search_faq.py              # 检索测试脚本 🔴
│   └── synonyms.txt                   # 同义词表 🔴
│
├── docker/                            # 中间件配置文件
│   ├── es/
│   │   └── elasticsearch.yml          ✅
│   └── redis/
│       └── redis.conf                 ✅
│
└── docs/                              # 项目文档
    ├── api.md                         # API 接口文档
    ├── architecture.md                # 架构说明（v0.2）
    ├── test_plan.md                   # 测试计划
    ├── vibecoding/                    # AI 开发规范（AI 编码助手必读）
    │   ├── README.md                   # 规则体系说明
    │   ├── ai-workflow.md              # AI 开发行为与流程规范
    │   ├── coding-standards.md         # 编码规范（Python + Vue + CSS）
    │   └── git-convention.md           # Git 提交规范
    └── superpowers/
        └── specs/
            └── 2026-06-29-auto-classify-support-system-design.md  # 本文件
```

### 2.1 核心模块职责

| 模块 | 职责 | 上游依赖 | 状态 |
|------|------|----------|------|
| `api/chat.py` | 接收用户消息，触发编排器，SSE 流式返回 | `orchestrator` | 🔴 |
| `api/session.py` | 管理会话 CRUD | Redis | 🔴 |
| `api/feedback.py` | 记录用户满意/不满意 | （原型阶段写 Redis） | 🔴 |
| `services/orchestrator.py` | 调度 SetFit NLP、BGE 检索、情感分析与 LLM 生成 | `classifier`, `retriever`, `sentiment`, `llm` | 🔴 |
| `services/classifier.py` | HTTP 调用 NLP 服务获取意图 | NLP Server (:5005) | ✅ |
| `services/retriever.py` | 使用 BGE 向量表示查询 ES 获取 Top-K FAQ，支持 Redis 缓存 | BGE, ES, Redis | 🔴 |
| `services/sentiment.py` | 使用 BERT 分析用户消息情感标签与得分 | BERT 模型 | 🔴 |
| `services/llm.py` | 调用 DeepSeek LLM 生成回答，支持流式 | DeepSeek API | 🔴 |
| `services/entity_extractor.py` | 实体抽取（订单号、商品名等） | 待定 | 🔴 |
| `utils/sse.py` | SSE 事件封装，支持逐 token 推送 | — | ⚠️ 空壳 |
| `nlp/src/server.py` | NLP HTTP API 服务（`/parse`, `/parse/batch`, `/intents`） | SetFit 模型 | ✅ |
| `nlp/src/train.py` | SetFit 少样本微调训练 | `training.jsonl` | ✅ |
| `nlp/src/predict.py` | IntentClassifier 推理类 | SetFit 模型 | ✅ |

---

## 3. 技术栈明细

### 3.1 技术栈总览

| 层级 | 技术 | 版本 | 用途 | 状态 |
|------|------|------|------|------|
| **语言** | Python | **3.10.x**（后端）/ **3.12+**（NLP） | 后端 & NLP 服务 | ✅ |
| **包管理器** | uv | **最新** | Rust 实现的极速 Python 包管理器 | ✅ |
| **后端框架** | Flask | **3.1.x** | REST API 服务 | ✅ |
| **前端框架** | Vue 3 | **3.5.x** | 用户界面 | ✅ |
| **构建工具** | Vite | **7.x** | 前端打包与开发服务器 | ✅ |
| **状态管理** | Pinia | **3.0.x** | 前端会话状态 | 🔴 |
| **HTTP 客户端** | Axios | **1.7.x** | 前端 API 调用 | 🔴 |
| **意图分类** | SetFit | **1.1.x** | 意图分类（少样本微调） | ✅ |
| **语义模型** | sentence-transformers | **3.0.x** | BGE 向量检索 / SetFit 基础模型 | ⚠️ 仅 NLP |
| **中文分词** | jieba | **0.42.x** | 中文分词预处理 | ✅ |
| **情感分析** | transformers | **4.45.x** | BERT pipeline 情感分类 | 🔴 |
| **搜索引擎** | Elasticsearch | **8.15.x** | FAQ 全文检索 | ⚠️ 已配置未集成 |
| **缓存/会话** | Redis | **8.x** | 会话存储 & FAQ 缓存 | ⚠️ 已配置未集成 |
| **LLM** | DeepSeek V4 Flash | `deepseek-v4-flash` | 回答生成 | 🔴 |
| **LLM SDK** | openai (Python) | **1.55.x** | 调用 DeepSeek（OpenAI 兼容） | ⚠️ 已安装未使用 |
| **容器运行时** | Docker | **最新稳定版** | 环境统一 | ✅ |
| **编排** | Docker Compose | **v2.x** | 多服务编排 | ✅ |
| **版本管理** | Git | — | 代码版本控制 | ✅ |
| **IDE** | VS Code | — | 开发环境 | ✅ |

### 3.2 Python 版本选择说明

- **后端（Flask）选择 Python 3.10**：Flask 3.1.x + elasticsearch + redis + openai 等依赖均在 3.10 上稳定运行。
- **NLP 服务选择 Python 3.12+**：SetFit 和 sentence-transformers 需要较新的 Python 版本以获得最佳兼容性。NLP 服务通过 Docker 独立部署，与后端隔离，因此可以使用不同 Python 版本。

### 3.3 后端依赖（backend/pyproject.toml）

```toml
[project]
name = "auto-classify-support-system"
version = "0.1.0"
description = "电商客服智能问答系统"
requires-python = ">=3.10,<3.11"
dependencies = [
    "flask>=3.1.1,<4.0",
    "flask-cors>=5.0.0",
    "openai>=1.55.0",            # DeepSeek API（OpenAI 兼容）
    "elasticsearch>=8.15.0,<9.0",
    "redis>=5.2.0",
    "pydantic>=2.9.0",
    "python-dotenv>=1.0.0",
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
| 知识检索 | BGE 中文向量 | `BAAI/bge-base-zh-v1.5` | `SentenceTransformer(...)` 自动下载 | 🔴 待实现 |
| 情感分析 | RoBERTa 电商情感 | `uer/roberta-base-finetuned-jd-binary-chinese` | `pipeline(...)` 自动下载 | 🔴 待实现 |
| 回答生成 | DeepSeek V4 Flash | `deepseek-v4-flash` | 云端 API（无需下载） | 🔴 待实现 |

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
| **状态** | 🔴 待实现 |

**选型理由：**
- BGE（BAAI General Embedding）在 C-MTEB 中文基准排名领先
- 与 `sentence-transformers` 完全兼容
- `encode()` 方法直接输出 768 维向量，送入 ES 做 kNN 检索

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
| **状态** | 🔴 待实现 |

**选型理由：**
- 在京东评论数据上微调，与电商客服场景高度匹配
- 对投诉类表述更敏感

#### 3.6.5 回答生成 — DeepSeek API

| 项目 | 内容 |
|------|------|
| **方案** | 云端 API 调用 |
| **模型** | `deepseek-v4-flash` |
| **SDK** | `openai`（DeepSeek 兼容 OpenAI 接口） |
| **费用** | $0.14 / 百万 input tokens |
| **配置** | `.env` 中 `DEEPSEEK_API_KEY` |
| **状态** | 🔴 待实现 |

> LLM 通过 API 调用，无需下载模型。如需本地部署，可考虑 Qwen2.5-7B、ChatGLM3-6B 等开源模型（需 GPU）。

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

| 中间件 | 镜像（国内代理源） | 端口 |
|--------|-------------------|------|
| Elasticsearch | `docker.1ms.run/library/elasticsearch:8.19.17` | 9200 |
| Redis | `docker.1ms.run/library/redis:latest` | 6379 |

> **拉取命令（已验证有效）：**
> ```bash
> docker pull docker.1ms.run/library/elasticsearch:8.19.17
> docker pull docker.1ms.run/library/redis:latest
> ```
> 如果代理源不可用，回退官方源：`docker.elastic.co/elasticsearch/elasticsearch:8.19.17` 和 `redis:8-alpine`。

### 3.8 关于 MongoDB 的决策：不引入

对各存储需求进行逐项评估：

| 存储需求 | 当前方案 | MongoDB 可替代？ | 结论 |
|----------|----------|-----------------|------|
| FAQ 知识库（全文检索） | Elasticsearch | ❌ Mongo 全文检索远弱于 ES（分词、相关性评分、同义词） | ES 不可替代 |
| 会话状态（多轮上下文） | Redis | ❌ 会话读写需微秒级延迟，Mongo 磁盘IO 太慢 | Redis 不可替代 |
| FAQ 检索缓存 | Redis | ❌ 缓存语义上就是内存DB的职责 | Redis 不可替代 |
| 对话历史持久化 | Redis（TTL 30min） | ⚠️ 原型阶段无需永久保留；未来可加 SQLite | 当前不需要 |
| 用户反馈记录 | Redis（原型阶段） | ⚠️ 量极小，和对话历史一起解决 | 当前不需要 |

**结论：不需要 MongoDB。** 理由有三：

1. **ES + Redis 已覆盖核心需求** — 全文检索走 ES，热数据缓存和会话走 Redis，分工清晰
2. **原型阶段无持久化强需求** — 对话历史和反馈暂时不需要永久存储；后续如需轻量持久化，SQLite 单文件零配置比 MongoDB 更合适
3. **减少认知负担** — 项目已有 5 个 Docker 服务（ES、Redis、NLP、Flask、Frontend），每多一个服务就多一份学习维护成本。YAGNI 原则：不需要的时候不加

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

# ─── Redis ───
REDIS_URL=redis://localhost:6379/0

# ─── NLP 服务 ───
NLP_SERVER_URL=http://localhost:5005

# ─── Flask ───
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=change-me-in-production
```

#### 步骤 2：拉取并启动中间件（ES + Redis）

```bash
# 首次使用：拉取镜像（国内代理源，已验证有效）
docker pull docker.1ms.run/library/elasticsearch:8.19.17
docker pull docker.1ms.run/library/redis:latest

# 启动中间件
docker compose up -d elasticsearch redis

# 验证 ES 是否就绪
curl http://localhost:9200/_cluster/health

# 验证 Redis 是否就绪
docker compose exec redis redis-cli PING
# 应返回: PONG
```

#### 步骤 3：初始化 ES 知识库（🔴 待实现）

```bash
cd knowledge

# 使用 uv 创建虚拟环境并安装依赖
uv venv
uv sync

# 导入 FAQ 数据
uv run python scripts/seed_es.py
# 预期输出: Indexed X FAQ documents into index 'faq'

# 测试检索
uv run python scripts/search_faq.py "如何退货"
# 预期输出: 返回相关 FAQ 条目
cd ..
```

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
# 一键启动: ES + Redis + NLP + Backend + Frontend
```

### 4.3 当前进度与推荐开发顺序

**当前进度总结：**

| 步骤 | 内容 | 状态 |
|------|------|------|
| 步骤 1 | 环境变量配置 | ✅ |
| 步骤 2 | ES + Redis 中间件 | ✅ 可启动 |
| 步骤 3 | ES 知识库初始化 | 🔴 待实现 |
| 步骤 4 | NLP 意图分类 | ✅ 已实现 |
| 步骤 5 | Flask 后端 | ✅ 骨架可用（仅 `/api/health`） |
| 步骤 6 | Vue 前端 | ✅ 骨架可用（欢迎态 + 侧边栏） |
| 步骤 7 | Docker Compose 全栈 | ✅ 编排就绪 |

**推荐开发顺序（更新）：**

为了让项目更容易开发，建议按"最小可用闭环 → 语义增强 → 生成增强"的顺序推进：

1. ✅ **已完成**：项目骨架、SetFit 意图分类、前端首屏、Docker 编排。
2. **下一步（最小闭环）**：实现 `POST /api/chat` → `orchestrator` → SSE 返回，先用固定模板回复验证整条链路能跑通，再逐步接入真实服务。
3. **语义增强**：接入 BGE 向量检索 + ES FAQ 检索（`retriever.py`），接入 BERT 情感分析（`sentiment.py`）。
4. **生成增强**：接入 DeepSeek LLM 生成（`llm.py`），实现 RAG Prompt 模板和流式输出。
5. **体验打磨**：前端会话组件、Pinia 状态管理、多轮对话上下文、反馈记录。
6. 开发期间优先使用假数据和 mock 服务，避免所有依赖都完成后才能联调。

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

  redis:
    image: docker.1ms.run/library/redis:latest
    container_name: acss-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      - ./docker/redis/redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf

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
      - redis
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
  redis_data:
```

> **注意：** Docker Compose 中 `nlp` 服务对应 SetFit NLP HTTP API（端口 5005），与 v1.1 设计中的 `rasa` 服务不同。

### 4.5 开发流程建议

```text
1. 拉代码 → git clone
2. 配环境 → cp .env.example .env → 填 API Key
3. 启中间件 → docker compose up -d elasticsearch redis
4. 灌数据 → cd knowledge && uv run python scripts/seed_es.py  （🔴 待实现）
5. 训模型 → cd nlp && uv run python src/train.py               （✅ 已可用）
6. 启动 NLP → cd nlp && uv run python src/server.py             （✅ 已可用）
7. 启动后端 → cd backend && uv run python run.py                 （✅ 可用，仅 /api/health）
8. 启动前端 → cd frontend && npm run dev                        （✅ 可用）
9. 打开浏览器 → http://localhost:5173
```

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

- SetFit NLP 不可用时，`classifier.py` 返回 `{"intent": "other", "confidence": 0.0}`，不中断主流程。
- BGE 检索不可用时，退回到 ES 关键词检索，保证 FAQ 仍可服务。
- LLM 不可用时，退回到 FAQ 直返或模板回复，不阻断完整请求链路。
- Redis 不可用时，允许短时降级为无缓存模式，但保留主流程。
- 检索和分类置信度过低时，优先澄清追问，而不是强行给出答案。

### 5.2 RAG Prompt 模板

LLM 生成回答时使用的 prompt 结构：

```text
System: 你是一个电商客服助手。请根据以下知识库内容回答用户问题。
如果知识库中没有相关信息，请如实告知用户，不要编造答案。

知识库参考内容：
{retrieved_faqs}

用户意图：{intent}
用户情感：{sentiment}

User: {user_message}
Assistant:
```

### 5.3 缓存策略

| 缓存键 | 内容 | TTL | 说明 |
|--------|------|-----|------|
| `session:{id}:messages` | 会话消息列表 | 30 min | 多轮对话上下文 |
| `faq_cache:{query_hash}` | 匹配的 FAQ 答案 | 10 min | 相同问题直接返回 |
| `session:{id}:intent` | 最近一次意图 | 5 min | 辅助多轮消歧 |

### 5.4 失败与兜底规则

| 场景 | 处理方式 | 目的 |
|------|----------|------|
| 意图置信度低于阈值 | 触发澄清追问 | 降低误答 |
| NLP 服务不可用 | 返回 `intent: "other"`，继续主流程 | 不阻断核心能力 |
| 检索 Top-K 无命中 | 返回"未找到相关 FAQ"并交给 LLM 生成保守回答 | 避免硬编码错误答案 |
| LLM 超时 | 返回模板兜底文案 + 引导重试 | 保持接口可用 |
| Redis 失效 | 跳过缓存继续主流程 | 不阻断核心能力 |

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
| `POST` | `/api/sessions` | 创建新会话 | — | JSON（session_id） | 🔴 |
| `DELETE` | `/api/sessions/<id>` | 删除会话 | — | JSON | 🔴 |
| `GET` | `/api/sessions` | 列出会话 | — | JSON | 🔴 |
| `POST` | `/api/chat` | 发送消息 | `{session_id, message}` | **SSE 流** | 🔴 |
| `POST` | `/api/feedback` | 提交反馈 | `{session_id, message_id, rating}` | JSON | 🔴 |

### 6.1 SSE 事件格式

聊天接口以 SSE 流式返回，事件类型：

```text
event: intent
data: {"intent": "logistics_inquiry", "confidence": 0.95}

event: sentiment
data: {"label": "negative", "score": 0.72}

event: token
data: {"token": "您"}

event: token
data: {"token": "的"}

event: token
data: {"token": "订单"}

...（逐 token 推送）...

event: done
data: {"message_id": "msg_001", "full_answer": "您的订单...", "source": "faq_123"}
```

建议前端按事件类型分别处理：`intent` 用于调试提示，`sentiment` 用于标签展示，`token` 用于逐字渲染，`done` 用于收尾和落库。

---

## 7. 测试策略

### 7.1 测试分层

| 层级 | 工具 | 覆盖范围 | 状态 |
|------|------|----------|------|
| 单元测试 | pytest | `services/` 中每个模块的独立逻辑 | 🔴 待编写 |
| 集成测试 | pytest + docker | Flask API → NLP/ES/Redis 联动 | 🔴 待编写 |
| NLP 测试 | pytest | 意图分类准确率验证 | ✅ `nlp/tests/test_classifier.py` |
| 前端测试 | Vitest | Pinia store、组件渲染 | 🔴 待编写 |
| API 测试 | Postman | 手动接口调试 | ⚠️ 仅 `/api/health` |

### 7.2 关键测试场景

1. **分类准确** — SetFit 正确识别 7 种意图 ✅ 可测试
2. **检索命中** — ES 能匹配同义词（"退款" ↔ "退钱"） 🔴
3. **缓存生效** — 相同问题第二次请求直接返回缓存 🔴
4. **流式输出** — SSE 逐 token 推送，前端逐字显示 🔴
5. **降级处理** — NLP 不可用时优雅降级而非崩溃 ✅ 已处理（classifier.py catch 异常）
6. **情感标注** — 正确识别投诉类消息为负面情感 🔴

### 7.3 验收标准

1. 前端能完整发起一次对话并收到 SSE 流式回复。
2. SetFit 能返回意图和置信度（✅ 已满足 — `/parse` 端点可用）。
3. FAQ 检索命中时能优先返回缓存或 FAQ 答案。
4. LLM 不可用时系统仍能返回可读兜底回复。
5. 关键配置通过 `.env` 即可完成本地启动，不需要改代码（✅ 已满足）。

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
- Redis-py: https://redis-py.readthedocs.io

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

> **当前实现状态：** Sidebar（✅）、Header 模型选择器（✅）、Welcome 空状态 + 推荐问题（✅）、Input Area（✅）。聊天消息气泡和 SSE 逐字渲染尚未实现。

### 10.2 侧边栏（Sidebar）

侧边栏建议兼顾"产品导航"和"会话入口"，不要做成纯列表堆叠。

| 区域 | 内容 | 说明 | 状态 |
|------|------|------|------|
| Header | 产品 Logo + 新建会话按钮 | 固定在顶部 | ✅ |
| Nav | 导航项列表（智能客服等） | 当前选中项高亮 | ✅ |
| Session | 会话列表 | 支持新建、选中、删除 | 🔴 |
| User | 头像 + 用户名 + 退出按钮 | 固定在底部 | ⚠️ 仅展示"未登录" |

### 10.3 主内容区（Chat View）

主内容区建议拆成三个部分：`ChatContainer`、`MessageBubble` 和 `InputBox`。

#### Header

| 元素 | 说明 | 状态 |
|------|------|------|
| 模型选择器 | 下拉选择 LLM 模型，保留扩展入口 | ✅ |
| API 按钮 | 跳转接口文档或测试页面 | ✅ |
| 运行状态 | 显示后端/NLP 服务在线状态 | 🔴 |

#### Welcome / Empty State

当没有对话时，页面中心显示欢迎态，降低首次使用成本：

- 大标题 + 一句短副标题 ✅
- 推荐问题卡片 ✅
- 说明当前系统支持的能力，例如"退货、物流、商品咨询" ✅

#### 消息区

- 用户消息和机器人消息使用不同气泡样式 🔴
- 机器人回复支持 SSE 逐字渲染 🔴
- 长消息自动滚动到底部，但保留手动回看能力 🔴

#### 输入区

- 输入框采用圆角卡片样式 ✅
- 发送按钮在无内容时禁用 ✅
- 发送后保持输入框聚焦，减少重复操作 ✅（handleSend 中 TODO 标记）

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
| Sidebar | `frontend/src/components/Sidebar.vue` | 侧边导航与会话入口 | ✅ |
| ChatArea | `frontend/src/components/ChatArea.vue` | 欢迎态 + 模型选择 + 输入区 | ✅ |
| ChatContainer | `frontend/src/components/ChatContainer.vue` | 聊天主体容器与滚动控制 | 🔴 |
| MessageBubble | `frontend/src/components/MessageBubble.vue` | 消息气泡 | 🔴 |
| InputBox | `frontend/src/components/InputBox.vue` | 输入和发送操作（从 ChatArea 拆出） | 🔴 |
| ChatView | `frontend/src/views/ChatView.vue` | 页面级组合容器 | 🔴 |

### 10.6 设计原则

1. 首屏要能一眼看懂系统做什么。
2. 空状态必须提供推荐问题，避免用户不知道怎么开始。
3. 交互优先保持轻量，不把 UI 设计得比业务更复杂。
4. 风格统一，组件复用优先于每个页面单独设计。
