# API 接口文档

> **版本**: v1.1
> **日期**: 2026-07-04
> **状态**: 与代码库（commit 8d760f3）对齐

## 1. 概述

本项目采用 Flask 作为后端 API 层，所有业务响应通过统一响应工具 `app.utils.response` 返回。Swagger/OpenAPI 文档可通过 `/docs` 访问（由 flasgger 提供）。

## 2. 统一响应规范

### 2.1 成功响应

```json
{
  "status": "success",
  "message": "服务运行中",
  "data": { "service": "auto-classify-support-system", "version": "0.1.0" }
}
```

### 2.2 错误响应

```json
{
  "status": "error",
  "message": "错误说明",
  "data": null
}
```

### 2.3 通用约定

- `status` 仅取 `success` 或 `error`
- `message` 面向用户，使用中文
- `data` 为业务数据，失败时为 `null`

## 3. 已实现接口

| 方法 | 路径 | 说明 | 响应类型 |
|------|------|------|----------|
| `GET` | `/api/health` | 服务健康检查 | JSON |
| `POST` | `/api/chat` | 发送消息，SSE 流式返回回复 | SSE（text/event-stream） |
| `GET` | `/api/sessions` | 会话列表（按 updated_at 倒序） | JSON |
| `GET` | `/api/sessions/<id>` | 会话详情（含全部消息） | JSON |
| `DELETE` | `/api/sessions/<id>` | 删除会话及关联消息 | JSON |
| `GET` | `/api/analytics` | 数据分析聚合数据 | JSON |
| `GET` | `/docs` | Swagger/OpenAPI 交互式文档 | HTML |

### 3.1 健康检查

**`GET /api/health`**

```json
{
  "status": "success",
  "message": "服务运行中",
  "data": { "service": "auto-classify-support-system", "version": "0.1.0" }
}
```

### 3.2 发送消息（SSE 流式）

**`POST /api/chat`**

请求体：

```json
{
  "session_id": "session_abc123",
  "message": "我的快递什么时候到？"
}
```

> `session_id` 和 `message` 均为必填。`session_id` 由前端在新建会话时自动生成。

**多轮对话：** 后端在每次请求时自动从 SQLite 加载该会话的历史消息，转换为 LLM 对话格式后传入生成阶段。历史消息在保存当前消息**之前**加载，确保不会将当前消息误包含进历史。超过上下文窗口（默认 28000 tokens）时自动截断最旧轮次，至少保留最近 3 轮对话。

### 3.3 会话管理

**`GET /api/sessions`** — 会话列表，返回 `{ sessions: [...] }`（含 `id`、`title`、`message_count`、`updated_at`）。

**`GET /api/sessions/<id>`** — 会话详情，返回 `{ session: {...}, messages: [...] }`。

**`DELETE /api/sessions/<id>`** — 删除会话，级联删除关联消息。

> 会话在首次发送消息时自动创建（title 取首条消息前 20 字），无需单独的 POST 创建端点。

### 3.4 数据分析

**`GET /api/analytics`**

返回聚合统计数据，供给前端数据看板使用：

```json
{
  "status": "success",
  "data": {
    "total_sessions": 42,
    "total_messages": 256,
    "average_session_depth": 6.1,
    "today_active_sessions": 3,
    "intent_distribution": [
      {"intent_label": "refund_inquiry", "count": 58},
      {"intent_label": "logistics_inquiry", "count": 42}
    ],
    "sentiment_distribution": [
      {"sentiment_label": "neutral", "count": 120},
      {"sentiment_label": "negative", "count": 45},
      {"sentiment_label": "positive", "count": 30}
    ],
    "daily_trend": [
      {"day": "2026-07-01", "count": 12},
      {"day": "2026-07-02", "count": 8}
    ],
    "hourly_activity": [
      {"hour": 9, "count": 35},
      {"hour": 14, "count": 48}
    ]
  }
}
```

| 字段 | 说明 |
|------|------|
| `total_sessions` | 会话总数 |
| `total_messages` | 消息总数（含 user + assistant） |
| `average_session_depth` | 平均每个会话的消息数 |
| `today_active_sessions` | 今日有消息的会话数 |
| `intent_distribution` | 各意图的消息数量分布 |
| `sentiment_distribution` | 各情感的消息数量分布 |
| `daily_trend` | 近 30 天每日消息量趋势 |
| `hourly_activity` | 按小时（0-23）的消息量分布 |

## 4. SSE 事件约定

`POST /api/chat` 返回 `text/event-stream`，事件序列如下：

```
event: intent
data: {"intent": "logistics_inquiry", "confidence": 0.95}

event: sentiment
data: {"label": "neutral", "score": 0.42}

event: entity                          （可选，仅当抽取到实体时）
data: {"entities": {"tracking": {"values": ["SF1234567890"]}}, "summary": "运单号: SF1234567890"}

event: token
data: {"token": "您"}

event: token                           （×N，逐字流式）
data: {"token": "的"}

event: done
data: {"message_id": "msg_abc123", "full_answer": "您的快递...", "source": "llm"}
```

错误时：

```
event: error
data: {"message": "处理您的问题时出现错误，请稍后重试"}

event: done
data: {"message_id": "msg_abc123", "full_answer": "", "source": "error"}
```

### 4.1 事件说明

| 事件 | 数据字段 | 说明 |
|------|----------|------|
| `intent` | `intent`, `confidence` | 意图分类结果（7 类之一） |
| `sentiment` | `label`, `score` | 情感分析结果（positive/negative/neutral） |
| `entity` | `entities`, `summary` | 实体抽取结果（可选，无实体时不发送） |
| `token` | `token` | 单字/词（流式生成时多次发送） |
| `done` | `message_id`, `full_answer`, `source` | 流结束信号（source: llm/error） |
| `error` | `message` | 错误说明（不可恢复错误，后跟 done） |
