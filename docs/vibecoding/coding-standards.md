# 编码规范

> 本项目统一编码规范。AI 编码助手生成的所有代码必须符合此规范。

---

## 1. Python 编码规范

### 1.1 风格基线

- 遵循 **PEP 8**，以 **Ruff** 为 lint 工具
- 行宽上限 100 字符（非 PEP 8 默认的 79）
- 缩进 4 空格，**禁止 Tab**

### 1.2 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| 模块/文件 | `snake_case` | `classifier.py`, `message.py` |
| 类 | `PascalCase` | `ChatService`, `FAQDocument` |
| 函数/方法 | `snake_case` | `classify_intent()`, `get_session()` |
| 变量 | `snake_case` | `user_message`, `faq_list` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT`, `DEFAULT_TTL` |
| 私有成员 | 前缀 `_` | `_cache_client`, `_build_prompt()` |

### 1.3 导入顺序

```python
# 1. 标准库
import json
from typing import Optional

# 2. 第三方库
from flask import Blueprint, request
from pydantic import BaseModel

# 3. 项目内部
from app.services.nlp_client import get_nlp_client
from app.utils.response import api_response
```

每组之间空一行。不使用 `import *`。

### 1.4 Docstring 格式（Google 风格）

```python
def classify_intent(message: str, threshold: float = 0.5) -> dict:
    """调用 NLP 微服务对用户消息进行意图分类。

    Args:
        message: 用户输入的原始文本。
        threshold: 意图置信度阈值，低于此值的意图归为 "other"。

    Returns:
        dict: 包含 intent (str) 和 confidence (float) 的字典。

    Raises:
        ConnectionError: NLP 服务不可达时抛出。
    """
    ...
```

### 1.5 类型注解

- 所有公开函数/方法的参数和返回值**必须**有类型注解
- 使用 `from __future__ import annotations`（若需延迟求值）
- 复杂类型用 `typing` 模块：`Optional`, `Union`, `Literal`

### 1.6 Pydantic 模型

```python
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """聊天消息请求体。"""
    session_id: str = Field(..., min_length=1, description="会话 ID")
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
```

### 1.7 项目特定约定

```python
# ─── 日志 ───
import logging
logger = logging.getLogger(__name__)
logger.info("分类完成: intent=%s, confidence=%.2f", intent, confidence)
# 注意: 使用 % 格式化而非 f-string，符合 logging 最佳实践

# ─── 统一响应 ───
from app.utils.response import api_response
return api_response(data={"session_id": sid}, message="创建成功")
# 禁止: return jsonify({...})  直接使用

# ─── 服务层注入 ───
# 通过 extensions.py 获取客户端实例，不在服务模块内直接创建连接
from app.extensions import get_es_client
```

### 1.8 代码规模限制

| 限制项 | 上限 | 说明 |
|--------|------|------|
| 单个函数 | ≤ 60 行 | 不含 docstring 和空行；超过则拆分 |
| 单个文件 | ≤ 400 行 | 超过则按职责拆分模块 |
| 嵌套层级 | ≤ 4 层 | `if` → `for` → `if` → `try` 即 4 层，再深就抽取函数 |
| 单行字符 | ≤ 100 字符 | 与 Ruff line-length 配置一致 |

### 1.9 错误处理

```python
# ✅ 正确：指定异常类型 + 上下文信息
try:
    result = es_client.search(index="faq", body=query)
except ConnectionError as e:
    logger.error("ES 连接失败: host=%s, error=%s", ES_HOST, e)
    raise ServiceUnavailableError("知识库暂时不可用，请稍后重试") from e

# ❌ 错误：裸异常捕获 + 无上下文
try:
    result = es_client.search(index="faq", body=query)
except:
    pass
```

**规则：**
- 所有外部调用（API、数据库、文件 I/O）**必须**有异常处理
- 异常类型必须具体（`ConnectionError` 非 `Exception`），**禁止**空 `except:`
- 错误信息必须包含上下文：操作名称 + 关键参数 + 原始错误
- 用户可见的错误消息用中文，**禁止**直接暴露堆栈信息
- 降级策略必须显式编码（如检索失败时回退关键词检索；NLP 服务不可用时 fallback 到 "other" 意图）

### 1.10 注释规范

| 场景 | 要求 | 示例 |
|------|------|------|
| 公开函数/类 | **必须**有 docstring（Google 风格，见 1.4） | — |
| 非直觉业务逻辑 | **必须**注释说明 **为什么** 这样做 | `# 此处用 SHA256 而非 MD5，因为需要符合安全审计要求` |
| 魔法数字 | **必须**命名常量并注释含义 | `CACHE_TTL_SECONDS = 600  # FAQ 缓存 10 分钟` |
| 临时方案 | **必须**标注 `# HACK:` 或 `# WORKAROUND:` 并说明限制 | `# HACK: SetFit 不支持 predict_proba 批量，暂分两次调用，后续考虑合并` |
| 待办事项 | 用 `# TODO(<姓名>): <描述>` 格式 | `# TODO(zhangsan): 切换为异步 HTTP 客户端` |

