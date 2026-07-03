# AI 开发行为与流程规范

> **适用对象**: AI 编码助手（Claude Code、Copilot、Cursor 等）  
> **优先级**: 低于用户显式指令，高于模型默认行为

---

## 1. 核心行为准则

### 1.1 先理解后行动

- **禁止**在未阅读相关文件的情况下直接修改代码
- 涉及多文件修改时，必须先通读所有受影响文件
- 不确定的实现细节必须询问用户确认，**禁止猜测**

### 1.2 最小改动原则

- 每次改动只解决一个问题，不夹带无关修改
- 优先选择对现有代码影响最小的方案
- 不擅自重构与当前任务无关的代码
- 如果发现需要重构的问题，**先向用户报告**，获得许可后再进行

### 1.3 保持一致性

- 严格遵循项目已有的代码风格和模式
- 新代码的命名、注释密度、文件组织方式与现有代码一致
- 不引入项目未使用的技术/模式/库，除非用户明确要求

### 1.4 编写可运行代码

- 每个开发阶段结束后，项目必须处于**可运行状态**
- 不允许提交存在已知 Bug 或语法错误的代码
- 写完代码后必须验证（运行、测试、检查）

---

## 2. 开发流程

### 2.1 设计 → 计划 → 实现

```
用户需求 → 设计探索 → 方案确认 → 实现计划 → 逐任务编码 → 验证
```

| 阶段 | 负责 | 产物 |
|------|------|------|
| **头脑风暴** | AI + 用户 | `docs/superpowers/specs/<date>-<topic>-design.md` |
| **实现计划** | AI | 任务列表（TaskCreate） |
| **编码实现** | AI | 代码文件，每任务独立 commit |
| **审查验证** | AI + 用户 | 测试通过 + 代码审查 |

### 2.2 任务粒度

- 每个 Task 对应一个明确的、可独立验证的开发目标
- 一个 Task 完成后才进入下一个
- 完成一个 Task 后立即提交（1 task = 1 commit）

### 2.3 遇到阻塞时

当遇到以下情况时，**必须停下来询问用户**，不得绕过：

- 依赖的 API/服务不可用，且无明确降级方案
- 需要访问外部资源但没有凭证（API Key 等）
- 发现设计文档与实现存在矛盾
- 修改会影响超过 3 个已有模块
- 需要在 2 个以上合理方案中做选择

### 2.4 模块开发顺序约束

AI 必须按照依赖关系**自底向上**开发模块。被依赖的模块必须先完成并验证，才能开发依赖方。

```
Phase 0: 项目骨架（无依赖）
  ├── .gitignore, .env.example, docker-compose.yml
  ├── backend/pyproject.toml, backend/app/__init__.py (create_app 工厂)
  ├── backend/app/config.py, backend/app/extensions.py
  └── frontend/ 脚手架 (Vite + Vue 空壳)

Phase 1: 基础设施（中间件就绪后）
  ├── nlp/config/intents.yml          → 意图标签定义
  ├── nlp/data/training.jsonl         → SetFit 少样本训练数据
  ├── nlp/train.py                    → 训练并导出 SetFit 模型
  └── docker/es/                      → 中间件配置

Phase 2: 后端服务（自底向上，无循环依赖）
  ├── 2.1 models/message.py                        （Pydantic，无外部依赖）
  ├── 2.2 utils/response.py, utils/sse.py         （纯工具，无外部依赖）
  ├── 2.3 services/llm.py                          （依赖: config.DeepSeek/Ollama）
  ├── 2.4 services/nlp_client.py                   （依赖: NLP 服务可用）
  ├── 2.5 services/retriever.py                    （依赖: ES 有数据 + BGE 模型可用）
  ├── 2.6 services/sentiment.py                    （依赖: BERT 模型可用）
  ├── 2.7 services/db.py                           （依赖: SQLite stdlib）
  └── 2.8 services/orchestrator.py + pipeline.py   （依赖: 以上 5 个 service）

Phase 3: API 层（依赖 Phase 2 全部）
  ├── 3.1 api/session.py              （依赖: db.py）
  ├── 3.2 api/chat.py                 （依赖: orchestrator, utils/sse.py）
  └── 3.3 api/__init__.py             （Blueprint + health）

Phase 4: 前端（依赖 Phase 3 API 可用）
  ├── 4.1 src/api/index.js            （axios + SSE 封装）
  ├── 4.2 src/stores/chat.js          （Pinia, 依赖 api/index.js）
  ├── 4.3 components/MessageBubble.vue（无内部依赖）
  ├── 4.4 components/Sidebar.vue      （依赖 stores/chat.js）
  └── 4.5 components/ChatArea.vue     （依赖 MessageBubble + stores/chat.js）

Phase 5: 集成联调
  ├── 端到端流程验证
  └── 错误场景与降级测试
```

