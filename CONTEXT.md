# 领域上下文

ACSS（Auto Classify Support System）是一个电商客服智能问答系统。

## 领域词汇

| 术语 | 定义 |
|------|------|
| **意图（Intent）** | 用户消息的客服意图分类，共 7 类：`refund_inquiry`（退货退款）、`logistics_inquiry`（物流查询）、`product_inquiry`（商品咨询）、`order_inquiry`（订单查询）、`complaint`（投诉）、`other`（其他）、`chitchat`（闲聊） |
| **情感（Sentiment）** | 用户消息的情感极性：`positive`（正面）、`negative`（负面）、`neutral`（中性）。通过 BERT 二分类模型 + 置信度阈值实现三分类 |
| **实体（Entity）** | 从用户消息中抽取的电商相关结构化信息，共 7 类：订单号、手机号、金额、日期、运单号、快递公司、商品名 |
| **会话（Session）** | 一次多轮对话，包含用户消息和助手回复。持久化在 SQLite 中 |
| **FAQ** | 预定义的常见问题及其答案，共 16 条，覆盖 7 个意图类别。通过 ES 混合检索或 BGE 向量检索匹配 |
| **RAG（Retrieval-Augmented Generation）** | 检索增强生成——先检索 FAQ 获取上下文，再交给 LLM 生成回答 |
| **SSE（Server-Sent Events）** | 服务端推送协议，用于流式返回 LLM token 和分析结果 |
| **Pipeline** | 分析步骤的编排模式：Intent → Sentiment → Entity → Retrieve → Generate，每步独立可测试 |

## 系统边界

- **用户侧**：Vue 3 前端（SPA），通过 SSE 接收流式回答
- **后端侧**：Flask API 服务（:5000），协调 NLP、检索、LLM 调用
- **NLP 侧**：独立 Flask 微服务（:5005），提供意图分类和实体抽取
- **存储侧**：SQLite（会话和消息）、Elasticsearch（FAQ 索引）
- **LLM 侧**：DeepSeek API（云端）或 Ollama（本地 qwen2.5:7b）
