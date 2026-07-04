# 测试计划

> **版本**: v1.0
> **日期**: 2026-07-04
> **状态**: 与代码库对齐（157 用例，全部通过）
> **目标**: 验证后端服务层、API 层、Pipeline 编排、适配器层的完整测试覆盖

## 1. 测试目标

本项目测试覆盖以下内容：

- 后端服务层逻辑（Pipeline、Retriever、NLPClient、Sentiment、LLM、DB）
- API 层（Chat SSE 流式、Session CRUD）
- 适配器层（NLPClient HTTP、情感分析、LLM 双后端、Token 估算）
- 失败与兜底路径（连接错误、超时、模型不可用、API Key 缺失）
- 多轮对话上下文管理（历史传递、截断、Token 估算）

## 2. 测试分层

| 层级 | 工具 | 关注点 | 测试文件 | 用例数 |
|------|------|--------|----------|--------|
| 单元测试 | pytest | 配置、工具函数、服务层单独逻辑 | `test_adapters.py`, `test_retriever.py` | 49 |
| 集成测试 | pytest + mock | Pipeline 编排、DB 操作、SSE 流式、NLP 客户端 | `test_pipeline.py`, `test_db.py`, `test_chat.py` | 74 |
| NLP 测试 | pytest | 实体抽取（jieba + 正则） | `nlp/tests/test_extract.py` | 37 |
| 冒烟测试 | curl / 浏览器 / Docker Compose | 最小启动链路是否正常 | 手动 | — |

## 3. 当前测试覆盖

### 3.1 backend 测试（136 用例）

| 测试文件 | 用例数 | 覆盖范围 |
|----------|--------|----------|
| `test_pipeline.py` | 23 | PipelineContext、Stage 接口、IntentStage、SentimentStage、EntityStage、RetrieveStage、GenerateStage（含 history 传递）、Pipeline runner、默认工厂 |
| `test_db.py` | 27 | init_db、ensure_session、save_message、get_session_messages、delete_session、get_all_sessions |
| `test_chat.py` | 24 | SSE 格式校验、Chat API 完整流式响应、done/error 事件 |
| `test_adapters.py` | 31 | NLPClient（classify + extract 成功/失败/fallback）、Sentiment（三分类/阈值/不可用）、LLM（build_messages/history/truncate/stream/双后端）、Token 估算、上下文截断 |
| `test_retriever.py` | 21 | Retriever 初始化、ES fallback、内存向量检索、关键词匹配、format_context（部分用例需 ES 运行，3 skipped） |
| `test_analytics.py` | 11 | 数据分析 API 聚合查询（空库/有数据/结构校验）、get_analytics() 函数、GET /api/analytics 端点 |

### 3.2 nlp 测试（42 用例）

| 测试文件 | 用例数 | 覆盖范围 |
|----------|--------|----------|
| `nlp/tests/test_extract.py` | 37 | 订单号、手机号、金额、日期、运单号、快递公司、商品名 7 类实体，边界情况 |

### 3.3 全部通过

```
backend: 133 passed, 3 skipped
nlp:     42 passed
───────────────
total:   175 passed, 3 skipped
```

## 4. 手动验证清单

- [x] `GET /api/health` 返回 success
- [x] 前端页面无控制台报错
- [x] `docker compose up -d` 后服务状态正常
- [x] `.env` 配置能正确被后端读取
- [x] 统一响应格式在前后端一致
- [x] 多轮对话历史正确传递（LLM 能感知之前对话）
- [x] 上下文超限时自动截断最旧轮次

## 5. 验收标准

当项目进入可演示状态时，至少应满足：

1. 前端页面可打开并正常显示首屏。
2. 后端 `/api/health` 可返回统一 JSON。
3. Docker Compose 能拉起 ES、Ollama、NLP、Backend、Frontend。
4. `/api/chat` 能完整走通一次 SSE 聊天流程（intent → sentiment → entity? → token×N → done）。
5. 多轮对话中 LLM 能感知历史上下文。
6. 所有 pytest 测试通过（`uv run pytest` backend + nlp）。
7. 所有新增接口都配套最少一个测试用例或冒烟验证步骤。