**约束规则：**

| 规则 | 说明 |
|------|------|
| **严格按 phase 顺序** | 不得跳过前置 phase 开发后续模块 |
| **同 phase 内可并行** | Phase 2 中 services/llm.py 和 models/ 可同步开发（无依赖） |
| **每完成一个模块必须验证** | `nlp_client.py` 写完后立即用 curl 调 NLP 服务验证，确认可用再写下一个 |
| **API 层可先写 mock** | 前端等不及后端时，API 层先返回假数据让前端先行，但 mock 必须标注 `# MOCK:` |
| **禁止循环依赖** | `services/` 模块之间如果出现 A → B 且 B → A，必须重构接口 |

### 2.5 跳过前置模块的例外

仅以下情况允许跳过前置依赖先行开发：

1. **用户明确指令** — 用户说"先写前端界面，后端后面再补"
2. **使用 Mock** — 被依赖模块用 mock 替代，且代码中显式标注 `# MOCK: 临时替代 <模块名>`，并在提交信息中注明 `(mock)` 前缀

---

## 3. 代码质量标准

具体编码规范见 **[`coding-standards.md`](coding-standards.md)**，涵盖：

| 规范 | 位置 |
|------|------|
| Python 风格基线、命名、导入、docstring、类型注解 | §1.1–§1.7 |
| 代码规模限制（函数 ≤60 行、文件 ≤400 行、嵌套 ≤4 层） | §1.8 |
| 错误处理规范（异常类型、上下文、降级、用户消息） | §1.9 |
| 注释规范（docstring、业务逻辑、HACK/TODO 标注） | §1.10 |
| 禁止事项（硬编码、调试代码、注释掉的代码、`import *`） | §1.11 |
| Vue 组件结构、Pinia Store、API 封装 | §2 |
| CSS BEM 命名与变量 | §3 |

AI 生成的所有代码必须符合 `coding-standards.md`，违规代码不得提交。

---

## 4. 本项目的 AI 行为约束

### 4.1 项目技术边界

- **Python 版本**: 3.10+（通过 uv 管理）
- **包管理器**: uv（不是 pip、poetry 或 conda）
- **前端**: Vue 3 + Vite + Pinia（不是 React 或 Angular）
- **LLM 调用**: 统一走 `services/llm.py`，不允许在 API 层直接调 DeepSeek/Ollama
- **NLP 微服务负责意图分类和实体抽取**: SetFit 模型 + jieba，通过 NLPClient 适配器调用
- **BERT 负责语义能力**: 检索（BGE）与情感分析（京东评论微调模型）使用独立模型
- **SQLite 负责会话持久化**: Python stdlib，WAL 模式，零额外依赖（不使用 Redis）

### 4.2 文件组织约束

- API 层（`api/`）只做参数校验和响应格式化，**不写业务逻辑**
- 业务逻辑全部在 `services/` 中，一个文件一个职责
- 数据模型在 `models/` 中，使用 Pydantic
- 工具函数在 `utils/` 中，纯函数、无副作用

### 4.3 修改项目设计文档

当开发过程中发现设计与实现存在差距需要更新设计文档时：

1. 先告知用户设计变更的内容和原因
2. 获得确认后更新 `docs/superpowers/specs/` 中的设计文档
3. 单独提交设计文档变更：`docs(spec): 更新 <变更说明>`

### 4.4 新依赖引入规则

AI **不得擅自添加**第三方依赖。引入新包必须经过以下审批流程：

**硬性规则：**

| 规则 | 说明 |
|------|------|
| **优先标准库** | 能用 Python 标准库解决的问题，不引入第三方包 |
| **优先已有依赖** | 检查 `pyproject.toml` 中已有依赖是否已能覆盖需求 |
| **引入前必须报告** | 向用户说明：包名、用途、体积、维护状态、替代方案 |
| **用户确认后再加** | 未获确认前不得执行 `uv add` |
| **锁定版本** | 通过 `>=x.y,<z` 锁定范围，禁止不加上限的 `>=x.y` |

