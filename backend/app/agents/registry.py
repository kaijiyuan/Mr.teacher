from __future__ import annotations
from app.agents.base import BaseAgent


class AgentRegistry:
    """Registry for agent classes.

    Agents should be lightweight. The registry stores classes and creates a new
    instance for each pipeline construction or run.
    """

    def __init__(self) -> None:
        self._agents: dict[str, type[BaseAgent]] = {}

    def register(self, agent_cls: type[BaseAgent]) -> None:
        agent_id = agent_cls.config.id
        if agent_id in self._agents:
            raise ValueError(f"Agent is already registered: {agent_id}")
        self._agents[agent_id] = agent_cls

    def create(self, agent_id: str) -> BaseAgent:
        if agent_id not in self._agents:
            raise KeyError(f"Agent is not registered: {agent_id}")
        return self._agents[agent_id]()

    def create_many(self, agent_ids: list[str]) -> list[BaseAgent]:
        return [self.create(agent_id) for agent_id in agent_ids]

    def list_ids(self) -> list[str]:
        return sorted(self._agents.keys())
