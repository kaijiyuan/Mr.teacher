# 同学 A/B Agent 开发指南

本文档基于当前项目代码结构编写，目标是让同学 A 和同学 B 可以直接开始开发各自 Agent，同时避免接口、状态字段和服务边界不一致。

## 先修正当前技术方案里的几个点

1. 当前项目还不是完整 LangGraph 工程，现阶段底座是 `BaseAgent + AgentRuntime + AgentResult + Director`。后续可以迁移到 LangGraph，但这次开发先按现有底座实现。
2. 不要在 Agent 内创建重服务，比如 LLM、向量库、文件存储。Agent 只通过 `runtime.get_service(...)` 或 `self.use_tool(...)` 获取能力。
3. 现在 `backend/app/services/container.py` 只有 `llm` 和 `profile`，还没有 `knowledge` 服务。同学 A 的第一优先级应该是补出统一 `KnowledgeService`，否则同学 B 无法稳定接入 RAG。
4. 当前项目没有 pytest 依赖，技术方案里“必须 pytest 覆盖率 80%”暂时不落地。第一阶段先提供可运行的本地验证脚本或最小测试，等测试依赖统一后再补 pytest。
5. 不建议每个 Agent 自己加 API。先完成 Agent 和 Service，API/前端由项目负责人统一接入，避免接口风格分裂。
6. `TutorAgent` 已经是模板，参考目录是 `backend/app/agents/tutor/`。后续 Agent 目录结构、`AgentConfig`、`AgentResult` 都按它来。

## 当前核心约定

每个 Agent 必须继承 `BaseAgent`：

```python
class MyAgent(BaseAgent):
    config = AgentConfig(
        id="my_agent",
        input_keys=[...],
        output_keys=[...],
        required_services=[...],
        allowed_tools=[...],
    )

    async def process(self, inputs: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        ...
```

统一返回：

```python
AgentResult(
    state_update={...},
    messages=[...],
    artifacts=[...],
    suggestions=[...],
)
```

Agent 之间只通过 `state_update` 传递必要字段，不要把所有中间产物都塞进下游。大文件和复杂产物放到 `Artifact` 或服务层存储，状态里只放 ID、摘要和必要元数据。

## 推荐状态字段

这些字段是 A/B 两位同学需要对齐的接口：

| 字段                  | 类型           | 生产方                                | 消费方                               | 说明              |
| ------------------- | ------------ | ---------------------------------- | --------------------------------- | --------------- |
| `document_id`       | `str`        | FileParserAgent                    | MindmapAgent, QuizAgent, PPTAgent | 文档唯一 ID         |
| `knowledge_base_id` | `str`        | FileParserAgent / KnowledgeService | TutorAgent, QuizAgent, PPTAgent   | RAG 检索范围        |
| `document_summary`  | `str`        | FileParserAgent / MindmapAgent     | TutorAgent, PPTAgent              | 文档摘要            |
| `document_metadata` | `dict`       | FileParserAgent                    | 其他 Agent                          | 文件名、页数、chunk 数等 |
| `knowledge_context` | `str`        | KnowledgeService / Retriever       | TutorAgent                        | 答疑时注入的检索上下文     |
| `mindmap`           | `dict`       | MindmapAgent                       | 前端                                | 思维导图结构          |
| `key_points`        | `list[dict]` | MindmapAgent                       | QuizAgent, PPTAgent               | 核心知识点           |
| `questions`         | `list[dict]` | QuizAgent                          | 前端/答题流程                           | 题目列表            |
| `quiz_session_id`   | `str`        | QuizAgent                          | 答题评估流程                            | 答题会话 ID         |
| `quiz_evaluation`   | `dict`       | QuizAgent 或 EvaluationAgent        | TutorAgent/PPTAgent               | 学习效果评估          |
| `ppt_artifact_id`   | `str`        | PPTAgent                           | 前端                                | PPT 产物 ID 或下载标识 |
| `ppt_outline`       | `list[dict]` | PPTAgent                           | 前端/Artifact                       | PPT 大纲          |

## 同学 A：知识库读取、文档摘要、思维导图

### A 的交付模块

建议按这个顺序开发：

1. `backend/app/services/knowledge.py`
2. `backend/app/agents/file_parser/`
3. `backend/app/agents/mindmap/`

### 1. KnowledgeService

这是 B 的前置依赖，优先级最高。第一版不用做复杂向量库也可以，但接口必须稳定。

建议接口：

```python
class KnowledgeService:
    async def add_document(
        self,
        *,
        file_name: str,
        text: str,
        chunks: list[dict],
        metadata: dict,
    ) -> dict:
        ...

    async def search(
        self,
        *,
        knowledge_base_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        ...

    async def get_document(self, document_id: str) -> dict:
        ...
```

