# Git 提交规范

> **强制遵守**。不合规的提交将被要求修正后重新提交。

---

## 1. 提交信息格式（Conventional Commits）

```
<type>(<scope>): <subject>

[body]

[footer]
```

### 1.1 格式要求

| 部分 | 要求 | 示例 |
|------|------|------|
| `type` | **必填**，限定为以下 8 种 | `feat`, `fix` |
| `scope` | **必填**，标识影响的模块 | `backend`, `nlp`, `frontend` |
| `subject` | **必填**，≤ 50 字符，中文描述，不以句号结尾 | `新增 DeepSeek LLM 调用模块` |
| `body` | 可选，说明做了什么、为什么、如何做的 | 见示例 |
| `footer` | 可选，关联 Issue / Breaking Change | `Closes #12` |

### 1.2 允许的 type

| Type | 含义 | 使用场景 |
|------|------|----------|
| `feat` | 新功能 | 新增 API 接口、新增业务模块、新增页面组件 |
| `fix` | 修复 Bug | 修复逻辑错误、修复异常、修复显示问题 |
| `docs` | 文档变更 | README、API 文档、注释补充 |
| `style` | 代码格式 | 空格、缩进、分号等（不改变逻辑） |
| `refactor` | 重构 | 不增功能、不修 Bug 的代码改动 |
| `test` | 测试 | 新增或修改测试用例 |
| `chore` | 构建/工具 | 依赖更新、配置修改、Docker 调整 |
| `perf` | 性能优化 | 提升性能的代码变更 |

### 1.3 允许的 scope

| Scope | 对应路径 | 说明 |
|-------|---------|------|
| `backend` | `backend/` | Flask API、services、models、utils |
| `nlp` | `nlp/` | SetFit 模型、训练数据、实体抽取、Flask API |
| `frontend` | `frontend/` | Vue 组件、状态管理、样式 |
| `knowledge` | `knowledge/` | FAQ 数据、ES 脚本、同义词 |
| `docker` | `docker/`, `docker-compose.yml` | 容器配置 |
| `docs` | `docs/` | 项目文档 |
| `vibecoding` | `docs/vibecoding/` | AI 开发规范 |
| `project` | 根目录 | `.gitignore`、`.env.example` 等 |

---

## 2. 分支命名规范

```
<type>/<简短描述>
```

| 分支类型 | 格式 | 示例 |
|----------|------|------|
| 功能开发 | `feat/<描述>` | `feat/llm-stream-response` |
| Bug 修复 | `fix/<描述>` | `fix/redis-connection-timeout` |
| 重构 | `refactor/<描述>` | `refactor/orchestrator-parallel` |
| 文档 | `docs/<描述>` | `docs/api-interface-spec` |

**规则：**
- 全部小写，单词用 `-` 连接
- 从 `main` 分支拉出，合并回 `main`
- 合并前必须通过代码审查

---

## 3. 提交粒度规则

| 规则 | 说明 |
|------|------|
| **一个提交一件事** | 不允许 "修复了A模块的Bug并顺便加了B功能" |
| **提交可编译** | 每个 commit 后项目必须处于可运行状态 |
| **先拉后推** | push 前必须先 `git pull --rebase`，禁止强制推送 |
| **二进制文件不入库** | 模型文件（`.tar.gz`）、图片、`.pyc` 等一律 gitignore |

---

## 4. `.gitignore` 最低要求

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# uv
uv.lock          # 库项目忽略，应用项目可保留（本项目保留）

# SetFit 模型文件（体积大，不入库）
nlp/models/
nlp/checkpoints/

# 环境变量（含密钥，严禁入库）
.env

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Docker
docker/data/

# ES 数据
es_data/
```

---

## 5. 提交前自检清单

每次 `git commit` 前必须逐项确认：

- [ ] 提交信息格式符合第 1 节规范（type + scope + subject）
- [ ] subject 用中文描述，≤ 50 字符
- [ ] scope 正确指向改动的模块
- [ ] 本次提交只做了一件事
- [ ] 无调试代码（`print`、`console.log`）残留
- [ ] 无硬编码的密钥或敏感信息
- [ ] `.env` 未被 staged
- [ ] 代码本地可运行（`uv run python run.py` 正常启动）

---

## 6. 提交示例

### 好的提交

```text
feat(backend): 新增 DeepSeek LLM 流式生成模块

在 services/llm.py 中实现基于 openai SDK 的 DeepSeek 调用，
支持 stream=True 逐 token 返回，配合 utils/sse.py 实现 SSE 推送。

