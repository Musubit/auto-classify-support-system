# Vibecoding 规则目录

本目录包含 **AI 辅助开发（Vibecoding）** 过程中 AI 编码助手必须遵守的行为规范、流程约束和编码标准。

## 目录结构

```
vibecoding/
├── README.md              # 本文件 — 规则体系说明
├── ai-workflow.md         # AI 开发行为与流程规范（AI 必读）
├── coding-standards.md    # 编码规范（Python + Vue + CSS）
└── git-convention.md      # Git 提交规范
```

## 规则优先级

1. **用户显式指令** — 最高优先级，覆盖以下所有规则
2. **本目录规则** — AI 编码助手的默认行为约束
3. **项目设计文档** — `docs/superpowers/specs/` 中的架构与接口约定

## 适用对象

本目录中的规则适用于以下 AI 编码场景：

- AI 辅助编写代码、修改代码、重构代码
- AI 生成 Git 提交信息
- AI 规划开发任务并执行
- AI 进行代码审查

## 规则更新

当发现规则不完善或有新的最佳实践时，通过以下流程更新：

1. 在实际开发中发现问题或改进点
2. 更新对应的规则文件
3. 提交 commit: `docs(vibecoding): 更新 <具体规则名称>`