### 1.11 禁止事项

| 禁止行为 | 说明 |
|----------|------|
| 硬编码密钥/Token | 一律走 `.env` 或环境变量 |
| 提交调试代码 | `print()`、`console.log()`、`breakpoint()` 提交前删除 |
| 注释掉的代码 | 要么删掉，要么补充注释说明为什么保留并标注恢复条件 |
| 裸异常捕获 | 禁止 `except:` 或 `except Exception:` |
| `import *` | 必须显式列出导入项 |
| 直接 `jsonify()` | 使用 `app.utils.response.api_response()` 统一响应格式 |
| 服务层内创建连接 | 通过 `extensions.py` 获取客户端实例 |

---

## 2. JavaScript / Vue 编码规范

### 2.1 风格基线

- 使用 **ESLint** + **Prettier**（默认配置）
- 缩进 2 空格
- 字符串用单引号 `'`
- 语句末尾加分号 `;`

### 2.2 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| 文件（组件） | `PascalCase` | `MessageBubble.vue` |
| 文件（工具） | `camelCase` | `formatTime.js` |
| 变量/函数 | `camelCase` | `userMessage`, `fetchSessions()` |
| Pinia Store | `camelCase` + `use` 前缀 | `useChatStore` |
| CSS 类名 | `kebab-case` | `.message-bubble`, `.chat-container` |

### 2.3 Vue 组件结构

```vue
<script setup>
// 1. imports
import { ref, computed } from 'vue';
import { useChatStore } from '@/stores/chat';

// 2. props & emits
const props = defineProps({
  message: { type: Object, required: true },
});
const emit = defineEmits(['retry']);

// 3. store / composables
const chatStore = useChatStore();

// 4. reactive state
const isExpanded = ref(false);

// 5. computed
const displayTime = computed(() => formatTime(props.message.timestamp));

// 6. methods
function handleRetry() {
  emit('retry', props.message.id);
}
</script>

<template>
  <div class="message-bubble" :class="{ 'is-expanded': isExpanded }">
    <p class="message-bubble__text">{{ message.text }}</p>
    <span class="message-bubble__time">{{ displayTime }}</span>
  </div>
</template>

<style scoped>
.message-bubble {
  /* 使用 BEM 命名 */
}
</style>
```

### 2.4 Pinia Store 约定

```javascript
// stores/chat.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { sendMessage, createSession } from '@/api';

export const useChatStore = defineStore('chat', () => {
  // state
  const sessions = ref([]);
  const currentSessionId = ref(null);

  // getters
  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value)
  );

  // actions（只有 actions 能修改 state）
  async function startNewSession() {
    const session = await createSession();
    sessions.value.unshift(session);
    currentSessionId.value = session.id;
    return session;
  }

  return { sessions, currentSessionId, currentSession, startNewSession };
});
```

### 2.5 API 调用约定

```javascript
// api/index.js — 所有后端调用集中在此模块
import axios from 'axios';

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
});

// SSE 流式请求封装
export function streamChat(sessionId, message, { onToken, onIntent, onSentiment, onDone, onError }) {
  // ...
}

// 普通 JSON 请求
export async function createSession() {
  const { data } = await http.post('/sessions');
  return data.data;
}
```

---

## 3. CSS 规范

### 3.1 命名约定

- 使用 **BEM**（Block Element Modifier）
- 组件内样式使用 `<style scoped>`
- 全局样式放在 `assets/style.css`

```css
/* Block */
.chat-container { }

/* Element */
.chat-container__header { }
.chat-container__message-list { }

/* Modifier */
.message-bubble--sent { }
.message-bubble--received { }
.message-bubble--error { }
```

### 3.2 CSS 变量

```css
:root {
  --color-primary: #4f46e5;
  --color-bg: #f8fafc;
  --color-text: #1e293b;
  --color-text-secondary: #64748b;
  --radius-sm: 6px;
  --radius-md: 10px;
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.08);
}
```

---

## 4. 配置文件规范

### 4.1 环境变量（`.env`）

- 本地开发用 `.env`，生产部署用 Docker 环境变量注入
- `.env` **不入库**（已在 `.gitignore` 中）
- `.env.example` 保留所有变量名和说明，值为假数据

### 4.2 Docker

- 镜像固定版本号，不使用 `latest` 标签
- 容器名统一前缀 `acss-`
- 数据卷命名与容器名对应
