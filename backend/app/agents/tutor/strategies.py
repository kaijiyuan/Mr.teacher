from __future__ import annotations
from typing import Any, Protocol

from app.agents.tutor.models import GuidanceMode
from app.agents.tutor.prompts import build_guidance_prompt


class GuidanceStrategy(Protocol):
    def generate_prompt(
        self,
        *,
        user_message: str,
        user_profile: dict[str, Any],
        knowledge_context: str,
        conversation_history: list[dict[str, Any]] | None,
    ) -> str:
        ...


class SocraticStrategy:
    def generate_prompt(
        self,
        *,
        user_message: str,
        user_profile: dict[str, Any],
        knowledge_context: str,
        conversation_history: list[dict[str, Any]] | None,
    ) -> str:
        return build_guidance_prompt(
            teaching_style="苏格拉底式引导",
            instruction=(
                "优先通过问题引导用户自己推理。"
                "每次最多提出 1 到 2 个关键问题，"
                "只在必要时补充简短提示。"
            ),
            user_message=user_message,
            user_profile=user_profile,
            knowledge_context=knowledge_context,
            conversation_history=conversation_history,
        )


class HeuristicStrategy:
    def generate_prompt(
        self,
        *,
        user_message: str,
        user_profile: dict[str, Any],
        knowledge_context: str,
        conversation_history: list[dict[str, Any]] | None,
    ) -> str:
        return build_guidance_prompt(
            teaching_style="启发式引导",
            instruction=(
                "先给出简洁解释，再用例子或类比帮助理解，"
                "最后给出一个可执行的小练习。"
            ),
            user_message=user_message,
            user_profile=user_profile,
            knowledge_context=knowledge_context,
            conversation_history=conversation_history,
        )


class DirectStrategy:
    def generate_prompt(
        self,
        *,
        user_message: str,
        user_profile: dict[str, Any],
        knowledge_context: str,
        conversation_history: list[dict[str, Any]] | None,
    ) -> str:
        return build_guidance_prompt(
            teaching_style="直接讲解式引导",
            instruction=(
                "用清晰步骤直接解释概念，"
                "从最基础的定义开始，"
                "避免假设用户已有背景知识。"
            ),
            user_message=user_message,
            user_profile=user_profile,
            knowledge_context=knowledge_context,
            conversation_history=conversation_history,
        )


class StrategyFactory:
    _strategies: dict[GuidanceMode, GuidanceStrategy] = {
        GuidanceMode.SOCRATIC: SocraticStrategy(),
        GuidanceMode.HEURISTIC: HeuristicStrategy(),
        GuidanceMode.DIRECT: DirectStrategy(),
    }

    @classmethod
    def get_strategy(cls, mode: GuidanceMode) -> GuidanceStrategy:
        return cls._strategies.get(mode, cls._strategies[GuidanceMode.HEURISTIC])

    @classmethod
    def select_mode(cls, user_profile: dict[str, Any], user_message: str) -> GuidanceMode:
        level = str(user_profile.get("knowledge_level", ""))
        style = str(user_profile.get("learning_style", ""))
        message = user_message or ""

        direct_signals = [
            "完全不了解",
            "零基础",
            "初学",
            "入门",
            "直接讲",
            "看不懂",
        ]
        socratic_signals = [
            "比较熟悉",
            "高级",
            "挑战",
            "自己推理",
            "提问引导",
        ]

        if any(signal in level or signal in style or signal in message for signal in direct_signals):
            return GuidanceMode.DIRECT
        if any(signal in level or signal in style for signal in socratic_signals):
            return GuidanceMode.SOCRATIC
        return GuidanceMode.HEURISTIC
