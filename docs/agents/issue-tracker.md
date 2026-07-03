# Issue tracker: Local Markdown

Issues 以 markdown 文件形式存放在 `.scratch/` 目录下。

## 约定

- 每个问题一个目录：`.scratch/<issue-slug>/`
- Issue 文件：`.scratch/<issue-slug>/issue.md`
- 状态记录在 issue 文件顶部的 `**状态**:` 行（标签字符串见 `triage-labels.md`）
- 讨论追加在文件底部的 `## 评论` 标题下

## 当技能说 "发布到 issue tracker"

在 `.scratch/<feature-slug>/` 下创建新的 `issue.md`（必要时创建目录）。

## 当技能说 "获取相关 ticket"

读取指定路径的 issue 文件。用户通常会直接传递路径或 slug。
