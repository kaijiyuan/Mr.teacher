from __future__ import annotations
from collections.abc import AsyncIterator
from typing import Any

from app.agents.base import BaseAgent
from app.agents.config import AgentConfig
from app.agents.tutor.models import GuidanceMode, UnderstandingLevel
from app.agents.tutor.strategies import StrategyFactory
from app.core.result import AgentResult, StreamEvent
from app.core.runtime import AgentRuntime


class TutorAgent(BaseAgent):
    """Guided Q&A agent used as the reference implementation for learning agents."""

    config = AgentConfig(
        id="tutor",
        name="Tutor Agent",
        role="tutor",
        persona="A patient Chinese learning tutor who adapts guidance to the learner profile.",
        description="引导式答疑 Agent，根据用户画像、对话历史和资料上下文提供个性化学习引导。",
        input_keys=[
            "user_message",
            "user_profile",
            "conversation_history",
            "knowledge_context",
        ],
        output_keys=[
            "response",
            "understanding_level",
            "guidance_mode",
            "conversation_history",
            "learning_suggestions",
        ],
        model="deepseek-chat",
        temperature=0.7,
        required_services=["llm"],
        allowed_tools=["knowledge_retriever"],
        priority=20,
        enabled=True,
        supports_streaming=True,
        strict_inputs=False,
    )

    async def process(self, inputs: dict[str, Any], runtime: AgentRuntime) -> AgentResult:
        turn = self._prepare_turn(inputs)
        raw_response = await self.call_llm(runtime, turn["prompt"])
        response = self._coerce_text(raw_response)

        return self._build_result(
            response=response,
            user_message=turn["user_message"],
            user_profile=turn["user_profile"],
            conversation_history=turn["conversation_history"],
            guidance_mode=turn["guidance_mode"],
        )

    async def stream_process(
        self,
        inputs: dict[str, Any],
        runtime: AgentRuntime,
    ) -> AsyncIterator[StreamEvent]:
        turn = self._prepare_turn(inputs)
        response_parts: list[str] = []

        async for chunk in self.stream_llm(runtime, turn["prompt"]):
            content = self._coerce_text(chunk)
            if not content:
                continue
            response_parts.append(content)
            yield StreamEvent(
                event="token",
                data={
                    "agent_id": self.config.id,
                    "content": content,
                },
            )

        response = "".join(response_parts)
        result = self._build_result(
            response=response,
            user_message=turn["user_message"],
            user_profile=turn["user_profile"],
            conversation_history=turn["conversation_history"],
            guidance_mode=turn["guidance_mode"],
        )
        yield StreamEvent(
            event="completed",
            data={
                "agent_id": self.config.id,
                "state_update": result.state_update,
                "messages": result.messages,
                "suggestions": result.suggestions,
            },
        )

    def _prepare_turn(self, inputs: dict[str, Any]) -> dict[str, Any]:
        user_message = str(inputs.get("user_message") or "").strip()
        user_profile = self._ensure_dict(inputs.get("user_profile"))
        conversation_history = self._ensure_history(inputs.get("conversation_history"))
        knowledge_context = str(inputs.get("knowledge_context") or "").strip()

        guidance_mode = StrategyFactory.select_mode(user_profile, user_message)
        strategy = StrategyFactory.get_strategy(guidance_mode)
        prompt = strategy.generate_prompt(
            user_message=user_message,
            user_profile=user_profile,
            knowledge_context=knowledge_context,
            conversation_history=conversation_history,
        )

        return {
            "user_message": user_message,
            "user_profile": user_profile,
            "conversation_history": conversation_history,
            "knowledge_context": knowledge_context,
            "guidance_mode": guidance_mode,
            "prompt": prompt,
        }

    def _build_result(
        self,
        *,
        response: str,
        user_message: str,
        user_profile: dict[str, Any],
        conversation_history: list[dict[str, Any]],
        guidance_mode: GuidanceMode,
    ) -> AgentResult:
        understanding = self._assess_understanding(user_message=user_message)
        suggestions = self._generate_suggestions(
            understanding=understanding,
            guidance_mode=guidance_mode,
            user_profile=user_profile,
        )
        updated_history = [
            *conversation_history,
            {"role": "user", "content": user_message},
            {
                "role": "assistant",
                "content": response,
                "guidance_mode": guidance_mode.value,
                "understanding": understanding.value,
            },
        ]

        return AgentResult(
            state_update={
                "response": response,
                "understanding_level": understanding.value,
                "guidance_mode": guidance_mode.value,
                "conversation_history": updated_history,
                "learning_suggestions": suggestions,
            },
            messages=[{"role": "assistant", "content": response}],
            suggestions=suggestions,
        )

    def _assess_understanding(self, *, user_message: str) -> UnderstandingLevel:
        confused_signals = [
            "完全不了解",
            "不懂",
            "不明白",
            "看不懂",
            "为什么",
            "什么意思",
            "怎么理解",
        ]
        good_signals = [
            "明白了",
            "懂了",
            "理解了",
            "原来如此",
            "会了",
        ]
        excellent_signals = [
            "我能总结",
            "我来解释",
            "我可以举例",
            "我掌握了",
        ]

        if any(signal in user_message for signal in excellent_signals):
            return UnderstandingLevel.EXCELLENT
        if any(signal in user_message for signal in good_signals):
            return UnderstandingLevel.GOOD
        if any(signal in user_message for signal in confused_signals):
            return UnderstandingLevel.CONFUSED
        return UnderstandingLevel.PARTIAL

    def _generate_suggestions(
        self,
        *,
        understanding: UnderstandingLevel,
        guidance_mode: GuidanceMode,
        user_profile: dict[str, Any],
    ) -> list[str]:
        topic = user_profile.get("topic") or "当前主题"

        if understanding == UnderstandingLevel.CONFUSED:
            return [
                f"先回到{topic}的基础概念。",
                "让用户用自己的话复述一个关键点。",
            ]
        if understanding == UnderstandingLevel.GOOD:
            return [
                f"围绕{topic}安排一道小练习。",
                "准备进入更具体的应用场景。",
            ]
        if understanding == UnderstandingLevel.EXCELLENT:
            return [
                f"总结{topic}的知识结构。",
                "可以切换到题库 Agent 检查掌握程度。",
            ]
        if guidance_mode == GuidanceMode.SOCRATIC:
            return [
                "继续用追问验证用户的推理链。",
                "必要时补充一个反例。",
            ]
        return [
            "补充一个更贴近用户场景的例子。",
            "下一轮可以生成一个简单练习。",
        ]

    def _coerce_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        content = getattr(value, "content", None)
        if content is not None:
            return str(content)
        choices = getattr(value, "choices", None)
        if choices:
            first_choice = choices[0]
            delta = getattr(first_choice, "delta", None)
            delta_content = getattr(delta, "content", None)
            if delta_content is not None:
                return str(delta_content)
            message = getattr(first_choice, "message", None)
            message_content = getattr(message, "content", None)
            if message_content is not None:
                return str(message_content)
        if isinstance(value, dict):
            if "content" in value:
                return str(value["content"])
            if "text" in value:
                return str(value["text"])
        return str(value)

    def _ensure_dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _ensure_history(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [turn for turn in value if isinstance(turn, dict)]
