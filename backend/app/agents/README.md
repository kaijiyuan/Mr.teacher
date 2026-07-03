# Agent Development Contract

Each agent should inherit from `BaseAgent`, declare a static `AgentConfig`, and
implement `process(inputs, runtime)`.

Rules:

- Do not create heavy services in `__init__`.
- Do not store request-specific data on `self`.
- Use `input_keys` to declare required inputs from pipeline state.
- Use `output_keys` to declare allowed `state_update` fields.
- Use `call_llm`, `stream_llm`, and `use_tool` instead of importing clients directly.
- Return `AgentResult`; raise `AgentError` for expected failures.

Minimal template:

```python
from typing import Any

from app.agents.base import BaseAgent
from app.agents.config import AgentConfig
from app.core.result import AgentResult
from app.core.runtime import AgentRuntime


class MyAgent(BaseAgent):
    config = AgentConfig(
        id="my_agent",
        name="My Agent",
        role="tutor",
        persona="A clear and patient learning assistant.",
        input_keys=["user_message", "user_profile"],
        output_keys=["answer", "learning_summary"],
        required_services=["llm"],
        allowed_tools=["knowledge_retriever"],
    )

    async def process(self, inputs: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        prompt = f"Question: {inputs['user_message']}"
        answer = await self.call_llm(runtime, prompt)
        return AgentResult(
            state_update={
                "answer": answer,
                "learning_summary": {"status": "completed"},
            }
        )
```
