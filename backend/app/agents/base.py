from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from app.agents.config import AgentConfig
from app.core.result import AgentError, AgentResult
from app.core.runtime import AgentRuntime


class BaseAgent(ABC):
    """Base class for all workflow agents.

    Subclasses implement process(). The base class owns input projection,
    dependency validation, tracing, exception wrapping, and output validation.
    """

    config: AgentConfig

    async def run(self, state: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        if not self.config.enabled:
            return AgentResult(
                error=AgentError(
                    code="agent.disabled",
                    message=f"Agent is disabled: {self.config.id}",
                )
            )

        await self.emit_trace(runtime, "agent.started", {"agent_id": self.config.id})

        try:
            inputs = self.project_inputs(state)
            self.validate_runtime(runtime)
            result = await self.process(inputs, runtime)
            self.validate_result(result)
            await self.emit_trace(
                runtime,
                "agent.completed",
                {
                    "agent_id": self.config.id,
                    "outputs": list(result.state_update.keys()),
                    "artifacts": [artifact.type for artifact in result.artifacts],
                },
            )
            return result
        except AgentError as exc:
            await self.emit_trace(
                runtime,
                "agent.failed",
                {"agent_id": self.config.id, "code": exc.code, "message": exc.message},
                level="error",
            )
            return AgentResult(error=exc)
        except Exception as exc:
            error = AgentError(
                code="agent.unhandled_error",
                message=str(exc),
                details={"agent_id": self.config.id},
            )
            await self.emit_trace(
                runtime,
                "agent.failed",
                {"agent_id": self.config.id, "code": error.code, "message": error.message},
                level="error",
            )
            return AgentResult(error=error)

    @abstractmethod
    async def process(self, inputs: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        """Run business logic with projected inputs."""

    def project_inputs(self, state: dict[str, Any]) -> dict[str, Any]:
        missing = [key for key in self.config.input_keys if key not in state]
        if missing and self.config.strict_inputs:
            raise AgentError(
                code="agent.missing_inputs",
                message=f"Missing inputs for {self.config.id}: {', '.join(missing)}",
                details={"missing": missing},
            )
        return {key: state.get(key) for key in self.config.input_keys}

    def validate_runtime(self, runtime: AgentRuntime) -> None:
        missing_services = [
            name for name in self.config.required_services if not runtime.services.has(name)
        ]
        missing_tools = [name for name in self.config.required_tools if not runtime.tools.has(name)]
        if missing_services or missing_tools:
            raise AgentError(
                code="agent.missing_dependencies",
                message=f"Missing dependencies for {self.config.id}",
                details={
                    "services": missing_services,
                    "tools": missing_tools,
                },
            )

    def validate_result(self, result: AgentResult) -> None:
        if result.error is not None:
            return
        if not self.config.output_keys:
            return
        unexpected = [
            key for key in result.state_update.keys() if key not in self.config.output_keys
        ]
        if unexpected:
            raise AgentError(
                code="agent.unexpected_outputs",
                message=f"Unexpected outputs for {self.config.id}: {', '.join(unexpected)}",
                details={"unexpected": unexpected},
            )

    async def call_llm(self, runtime: AgentRuntime, prompt: Any) -> Any:
        llm = runtime.get_service("llm")
        return await llm.ainvoke(
            prompt,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    async def stream_llm(self, runtime: AgentRuntime, prompt: Any) -> AsyncIterator[Any]:
        llm = runtime.get_service("llm")
        async for chunk in llm.astream(
            prompt,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ):
            yield chunk

    async def use_tool(self, runtime: AgentRuntime, name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in self.config.allowed_tools:
            raise AgentError(
                code="agent.tool_not_allowed",
                message=f"Tool is not allowed for {self.config.id}: {name}",
                details={"tool": name},
            )
        return await runtime.tools.call(name, *args, **kwargs)

    async def emit_trace(
        self,
        runtime: AgentRuntime,
        event: str,
        data: dict[str, Any] | None = None,
        level: str = "info",
    ) -> None:
        payload = {"agent_id": self.config.id, **(data or {})}
        await runtime.emit(event, payload, level=level)