第一版可接受实现：

- 文本抽取后按 chunk 存储到本地内存或本地文件。
- `search()` 可以先做关键词匹配，后续再替换成 Chroma/Faiss/其他向量库。
- 返回结构先稳定，底层检索算法可以后续升级。

`search()` 返回建议：

```python
[
    {
        "chunk_id": "chunk_xxx",
        "document_id": "doc_xxx",
        "text": "...",
        "score": 0.82,
        "metadata": {"page": 3}
    }
]
```

### 2. FileParserAgent

目录：

```text
backend/app/agents/file_parser/
├── __init__.py
├── agent.py
├── models.py
├── pdf_processor.py
└── prompts.py
```

`AgentConfig` 建议：

```python
config = AgentConfig(
    id="file_parser",
    name="File Parser Agent",
    role="document_ingestor",
    input_keys=["file_content", "file_name", "user_profile"],
    output_keys=[
        "document_id",
        "knowledge_base_id",
        "document_metadata",
        "document_summary",
    ],
    required_services=["llm", "knowledge"],
    priority=10,
    enabled=True,
    strict_inputs=True,
)
```

处理流程：

1. 校验文件类型，只接受 PDF。
2. 解析 PDF 文本和页码信息。
3. 清洗文本，去除空页、页眉页脚噪声。
4. 切分 chunk，每个 chunk 保留页码和来源。
5. 调用 `KnowledgeService.add_document(...)`。
6. 调用 LLM 生成 `document_summary`。
7. 返回 `AgentResult`，同时生成 `Artifact(type="document")`。

最小输出：

```python
AgentResult(
    state_update={
        "document_id": document_id,
        "knowledge_base_id": knowledge_base_id,
        "document_metadata": metadata,
        "document_summary": summary,
    },
    artifacts=[
        Artifact(
            type="document",
            name=file_name,
            content={
                "document_id": document_id,
                "summary": summary,
                "metadata": metadata,
            },
            format="json",
        )
    ],
)
```

### 3. MindmapAgent

目录：

```text
backend/app/agents/mindmap/
├── __init__.py
├── agent.py
├── models.py
├── prompts.py
└── builder.py
```

`AgentConfig` 建议：

```python
config = AgentConfig(
    id="mindmap",
    name="Mindmap Agent",
    role="knowledge_structurer",
    input_keys=[
        "document_id",
        "knowledge_base_id",
        "document_summary",
        "user_profile",
    ],
    output_keys=["mindmap", "key_points", "document_summary"],
    required_services=["llm", "knowledge"],
    priority=20,
    enabled=True,
    strict_inputs=False,
)
```

思维导图输出建议固定为树结构：

```python
{
    "title": "文档主题",
    "nodes": [
        {
            "id": "node_1",
            "title": "核心概念",
            "summary": "一句话解释",
            "children": []
        }
    ]
}
```

A 的验收标准：

- 能读取 PDF 并生成非空文本。
- 能建立可被 `search()` 调用的知识库。
- `search()` 能按 topic 返回相关片段。
- 能输出稳定 JSON 思维导图。
- 不直接改 `backend/main.py`，除非负责人要求接 API。

## 同学 B：题库、交互式作答、PPT

### B 的交付模块

建议按这个顺序开发：

1. `backend/app/agents/quiz/`
2. `backend/app/agents/ppt/`
3. 可选：`backend/app/services/quiz_session.py`

B 的开发依赖 A 的 `KnowledgeService.search()`。在 A 完成前，可以先写一个 FakeKnowledgeService 本地验证。

### 1. QuizAgent

目录：

```text
backend/app/agents/quiz/
├── __init__.py
├── agent.py
├── models.py
├── prompts.py
└── evaluator.py
```

`AgentConfig` 建议：

```python
config = AgentConfig(
    id="quiz",
    name="Quiz Agent",
    role="quiz_generator",
    input_keys=[
        "knowledge_base_id",
        "topic",
        "question_count",
        "question_types",
        "difficulty",
        "user_profile",
    ],
    output_keys=["questions", "quiz_session_id", "quiz_metadata"],
    required_services=["llm", "knowledge"],
    priority=30,
    enabled=True,
    strict_inputs=False,
)
```

题目结构建议：

```python
{
    "id": "q_1",
    "type": "single_choice",
    "stem": "题干",
    "options": [
        {"id": "A", "text": "..."},
        {"id": "B", "text": "..."}
    ],
    "answer": "A",
    "explanation": "解析",
    "knowledge_point": "知识点",
    "difficulty": 2,
    "source": {
        "document_id": "doc_xxx",
        "chunk_id": "chunk_xxx"
    }
}
```