模型使用 deepseek-v4-flash，base_url 从 config 读取。
```

```text
fix(nlp): 修复 SetFit 训练数据中退货意图样本不足问题

nlu.yml 中 refund_inquiry 意图仅 3 条样本，导致分类准确率低。
补充至 15 条，覆盖"退货""退款""换货"等表达。
重新训练后该意图 F1 从 0.62 提升至 0.91。
```

```text
chore(docker): ES 镜像升级至 8.19.17 并调整 JVM 内存限制

解决本地开发时 ES 内存溢出问题，限制 Xms/Xmx 为 512m。
```

### 不好的提交

```text
fix: 修bug                          ← 缺少 scope，描述不清
update code                         ← 全英文，不知道改了什么
feat(backend): 新增LLM模块 + 修复ES连接池bug + 更新README
                                    ← 一次提交做了三件事
WIP                                 ← 无意义
```

---

## 7. 违规处理

| 违规行为 | 处理方式 |
|----------|----------|
| 提交信息格式错误 | 拒绝合并，要求 `git commit --amend` 修正 |
| 一次提交包含多个不相关改动 | 拒绝合并，要求拆分提交 |
| `.env` 或密钥被提交 | 立即回滚，使用 `git filter-branch` 清除历史 |
| 强制推送至共享分支 | 严肃警告，恢复分支 |

> **团队协作时**：在 `main` 分支设置分支保护，开启 "Require a pull request before merging"。  
> **个人学习项目**：建议同样严格遵循以养成工程习惯。

---

## 8. AI 自动提交规范

当 AI 编码助手代为执行 `git commit` 时，除遵守上述所有规则外，还必须满足以下额外约束。

### 8.1 AI 生成提交信息的红线

| 禁止 | 原因 |
|------|------|
| 模糊动词如 `update`、`change`、`modify` | 无法从 commit log 理解改了什么 |
| 纯英文 subject（本项目约定中文） | 提交历史混搭语言难以检索 |
| 一次提交混合超过一个 type | `feat + fix + chore` 合并在一起无法 cherry-pick |
| 只写 what 不写 why | body 必须解释"为什么这样做"，尤其对于非机械性改动 |
| 虚报完成状态 | 代码未经验证就提交并标记 `feat` |
| 使用 `-m` 单行提交任何非 trivial 改动 | 单行适合 `docs:` 或 `chore:` 类微调，功能代码必须有 body |

### 8.2 AI 提交前必须执行的验证

在执行 `git commit` 之前，AI 必须：

```text
1. 运行 git diff --staged 确认改动内容
2. 检查是否有意外 staged 的文件（.env、缓存、临时文件）
3. 确认改动仅涉及本次任务的范围（无 scope creep）
4. 运行项目启动/测试，确认可运行
```

### 8.3 AI 提交信息生成流程

```text
1. 识别改动范围  → git diff --stat 看改了哪些文件
2. 确定 type     → 对照 1.2 表选择最准确的 type
3. 确定 scope    → 对照 1.3 表选择最准确的 scope
4. 撰写 subject  → 中文，≤50 字符，动词开头，描述核心变更
5. 撰写 body     → 说明：为什么改(sql)，怎么改的(关键实现细节)
6. 用户确认      → 将生成的提交信息展示给用户，获得确认后执行
```

**步骤 6 不可跳过。** AI 不得在用户未审阅提交信息的情况下直接执行 commit。

### 8.4 AI 提交信息示例

**功能开发：**
```text
feat(backend): 实现 orchestrator 并行调度分类+检索+情感

三个服务调用之间无依赖关系，使用 concurrent.futures.ThreadPoolExecutor
并行执行，将 /api/chat 端到端延迟从 ~3.2s 降至 ~1.1s。

每个子任务设置 2s 超时，任一失败不影响其他子任务，走降级逻辑。
```

**Bug 修复：**
```text
fix(backend): 修复 SQLite 连接未关闭导致 WAL 文件膨胀

问题: 每次请求创建新 SQLite 连接而未关闭，WAL 文件持续增长。
修复: 通过 extensions.py 统一管理单例连接池，max_connections=10。
验证: 50 并发压测不再出现 ConnectionError。
```

**依赖变更：**
```text
chore(backend): 新增 redis 依赖用于会话缓存

按 `ai-workflow.md` §4.4 依赖引入流程审批:
- 包名: redis (redis-py)
- 用途: Flask 会话管理 + FAQ 检索结果缓存
- 已确认: pyproject.toml 中无替代包可覆盖此需求
```
