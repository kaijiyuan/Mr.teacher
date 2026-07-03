from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentConfig:
    """Static contract for an agent.

    Runtime user data must not be stored here. Use pipeline state and runtime
    services for request-specific values.
    """

    id: str
    name: str
    role: str
    persona: str = ""
    version: str = "0.1.0"
    description: str = ""

    input_keys: list[str] = field(default_factory=list)
    output_keys: list[str] = field(default_factory=list)

    model: str = "default"
    temperature: float = 0.7
    max_tokens: int | None = None

    allowed_tools: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    required_services: list[str] = field(default_factory=list)

    priority: int = 100
    enabled: bool = True
    supports_streaming: bool = False
    strict_inputs: bool = True
