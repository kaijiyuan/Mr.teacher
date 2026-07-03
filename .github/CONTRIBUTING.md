# 贡献指南

本项目采用分支开发、负责人统一合并的方式协作。

## 开发流程

```bash
git checkout master
git pull
git checkout -b feature/<功能名称>
```

开发完成后只暂存本任务相关文件：

```bash
git status
git diff
git add backend/app/agents/<agent_name>
git commit -m "feat(<scope>): <subject>"
git push origin feature/<功能名称>
```

不要直接提交 `.env`、`__pycache__`、`.pyc`、`node_modules`、临时 PDF/PPT 或 IDE 配置。

## Agent 开发规范

1. 继承 `BaseAgent`。
2. 定义静态 `AgentConfig`。
3. 实现 `process(inputs, runtime) -> AgentResult`。
4. 通过 `runtime.get_service(...)`、`self.call_llm(...)`、`self.use_tool(...)` 使用服务和工具。
5. 不在 Agent 内创建 LLM、向量库、文件存储等重服务。

参考：

- `docs/同学A-B开发指南.md`
- `docs/Git开发指南.md`
- `backend/app/agents/README.md`
- `backend/app/agents/tutor/`

## 验证要求

当前项目尚未统一 pytest 依赖。提交前至少提供一种本地验证方式，并说明运行命令和结果。后续测试框架统一后，再补正式单元测试。