**报告模板：**

```text
建议新增依赖：
- 包名: xxx
- 用途: 用于 <具体场景>
- 大小: ~X MB（含传递依赖）
- 活跃度: GitHub Stars Xk，最近更新 <日期>
- 替代方案: 已考虑 Y / Z，不选的原因 <...>
- 如果不用这个包，是否可以实现同样功能: 是/否（代价: ...）
```

**禁止引入的情况：**

- 包的最新版本超过 6 个月未更新且无活跃维护者
- 功能可以用 ≤ 30 行代码自行实现（避免"left-pad 问题"）
- 仅为了使用一个简单函数而引入整个重型框架
- 与项目中已有依赖存在已知冲突

---

## 5. 环境检测规范

AI 在**任何代码编写之前**，必须先执行环境检测。所有检测项通过后才能开始开发。任一检测失败，必须**停止并提示用户**，不得自行绕过。

### 5.1 检测流程

```text
                 ┌─────────────────┐
                 │ 开始环境检测     │
                 └────────┬────────┘
                          │
                 ┌────────▼────────┐
                 │ 1. Python 3.10  │
                 └────────┬────────┘
                    ┌─────┴─────┐
                    │ 通过？     │
                    └─────┬─────┘
                     No   │   Yes
                    ┌─────▼─────┐
                    │ 提示用户   │      ┌──────────────┐
                    │ 安装3.10   │      │ 2. uv 版本   │
                    │ 并停止     │      └──────┬───────┘
                    └───────────┘         ┌─────┴─────┐
                                          │ 通过？     │
                                          └─────┬─────┘
                                           No   │   Yes
                                          ...   │   ...
                                                │
                                    (依次检测 3~9)
                                                │
                                         ┌──────▼──────┐
                                         │ 全部通过     │
                                         │ 开始开发     │
                                         └─────────────┘
```

### 5.2 检测项（9 项）

AI 必须逐项执行以下命令并验证输出，**不可跳过任何一项**。

| # | 检测项 | 命令 | 预期输出 | 失败时提示用户 |
|---|--------|------|----------|---------------|
| 1 | Python 版本 | `python3 --version` 或 `uv run python --version` | `Python 3.10.x` | `请安装 Python 3.10: uv python install 3.10` |
| 2 | uv 可用 | `uv --version` | `uv 0.x.x`（任意版本） | `请安装 uv: curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| 3 | Node.js | `node --version` | `v20.x` 或更高 | `请安装 Node.js 20+: nvm install 20` |
| 4 | Docker 运行中 | `docker info` | `Server Version: ...`（无 error） | `请启动 Docker Desktop 或 sudo service docker start` |
| 5 | ES 镜像存在 | `docker image ls --format '{{.Repository}}:{{.Tag}}' \| grep elasticsearch` | 输出含 `elasticsearch:8.19.17` | `请拉取: docker pull docker.1ms.run/library/elasticsearch:8.19.17` |
| 6 | Ollama 镜像存在 | `docker image ls --format '{{.Repository}}:{{.Tag}}' \| grep ollama` | 输出含 `ollama` | `请拉取: docker pull ollama/ollama:latest` |
| 7 | ES 可达 | `curl -s http://localhost:9200/_cluster/health` | JSON 含 `"status":"green"` 或 `"yellow"` | `请启动: docker compose up -d elasticsearch` |
| 8 | NLP 服务可达 | `curl -s http://localhost:5005/health` | JSON 含 `"status":"ok"` | `请启动: docker compose up -d nlp` |
| 9 | .env 已配置 | `grep -q "sk-" .env && echo "OK"` | `OK` | `请复制 .env.example 为 .env 并填入 DEEPSEEK_API_KEY` |

> **首次运行补充检测**：如果镜像拉取失败（5/6 项），提示用户切换到备用代理 `docker.xuanyuan.me` 或官方源 `docker.elastic.co`。

### 5.3 检测报告格式

AI 完成检测后，向用户输出以下格式的报告：