必须支持的题型：

- `single_choice`
- `multiple_choice`
- `fill_blank`
- `true_false`

交互式作答建议不要全放在 QuizAgent 里。第一版可以：

- QuizAgent 只负责生成题目和答案解析。
- 前端或后续 AnswerEvaluatorAgent 负责逐题作答。
- 如果必须由 B 做评估，新增 `evaluator.py`，输入 `questions + user_answers`，输出 `quiz_evaluation`。

评估输出建议：

```python
{
    "score": 80,
    "correct_count": 4,
    "total_count": 5,
    "weak_points": ["概念 A", "概念 B"],
    "suggestions": ["复习第 2 节", "重新练习判断题"]
}
```

### 2. PPTAgent

目录：

```text
backend/app/agents/ppt/
├── __init__.py
├── agent.py
├── models.py
├── prompts.py
└── builder.py
```

`AgentConfig` 建议：

```python
config = AgentConfig(
    id="ppt",
    name="PPT Agent",
    role="review_material_builder",
    input_keys=[
        "knowledge_base_id",
        "topic",
        "slide_count",
        "user_profile",
        "key_points",
        "quiz_evaluation",
    ],
    output_keys=["ppt_artifact_id", "ppt_file_path", "ppt_outline"],
    required_services=["llm", "knowledge"],
    priority=40,
    enabled=True,
    strict_inputs=False,
)
```

处理流程：

1. 用 `knowledge_base_id + topic` 检索 RAG 内容。
2. 结合 `key_points` 和可选 `quiz_evaluation` 生成复习大纲。
3. 生成 PPT outline。
4. 用 `python-pptx` 或先输出 JSON outline。
5. 返回 `Artifact(type="ppt", format="file")` 或 `Artifact(type="ppt_outline", format="json")`。

第一版如果 PPT 文件生成不稳定，可以先交付 `ppt_outline`，再补真实 `.pptx` 文件导出。

PPT 大纲建议：

```python
[
    {
        "title": "标题",
        "bullets": ["要点 1", "要点 2"],
        "speaker_notes": "讲稿或复习提示",
        "source_chunks": ["chunk_1", "chunk_2"]
    }
]
```

B 的验收标准：

- 能从 `KnowledgeService.search()` 获取上下文。
- 能生成结构稳定的题目 JSON。
- 题目必须带答案、解析、知识点、来源。
- 能根据用户答题结果输出薄弱点和建议。
- PPT 至少能输出结构化大纲；文件生成可以作为第二阶段。

## A/B 对接顺序

第一阶段建议这样排：

1. A 先完成 `KnowledgeService` 的最小实现和接口文档。
2. B 用 FakeKnowledgeService 并行开发 `QuizAgent` 和 `PPTAgent` 的 prompt、模型、输出结构。
3. A 完成 `FileParserAgent`，打通 PDF 到知识库。
4. A 完成 `MindmapAgent`。
5. B 替换 FakeKnowledgeService，接真实 `KnowledgeService.search()`。
6. 负责人统一接入 API 和前端，不建议 A/B 分别改 `main.py`。

## 不要做的事情

- 不要在 Agent 里直接实例化 OpenAI、Chroma、PPT、数据库等重对象。
- 不要在各 Agent 里自行定义不兼容的 `document_id`、`knowledge_base_id`。
- 不要直接把整篇 PDF 文本传给下游 Agent。
- 不要把 API 路由散落到每个 Agent 文件里。
- 不要提交 `__pycache__`、`.env`、临时 PDF、生成的 PPT 文件。
- 不要修改 `TutorAgent` 的输入输出字段，除非先和负责人确认。

## 开发自检清单

提交 PR 前至少确认：

- `AgentConfig.input_keys` 和 `output_keys` 与实际 `state_update` 一致。
- `required_services` 中声明的服务确实存在。
- 大文件内容不直接进入 pipeline state。
- `AgentResult.artifacts` 能表达生成物。
- 异常场景返回 `AgentError` 或让 `BaseAgent.run()` 正确包装。
- 能用一个本地脚本跑通 Agent 的 `process()`。
- 如果支持流式，事件使用 `StreamEvent(event="token" | "completed", data={...})`。

## 推荐本地验证方式

可以参考这个模式写本地验证脚本：

```python
from app.core.runtime import AgentRuntime, ServiceRegistry
from app.core.fakes import EchoLLMClient

services = ServiceRegistry()
services.register("llm", EchoLLMClient())
# services.register("knowledge", FakeKnowledgeService())

runtime = AgentRuntime(services=services)
result = await agent.run(inputs, runtime)
assert result.error is None
```

真正接入主流程前，先把 Agent 自己跑通，再由负责人统一编排。
