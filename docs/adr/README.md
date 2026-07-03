# 架构决策记录（ADR）

此目录用于记录项目的关键架构决策。

## 已有决策

| ADR | 日期 | 决策 | 状态 |
|-----|------|------|------|
| — | — | 尚无正式 ADR | — |

## 未记录的重要决策

以下决策已体现在代码中，但尚未正式写成 ADR：

1. **Redis 移除** — 会话和缓存使用 SQLite 替代 Redis，减少依赖
2. **双 LLM 后端** — DeepSeek API 和 Ollama 本地模型通过 `LLM_BACKEND` 环境变量切换
3. **Pipeline 模式** — orchestrator God Function 重构为 Pipeline + 5 个独立 Stage
4. **NLPClient 适配器** — 统一对 NLP 微服务的所有 HTTP 调用
5. **置信度阈值三分类** — BERT 二分类模型 + SENTIMENT_THRESHOLD 实现 neutral