```text
🔍 环境检测报告:

  ✅ Python 3.10.15     (uv 管理)
  ✅ uv v0.11.25
  ✅ Node.js v24.16.0
  ✅ Docker 27.x
  ⚠️ ES 未启动           → 请执行: docker compose up -d elasticsearch
  ❌ .env 未配置 API Key  → 请编辑 .env 填入 DEEPSEEK_API_KEY

检测结果: 5/9 通过。请修复以上 ⚠️/❌ 项后重新检测。
```

- `✅` = 通过，`⚠️` = 警告（服务未启动但不阻塞部分开发），`❌` = 阻断（必须修复）
- **有 `❌` 项时 AI 不得开始编码**
- **仅 `⚠️` 项时**，AI 可开始不依赖该服务的模块开发（如 ES 未启动时仍可写前端代码）

### 5.4 按开发阶段的精简检测

不同 Phase 对环境的依赖不同，允许按需检测：

| 开发阶段 | 必须通过的检测项 | 可跳过 |
|----------|-----------------|--------|
| Phase 0 骨架搭建 | 1, 2 | 3~9 |
| Phase 1 基础设施 | 1, 2, 4, 5, 6 | 3, 7, 8, 9 |
| Phase 2 后端服务 | 1, 2, 7, 8, 9 | 3（如不写前端） |
| Phase 3 API 层 | 1, 2, 7, 8, 9 | 3, 5, 6 |
| Phase 4 前端 | 2, 3 | 1, 5~9（后端可用 mocks） |
| Phase 5 集成联调 | **全部 9 项** | 无 |

> AI 必须在每个 Phase 开始前重新执行对应检测，不允许"上次通过了这次就跳过"。

---

## 6. 开发前必读检查清单

AI 编码助手在通过环境检测后、开始任何编码任务前，必须完成以下检查：

- [ ] 已阅读 `docs/superpowers/specs/` 中的最新设计文档
- [ ] 已阅读 `docs/vibecoding/` 中的所有规范文件
- [ ] 理解了当前任务的范围和边界
- [ ] 确认了要修改文件所在的目录结构和代码风格
- [ ] 如有不确定的决策点，已向用户询问

---

## 7. AI 完成任务自检清单

当 AI 声称"完成"一项开发任务时，**必须在报告完成前逐项验证**。未通过以下检查的任务不得标记为完成。

### 7.1 功能验证

- [ ] 代码可运行：`uv run python run.py` 正常启动，无 import 错误
- [ ] 核心路径已手动验证：至少用一个真实输入走通主线逻辑
- [ ] 新增/修改的接口已用 curl 或 Postman 验证返回符合预期
- [ ] 前端页面可正常渲染，无白屏或控制台报错

### 7.2 边界与异常验证

- [ ] 空输入、超长输入、特殊字符输入不会导致崩溃
- [ ] 外部依赖不可用时（ES、NLP 服务、DeepSeek/Ollama）有清晰的错误返回或降级
- [ ] 并发/重复请求不会导致状态错乱（至少脑内推演）

### 7.3 规范合规

- [ ] 代码符合 `docs/vibecoding/coding-standards.md`（命名、类型注解、docstring、行宽）
- [ ] 无违反禁止事项：无 `print()`、无硬编码密钥、无裸 `except:`
- [ ] 无调试代码残留（全局搜索 `TODO`、`FIXME`、`HACK`、`print(` 确认）
- [ ] 无注释掉的代码块
- [ ] API 层无业务逻辑，业务逻辑层无直接 Flask 依赖

### 7.4 Git 合规

- [ ] 提交信息符合 `docs/vibecoding/git-convention.md` 规范
- [ ] 本次提交只包含相关改动，不夹带无关文件
- [ ] `.env` 及任何含密钥的文件未 staged
- [ ] `git status` 干净或只有预期的文件变更

### 7.5 文档同步

- [ ] 如果新增了 API 端点，`docs/api.md` 是否需更新
- [ ] 如果改变了架构或流程，`docs/superpowers/specs/` 中的设计文档是否需更新
- [ ] 如果新增了通用工具/模式，是否需要在注释中说明用法

### 7.6 完成报告模板

AI 完成任务后，向用户的报告应遵循以下结构：

```text
✅ 已完成: <任务简述>

改动文件:
  - path/to/file1.py  — <改了什么>
  - path/to/file2.py  — <改了什么>

验证结果:
  - [具体验证步骤和结果，不要只说"测试通过了"]

未覆盖的边界:
  - <诚实列出已知未覆盖的场景，如有>
```

