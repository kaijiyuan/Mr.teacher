from __future__ import annotations
from typing import Any

from app.agents.base import BaseAgent
from app.agents.config import AgentConfig
from app.core.result import AgentResult
from app.core.runtime import AgentRuntime


class FakeProfileAgent(BaseAgent):
    config = AgentConfig(
        id="fake_profile",
        name="Fake Profile Agent",
        role="profile",
        description="Creates a minimal user profile for framework validation.",
        input_keys=["user_message"],
        output_keys=["user_profile"],
    )

    async def process(self, inputs: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        return AgentResult(
            state_update={
                "user_profile": {
                    "goal": "learn effectively",
                    "source": inputs["user_message"],
                }
            }
        )


class FakeTutorAgent(BaseAgent):
    config = AgentConfig(
        id="fake_tutor",
        name="Fake Tutor Agent",
        role="tutor",
        description="Produces a minimal tutor reply for framework validation.",
        input_keys=["user_message", "user_profile"],
        output_keys=["answer", "learning_summary"],
    )

    async def process(self, inputs: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        return AgentResult(
            state_update={
                "answer": f"Received: {inputs['user_message']}",
                "learning_summary": {
                    "profile_goal": inputs["user_profile"].get("goal"),
                    "status": "fake_completed",
                },
            },
            suggestions=["Replace fake agents with concrete implementations."],
        )
