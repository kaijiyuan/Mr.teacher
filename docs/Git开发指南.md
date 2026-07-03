# Git 开发指南

本文档用于当前多 Agent 学习助手项目的团队协作。目标是让每个同学在自己的分支开发，负责人统一合并，避免互相覆盖代码。

## 推荐协作方式

使用 Git 分支协作，不建议直接本地互传文件。

推荐分支：

```text
master
├── feature/file-parser-agent
├── feature/mindmap-agent
├── feature/quiz-agent
└── feature/ppt-agent
```

分工建议：

| 成员 | 分支 | 主要内容 |
| --- | --- | --- |
| 同学 A | `feature/file-parser-agent` | PDF 解析、知识库写入 |
| 同学 A | `feature/mindmap-agent` | 摘要、思维导图 |
| 同学 B | `feature/quiz-agent` | 题库生成、答题评估 |
| 同学 B | `feature/ppt-agent` | PPT 大纲和 PPT 文件生成 |

## 开始开发

从最新主分支创建自己的功能分支：

```bash
git checkout master
git pull
git checkout -b feature/file-parser-agent
```

如果使用 Fork 模式：

```bash
git clone https://github.com/<your-name>/<repo>.git
cd <repo>
git remote add upstream https://github.com/<owner>/<repo>.git

git fetch upstream
git checkout master
git merge upstream/master
git checkout -b feature/file-parser-agent
```

## 日常提交

提交前先看工作区：

```bash
git status
git diff
```

只提交和本任务有关的文件：

```bash
git add backend/app/agents/file_parser
git add backend/app/services/knowledge.py
git commit -m "feat(file-parser): add pdf ingestion agent"
```

不要直接 `git add .`，除非你已经确认没有 `.env`、缓存、临时文件、IDE 配置混进去。

## 提交信息规范

格式：

```text
<type>(<scope>): <subject>
```

常用 type：

| type | 用途 | 示例 |
| --- | --- | --- |
| `feat` | 新功能 | `feat(quiz): add question generator` |
| `fix` | 修复问题 | `fix(ppt): handle empty outline` |
| `refactor` | 重构 | `refactor(core): simplify runtime setup` |
| `docs` | 文档 | `docs(agent): add development guide` |
| `test` | 测试 | `test(mindmap): add local verification` |
| `chore` | 工具/依赖 | `chore(deps): add pdf parser dependency` |

推荐 scope：

| scope | 范围 |
| --- | --- |
| `core` | `backend/app/core` |
| `service` | `backend/app/services` |
| `tutor` | 引导式答疑 Agent |
| `file-parser` | 文件解析 Agent |
| `mindmap` | 思维导图 Agent |
| `quiz` | 题库 Agent |
| `ppt` | PPT Agent |
| `docs` | 文档 |

## 开发约束

每个同学遵守以下规则：

1. 不直接改 `master`。
2. 不提交 `.env`、API Key、`__pycache__`、`.pyc`、`node_modules`、生成的临时 PDF/PPT。
3. 不随意改别人负责的 Agent 目录。
4. 不直接改 `backend/main.py` 接 API，除非负责人明确安排。
5. Agent 必须参考 `backend/app/agents/tutor/` 的结构。
6. Agent 通过 `runtime.get_service(...)`、`self.call_llm(...)`、`self.use_tool(...)` 获取服务和工具，不在 Agent 内创建重服务。

## 推送和合并

推送自己的分支：

```bash
git push origin feature/file-parser-agent
```

如果使用 GitHub：

1. 创建 Pull Request。
2. PR 描述里写清楚输入输出、改了哪些文件、如何验证。
3. 负责人 Review 后再合并。

如果只在本地协作：

1. 每个人保持自己的分支。
2. 完成后把分支交给负责人。
3. 负责人切到 `master` 后合并：

```bash
git checkout master
git merge feature/file-parser-agent
```

## 合并前自检

提交 PR 或交付分支前检查：

- `git status` 里没有无关文件。
- 没有提交 `.env`、缓存、临时产物。
- Agent 的 `input_keys` 和 `output_keys` 与实际 `state_update` 一致。
- 新增服务已在文档说明清楚。
- 至少有一个本地验证方式，能说明如何运行。
- 如果改了依赖，已更新 `backend/requirements.txt` 或前端依赖文件。

## 常见问题

### 同步主分支更新

```bash
git checkout master
git pull
git checkout feature/file-parser-agent
git merge master
```

### 查看当前改了什么

```bash
git status
git diff
```

### 只撤销某个文件的本地改动

谨慎使用，确认不是别人需要的改动：

```bash
git restore path/to/file.py
```

### 删除已经合并的本地分支

```bash
git branch -d feature/file-parser-agent
```

## 参考文档

- `docs/同学A-B开发指南.md`
- `backend/app/agents/README.md`
- `backend/app/agents/tutor/`
